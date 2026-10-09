export class ApiError extends Error {
  constructor(
    message: string,
    public status: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export type JsonObject = Record<string, unknown>;
export type Health = { status: string; service: string };
export type RecordedEvent = {
  id: number;
  session_id: string;
  timestamp: string;
  url: string;
  action: string;
  target: JsonObject & {
    tag?: string | null;
    role?: string | null;
    label?: string | null;
    selector?: string | null;
  };
  [key: string]: unknown;
};
export type LoadedRecording = {
  sessionId: string;
  events: RecordedEvent[];
  loadedAt: string;
};
export type CompileRequest = { session_id: string; task_description: string };
export type CompileResult = {
  sessionId: string;
  taskDescription: string;
  payload: unknown;
};
export function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
export function validateSessionId(value: string): string {
  const id = value.trim();
  if (
    !id ||
    id.length > 128 ||
    /[\u0000-\u001f\u007f/\\?#]/.test(id) ||
    id === "." ||
    id === ".."
  ) {
    throw new ApiError(
      "Enter a session ID of 1–128 characters, without slashes, URL delimiters or control characters.",
    );
  }
  return id;
}
function errorDetail(payload: unknown): string | null {
  if (!isObject(payload)) return null;
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return (
      payload.detail
        .map((item) =>
          typeof item === "string"
            ? item
            : isObject(item) && typeof item.msg === "string"
              ? `${Array.isArray(item.loc) ? item.loc.join(".") + ": " : ""}${item.msg}`
              : "",
        )
        .filter(Boolean)
        .join("; ") || null
    );
  }
  return typeof payload.message === "string" ? payload.message : null;
}
export async function requestJson(
  path: string,
  init: RequestInit = {},
  timeoutMs = 15000,
): Promise<unknown> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  let externallyAborted = false;
  const abort = () => {
    externallyAborted = true;
    controller.abort();
  };
  if (init.signal?.aborted) abort();
  init.signal?.addEventListener("abort", abort, { once: true });
  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: { Accept: "application/json", ...init.headers },
    });
    const body = await response.text();
    let payload: unknown;
    try {
      payload = JSON.parse(body);
    } catch {
      payload = undefined;
    }
    if (!response.ok) {
      const fallback =
        response.status >= 500
          ? "Backend unavailable or server error. Check FastAPI on port 8000 and try again."
          : `Request failed (HTTP ${response.status}).`;
      throw new ApiError(
        `${errorDetail(payload) || fallback} (HTTP ${response.status})`,
        response.status,
      );
    }
    if (payload === undefined)
      throw new ApiError(
        "The backend returned an unexpected non-JSON response.",
        response.status,
      );
    return payload;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (externallyAborted)
      throw new DOMException("Request cancelled", "AbortError");
    throw new ApiError(
      controller.signal.aborted
        ? "Request timed out. Check FastAPI on port 8000 and try again."
        : "Unable to reach the backend. Check FastAPI on port 8000 and try again.",
    );
  } finally {
    clearTimeout(timeout);
    init.signal?.removeEventListener("abort", abort);
  }
}
export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const data = await requestJson("/health", { signal });
  if (
    !isObject(data) ||
    typeof data.status !== "string" ||
    typeof data.service !== "string"
  )
    throw new ApiError(
      "Unexpected health response: expected status and service.",
    );
  if (data.status !== "ok" || data.service !== "shadowops-backend")
    throw new ApiError(
      "The backend did not report a healthy ShadowOps service.",
    );
  return { status: data.status, service: data.service };
}
export function parseEvents(data: unknown, sessionId: string): RecordedEvent[] {
  if (!Array.isArray(data))
    throw new ApiError("Unexpected events response: expected an array.");
  const events = data.map((item, index) => {
    if (
      !isObject(item) ||
      typeof item.id !== "number" ||
      !Number.isInteger(item.id) ||
      item.session_id !== sessionId ||
      typeof item.timestamp !== "string" ||
      !Number.isFinite(Date.parse(item.timestamp)) ||
      typeof item.url !== "string" ||
      typeof item.action !== "string" ||
      !isObject(item.target)
    ) {
      throw new ApiError(
        `Unexpected event at position ${index + 1}. The recording contract or session does not match.`,
      );
    }
    for (const field of ["tag", "role", "label", "selector"]) {
      if (
        item.target[field] !== undefined &&
        item.target[field] !== null &&
        typeof item.target[field] !== "string"
      )
        throw new ApiError(`Unexpected target metadata at event ${index + 1}.`);
    }
    return item as RecordedEvent;
  });
  // The API returns insertion order. Present timestamp chronology; ID breaks ties.
  return events.sort(
    (a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp) || a.id - b.id,
  );
}
export async function getEvents(sessionId: string): Promise<LoadedRecording> {
  const id = validateSessionId(sessionId);
  const data = await requestJson(`/api/events/${encodeURIComponent(id)}`);
  return {
    sessionId: id,
    events: parseEvents(data, id),
    loadedAt: new Date().toISOString(),
  };
}
export async function compileSkill(
  input: CompileRequest,
): Promise<CompileResult> {
  const sessionId = validateSessionId(input.session_id);
  const taskDescription = input.task_description.trim();
  if (!taskDescription)
    throw new ApiError("Enter a task description before compiling.");
  const payload = await requestJson(
    "/api/skills/compile",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        task_description: taskDescription,
      }),
    },
    120000,
  );
  return { sessionId, taskDescription, payload };
}
// Typed review and replay operations live in workflows.ts.
