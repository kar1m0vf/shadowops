import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ApiError,
  compileSkill,
  getEvents,
  getHealth,
  parseEvents,
  requestJson,
  validateSessionId,
} from "./client";

// Isolated test fixtures only. Production has no mock transport or seeded data.
test("session validation rejects unsafe or empty paths and encodes valid IDs", () => {
  for (const value of [
    "",
    " ",
    "../other",
    "a/b",
    "a?b",
    "a#b",
    "a\\b",
    "x".repeat(129),
  ])
    assert.throws(() => validateSessionId(value), ApiError);
  assert.equal(validateSessionId(" teach-A "), "teach-A");
});
test("API insertion order survives inconsistent timestamps; malformed or cross-session data fails", () => {
  const base = {
    session_id: "unit-session",
    url: "about:blank",
    action: "click",
    target: { tag: "button", role: "button", label: "Load", selector: "#load" },
  };
  const records = [
    { ...base, id: 2, timestamp: "2026-10-09T12:00:00Z", checked: false },
    { ...base, id: 3, timestamp: "2026-10-09T11:00:00Z" },
    { ...base, id: 1, timestamp: "2026-10-09T12:00:00Z" },
  ];
  assert.deepEqual(
    parseEvents(records, "unit-session").map((event) => event.id),
    [2, 3, 1],
  );
  assert.equal(parseEvents(records, "unit-session")[0].checked, false);
  assert.deepEqual(parseEvents([], "unit-session"), []);
  assert.throws(
    () => parseEvents({ events: records }, "unit-session"),
    /expected an array/,
  );
  assert.throws(() => parseEvents(records, "other-session"), /does not match/);
  assert.throws(
    () =>
      parseEvents([{ ...records[0], timestamp: "invalid" }], "unit-session"),
    /does not match/,
  );
});
test("transport preserves server errors and rejects non-JSON success and malformed health", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }),
  );
  await assert.rejects(
    requestJson("/api/skills/compile"),
    (error) =>
      error instanceof ApiError &&
      error.status === 404 &&
      /Not Found/.test(error.message),
  );
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("proxy failed", { status: 500 }),
  );
  await assert.rejects(requestJson("/health"), /Backend unavailable/);
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("<html>not API data</html>"),
  );
  await assert.rejects(requestJson("/health"), /non-JSON/);
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response(JSON.stringify({ status: "ok" })),
  );
  await assert.rejects(getHealth(), /Unexpected health/);
});
test("compile sends exactly the known request contract; response remains untouched", async (t) => {
  const returned = { arbitrary_draft_field: "unit fixture" };
  t.mock.method(
    globalThis,
    "fetch",
    async (path: string | URL | Request, init?: RequestInit) => {
      assert.equal(path, "/api/skills/compile");
      assert.equal(init?.method, "POST");
      assert.deepEqual(JSON.parse(String(init?.body)), {
        session_id: "unit-session",
        task_description: "Review the request",
      });
      return new Response(JSON.stringify(returned));
    },
  );
  const result = await compileSkill({
    session_id: " unit-session ",
    task_description: " Review the request ",
  });
  assert.deepEqual(result.payload, returned);
});
test("empty retrieval is not converted into a successful recording", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response("[]"));
  const result = await getEvents("unit-empty");
  assert.equal(result.sessionId, "unit-empty");
  assert.equal(result.events.length, 0);
});
