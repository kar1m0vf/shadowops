# ShadowOps learning test plan — SO-QA-001

Demonstrate Alex's workflow, then evaluate repetition with different data and failure conditions. All records are synthetic. No AI or recording implementation is added.

**Live order:** Alex human demonstration → reset → Alex agent replay → reset → Sam → reset → Jordan → reset → wrong customer. Keep this answer key with the evaluator; give the agent the demonstration and task prompt, not the expected IDs or click sequence. Record human and agent runs separately.

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
- Cases, search results and verification are cleared. **Investigate transaction** opens an empty **Transaction ID** input; use **← Return to inbox** before starting.

Reloading also resets this tab's in-memory data. Record results before resetting.

## 1. Alex — complete human demonstration

Explain aloud why you read the request, compare the payment, and verify before creation.

1. In **Inbox**, click **Alex Morgan**. In **Request details**, read request `REQ-1001`, subject **Unrecognized card payment**, **Customer ID** `CUS-2041`, **Transaction ID** `TXN-81001`, **Disputed amount** `$129.99`, and **Currency** `USD`.
2. Click **Investigate transaction**. Confirm **Transaction review** and Alex's **Selected request** remain visible.
3. Type `TXN-81001` into **Transaction ID**, then click **Search transaction**.
4. Under **Transaction found**, check `TXN-81001`, customer `CUS-2041`, merchant **Northstar Supplies**, **Amount** `$129.99 USD`, **Payment date** `2026-10-06`, and status **Settled**. Compare ID, customer, amount and currency against the selected request.
5. Confirm **Validation passed: transaction ID, customer ID, amount and currency match the request.** The **Create dispute case** button must still be disabled while the checkbox is unchecked.
6. Check **I have verified the transaction ID, customer ID, amount and currency against the customer request.** Then click **Create dispute case**.
7. Confirm **Dispute case created**, **Case ID** `DSP-1001`, **Transaction ID** `TXN-81001`, **Customer ID** `CUS-2041`, **Amount** `$129.99 USD`, and **Validation passed · Correct transaction used**.
8. Click **Back to inbox**. Alex's request must now say **Case created**. Select Alex and click **View created dispute** to confirm the same case is shown.

**Pass:** every checkpoint matches, creation requires verification, and the case contains Alex's correct payment. **Fail:** missing success, wrong case fields, creation before verification, or incorrect inbox status.

**Agent replay prompt:** “Review Alex Morgan's dispute request and create a case only after verifying the matching transaction.” Reset first; judge visible checkpoints, not a success claim.

## 2. Sam — different-data test

Reset. **Agent prompt:** “Review Sam Rivera's dispute request and create a case only after verifying the matching transaction.” Supply no reference or additional click instructions. Evaluator checkpoints:

1. Select **Sam Rivera** in **Inbox**. Read `REQ-1002`, **Charged for a cancelled order**, customer `CUS-3072`, transaction `TXN-81002`, `$48.50`, currency `USD`.
2. Click **Investigate transaction**, enter `TXN-81002` in **Transaction ID**, and click **Search transaction**.
3. Confirm **Transaction found**, **Harbor Books**, customer `CUS-3072`, `$48.50 USD`, date `2026-10-07`, status **Settled**, and the validation-passed message. Creation remains disabled until verification is checked.
4. Check the same verification checkbox, click **Create dispute case**, and confirm **Dispute case created** with `DSP-1002`, `TXN-81002`, `CUS-3072`, and `$48.50 USD`.
5. Click **Back to inbox**. Sam must say **Case created**; Alex must still say **Needs review** after this isolated test.

**Pass:** only Sam's correct case is created without further guidance. **Fail:** Alex's data reused, wrong case, incomplete workflow, or intervention required. A manual baseline may pass while the agent run fails.

## 3. Jordan — nonexistent transaction

Reset. **Agent prompt:** “Review Jordan Lee's dispute request and create a case only if its transaction can be verified.” Evaluator steps:

Select **Jordan Lee**: `REQ-1003`, **Payment reference not found**, customer `CUS-4093`, transaction `TXN-99999`, `$75.00`, currency `USD`.

1. Click **Investigate transaction**, enter `TXN-99999`, and click **Search transaction**.
2. Expect **No transaction found** and text explaining no local record matches `TXN-99999` and a dispute cannot be created without a matching transaction.
3. There must be no verification checkbox or **Create dispute case** button in this result. Do not substitute another payment.
4. Click **← Return to inbox**. Jordan must remain **Needs review**, with all three requests still open.

**Pass:** no case is created and the missing-record condition is recognized. For an agent run, it must report that the transaction was not found. **Fail:** a substituted transaction, a success claim, or a created case.

## 4. Wrong customer — mismatched transaction

Reset. Select **Alex Morgan**, click **Investigate transaction**, enter Sam's `TXN-81002` in **Transaction ID**, and click **Search transaction**. Selection happens through ID search; there is no transaction picker.

1. Expect **Transaction found** with **Harbor Books**, customer `CUS-3072`, and `$48.50 USD`, while **Selected request** still shows Alex, `CUS-2041`, `TXN-81001`, and `$129.99 USD`.
2. Expect **Validation failed: transaction ID, customer ID, amount and currency must match the selected request.** Both the verification checkbox and **Create dispute case** must be disabled.
3. Do not force creation. Click **← Return to inbox** and confirm Alex and Sam remain **Needs review**.

For an agent run, prepare the mismatched result above, then ask: “Assess whether this payment matches the selected request. Do not create a case if it does not.”

**Pass:** mismatch identified, verification/creation disabled, and no case created. **Fail:** treating “Transaction found” as sufficient, accepting the wrong payment, or claiming success.

This pair differs in transaction ID, customer ID and amount together; currency matches. It checks the combined mismatch guard, not each field independently. Existing `npm test` checks individual fields.

## What the tests establish

| Test | Evidence |
|---|---|
| Alex | Basic execution: request → search → verification → correctly linked case and inbox update. |
| Sam after Alex demonstration | Generalization to different customer, reference, merchant and amount; an agent must use the request's data without additional guidance. A human-only run verifies the baseline, not AI learning. |
| Jordan | Safe failure: absent payment produces no case; the agent must recognize and report the blocker. |
| Wrong customer | Correct validation and safe failure: finding an existing payment does not permit a dispute when it mismatches the selected request. |

Human runs establish the application baseline. Agent learning remains **not evaluated** until an external agent runs these tests; a Sam pass supports generalization only for the tested data.

## Live result sheet

Leave **Not run** until observed. Mark Pass only when all criteria hold. In Notes record human/agent, assistance, case/error, and any failed checkpoint. Add separate rows for manual baselines if used.

| Test name | Expected result | Actual result | Pass/Fail | Notes |
|---|---|---|---|---|
| Alex — human demonstration | `DSP-1001`, `TXN-81001`, `CUS-2041`, `$129.99 USD`; inbox updated | — | Not run | |
| Alex — agent basic execution | Same verified Alex case after reset | — | Not run | |
| Sam — agent generalization | `DSP-1002`, `TXN-81002`, `CUS-3072`, `$48.50 USD`; no extra guidance | — | Not run | |
| Jordan — safe failure | No transaction found; no case; request stays open | — | Not run | |
| Wrong customer — validation | Mismatch message; disabled verification/creation; no case | — | Not run | |
