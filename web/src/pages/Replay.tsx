import { useEffect, useState } from "react";
import { Activity, Play, RefreshCw, Square } from "lucide-react";
import type {
  SavedSkill,
  ReplayRecord,
  PreflightReport,
  ReplayInput,
  ResumeRequest,
  StepResult,
} from "../api/contracts";
import { replayInputSchema, stepContextsSchema } from "../api/contracts";
import {
  parseContract,
  retrieveSkill,
  preflightReplay,
  startReplay,
  retrieveReplay,
  retrieveReplaySteps,
  resumeReplay,
  stopReplay,
} from "../api/workflows";
import { ApiError, validateSessionId } from "../api/client";
import { ReplayApproval } from "../components/ReplayApproval";
import { SkillReview } from "../components/SkillReview";
import {
  EmptyState,
  ErrorNotice,
  JsonView,
  Loading,
  Panel,
  timeLabel,
} from "../components/ui";

export function Replay({
  confirmedSkill,
}: {
  confirmedSkill: SavedSkill | null;
}) {
  const [skillId, setSkillId] = useState("");
  const [skill, setSkill] = useState<SavedSkill | null>(null);
  const [parameters, setParameters] = useState<Record<string, string>>({});
  const [setup, setSetup] = useState(false);
  const [selector, setSelector] = useState("");
  const [text, setText] = useState("");
  const [contexts, setContexts] = useState("{}");
  const [approvedSteps, setApprovedSteps] = useState<number[]>([]);
  const [approved, setApproved] = useState(false);
  const [preflight, setPreflight] = useState<{
    request: ReplayInput;
    report: PreflightReport;
  } | null>(null);
  const [replayId, setReplayId] = useState("");
  const [trackedId, setTrackedId] = useState("");
  const [record, setRecord] = useState<ReplayRecord | null>(null);
  const [logs, setLogs] = useState<StepResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollError, setPollError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  function invalidate() {
    setPreflight(null);
    setApproved(false);
  }
  function loadSkill(data: SavedSkill) {
    setSkill(data);
    setSkillId(data.id);
    setParameters({});
    setApprovedSteps([]);
    setSetup(false);
    setSelector("");
    setText("");
    setContexts("{}");
    invalidate();
  }
  async function run(action: () => Promise<void>, mutating = false) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    setApproved(false);
    try {
      await action();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Request failed.";
      setError(
        mutating && error instanceof ApiError && error.status === null
          ? `${message} The request may have reached the backend. Inspect its state before retrying; no action is retried automatically.`
          : message,
      );
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!trackedId || busy) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      try {
        const [state, attempts] = await Promise.all([
          retrieveReplay(trackedId, controller.signal),
          retrieveReplaySteps(trackedId, controller.signal),
        ]);
        if (controller.signal.aborted) return;
        setRecord(state);
        setLogs(attempts);
        setPollError(null);
        if (["pending", "running", "paused"].includes(state.status))
          timer = setTimeout(() => void poll(), 2500);
      } catch (error) {
        if (controller.signal.aborted) return;
        setPollError(
          error instanceof Error ? error.message : "Unable to refresh replay.",
        );
        // No mutation or automatic retry of a browser action. Only status is retried.
        timer = setTimeout(() => void poll(), 5000);
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [trackedId, busy, refreshKey]);
  function request(): ReplayInput {
    return parseContract(replayInputSchema, {
      skill_id: validateSessionId(skillId),
      parameters,
      context_selection: setup ? { selector, ...(text ? { text } : {}) } : null,
      step_contexts: parseContract(stepContextsSchema, JSON.parse(contexts)),
      approved_steps: approvedSteps,
    });
  }
  function track(data: ReplayRecord) {
    setReplayId(data.id);
    setTrackedId(data.id);
    setRecord(data);
    setLogs(data.results);
    setPollError(null);
  }
  const live =
    record !== null && ["pending", "running", "paused"].includes(record.status);
  const canStart =
    !!preflight &&
    preflight.report.ready &&
    preflight.report.can_start &&
    preflight.report.confirmed &&
    preflight.report.errors.length === 0 &&
    skill?.id === preflight.request.skill_id &&
    !live;
  async function resume(input: ResumeRequest) {
    if (!record || record.status !== "paused") return;
    await run(async () => track(await resumeReplay(record.id, input)), true);
  }
  return (
    <div className="feature-stack">
      <div className="two-column">
        <Panel
          title="Prepare a replay"
          subtitle="Load a confirmed skill and enter new runtime data"
        >
          <form
            className="panel-body compile-form"
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => loadSkill(await retrieveSkill(skillId)));
            }}
          >
            <label htmlFor="replay-skill-id">Skill ID</label>
            <input
              id="replay-skill-id"
              required
              maxLength={128}
              disabled={busy || live}
              value={skillId}
              onChange={(e) => {
                setSkillId(e.target.value);
                setSkill(null);
                invalidate();
              }}
              autoComplete="off"
            />
            <button className="button secondary" disabled={busy || live}>
              Load skill
            </button>
            {confirmedSkill && (
              <button
                type="button"
                className="text-button"
                disabled={busy || live}
                onClick={() => loadSkill(confirmedSkill)}
              >
                Use recently confirmed skill
              </button>
            )}
          </form>
          {skill && (
            <div className="panel-body replay-inputs">
              <h3>{skill.skill.name}</h3>
              <p className="small muted">{skill.id}</p>
              <fieldset className="review-fields" disabled={busy || live}>
                <legend>Runtime variables</legend>
                {skill.skill.variables.length === 0 && (
                  <p className="small muted">No variables declared.</p>
                )}
                {skill.skill.variables.map((variable) => (
                  <label key={variable.name}>
                    {variable.name}
                    <span className="small muted">{variable.description}</span>
                    <input
                      maxLength={4096}
                      autoComplete="off"
                      value={parameters[variable.name] ?? ""}
                      onChange={(e) => {
                        setParameters({
                          ...parameters,
                          [variable.name]: e.target.value,
                        });
                        invalidate();
                      }}
                    />
                  </label>
                ))}
                <p className="small muted">
                  Enter synthetic local demo data. Recorded examples and
                  defaults are never prefilled.
                </p>
              </fieldset>
              <fieldset className="review-fields" disabled={busy || live}>
                <legend>Optional setup context</legend>
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={setup}
                    onChange={(e) => {
                      setSetup(e.target.checked);
                      setApprovedSteps(approvedSteps.filter((n) => n !== 0));
                      invalidate();
                    }}
                  />
                  Select a context after the initial navigation (step 0)
                </label>
                {setup && (
                  <>
                    <label>
                      Context selector
                      <input
                        maxLength={1024}
                        value={selector}
                        onChange={(e) => {
                          setSelector(e.target.value);
                          invalidate();
                        }}
                      />
                    </label>
                    <label>
                      Visible context text (optional)
                      <input
                        maxLength={128}
                        value={text}
                        onChange={(e) => {
                          setText(e.target.value);
                          invalidate();
                        }}
                      />
                    </label>
                  </>
                )}
                <details>
                  <summary>Scope individual steps</summary>
                  <label className="field-label">
                    Step contexts (JSON)
                    <textarea
                      rows={4}
                      spellCheck={false}
                      className="mono"
                      value={contexts}
                      onChange={(e) => {
                        setContexts(e.target.value);
                        invalidate();
                      }}
                    />
                  </label>
                  <p className="small muted">
                    Actual one-based step numbers mapped to{" "}
                    {"{ selector, text? }"}. No target is chosen automatically.
                  </p>
                </details>
              </fieldset>
              <fieldset className="review-fields" disabled={busy || live}>
                <legend>Explicit click approvals</legend>
                <p className="small muted">
                  Leave clicks unchecked to review them at a pause. Approve a
                  click only after inspecting its target and effect.
                </p>
                {[
                  ...(setup
                    ? [
                        {
                          number: 0,
                          description: "Select the supplied setup context",
                        },
                      ]
                    : []),
                  ...skill.skill.steps.flatMap((step, i) =>
                    step.action === "click"
                      ? [{ number: i + 1, description: step.description }]
                      : [],
                  ),
                ].map((step) => (
                  <label className="check-label" key={step.number}>
                    <input
                      type="checkbox"
                      checked={approvedSteps.includes(step.number)}
                      onChange={(e) => {
                        setApprovedSteps(
                          e.target.checked
                            ? [...approvedSteps, step.number]
                            : approvedSteps.filter((n) => n !== step.number),
                        );
                        invalidate();
                      }}
                    />
                    Step {step.number}: {step.description}
                  </label>
                ))}
              </fieldset>
              <button
                className="button secondary"
                disabled={busy || live}
                onClick={() =>
                  void run(async () => {
                    const input = request();
                    setPreflight(null);
                    const report = await preflightReplay(input);
                    setPreflight({ request: input, report });
                  })
                }
              >
                Run preflight
              </button>
              <details>
                <summary>Inspect the saved workflow</summary>
                <SkillReview skill={skill.skill} readOnly />
              </details>
            </div>
          )}
        </Panel>
        <Panel
          title="Preflight results"
          subtitle="Read-only backend validation; no browser actions"
        >
          {preflight ? (
            <div className="panel-body">
              <span
                className={`badge ${preflight.report.ready ? "status-completed" : "amber"}`}
              >
                {preflight.report.ready ? "Structurally ready" : "Not ready"}
              </span>
              {preflight.report.errors.length > 0 && (
                <ErrorNotice
                  message={preflight.report.errors.join("; ")}
                  title="Preflight rejected"
                />
              )}
              {preflight.report.missing_parameters.length > 0 && (
                <p>
                  Missing runtime values:{" "}
                  {preflight.report.missing_parameters.join(", ")}
                </p>
              )}
              <h3>Warnings and review requirements</h3>
              <ul className="message-list">
                {preflight.report.warnings.map((warning, i) => (
                  <li key={i}>{warning}</li>
                ))}
              </ul>
              <details>
                <summary>
                  Resolved workflow and original preflight response
                </summary>
                <JsonView value={preflight.report} />
              </details>
              <div className="approval-box">
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={approved}
                    disabled={busy || !canStart}
                    onChange={(e) => setApproved(e.target.checked)}
                  />
                  I reviewed this preflight and approve starting a real browser
                  replay with these inputs.
                </label>
                <button
                  className="button primary"
                  disabled={busy || !canStart || !approved}
                  onClick={() =>
                    void run(async () => {
                      if (!preflight || !approved || !canStart) return;
                      track(
                        await startReplay({
                          ...preflight.request,
                          approved: true,
                        }),
                      );
                    }, true)
                  }
                >
                  <Play size={16} />
                  Start Replay
                </button>
                <p className="small muted">
                  Individual unapproved clicks and verification steps still
                  pause for human review. Editing inputs invalidates this
                  preflight.
                </p>
              </div>
            </div>
          ) : (
            <EmptyState
              icon={<Activity size={25} />}
              title="No preflight result"
            >
              <p>
                Load a skill, supply runtime values and run the real backend
                check before starting.
              </p>
            </EmptyState>
          )}
        </Panel>
      </div>
      {busy && <Loading>Waiting for the backend…</Loading>}
      {error && <ErrorNotice message={error} />}
      {pollError && (
        <ErrorNotice
          message={`${pollError} Last displayed state may be stale; approvals are disabled until status refresh succeeds.`}
        />
      )}
      {notice && (
        <p className="connection-banner" role="status">
          {notice}
        </p>
      )}
      <Panel
        title="Execution timeline"
        subtitle="Actual replay status and ordered attempt logs"
      >
        <form
          className="panel-body session-form"
          onSubmit={(e) => {
            e.preventDefault();
            void run(async () => {
              const id = validateSessionId(replayId);
              const [data, attempts] = await Promise.all([
                retrieveReplay(id),
                retrieveReplaySteps(id),
              ]);
              const saved = await retrieveSkill(data.skill_id);
              setSkill(saved);
              setSkillId(saved.id);
              invalidate();
              track(data);
              setLogs(attempts);
              setRefreshKey((n) => n + 1);
            });
          }}
        >
          <div>
            <label htmlFor="existing-replay-id">Replay ID</label>
            <input
              id="existing-replay-id"
              required
              maxLength={128}
              value={replayId}
              disabled={busy || live}
              onChange={(e) => setReplayId(e.target.value)}
              autoComplete="off"
            />
          </div>
          <button className="button secondary" disabled={busy || live}>
            Load replay
          </button>
        </form>
        {record ? (
          <div className="panel-body">
            <div className="review-card-heading" role="status">
              <strong className="mono">{record.id}</strong>
              <span className={`badge status-${record.status}`}>
                {record.status}
              </span>
              <span>Step {record.current_step ?? "not reported"}</span>
            </div>
            <p className="small muted">
              Created {timeLabel(record.created_at)} · Outcome verified:{" "}
              {record.outcome_verified ? "yes" : "no"}
            </p>
            {record.error && (
              <ErrorNotice message={record.error} title="Replay failed" />
            )}
            <div className="button-row">
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => setRefreshKey((n) => n + 1)}
              >
                <RefreshCw size={15} />
                Refresh status
              </button>
              {live && (
                <button
                  className="button danger"
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await stopReplay(record.id);
                      setNotice(
                        "Backend accepted the stop request. Waiting for the worker's actual status; this does not undo completed actions.",
                      );
                      setRefreshKey((n) => n + 1);
                    }, true)
                  }
                >
                  <Square size={15} />
                  Stop replay
                </button>
              )}
            </div>
            {record.status === "paused" && (
              <ReplayApproval
                key={`${record.id}:${record.current_step}:${record.pause_reason}:${!!pollError}:${JSON.stringify(record.review_evidence)}`}
                record={record}
                skill={skill?.id === record.skill_id ? skill : null}
                disabled={busy || !!pollError}
                onResume={(input) => void resume(input)}
              />
            )}
            {logs.length ? (
              <ol className="replay-timeline">
                {logs.map((result, index) => (
                  <li className="review-card" key={index}>
                    <div className="review-card-heading">
                      <strong>
                        Step {result.step} · {result.action}
                      </strong>
                      <span className={`badge status-${result.status}`}>
                        {result.status}
                      </span>
                    </div>
                    <p>{result.detail}</p>
                    <span className="small muted">
                      {timeLabel(result.timestamp)} · Event{" "}
                      {result.source_event_id ?? "not supplied"}
                    </span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="small muted">No step attempts returned yet.</p>
            )}
            <details>
              <summary>Actual replay response</summary>
              <JsonView value={record} />
            </details>
          </div>
        ) : (
          <EmptyState icon={<Activity size={25} />} title="No replay loaded">
            <p>
              Start an explicitly approved replay or retrieve an existing run by
              ID. No executions are simulated.
            </p>
          </EmptyState>
        )}
      </Panel>
    </div>
  );
}
