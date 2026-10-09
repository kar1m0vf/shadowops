import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { archiveSchema } from "./archive";

// Actual sanitized acceptance evidence; no fabricated LLM or execution fixtures.
const source = JSON.parse(readFileSync(new URL("../../public/demo/archive.json", import.meta.url), "utf8"));
test("real archive preserves demonstration, variable, human correction and execution evidence", () => {
  const archive = archiveSchema.parse(source);
  assert.deepEqual(archive.events.map(event => event.id), [26,27,28,29,30,31,32,33,34]);
  assert.equal(archive.draft.skill.variables[0].name, "transaction_id");
  assert.equal(archive.draft.skill.variables[0].requires_human_input, true);
  assert.equal(archive.events.find(event => event.id === 31)?.checked, false);
  assert.equal(archive.confirmed_skill.skill.steps[5].checked, false);
  assert.match(archive.confirmed_skill.skill.steps[5].description, /does not confirm verification/);
  assert.equal(archive.replay.results.length, 14);
  assert.ok(archive.replay.results.some(result => result.status === "paused"));
  assert.equal(archive.outcome.case_id, "DSP-1002");
});
test("archive rejects mismatched identities, unverified outcomes and altered amounts", () => {
  for (const change of [
    (data: typeof source) => { data.replay.status = "running"; },
    (data: typeof source) => { data.verification.human_confirmation.confirmed = false; },
    (data: typeof source) => { data.replay.skill_id = "different-skill"; },
    (data: typeof source) => { data.outcome.amount = "99.00"; },
    (data: typeof source) => { data.events.reverse(); },
  ]) {
    const altered = structuredClone(source); change(altered);
    assert.equal(archiveSchema.safeParse(altered).success, false);
  }
});
test("public evidence contains no machine paths, credentials or external screenshot URLs", () => {
  const text = JSON.stringify(source);
  assert.doesNotMatch(text, /C:\\|C:\/|sk-[A-Za-z0-9_-]{24,}|gsk_[A-Za-z0-9]{24,}|BEGIN PRIVATE KEY/);
  assert.equal(source.synthetic_data, true);
  assert.deepEqual(Object.values(source.screenshots), ["/demo/before-dispute.png", "/demo/dispute-confirmation.png"]);
});
