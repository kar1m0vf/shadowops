import { JsonView, TextField } from "./ui";
import type { Skill, SkillStep } from "../api/contracts";

export function SkillReview({
  skill,
  onChange,
  readOnly = false,
}: {
  skill: Skill;
  onChange?: (skill: Skill) => void;
  readOnly?: boolean;
}) {
  function stepChange(index: number, patch: Partial<SkillStep>) {
    onChange?.({
      ...skill,
      steps: skill.steps.map((step, i) =>
        i === index ? { ...step, ...patch } : step,
      ),
    });
  }
  return (
    <div className="review-content">
      <fieldset className="review-fields" disabled={readOnly}>
        <legend>Skill details</legend>
        <TextField
          label="Skill name"
          value={skill.name}
          maxLength={128}
          onChange={(value) => onChange?.({ ...skill, name: value })}
        />
        <TextField
          label="Skill description"
          multiline
          rows={3}
          value={skill.description}
          onChange={(value) => onChange?.({ ...skill, description: value })}
        />
      </fieldset>
      <h3>
        Workflow steps <span className="badge">{skill.steps.length}</span>
      </h3>
      <p className="small muted">
        Review each action and its evidence. Recorded targets, action types and
        source event IDs stay attached to their original evidence.
      </p>
      <ol className="workflow-steps">
        {skill.steps.map((step, index) => (
          <li className="review-card" key={index}>
            <div className="review-card-heading">
              <strong>Step {index + 1}</strong>
              <span className="badge">{step.action}</span>
              <span className="small muted">
                Event {step.source_event_id ?? "not supplied"}
              </span>
            </div>
            <fieldset className="review-fields" disabled={readOnly}>
              <legend className="sr-only">Step {index + 1} corrections</legend>
              <TextField
                label="Description"
                multiline
                value={step.description}
                onChange={(value) => stepChange(index, { description: value })}
              />
              {step.action === "fill" && (
                <TextField
                  label="Input value or variable reference"
                  maxLength={4096}
                  value={step.value ?? ""}
                  onChange={(value) => stepChange(index, { value })}
                />
              )}
              {step.action === "set_checked" && (
                <label className="check-label">
                  <input
                    type="checkbox"
                    checked={step.checked === true}
                    onChange={(e) =>
                      stepChange(index, { checked: e.target.checked })
                    }
                  />
                  Checked state: {step.checked ? "true" : "false"}
                </label>
              )}
              {step.action === "ask_human" && (
                <TextField
                  label="Question"
                  multiline
                  value={step.question ?? ""}
                  onChange={(value) => stepChange(index, { question: value })}
                />
              )}
              <TextField
                label="Uncertainty"
                multiline
                value={step.uncertainty ?? ""}
                onChange={(value) =>
                  stepChange(index, { uncertainty: value || null })
                }
              />
            </fieldset>
            {step.url && (
              <p className="small">
                Destination: <span className="mono">{step.url}</span>
              </p>
            )}
            {step.target && (
              <details>
                <summary>Recorded target and semantic locators</summary>
                <JsonView
                  value={step.target}
                  label={`Step ${index + 1} recorded target`}
                />
              </details>
            )}
          </li>
        ))}
      </ol>
      <h3>
        Runtime variables{" "}
        <span className="badge">{skill.variables.length}</span>
      </h3>
      {skill.variables.length === 0 && (
        <p className="small muted">This skill declares no runtime variables.</p>
      )}
      {skill.variables.map((variable, index) => (
        <fieldset
          className="review-fields review-card"
          key={variable.name}
          disabled={readOnly}
        >
          <legend>{variable.name}</legend>
          <p className="small muted">
            Human input required · Source event {variable.source_event_id}
          </p>
          <p className="small">
            Recorded example:{" "}
            <span className="mono">
              {variable.example_value ?? "Not supplied"}
            </span>
          </p>
          <TextField
            label="Variable description"
            multiline
            value={variable.description}
            onChange={(value) =>
              onChange?.({
                ...skill,
                variables: skill.variables.map((item, i) =>
                  i === index ? { ...item, description: value } : item,
                ),
              })
            }
          />
          <TextField
            label="Default value (optional)"
            maxLength={4096}
            value={variable.default_value ?? ""}
            onChange={(value) =>
              onChange?.({
                ...skill,
                variables: skill.variables.map((item, i) =>
                  i === index
                    ? { ...item, default_value: value || null }
                    : item,
                ),
              })
            }
          />
          <p className="small muted">
            Replay requires explicit runtime values and never substitutes
            examples or defaults.
          </p>
        </fieldset>
      ))}
      <h3>Success conditions</h3>
      {skill.success_conditions.map((condition, index) => (
        <fieldset
          className="review-fields review-card"
          key={index}
          disabled={readOnly}
        >
          <legend>Condition {index + 1} · Human verification required</legend>
          <TextField
            label="Expected outcome"
            multiline
            value={condition.description}
            onChange={(value) =>
              onChange?.({
                ...skill,
                success_conditions: skill.success_conditions.map((item, i) =>
                  i === index ? { ...item, description: value } : item,
                ),
              })
            }
          />
        </fieldset>
      ))}
      <h3>Compiler uncertainties</h3>
      <ul className="message-list">
        {skill.uncertainties.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
      <details>
        <summary>Omitted events ({skill.omitted_events.length})</summary>
        <JsonView value={skill.omitted_events} />
      </details>
      <details>
        <summary>
          Complete {readOnly ? "saved" : "corrected"} skill JSON
        </summary>
        <JsonView value={skill} />
      </details>
    </div>
  );
}
