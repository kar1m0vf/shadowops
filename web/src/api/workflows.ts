import { z } from "zod";
import { ApiError, requestJson, validateSessionId } from "./client";
import {
  draftSchema,
  savedSkillSchema,
  skillSchema,
  replayInputSchema,
  startSchema,
  resumeSchema,
  replaySchema,
  preflightSchema,
  stepResultSchema,
  type Skill,
  type ReplayInput,
  type StartRequest,
  type ResumeRequest,
} from "./contracts";

export function parseContract<T>(schema: z.ZodType<T>, value: unknown): T {
  const parsed = schema.safeParse(value);
  if (!parsed.success)
    throw new ApiError(
      `API contract validation failed: ${parsed.error.issues
        .slice(0, 5)
        .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
        .join("; ")}`,
    );
  return parsed.data;
}
function pathId(id: string) {
  return encodeURIComponent(validateSessionId(id));
}
function post(path: string, body: unknown) {
  return requestJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
export async function retrieveDraft(id: string) {
  const draft = parseContract(
    draftSchema,
    await requestJson(`/api/skill-drafts/${pathId(id)}`),
  );
  if (draft.id !== id.trim())
    throw new ApiError(
      "The returned draft ID does not match the requested draft.",
    );
  return draft;
}
export async function retrieveSkill(id: string) {
  const skill = parseContract(
    savedSkillSchema,
    await requestJson(`/api/skills/${pathId(id)}`),
  );
  if (skill.id !== id.trim())
    throw new ApiError(
      "The returned skill ID does not match the requested skill.",
    );
  return skill;
}
export async function confirmDraft(
  id: string,
  skill: Skill,
  confirmed: boolean,
) {
  if (!confirmed)
    throw new ApiError(
      "Review the complete skill and explicitly approve confirmation first.",
    );
  const saved = parseContract(
    savedSkillSchema,
    await post(`/api/skill-drafts/${pathId(id)}/confirm`, {
      confirmed: true,
      skill: parseContract(skillSchema, skill),
    }),
  );
  if (saved.draft_id !== id.trim())
    throw new ApiError(
      "The confirmed skill belongs to a different draft. Inspect the backend before retrying.",
    );
  return saved;
}
export async function preflightReplay(input: ReplayInput) {
  const report = parseContract(
    preflightSchema,
    await post(
      "/api/replays/preflight",
      parseContract(replayInputSchema, input),
    ),
  );
  if (report.skill_id !== input.skill_id)
    throw new ApiError("Preflight returned a different skill ID.");
  return report;
}
export async function startReplay(input: StartRequest) {
  const record = parseContract(
    replaySchema,
    await post("/api/replays", parseContract(startSchema, input)),
  );
  if (record.skill_id !== input.skill_id)
    throw new ApiError(
      "Replay returned a different skill ID. Inspect the backend before retrying.",
    );
  return record;
}
export async function retrieveReplay(id: string, signal?: AbortSignal) {
  const record = parseContract(
    replaySchema,
    await requestJson(`/api/replays/${pathId(id)}`, { signal }),
  );
  if (record.id !== id.trim())
    throw new ApiError(
      "The returned replay ID does not match the requested replay.",
    );
  return record;
}
export async function retrieveReplaySteps(id: string, signal?: AbortSignal) {
  return parseContract(
    z.array(stepResultSchema),
    await requestJson(`/api/replays/${pathId(id)}/steps`, { signal }),
  );
}
export async function resumeReplay(id: string, input: ResumeRequest) {
  const record = parseContract(
    replaySchema,
    await post(
      `/api/replays/${pathId(id)}/resume`,
      parseContract(resumeSchema, input),
    ),
  );
  if (record.id !== id.trim())
    throw new ApiError(
      "Resume returned a different replay. Inspect the backend before retrying.",
    );
  return record;
}
export async function stopReplay(id: string) {
  const result = parseContract(
    z.object({ id: z.string(), stop_requested: z.literal(true) }),
    await requestJson(`/api/replays/${pathId(id)}/stop`, { method: "POST" }),
  );
  if (result.id !== id.trim())
    throw new ApiError("Stop response returned a different replay ID.");
  return result;
}
