import { Activity, Cable } from "lucide-react";
import type { Connection } from "../hooks/useBackend";
import { EmptyState, Panel, timeLabel } from "../components/ui";

export function AgentActivity() {
  return (
    <Panel
      title="Execution history"
      subtitle="Replay integration is coming soon"
    >
      <EmptyState
        icon={<Activity size={30} />}
        title="Ready for the next chapter"
      >
        <p>
          Autonomous execution is not connected. When a real replay service is
          available, its activity and outcomes can appear here.
        </p>
        <span className="badge">Coming soon</span>
      </EmptyState>
    </Panel>
  );
}
export function Settings({ connection }: { connection: Connection }) {
  return (
    <div className="two-column">
      <Panel
        title="Connection configuration"
        subtitle="Read-only development configuration"
        action={<Cable size={18} />}
      >
        <div className="panel-body">
          <dl className="settings-list">
            <div>
              <dt>Control Center</dt>
              <dd className="mono">http://127.0.0.1:5174</dd>
            </div>
            <div>
              <dt>FastAPI proxy target</dt>
              <dd className="mono">http://localhost:8000</dd>
            </div>
            <div>
              <dt>Proxied paths</dt>
              <dd className="mono">/api · /health</dd>
            </div>
            <div>
              <dt>ShadowBank Lite</dt>
              <dd className="mono">http://127.0.0.1:5173</dd>
            </div>
            <div>
              <dt>Last health check</dt>
              <dd>
                {connection.checkedAt
                  ? timeLabel(connection.checkedAt)
                  : "Not completed"}
              </dd>
            </div>
          </dl>
          <p className="small muted">
            Connection settings are defined in vite.config.ts. No API keys or
            secrets are used by this frontend.
          </p>
        </div>
      </Panel>
      <Panel title="Workspace preferences" subtitle="Coming soon">
        <div className="panel-body">
          <p>
            Editable preferences and replay configuration will be added when
            their backend contracts are available.
          </p>
          <button className="button secondary" disabled>
            Save preferences · Coming soon
          </button>
        </div>
      </Panel>
    </div>
  );
}
