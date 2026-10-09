import { useState } from "react";
import {
  Activity,
  BookOpen,
  ChevronRight,
  CircleDot,
  Clapperboard,
  LayoutDashboard,
  RefreshCw,
  ScanLine,
  Settings as SettingsIcon,
  Sparkles,
} from "lucide-react";
import type { CompileResult, LoadedRecording } from "./api/client";
import { useBackend } from "./hooks/useBackend";
import { Overview } from "./pages/Overview";
import { TeachMode } from "./pages/TeachMode";
import { Recordings } from "./pages/Recordings";
import { Skills } from "./pages/Skills";
import { AgentActivity, Settings } from "./pages/System";

const pages = [
  {
    id: "overview",
    label: "Overview",
    icon: LayoutDashboard,
    description: "Your workspace for teaching and inspecting workflows.",
  },
  {
    id: "teach",
    label: "Teach Mode",
    icon: BookOpen,
    description: "Show the workflow. Make every action count.",
  },
  {
    id: "recordings",
    label: "Recordings",
    icon: Clapperboard,
    description: "Explore the evidence behind a human demonstration.",
  },
  {
    id: "skills",
    label: "Skills",
    icon: Sparkles,
    description: "Turn a recorded workflow into a compiler request.",
  },
  {
    id: "activity",
    label: "Agent Activity",
    icon: Activity,
    description: "A place for future replay activity and outcomes.",
    soon: true,
  },
  {
    id: "settings",
    label: "Settings",
    icon: SettingsIcon,
    description: "Connection details and workspace configuration.",
  },
] as const;
type Page = (typeof pages)[number]["id"];
export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [recording, setRecording] = useState<LoadedRecording | null>(null);
  const [compileResult, setCompileResult] = useState<CompileResult | null>(
    null,
  );
  const { connection, refresh } = useBackend();
  const current = pages.find((item) => item.id === page)!;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <a
          className="brand"
          href="#main-content"
          onClick={() => setPage("overview")}
        >
          <span className="brand-symbol">
            <ScanLine size={23} />
          </span>
          <span>
            ShadowOps<small>CONTROL CENTER</small>
          </span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {pages.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              aria-current={page === item.id ? "page" : undefined}
              onClick={() => setPage(item.id)}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
              {"soon" in item && (
                <span
                  className="soon-dot"
                  title="Coming soon"
                  aria-label="Coming soon"
                />
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div>
            <CircleDot size={16} />
            <span>Local workspace</span>
          </div>
          <p>Observe. Understand. Repeat.</p>
          <span className="version">ShadowOps / Hackathon MVP</span>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} />
            <span>{current.label}</span>
          </div>
          <div className="connection-area">
            <span className={`connection ${connection.state}`} role="status">
              <span className="status-dot" />
              {connection.state === "connected"
                ? "Backend connected"
                : connection.state === "checking"
                  ? "Checking backend"
                  : "Backend unavailable"}
            </span>
            <button
              className="icon-button"
              onClick={() => void refresh()}
              disabled={connection.state === "checking"}
              aria-label="Refresh backend connection"
            >
              <RefreshCw size={15} />
            </button>
          </div>
        </header>
        <main id="main-content">
          <div className="page-title">
            <div>
              <h1>
                {current.label === "Overview"
                  ? "Workspace overview"
                  : current.label}
              </h1>
              <p>{current.description}</p>
            </div>
            {page === "overview" && (
              <button
                className="button secondary"
                onClick={() => setPage("recordings")}
              >
                <Clapperboard size={16} />
                Load recording
              </button>
            )}
          </div>
          {connection.error && (
            <div className="connection-banner">
              {connection.error}{" "}
              <button className="text-button" onClick={() => void refresh()}>
                Retry connection
              </button>
            </div>
          )}
          {page === "overview" && (
            <Overview
              connection={connection}
              recording={recording}
              navigate={setPage}
            />
          )}
          {page === "teach" && (
            <TeachMode openRecordings={() => setPage("recordings")} />
          )}
          {page === "recordings" && (
            <Recordings recording={recording} setRecording={setRecording} />
          )}
          {page === "skills" && (
            <Skills
              loadedSessionId={recording?.sessionId || ""}
              result={compileResult}
              setResult={setCompileResult}
            />
          )}
          {page === "activity" && <AgentActivity />}
          {page === "settings" && <Settings connection={connection} />}
          <footer className="app-footer">
            <span>ShadowOps Control Center</span>
            <span>Human demonstrations. Observable evidence.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
