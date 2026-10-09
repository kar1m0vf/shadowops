import { useState } from "react";
import {
  CheckSquare,
  Clapperboard,
  Keyboard,
  MousePointer2,
  Search,
} from "lucide-react";
import {
  getEvents,
  type LoadedRecording,
  type RecordedEvent,
  isObject,
} from "../api/client";
import {
  EmptyState,
  ErrorNotice,
  JsonView,
  Loading,
  Panel,
  timeLabel,
} from "../components/ui";

function suppliedField(event: RecordedEvent, key: string): unknown {
  if (Object.hasOwn(event, key)) return event[key];
  if (Object.hasOwn(event.target, key)) return event.target[key];
  return undefined;
}
function displayValue(value: unknown): string {
  return typeof value === "string"
    ? value === ""
      ? '"" (empty string)'
      : value
    : (JSON.stringify(value) ?? "Not supplied");
}
function EventRow({ event, index }: { event: RecordedEvent; index: number }) {
  const recordedValue = suppliedField(event, "value");
  const value =
    recordedValue !== undefined
      ? recordedValue
      : suppliedField(event, "input_value");
  const checked = suppliedField(event, "checked");
  const semantic = suppliedField(event, "locator_candidates");
  const Icon = /input|type|change/.test(event.action)
    ? Keyboard
    : /check/.test(event.action)
      ? CheckSquare
      : MousePointer2;
  return (
    <li className="event-row">
      <div className="event-rail">
        <span className="event-icon">
          <Icon size={16} />
        </span>
        <span className="rail-line" />
      </div>
      <div className="event-content">
        <div className="event-top">
          <span className="event-index">
            {String(index + 1).padStart(2, "0")}
          </span>
          <span className="badge">{event.action}</span>
          <time dateTime={event.timestamp} title={event.timestamp}>
            {timeLabel(event.timestamp)}
          </time>
        </div>
        <h3>
          {event.target.label ||
            event.target.selector ||
            event.target.tag ||
            "Unlabeled target"}
        </h3>
        <div className="event-meta">
          <span>Event #{event.id}</span>
          <span className="mono">{event.url}</span>
        </div>
        <dl className="event-fields">
          <div>
            <dt>Input value</dt>
            <dd>
              {value !== undefined ? displayValue(value) : "Not supplied"}
            </dd>
          </div>
          <div>
            <dt>Checkbox state</dt>
            <dd>
              {typeof checked === "boolean"
                ? checked
                  ? "Checked"
                  : "Unchecked"
                : "Not supplied"}
            </dd>
          </div>
          <div>
            <dt>Tag</dt>
            <dd>{event.target.tag || "Not supplied"}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{event.target.role || "Not supplied"}</dd>
          </div>
          <div>
            <dt>Label</dt>
            <dd>{event.target.label || "Not supplied"}</dd>
          </div>
          <div>
            <dt>Selector</dt>
            <dd className="mono">{event.target.selector || "Not supplied"}</dd>
          </div>
        </dl>
        {semantic !== undefined && (
          <div className="semantic-block">
            <span className="field-label">
              Recorded locator candidates
            </span>
            {isObject(semantic) || Array.isArray(semantic) ? (
              <JsonView
                value={semantic}
                label={`Locator candidates for event ${event.id}`}
              />
            ) : (
              <p className="mono">{displayValue(semantic)}</p>
            )}
          </div>
        )}
        <details>
          <summary>Raw event · original timestamp and metadata</summary>
          <JsonView value={event} label={`Raw event ${event.id}`} />
        </details>
      </div>
    </li>
  );
}
export function Recordings({
  recording,
  setRecording,
}: {
  recording: LoadedRecording | null;
  setRecording: (recording: LoadedRecording) => void;
}) {
  const [sessionId, setSessionId] = useState(recording?.sessionId || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<LoadedRecording | null>(recording);
  async function load() {
    if (loading) return;
    setLoading(true);
    setError(null);
    setView(null);
    try {
      const data = await getEvents(sessionId);
      setView(data);
      setRecording(data);
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to load recording.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <>
      <Panel
        title="Load a recording"
        subtitle="Retrieve a session directly from the event API"
      >
        <form
          className="panel-body session-form"
          onSubmit={(event) => {
            event.preventDefault();
            void load();
          }}
        >
          <div>
            <label htmlFor="recording-session">Session ID</label>
            <input
              id="recording-session"
              required
              maxLength={128}
              autoComplete="off"
              spellCheck={false}
              value={sessionId}
              onChange={(event) => setSessionId(event.target.value)}
              placeholder="Enter your recorder session ID"
              aria-describedby="session-help"
            />
          </div>
          <button type="submit" className="button primary" disabled={loading}>
            <Search size={16} />
            {loading ? "Loading…" : "Load recording"}
          </button>
          <p id="session-help" className="form-help">
            Use the exact ID from your Python recorder. No session listing
            endpoint is available.
          </p>
        </form>
      </Panel>
      {error && <ErrorNotice message={error} title="Recording unavailable" />}
      <Panel
        title="Event timeline"
        subtitle={
          view
            ? `Session ${view.sessionId} · Loaded ${timeLabel(view.loadedAt)}`
            : "Inspect the actions behind a demonstration"
        }
        action={
          view && <span className="badge">{view.events.length} events</span>
        }
      >
        {loading ? (
          <Loading>Retrieving recorded events…</Loading>
        ) : view ? (
          view.events.length ? (
            <>
              <div className="timeline-note">
                Original recording order from the API. Times shown in your
                browser's timezone.
              </div>
              <ol className="event-timeline">
                {view.events.map((event, index) => (
                  <EventRow event={event} index={index} key={event.id} />
                ))}
              </ol>
            </>
          ) : (
            <EmptyState
              icon={<Clapperboard size={26} />}
              title="No events returned"
            >
              <p>
                The backend returned an empty array for{" "}
                <code>{view.sessionId}</code>. This can mean an unknown session
                or a session with no saved events; the API does not distinguish
                them.
              </p>
            </EmptyState>
          )
        ) : (
          <EmptyState
            icon={<Clapperboard size={26} />}
            title="Your demonstration starts here"
          >
            <p>
              Load a recording to inspect its actions, targets and semantic
              locator metadata.
            </p>
          </EmptyState>
        )}
      </Panel>
    </>
  );
}
