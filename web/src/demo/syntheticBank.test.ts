import test from "node:test";
import assert from "node:assert/strict";
import { requests, transactions, validateTransaction, createDispute } from "./syntheticBank";
test("synthetic bank validates all four fields and rejects cross-customer payment", () => {
  assert.equal(validateTransaction(requests[1], transactions[1]).valid, true);
  assert.equal(validateTransaction(requests[0], transactions[1]).valid, false);
  assert.equal(validateTransaction(requests[1], undefined).valid, false);
});
test("synthetic write requires verification and blocks duplicates", () => {
  assert.throws(() => createDispute(requests[1], transactions[1], false, []));
  const dispute = createDispute(requests[1], transactions[1], true, []);
  assert.throws(() => createDispute(requests[1], transactions[1], true, [dispute]));
});
