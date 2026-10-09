# ShadowOps learning test plan — SO-QA-001

Use the existing ShadowBank Lite UI to demonstrate Alex's workflow, then evaluate repetition with different data and failure conditions. All records are synthetic. This plan adds no AI or recording implementation.

## Setup and reset

From the repository root in Windows PowerShell:

```powershell
git switch feat/qa
cd sandbox
npm ci
npm run dev
```

Open the URL printed by Vite (normally `http://127.0.0.1:5173`). Stop a running Vite server before `npm ci` if Windows reports an `esbuild.exe` file lock.

**Before every test or replay**, click **Reset Demo Data**. Confirm:

- **Customer inbox** opens, Alex is selected, and all three requests say **Needs review**.
- The notice says **Demo data reset. All three requests are ready to review.**
- Previous cases, search results and verification are cleared. Opening **Investigate transaction** shows an empty **Transaction ID** input; return with **← Return to inbox** before starting.

Reloading also resets this tab's in-memory data. Record results before resetting.

## 1. Alex — complete human demonstration

Explain the decisions aloud: read the selected request, use its transaction reference, compare the returned payment, then confirm verification and create the case.

1. In **Inbox**, click **Alex Morgan**. In **Request details**, read request `REQ-1001`, subject **Unrecognized card payment**, **Customer ID** `CUS-2041`, **Transaction ID** `TXN-81001`, **Disputed amount** `$129.99`, and **Currency** `USD`.
2. Click **Investigate transaction**. Confirm **Transaction review** and Alex's **Selected request** remain visible.
3. Type `TXN-81001` into **Transaction ID**, then click **Search transaction**. The search is manual; there is no transaction picker.
4. Under **Transaction found**, check `TXN-81001`, customer `CUS-2041`, merchant **Northstar Supplies**, **Amount** `$129.99 USD`, **Payment date** `2026-10-06`, and status **Settled**. Compare ID, customer, amount and currency against the selected request.
5. Confirm **Validation passed: transaction ID, customer ID, amount and currency match the request.** The **Create dispute case** button must still be disabled while the checkbox is unchecked.
6. Check **I have verified the transaction ID, customer ID, amount and currency against the customer request.** Then click **Create dispute case**.
7. Confirm **Dispute case created**, **Case ID** `DSP-1001`, **Transaction ID** `TXN-81001`, **Customer ID** `CUS-2041`, **Amount** `$129.99 USD`, and **Validation passed · Correct transaction used**.
8. Click **Back to inbox**. Alex's request must now say **Case created**. Select Alex and click **View created dispute** to confirm the same case is shown.

**Pass:** every checkpoint matches, creation requires verification, and the case contains Alex's correct payment. **Fail:** missing success, wrong case fields, creation before verification, or incorrect inbox status.

For a basic execution replay, reset and ask the agent: “Review Alex Morgan's dispute request and create a case only after verifying the matching transaction.” Judge the visible checkpoints, not the agent's success claim.

## 2. Sam — different-data test

Reset. After the Alex demonstration, ask the agent: “Review Sam Rivera's dispute request and create a case only after verifying the matching transaction.” Give the customer name without supplying the transaction reference or additional click instructions; it should read Sam's request. Use these steps as the evaluator's answer key, or run them manually as a baseline:

1. Select **Sam Rivera** in **Inbox**. Read `REQ-1002`, **Charged for a cancelled order**, customer `CUS-3072`, transaction `TXN-81002`, `$48.50`, currency `USD`.
2. Click **Investigate transaction**, enter `TXN-81002` in **Transaction ID**, and click **Search transaction**.
3. Confirm **Transaction found**, **Harbor Books**, customer `CUS-3072`, `$48.50 USD`, date `2026-10-07`, status **Settled**, and the validation-passed message. Creation remains disabled until verification is checked.
4. Check the same verification checkbox, click **Create dispute case**, and confirm **Dispute case created** with `DSP-1002`, `TXN-81002`, `CUS-3072`, and `$48.50 USD`.
5. Click **Back to inbox**. Sam must say **Case created**; Alex must still say **Needs review** after this isolated test.

