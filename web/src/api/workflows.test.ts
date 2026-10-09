import { test } from "node:test";
import assert from "node:assert/strict";
import { ApiError, requestJson } from "./client";
import {
  draftSchema,
  replaySchema,
  skillSchema,
  type ReplayInput,
} from "./contracts";
import {
  confirmDraft,
  retrieveDraft,
  retrieveSkill,
  parseContract,
  preflightReplay,
  startReplay,
  resumeReplay,
  retrieveReplay,
  retrieveReplaySteps,
  stopReplay,
} from "./workflows";

// Protocol fixtures only: these do not establish successful real AI/replay integration.
const skill = {
  name: "Unit workflow",
  description: "Protocol test only",
  steps: [
    {
      action: "navigate",
      description: "Open demo",
      source_event_id: 1,
      url: "http://127.0.0.1:5173/",
    },
    {
      action: "fill",
      description: "Enter variable",
      source_event_id: 2,
      target: { selector: "#transaction" },
      value: "{{transaction_id}}",
    },
    {
      action: "set_checked",
      description: "Clear attestation",
      source_event_id: 3,
      target: { role: "checkbox", label: "Verified" },
      checked: false,
    },
    {
      action: "click",
      description: "Submit",
      source_event_id: 4,
      target: { role: "button", label: "Submit" },
    },
  ],
  variables: [
    {
      name: "transaction_id",
      description: "New synthetic ID",
      source_event_id: 2,
      example_value: "TXN-UNIT-OLD",
      source: "human_input",
      requires_human_input: true,
      default_value: null,
    },
  ],
  uncertainties: ["Human review required"],
  success_conditions: [
    {
      description: "Inspect visible result",
      requires_human_verification: true,
    },
  ],
  omitted_events: [],
};
const draft = {
  id: "draft-unit",
  session_id: "unit",
  task_description: "Test",
  created_at: "2026-10-09T12:00:00Z",
  model: "test-only",
  status: "pending_review",
  source_event_ids: [1, 2, 3, 4],
  skill,
};
const saved = {
  id: "skill-unit",
  draft_id: draft.id,
  session_id: "unit",
  confirmed_at: draft.created_at,
  status: "confirmed",
  skill,
};
const input: ReplayInput = {
  skill_id: "skill-unit",
  parameters: { transaction_id: "TXN-UNIT-NEW" },
  context_selection: null,
  step_contexts: {},
  approved_steps: [],
};
const record = {
  id: "replay-unit",
  skill_id: input.skill_id,
  parameters: input.parameters,
  status: "paused",
  created_at: draft.created_at,
  current_step: 4,
  pause_reason: "Explicit approval required",
  outcome_verified: false,
  results: [],
};

test("draft parsing rejects malformed steps, unknown corrections and implicit variable/success verification", () => {
  const parsed = parseContract(draftSchema, draft);
  assert.equal(parsed.skill.steps[2].checked, false);
  assert.throws(
    () =>
      parseContract(skillSchema, {
        ...skill,
        variables: [{ ...skill.variables[0], requires_human_input: false }],
      }),
    ApiError,
  );
  assert.throws(
    () =>
      parseContract(skillSchema, {
        ...skill,
        success_conditions: [
          { description: "Invented", requires_human_verification: false },
        ],
      }),
    ApiError,
  );
  assert.throws(
    () =>
      parseContract(skillSchema, {
        ...skill,
        steps: [{ ...skill.steps[3], checked: false }],
      }),
    ApiError,
  );
  assert.throws(
    () => parseContract(skillSchema, { ...skill, invented_field: true }),
    ApiError,
  );
  assert.throws(
    () =>
      parseContract(skillSchema, {
        ...skill,
        steps: skill.steps.map((step, i) =>
          i === 1 ? { ...step, value: "{{unknown}}" } : step,
        ),
      }),
    ApiError,
  );
});

test("confirmation requires explicit approval and sends the entire corrected skill with checked=false preserved", async (t) => {
  let calls = 0;
  const edited = parseContract(skillSchema, {
    ...skill,
    description: "Human corrected description",
  });
  t.mock.method(
    globalThis,
    "fetch",
    async (path: string | URL | Request, init?: RequestInit) => {
      calls++;
      assert.equal(path, "/api/skill-drafts/draft-unit/confirm");
      assert.equal(init?.method, "POST");
      assert.deepEqual(JSON.parse(String(init?.body)), {
        confirmed: true,
        skill: edited,
      });
      return new Response(JSON.stringify({ ...saved, skill: edited }), {
        status: 201,
      });
    },
  );
  await assert.rejects(
    confirmDraft(draft.id, edited, false),
    /explicitly approve/,
  );
  assert.equal(calls, 0);
  assert.equal(
    (await confirmDraft(draft.id, edited, true)).skill.steps[2].checked,
    false,
  );
  assert.equal(calls, 1);
});

