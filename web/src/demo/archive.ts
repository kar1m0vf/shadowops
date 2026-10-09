import { z } from "zod";
import { draftSchema, replaySchema, savedSkillSchema } from "../api/contracts";

const facts = z.record(z.string(), z.string());
export const archiveSchema = z.object({
  archive_version: z.literal(1),
  mode: z.literal("archived_verified_read_only"),
  synthetic_data: z.literal(true),
  events: z.array(z.object({
    id: z.number().int(), session_id: z.string(), timestamp: z.string(),
    url: z.string(), action: z.string(),
    target: z.object({ tag: z.string().nullable().optional(), role: z.string().nullable().optional(),
      label: z.string().nullable().optional(), selector: z.string().nullable().optional() }).passthrough(),
    value: z.string().optional(), checked: z.boolean().optional(),
  }).passthrough()).min(1),
  draft: draftSchema,
  confirmed_skill: savedSkillSchema,
  replay: replaySchema,
  verification: z.object({
    actual_visible_confirmation: z.object({
      customer_name: z.string(), request: facts, transaction: facts,
      field_matches: z.object({ transaction_id: z.literal(true), customer_id: z.literal(true),
        amount: z.literal(true), currency: z.literal(true) }),
      independently_verified_before_attestation: z.literal(true),
      dispute_confirmation_visible: z.literal(true),
    }).passthrough(),
    human_confirmation: z.object({ confirmed: z.literal(true), statement: z.string() }).passthrough(),
  }).passthrough(),
  outcome: z.object({ case_id: z.string(), customer: z.string(), customer_id: z.string(),
    transaction_id: z.string(), amount: z.string(), currency: z.string() }),
  provenance: z.object({ session_id: z.string(), generated_at_baku: z.string(),
    source_artifact_hashes: z.array(z.object({ file: z.string(), sha256: z.string().length(64) })) }),
  screenshots: z.object({ before_dispute: z.literal("/demo/before-dispute.png"),
    confirmation: z.literal("/demo/dispute-confirmation.png") }),
}).superRefine((archive, ctx) => {
  const ids = archive.events.map(event => event.id);
  const confirmation = archive.verification.actual_visible_confirmation;
  if (archive.replay.status !== "completed" || !archive.replay.outcome_verified ||
      archive.replay.skill_id !== archive.confirmed_skill.id ||
      archive.confirmed_skill.draft_id !== archive.draft.id ||
      archive.confirmed_skill.session_id !== archive.provenance.session_id ||
      archive.draft.session_id !== archive.provenance.session_id ||
      archive.events.some(event => event.session_id !== archive.provenance.session_id) ||
      JSON.stringify(ids) !== JSON.stringify(archive.draft.source_event_ids) ||
      new Set(ids).size !== ids.length ||
      archive.outcome.case_id !== confirmation.transaction["Case ID"] ||
      archive.outcome.transaction_id !== confirmation.transaction["Transaction ID"] ||
      archive.outcome.customer_id !== confirmation.transaction["Customer ID"] ||
      confirmation.transaction["Amount"] !== `$${archive.outcome.amount} ${archive.outcome.currency}` ||
      confirmation.request["Disputed amount"] !== confirmation.transaction["Amount"] ||
      archive.outcome.customer !== confirmation.customer_name ||
      confirmation.request["Transaction ID to find"] !== archive.outcome.transaction_id ||
      confirmation.request["Customer ID"] !== archive.outcome.customer_id) {
    ctx.addIssue({ code: "custom", message: "Archive evidence identities or verified outcome do not match." });
  }
});
export type Archive = z.infer<typeof archiveSchema>;
