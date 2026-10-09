import { ExternalLink, MousePointer2, Terminal } from "lucide-react";
import { ArrowLabel, Panel } from "../components/ui";

export function TeachMode({ openRecordings }: { openRecordings: () => void }) {
  return (
    <div className="two-column">
      <Panel
        title="Demonstrate a workflow"
        subtitle="Use your team's Python recorder"
      >
        <div className="panel-body">
          <p className="lead">
            Work through ShadowBank naturally. The recorder captures the
            actions; the Control Center lets you inspect them.
          </p>
          <ol className="instruction-list">
            <li>
              <span>01</span>
              <div>
                <h3>Open ShadowBank Lite</h3>
                <p>
                  Start the existing sandbox on port 5173. Preserve the current
                  demo data during integration checks.
                </p>
                <a
                  className="text-button"
                  href="http://127.0.0.1:5173"
                  target="_blank"
                  rel="noreferrer"
                >
                  Open ShadowBank <ExternalLink size={14} />
                </a>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <h3>Start the Python recorder</h3>
                <p>
                  From the repository's backend folder, run the command below.
                  It opens visible Chromium at ShadowBank and prints a unique
                  Session ID. Keep that ID for Recordings.
                </p>
                <pre className="mono"><code>{".\\.venv\\Scripts\\python.exe -m recorder"}</code></pre>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <h3>Perform the demonstration</h3>
                <p>
                  Demonstrate the workflow you intend to teach using synthetic
                  local data. Review customer and transaction details before
                  any attestation or business action.
                </p>
              </div>
            </li>
            <li>
              <span>04</span>
              <div>
                <h3>Stop recording and inspect</h3>
                <p>
                  Return to the recorder terminal and press Enter to stop and
                  flush pending events. Enter
                  that session ID in Recordings and load the events from
                  FastAPI.
                </p>
                <button className="text-button" onClick={openRecordings}>
                  <ArrowLabel>Inspect a recording</ArrowLabel>
                </button>
              </div>
            </li>
          </ol>
        </div>
      </Panel>
      <div className="side-stack">
        <Panel title="Recorder integration" action={<Terminal size={18} />}>
          <div className="panel-body">
            <span className="badge">Python recorder available</span>
            <p>
              The recorder uses backend/recorder_config.json to restrict
              recording to configured local test origins and explicitly
              allowlisted non-sensitive field values.
            </p>
            <p>
              There is no recording control or live session detection in this
              frontend. A loaded session is not evidence that recording is
              currently active.
            </p>
          </div>
        </Panel>
        <Panel title="What to inspect" action={<MousePointer2 size={18} />}>
          <div className="panel-body">
            <ul className="check-list">
              <li>Actions and timestamps in sequence</li>
              <li>Labels, roles and element selectors</li>
              <li>Input values and checked state, if supplied</li>
              <li>The correct customer's transaction</li>
            </ul>
            <p className="small muted">
              Events include semantic locator candidates, allowed synthetic
              input values and boolean checked states. Sensitive values remain
              excluded.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