test("draft and skill retrieval reject a response belonging to another ID", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response(JSON.stringify(draft)),
  );
  await assert.rejects(retrieveDraft("draft-other"), /does not match/);
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response(JSON.stringify(saved)),
  );
  await assert.rejects(retrieveSkill("skill-other"), /does not match/);
});

test("preflight uses explicit runtime parameters without examples/defaults or automatic click approvals", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async (path: string | URL | Request, init?: RequestInit) => {
      assert.equal(path, "/api/replays/preflight");
      assert.deepEqual(JSON.parse(String(init?.body)), input);
      return new Response(
        JSON.stringify({
          skill_id: input.skill_id,
          confirmed: true,
          ready: true,
          can_start: true,
          errors: [],
          missing_parameters: [],
          warnings: ["Live uniqueness unverified"],
          steps: [],
          context_selection: null,
          allowed_origins: ["http://127.0.0.1:5173"],
        }),
      );
    },
  );
  assert.equal((await preflightReplay(input)).ready, true);
});

test("starting rejects implicit approval before sending any network request", async (t) => {
  let calls = 0;
  t.mock.method(
    globalThis,
    "fetch",
    async (path: string | URL | Request, init?: RequestInit) => {
      calls++;
      assert.equal(path, "/api/replays");
      assert.deepEqual(JSON.parse(String(init?.body)), {
        ...input,
        approved: true,
      });
      return new Response(JSON.stringify(record), { status: 202 });
    },
  );
  await assert.rejects(
    startReplay({ ...input, approved: false } as unknown as Parameters<
      typeof startReplay
    >[0]),
    /contract validation/,
  );
  assert.equal(calls, 0);
  assert.equal(
    (await startReplay({ ...input, approved: true })).status,
    "paused",
  );
  assert.equal(calls, 1);
});

test("resume only sends human-selected approval fields, stop does not claim a completed or stopped outcome", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async (path: string | URL | Request, init?: RequestInit) => {
      if (String(path).endsWith("/resume")) {
        assert.deepEqual(JSON.parse(String(init?.body)), {
          approved_steps: [4],
        });
        return new Response(JSON.stringify({ ...record, status: "running" }));
      }
      assert.equal(path, "/api/replays/replay-unit/stop");
      assert.equal(init?.body, undefined);
      return new Response(
        JSON.stringify({ id: record.id, stop_requested: true }),
        { status: 202 },
      );
    },
  );
  assert.equal(
    (await resumeReplay(record.id, { approved_steps: [4] })).outcome_verified,
    false,
  );
  assert.deepEqual(await stopReplay(record.id), {
    id: record.id,
    stop_requested: true,
  });
});

test("replay lookup and logs preserve paused attempts; malformed status fails rather than inventing success", async (t) => {
  const attempts = [
    {
      step: 4,
      action: "click",
      status: "paused",
      detail: "Ambiguous target",
      timestamp: draft.created_at,
    },
    {
      step: 4,
      action: "click",
      status: "succeeded",
      detail: "Unique after human context",
      timestamp: draft.created_at,
    },
  ];
  t.mock.method(
    globalThis,
    "fetch",
    async (path: string | URL | Request) =>
      new Response(
        JSON.stringify(String(path).endsWith("/steps") ? attempts : record),
      ),
  );
  assert.equal((await retrieveReplay(record.id)).status, "paused");
  assert.deepEqual(
    (await retrieveReplaySteps(record.id)).map((step) => step.status),
    ["paused", "succeeded"],
  );
  assert.throws(
    () => parseContract(replaySchema, { ...record, status: "success" }),
    ApiError,
  );
  await assert.rejects(retrieveReplay("replay-other"), /does not match/);
});

test("preflight error lists and approval failures remain visible without automatic retry", async (t) => {
  let calls = 0;
  t.mock.method(globalThis, "fetch", async () => {
    calls++;
    return new Response(
      JSON.stringify({ detail: ["Unconfirmed skill", "Invalid context"] }),
      { status: 422 },
    );
  });
  await assert.rejects(
    preflightReplay(input),
    /Unconfirmed skill; Invalid context/,
  );
  assert.equal(calls, 1);
});

test("cancelled monitoring requests stay cancelled", async (t) => {
  const controller = new AbortController();
  controller.abort();
  t.mock.method(
    globalThis,
    "fetch",
    async (_path: unknown, init?: RequestInit) => {
      init?.signal?.throwIfAborted();
      return new Response("{}");
    },
  );
  await assert.rejects(
    requestJson("/api/replays/unit", { signal: controller.signal }),
    (error) => error instanceof DOMException && error.name === "AbortError",
  );
});
