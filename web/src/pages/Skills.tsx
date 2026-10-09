import { useState } from "react";
import { FileCode2, Sparkles } from "lucide-react";
import { compileSkill, type CompileResult } from "../api/client";
import {
  EmptyState,
  ErrorNotice,
  JsonView,
  Loading,
  Panel,
} from "../components/ui";

export function Skills({
  loadedSessionId,
  result,
  setResult,
}: {
  loadedSessionId: string;
  result: CompileResult | null;
  setResult: (result: CompileResult) => void;
}) {
  const [sessionId, setSessionId] = useState(loadedSessionId);
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<CompileResult | null>(result);
  async function compile() {
    if (loading) return;
    setLoading(true);
    setError(null);
    setView(null);
    try {
      const data = await compileSkill({
        session_id: sessionId,
        task_description: description,
      });
      setView(data);
      setResult(data);
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Compilation request failed.",
      );
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="two-column">
      <Panel
        title="Compile a skill"
        subtitle="Submit a recorded session and its intended task"
      >
        <form
          className="panel-body compile-form"
          onSubmit={(event) => {
            event.preventDefault();
            void compile();
          }}
        >
          <label htmlFor="compile-session">Recorded session ID</label>
          <input
            id="compile-session"
            required
            maxLength={128}
            spellCheck={false}
            autoComplete="off"
            value={sessionId}
            onChange={(event) => setSessionId(event.target.value)}
            placeholder="Enter the session you demonstrated"
          />
          <label htmlFor="task-description">Task description</label>
          <textarea
            id="task-description"
            required
            rows={5}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Describe the workflow and what a successful outcome looks like."
          />
          <p className="form-help">
            This sends a real request to the compiler. It does not execute the
            workflow.
          </p>
          <button type="submit" className="button primary" disabled={loading}>
            <Sparkles size={16} />
            {loading ? "Compiling…" : "Compile skill"}
          </button>
        </form>
        <div className="panel-footer integration-note">
          <span className="badge amber">Pending integration</span>
          <p>
            Compiler endpoints are not present in this checkout's backend. Until
            your teammate connects them, the request may return HTTP 404.
          </p>
        </div>
      </Panel>
      <div className="side-stack">
        {error && (
          <ErrorNotice message={error} title="Compilation request failed" />
        )}
        <Panel
          title="Compiler response"
          subtitle="The actual JSON returned by the API"
        >
          {loading ? (
            <Loading>Waiting for the compiler…</Loading>
          ) : view ? (
            <div className="panel-body">
              <dl className="response-context">
                <div>
                  <dt>Submitted session</dt>
                  <dd className="mono">{view.sessionId}</dd>
                </div>
                <div>
                  <dt>Submitted task</dt>
                  <dd>{view.taskDescription}</dd>
                </div>
              </dl>
              <JsonView value={view.payload} label="Actual compiler response" />
            </div>
          ) : (
            <EmptyState
              icon={<FileCode2 size={25} />}
              title="No draft response yet"
            >
              <p>
                A successful API response will appear here exactly as returned.
                No skill data is preloaded.
              </p>
            </EmptyState>
          )}
          <div className="panel-footer">
            <button className="button secondary" disabled>
              Confirm draft · Coming soon
            </button>
            <p className="small muted">
              Draft confirmation and skill retrieval await the backend response
              and confirmation contracts. No confirmation payload is assumed.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
