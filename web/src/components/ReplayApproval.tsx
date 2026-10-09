import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import type { ReplayRecord, ResumeRequest, SavedSkill } from "../api/contracts";
import { stepContextsSchema } from "../api/contracts";
import { parseContract } from "../api/workflows";
import { ErrorNotice, JsonView, TextField } from "./ui";

export function ReplayApproval({
  record,
  skill,
  disabled,
  onResume,
}: {
  record: ReplayRecord;
  skill: SavedSkill | null;
  disabled: boolean;
  onResume: (input: ResumeRequest) => void;
}) {
  const [approved, setApproved] = useState(false);
  const [parameters, setParameters] = useState<Record<string, string>>({});
  const [contexts, setContexts] = useState("{}");
  const [error, setError] = useState<string | null>(null);
  const number = record.current_step;
  const step =
    skill && number && number > 0 ? skill.skill.steps[number - 1] : undefined;
  const outcome = skill !== null && number === skill.skill.steps.length + 1;
  const canApprove =
    number != null &&
    ((number === 0 && record.context_selection != null) ||
      step?.action === "click" ||
      (step?.action === "set_checked" && step.checked === true) ||
      step?.action === "ask_human" ||
      outcome);
  function submit(approval: boolean) {
    try {
      const changes: ResumeRequest = {};
      const scopes = parseContract(stepContextsSchema, JSON.parse(contexts));
      if (Object.keys(scopes).length) changes.step_contexts = scopes;
      if (number === 0 && Object.keys(parameters).length)
        changes.parameters = parameters;
      if (approval) {
        if (!approved || !canApprove || number == null) return;
        if (outcome) changes.outcome_verified = true;
        else if (step?.action === "set_checked")
          changes.human_verified_step = number;
        else if (step?.action === "ask_human")
          changes.acknowledged_step = number;
        else changes.approved_steps = [number];
      }
      if (!Object.keys(changes).length)
        throw new Error(
          "Enter runtime values or a scoped context correction before resuming.",
        );
      setError(null);
      setApproved(false);
      onResume(changes);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Invalid correction.");
    }
  }
  return (
    <div className="approval-box">
      <h3>
        <ShieldCheck size={18} /> Human review required
      </h3>
      <p>
        {record.pause_reason ||
          "Inspect the live browser before taking action."}
      </p>
      {step && (
        <div className="review-card">
          <strong>
            Step {number} · {step.action}
          </strong>
          <p>{step.description}</p>
          {step.question && <p>{step.question}</p>}
          {step.target && (
            <details>
              <summary>Target to inspect</summary>
              <JsonView value={step.target} />
            </details>
          )}
        </div>
      )}
      {record.review_evidence && (
        <details open>
          <summary>Backend review evidence</summary>
          <JsonView value={record.review_evidence} />
        </details>
      )}
      {record.review_screenshot && (
        <p className="small muted">
          Screenshot on backend host:{" "}
          <span className="mono">{record.review_screenshot}</span>. Inspect the
          visible replay browser; this API does not serve the image.
        </p>
      )}
      {outcome && (
        <>
          <p>
            Inspect the final result independently and verify every saved
            success condition.
          </p>
          <ul className="message-list">
            {skill.skill.success_conditions.map((condition, i) => (
              <li key={i}>{condition.description}</li>
            ))}
          </ul>
        </>
      )}
      {number === 0 && skill && (
        <fieldset className="review-fields" disabled={disabled}>
          <legend>Supply missing runtime variables</legend>
          {skill.skill.variables.map((variable) => (
            <label key={variable.name}>
              {variable.name}
              <input
                maxLength={4096}
                value={parameters[variable.name] ?? ""}
                onChange={(e) =>
                  setParameters({
                    ...parameters,
                    [variable.name]: e.target.value,
                  })
                }
              />
            </label>
          ))}
        </fieldset>
      )}
      <details>
        <summary>Correct an ambiguous target using scoped context</summary>
        <TextField
          label="Step contexts (JSON)"
          multiline
          rows={5}
          maxLength={640000}
          disabled={disabled}
          value={contexts}
          onChange={(value) => {
            setContexts(value);
            setApproved(false);
          }}
        />
        <p className="small muted">
          Map actual one-based step numbers to {"{ selector, text? }"}. Use
          simple CSS and literal text from the live app. Runtime parameters can
          only change before browser execution (step 0).
        </p>
      </details>
      {error && <ErrorNotice message={error} />}
      <button
        className="button secondary"
        disabled={disabled}
        onClick={() => submit(false)}
      >
        Submit corrections and resume
      </button>
      {canApprove ? (
        <>
          <label className="check-label">
            <input
              type="checkbox"
              checked={approved}
              disabled={disabled}
              onChange={(e) => setApproved(e.target.checked)}
            />
            {outcome
              ? "I independently verified all success conditions."
              : step?.action === "set_checked"
                ? "I personally verified the visible data for this attestation."
                : step?.action === "ask_human"
                  ? "I reviewed and acknowledge this question."
                  : `I inspected the current target and approve the click at step ${number}.`}
          </label>
          <button
            className="button primary"
            disabled={disabled || !approved}
            onClick={() => submit(true)}
          >
            {outcome
              ? "Verify outcome and complete"
              : "Approve current step and resume"}
          </button>
        </>
      ) : (
        <p className="small muted">
          No action approval is offered for this step. Supply a supported
          correction above, or stop and inspect the run.
        </p>
      )}
    </div>
  );
}
