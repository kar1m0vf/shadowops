import { useState } from "react";
import { FileCode2, Sparkles, ShieldCheck } from "lucide-react";
import { ApiError, compileSkill, type CompileResult } from "../api/client";
import {
  draftSchema,
  type DraftRecord,
  type Skill,
  type SavedSkill,
} from "../api/contracts";
import { retrieveDraft, confirmDraft, parseContract } from "../api/workflows";
import { SkillReview } from "../components/SkillReview";
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
  onConfirmed,
}: {
  loadedSessionId: string;
  result: CompileResult | null;
  setResult: (result: CompileResult) => void;
  onConfirmed: (skill: SavedSkill) => void;
}) {
  const [sessionId, setSessionId] = useState(loadedSessionId);
  const [description, setDescription] = useState("");
  const [draftId, setDraftId] = useState("");
  const [draft, setDraft] = useState<DraftRecord | null>(null);
  const [edited, setEdited] = useState<Skill | null>(null);
  const [saved, setSaved] = useState<SavedSkill | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<CompileResult | null>(result);
  function loadDraft(data: DraftRecord) {
    setDraft(data);
    setDraftId(data.id);
    setEdited(structuredClone(data.skill));
    setSaved(null);
    setApproved(false);
  }
  async function run(action: () => Promise<void>, mutating = false) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Request failed.";
      setError(
        mutating && error instanceof ApiError && error.status === null
          ? `${message} Inspect backend state before retrying: confirmation may have been saved despite a lost response.`
          : message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="feature-stack">
      <div className="two-column">
        <Panel
          title="Compile a skill"
          subtitle="Submit a real recording to the AI compiler"
        >
          <form
            className="panel-body compile-form"
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                const data = await compileSkill({
                  session_id: sessionId,
                  task_description: description,
                });
                setView(data);
                setResult(data);
                loadDraft(parseContract(draftSchema, data.payload));
              });
            }}
          >
            <label htmlFor="compile-session">Recorded session ID</label>
            <input
              id="compile-session"
              required
              maxLength={128}
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              autoComplete="off"
            />
            {loadedSessionId && sessionId !== loadedSessionId && (
              <button
                type="button"
                className="text-button"
                onClick={() => setSessionId(loadedSessionId)}
              >
                Use loaded recording
              </button>
            )}
            <label htmlFor="task-description">Task description</label>
            <textarea
              id="task-description"
              required
              maxLength={2000}
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <p className="form-help">
              Compilation proposes a draft. Review and confirmation are separate
              human actions.
            </p>
            <button type="submit" className="button primary" disabled={busy}>
              <Sparkles size={16} />
              Compile skill
            </button>
          </form>
        </Panel>
        <Panel
          title="Retrieve a draft"
          subtitle="Open an existing proposal for human review"
        >
          <form
            className="panel-body compile-form"
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => loadDraft(await retrieveDraft(draftId)));
            }}
          >
            <label htmlFor="draft-id">Draft ID</label>
            <input
              id="draft-id"
              required
              maxLength={128}
              disabled={busy}
              value={draftId}
              onChange={(e) => {
                setDraftId(e.target.value);
                setDraft(null);
                setEdited(null);
                setSaved(null);
                setApproved(false);
              }}
              autoComplete="off"
            />
            <button className="button secondary" disabled={busy}>
              Retrieve draft
            </button>
            <p className="form-help">
              Uses the actual stored draft. Your corrections are sent only when
              you explicitly confirm.
            </p>
          </form>
          {view && (
            <div className="panel-footer">
              <details>
                <summary>Last actual compiler response</summary>
                <JsonView value={view.payload} />
              </details>
            </div>
          )}
        </Panel>
      </div>
      {busy && <Loading>Waiting for the backend…</Loading>}
      {error && <ErrorNotice message={error} />}
      <Panel
        title="Human skill review"
        subtitle={
          draft
            ? `${draft.id} · ${draft.model} · ${draft.session_id}`
            : "Inspect the workflow before saving a confirmed skill"
        }
      >
        {draft && edited ? (
          <div className="panel-body">
            <SkillReview
              skill={edited}
              readOnly={busy || saved !== null}
              onChange={(skill) => {
                setEdited(skill);
                setApproved(false);
              }}
            />
            {saved ? (
              <div className="success-notice" role="status">
                <ShieldCheck size={20} />
                <div>
                  <strong>Skill confirmed by the backend</strong>
                  <p className="mono">{saved.id}</p>
                  <p>
                    Open Agent Activity and load this skill to prepare replay.
                  </p>
                </div>
              </div>
            ) : (
              <div className="approval-box">
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={approved}
                    disabled={busy}
                    onChange={(e) => setApproved(e.target.checked)}
                  />
                  I reviewed all steps, variables, uncertainties and success
                  conditions, and approve saving this skill.
                </label>
                <button
                  className="button primary"
                  disabled={!approved || busy}
                  onClick={() =>
                    void run(async () => {
                      setApproved(false);
                      const confirmed = await confirmDraft(
                        draft.id,
                        edited,
                        approved,
                      );
                      setSaved(confirmed);
                      onConfirmed(confirmed);
                    }, true)
                  }
                >
                  <ShieldCheck size={16} />
                  Confirm skill
                </button>
                <p className="small muted">
                  Confirmation saves the corrected skill. It does not start a
                  replay. Backend evidence validation may reject unsupported
                  corrections.
                </p>
              </div>
            )}
          </div>
        ) : (
          <EmptyState icon={<FileCode2 size={25} />} title="No draft loaded">
            <p>
              Compile a recording or retrieve a draft by its ID. No skill data
              is preloaded.
            </p>
          </EmptyState>
        )}
      </Panel>
    </div>
  );
}
