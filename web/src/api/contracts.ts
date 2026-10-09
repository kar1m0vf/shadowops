import { z } from "zod";

// Verified against origin/feat/replay, commit 4bc5a8af37a2f221660e3511fc7be6b475be1cd2.
// Backend evidence/privacy validators remain authoritative; no schema is inferred.
const text = z.string().trim().min(1).max(2000);
const identifier = z.string().trim().min(1).max(128);
const variableName = z.string().regex(/^[a-z][a-z0-9_]{0,63}$/);
const optionalString = (max: number) =>
  z.string().max(max).nullable().optional();
const timestamp = z
  .string()
  .refine((value) => Number.isFinite(Date.parse(value)), "Invalid timestamp");
const targetContext = z.strictObject({
  tag: optionalString(64),
  role: optionalString(128),
  label: optionalString(1024),
  selector: optionalString(4096),
});
const target = targetContext.extend({
  placeholder: optionalString(1024),
  locator_candidates: z
    .array(
      z.strictObject({
        strategy: z.enum(["role", "label", "placeholder", "test_id", "css"]),
        value: z.string().min(1).max(4096),
        name: optionalString(1024),
        match_count: z.number().int().nonnegative().nullable().optional(),
      }),
    )
    .max(8)
    .nullable()
    .optional(),
  context: targetContext.nullable().optional(),
});
export const skillStepSchema = z
  .strictObject({
    action: z.enum([
      "navigate",
      "click",
      "fill",
      "set_checked",
      "assert_visible",
      "ask_human",
    ]),
    description: text,
    source_event_id: z.number().int().positive().nullable().optional(),
    target: target.nullable().optional(),
    url: optionalString(4096),
    value: optionalString(4096),
    checked: z.boolean().nullable().optional(),
    question: text.nullable().optional(),
    uncertainty: text.nullable().optional(),
  })
  .superRefine((step, ctx) => {
    const required = {
      navigate: ["url"],
      click: ["target"],
      fill: ["target", "value"],
      set_checked: ["target", "checked"],
      assert_visible: ["target"],
      ask_human: ["question"],
    }[step.action];
    for (const key of [
      "target",
      "url",
      "value",
      "checked",
      "question",
    ] as const) {
      if ((step[key] != null) !== required.includes(key))
        ctx.addIssue({
          code: "custom",
          path: [key],
          message: `${step.action} requires exactly ${required.join(", ")}`,
        });
    }
    if (step.action !== "ask_human" && step.source_event_id == null)
      ctx.addIssue({
        code: "custom",
        path: ["source_event_id"],
        message: "Recorded evidence is required",
      });
    if (step.action === "assert_visible" && !step.uncertainty)
      ctx.addIssue({
        code: "custom",
        path: ["uncertainty"],
        message: "Proposed checks must state uncertainty",
      });
  });
export const skillSchema = z
  .strictObject({
    name: identifier,
    description: text,
    steps: z.array(skillStepSchema).min(1).max(500),
    variables: z
      .array(
        z.strictObject({
          name: variableName,
          description: text,
          source_event_id: z.number().int().positive(),
          example_value: z.string().max(4096).nullable(),
          source: z.literal("human_input"),
          requires_human_input: z.literal(true),
          default_value: optionalString(4096),
        }),
      )
      .max(100),
    uncertainties: z.array(text).min(1).max(100),
    success_conditions: z
      .array(
        z.strictObject({
          description: text,
          requires_human_verification: z.literal(true),
        }),
      )
      .min(1)
      .max(20),
    omitted_events: z
      .array(
        z.strictObject({ event_id: z.number().int().positive(), reason: text }),
      )
      .max(500),
  })
  .superRefine((skill, ctx) => {
    const names = skill.variables.map((variable) => variable.name);
    const used = new Set<string>();
    if (new Set(names).size !== names.length)
      ctx.addIssue({
        code: "custom",
        path: ["variables"],
        message: "Variable names must be unique",
      });
    for (const [index, step] of skill.steps.entries()) {
      if (step.value != null && /\{\{|\}\}/.test(step.value)) {
        const match = /^\{\{([a-z][a-z0-9_]{0,63})\}\}$/.exec(step.value);
        if (!match || !names.includes(match[1]))
          ctx.addIssue({
            code: "custom",
            path: ["steps", index, "value"],
            message: "Use an existing variable as {{variable_name}}",
          });
        else used.add(match[1]);
      }
    }
    if (names.some((name) => !used.has(name)))
      ctx.addIssue({
        code: "custom",
        path: ["variables"],
        message: "Every variable must be used by a fill step",
      });
  });
