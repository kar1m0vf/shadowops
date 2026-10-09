import { test } from 'node:test';
import assert from 'node:assert/strict';
import { requests, transactions, validateTransaction, createDispute } from './domain';

test('both seeded customers can create correctly linked disputes', () => {
  const cases = requests.slice(0, 2).map((request, index) => createDispute(request, transactions[index], true, []));
  assert.notEqual(cases[0].customerId, cases[1].customerId);
  assert.notEqual(cases[0].transactionId, cases[1].transactionId);
  assert.notEqual(cases[0].amountCents, cases[1].amountCents);
  assert.equal(cases[0].id, 'DSP-1001');
});
test('wrong customer transaction and nonexistent transaction cannot create cases', () => {
  assert.equal(validateTransaction(requests[0], transactions[1]).valid, false);
  assert.throws(() => createDispute(requests[0], transactions[1], true, []), /Validation failed/);
  assert.throws(() => createDispute(requests[2], undefined, true, []), /not found/);
});
test('amount, currency and customer ID are independently validated', () => {
  for (const patch of [{ amountCents: 1 }, { currency: 'EUR' }, { customerId: 'CUS-WRONG' }]) {
    assert.equal(validateTransaction(requests[0], { ...transactions[0], ...patch }).valid, false);
  }
});
test('verification and duplicate protection are enforced at case creation', () => {
  assert.throws(() => createDispute(requests[0], transactions[0], false, []), /Confirm/);
  const existing = createDispute(requests[0], transactions[0], true, []);
  assert.throws(() => createDispute(requests[0], transactions[0], true, [existing]), /already exists/);
});
