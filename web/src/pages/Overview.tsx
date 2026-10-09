import {
  Activity,
  ArrowUpRight,
  Cable,
  Clapperboard,
  MousePointer2,
  ScanLine,
  Sparkles,
} from "lucide-react";
import type { LoadedRecording } from "../api/client";
import type { Connection } from "../hooks/useBackend";
import { ArrowLabel, EmptyState, Panel, timeLabel } from "../components/ui";

export function Overview({
  connection,
  recording,
  navigate,
}: {
  connection: Connection;
  recording: LoadedRecording | null;
  navigate: (page: "teach" | "recordings" | "skills" | "activity") => void;
}) {
  return (
    <>
      <div className="intro-panel">
        <div>
          <div className="intro-icon">
            <ScanLine size={26} />
          </div>
          <h2>
            From demonstration
            <br />
            to repeatable work.
          </h2>
          <p>
            Teach a workflow. Inspect the evidence.
            <br />
            Review a skill. Approve its replay.
          </p>
          <button className="button primary" onClick={() => navigate("teach")}>
            <ArrowLabel>Explore Teach Mode</ArrowLabel>
          </button>
        </div>
        <div className="workflow-map" aria-label="Workflow stages">
          <div>
            <MousePointer2 size={20} />
            <span>Observe</span>
            <small>Python recorder</small>
          </div>
          <span className="connector" />
          <div>
            <Clapperboard size={20} />
            <span>Inspect</span>
            <small>Recorded events</small>
          </div>
          <span className="connector" />
          <div>
            <Sparkles size={20} />
            <span>Compile</span>
            <small>Human review</small>
          </div>
        </div>
      </div>
      <div className="metrics">
        <div>
          <Cable size={18} />
          <span>Backend connection</span>
          <strong
            className={connection.state === "connected" ? "text-cyan" : ""}
          >
            {connection.state === "connected"
              ? "Connected"
              : connection.state === "checking"
                ? "Checking…"
                : "Unavailable"}
          </strong>
          <small>
            {connection.health?.service || "Health check on port 8000"}
          </small>
        </div>
        <div>
          <ScanLine size={18} />
          <span>Current recording session</span>
          <strong className="metric-empty">Not available</strong>
          <small>Recorder status is not exposed by the API</small>
        </div>
        <div>
          <MousePointer2 size={18} />
          <span>Events in loaded recording</span>
          <strong>{recording ? recording.events.length : "—"}</strong>
          <small>
            {recording
              ? recording.sessionId
              : "Load a session to inspect events"}
          </small>
        </div>
      </div>
      <div className="overview-bottom">
        <Panel
          title="Last loaded recording"
          subtitle="Only data retrieved from the backend"
          action={
            <button
              className="icon-button"
              aria-label="Open recordings"
              onClick={() => navigate("recordings")}
            >
              <ArrowUpRight size={18} />
            </button>
          }
        >
          {recording ? (
            <div className="recording-summary">
              <div className="summary-icon">
                <Clapperboard size={22} />
              </div>
              <div>
                <strong className="mono">{recording.sessionId}</strong>
                <p>
                  {recording.events.length} recorded events · Loaded{" "}
                  {timeLabel(recording.loadedAt)}
                </p>
              </div>
              <dl className="summary-facts">
                <div>
                  <dt>First event</dt>
                  <dd>
                    {recording.events[0]
                      ? timeLabel(recording.events[0].timestamp)
                      : "No events returned"}
                  </dd>
                </div>
                <div>
                  <dt>Last event</dt>
                  <dd>
                    {recording.events.at(-1)
                      ? timeLabel(recording.events.at(-1)!.timestamp)
                      : "No events returned"}
                  </dd>
                </div>
              </dl>
            </div>
          ) : (
            <EmptyState
              icon={<Clapperboard size={25} />}
              title="No recording loaded"
            >
              <p>Enter a session ID to inspect its event timeline.</p>
            </EmptyState>
          )}
          <div className="panel-footer">
            <button
              className="text-button"
              onClick={() => navigate("recordings")}
            >
              <ArrowLabel>Open recording viewer</ArrowLabel>
            </button>
          </div>
        </Panel>
        <Panel
          title="Agent activity"
          subtitle="Real replay controls and execution logs"
        >
          <EmptyState icon={<Activity size={25} />} title="Inspect a replay">
            <p>
              Open Agent Activity to load a confirmed skill, run preflight and
              explicitly approve replay. Results are shown only after an API
              response.
            </p>
          </EmptyState>
          <div className="panel-footer">
            <button
              className="text-button"
              onClick={() => navigate("activity")}
            >
              <ArrowLabel>Open replay workspace</ArrowLabel>
            </button>
          </div>
        </Panel>
      </div>
    </>
  );
}