export const draftSchema = z.object({
  id: identifier,
  session_id: identifier,
  task_description: z.string(),
  created_at: timestamp,
  model: z.string(),
  status: z.literal("pending_review"),
  source_event_ids: z.array(z.number().int()),
  skill: skillSchema,
});
export const savedSkillSchema = z.object({
  id: identifier,
  draft_id: identifier,
  session_id: identifier,
  confirmed_at: timestamp,
  status: z.literal("confirmed"),
  skill: skillSchema,
});
export const contextHintSchema = z.strictObject({
  selector: z.string().min(1).max(1024),
  text: z.string().min(1).max(128).nullable().optional(),
});
const parameters = z
  .record(variableName, z.string().max(4096))
  .refine((value) => Object.keys(value).length <= 100);
export const stepContextsSchema = z
  .record(z.string().regex(/^[1-9][0-9]*$/), contextHintSchema)
  .refine((value) => Object.keys(value).length <= 500);
const approvedSteps = z.array(z.number().int().nonnegative()).max(501);
export const replayInputSchema = z.strictObject({
  skill_id: identifier,
  parameters,
  context_selection: contextHintSchema.nullable(),
  step_contexts: stepContextsSchema,
  approved_steps: approvedSteps,
});
export const startSchema = replayInputSchema.extend({
  approved: z.literal(true),
});
export const resumeSchema = z.strictObject({
  parameters: parameters.optional(),
  step_contexts: stepContextsSchema.optional(),
  approved_steps: approvedSteps.optional(),
  human_verified_step: z.number().int().positive().optional(),
  acknowledged_step: z.number().int().positive().optional(),
  outcome_verified: z.boolean().optional(),
});
export const stepResultSchema = z.object({
  step: z.number().int(),
  action: z.string(),
  source_event_id: z.number().int().nullable().optional(),
  status: z.enum(["succeeded", "paused", "failed"]),
  detail: z.string(),
  timestamp,
});
export const replaySchema = z.object({
  id: identifier,
  skill_id: identifier,
  parameters: z.record(z.string(), z.string()),
  context_selection: contextHintSchema.nullable().optional(),
  step_contexts: z.record(z.string(), contextHintSchema).optional(),
  approved_steps: approvedSteps.optional(),
  status: z.enum(["pending", "running", "paused", "failed", "completed"]),
  created_at: timestamp,
  current_step: z.number().int().nullable().optional(),
  pause_reason: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
  outcome_verified: z.boolean(),
  review_screenshot: z.string().nullable().optional(),
  review_evidence: z.record(z.string(), z.unknown()).nullable().optional(),
  results: z.array(stepResultSchema),
});
export const preflightSchema = z.object({
  skill_id: identifier,
  confirmed: z.boolean(),
  ready: z.boolean(),
  can_start: z.boolean(),
  errors: z.array(z.string()),
  missing_parameters: z.array(z.string()),
  warnings: z.array(z.string()),
  steps: z.array(
    z.object({
      step: z.number().int(),
      action: z.string(),
      description: z.string(),
      source_event_id: z.number().int().nullable().optional(),
      target: target.nullable().optional(),
      checked: z.boolean().nullable().optional(),
      resolved_value: z.string().nullable().optional(),
      requires_click_approval: z.boolean(),
      requires_verification: z.boolean(),
    }),
  ),
  context_selection: contextHintSchema.nullable(),
  allowed_origins: z.array(z.string()),
});
export type Skill = z.infer<typeof skillSchema>;
export type SkillStep = z.infer<typeof skillStepSchema>;
export type DraftRecord = z.infer<typeof draftSchema>;
export type SavedSkill = z.infer<typeof savedSkillSchema>;
export type ReplayInput = z.infer<typeof replayInputSchema>;
export type StartRequest = z.infer<typeof startSchema>;
export type ResumeRequest = z.infer<typeof resumeSchema>;
export type ReplayRecord = z.infer<typeof replaySchema>;
export type PreflightReport = z.infer<typeof preflightSchema>;
export type StepResult = z.infer<typeof stepResultSchema>;
