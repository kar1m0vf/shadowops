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
                  Start the existing sandbox on port 5173. Click{" "}
                  <strong>Reset Demo Data</strong> before your demonstration.
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
                  Use the recorder teammate's documented launch command and
                  connect it to the ShadowBank browser. Keep the session ID it
                  generates or asks you to set.
                </p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <h3>Perform the demonstration</h3>
                <p>
                  Select Alex Morgan, investigate the transaction, search the
                  reference from the request, verify the matching payment and
                  create the dispute. Review the success state.
                </p>
              </div>
            </li>
            <li>
              <span>04</span>
              <div>
                <h3>Stop recording and inspect</h3>
                <p>
                  Stop the Python recorder using its documented controls. Enter
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
            <span className="badge amber">Pending handoff</span>
            <p>
              The recorder is developed separately. Its script and launch
              contract are not present in this checkout, so a verified command
              cannot be supplied yet.
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
              The current API stores tag, role, label and selector. Input values
              and checked state need recorder/backend support.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