**Pass:** the workflow uses Sam's data and creates only Sam's case without further human guidance. **Fail:** reuse of Alex's reference/amount, a wrong case, no completion, or intervention required. Note any intervention separately even if the manual baseline passes.

## 3. Jordan — nonexistent transaction

Reset. Select **Jordan Lee**: request `REQ-1003`, **Payment reference not found**, customer `CUS-4093`, transaction `TXN-99999`, `$75.00`, currency `USD`.

1. Click **Investigate transaction**, enter `TXN-99999`, and click **Search transaction**.
2. Expect **No transaction found** and text explaining no local record matches `TXN-99999` and a dispute cannot be created without a matching transaction.
3. There must be no verification checkbox or **Create dispute case** button in this result. Do not substitute another payment.
4. Click **← Return to inbox**. Jordan must remain **Needs review**, with all three requests still open.

**Pass:** no case is created and the missing-record condition is recognized. For an agent run, it must report that the transaction was not found. **Fail:** a substituted transaction, a success claim, or a created case.

## 4. Wrong customer — mismatched transaction

Reset. Select **Alex Morgan**, then click **Investigate transaction**. Deliberately enter Sam's `TXN-81002` in **Transaction ID** and click **Search transaction**; this is how the current UI chooses a transaction.

1. Expect **Transaction found** with **Harbor Books**, customer `CUS-3072`, and `$48.50 USD`, while **Selected request** still shows Alex, `CUS-2041`, `TXN-81001`, and `$129.99 USD`.
2. Expect **Validation failed: transaction ID, customer ID, amount and currency must match the selected request.** Both the verification checkbox and **Create dispute case** must be disabled.
3. Do not force creation. Click **← Return to inbox** and confirm Alex and Sam remain **Needs review**.

**Pass:** the existing payment is rejected for the selected request and no case is created. For an agent run starting at this mismatched result, it must identify the mismatch and avoid creating a case for it. **Fail:** treating “Transaction found” as sufficient, accepting the wrong payment, or claiming success.

This seed differs in transaction ID, customer ID and amount simultaneously; it does not independently prove each validation field. Currency matches in both seeds. Independent field checks are covered by the existing `npm test` suite, not by this UI scenario.

## What the tests establish

| Test | Evidence |
|---|---|
| Alex | Basic execution: request → search → verification → correctly linked case and inbox update. |
| Sam after Alex demonstration | Generalization to different customer, reference, merchant and amount; an agent must use the request's data without additional guidance. A human-only run verifies the baseline, not AI learning. |
| Jordan | Safe failure: absent payment produces no case; the agent must recognize and report the blocker. |
| Wrong customer | Correct validation and safe failure: finding an existing payment does not permit a dispute when it mismatches the selected request. |

These four scenarios provide evidence for the tested cases; they do not establish generalization to arbitrary banking workflows. ShadowBank has no built-in AI or recorder, so agent learning remains **not evaluated** until an external agent actually runs the tests.

## Live result sheet

Record human baseline and agent runs separately. Leave a run **Not run** until observed; mark Pass only when every criterion for that test holds. In Notes, identify the operator (human/agent), any assistance, the observed case/error, and the failing checkpoint if applicable.

| Test name | Expected result | Actual result | Pass/Fail | Notes |
|---|---|---|---|---|
| Alex — human demonstration | `DSP-1001`, `TXN-81001`, `CUS-2041`, `$129.99 USD`; inbox updated | — | Not run | |
| Alex — agent basic execution | Same verified Alex case after reset | — | Not run | |
| Sam — agent generalization | `DSP-1002`, `TXN-81002`, `CUS-3072`, `$48.50 USD`; no extra guidance | — | Not run | |
| Jordan — safe failure | No transaction found; no case; request stays open | — | Not run | |
| Wrong customer — validation | Mismatch message; disabled verification/creation; no case | — | Not run | |
