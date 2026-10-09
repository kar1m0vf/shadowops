# ShadowOps Control Center

Public submission: [Archived Verified Demo — Read Only](https://shadowops-verified-demo.vercel.app).
See [SUBMISSION.md](../docs/SUBMISSION.md) for the real evidence, demo instructions
and limitations. `npm run dev` and `npm run build` retain local live mode;
`npm run build:demo` builds the static archive with no live API hooks. Vercel
deploys only `web/` using `vercel.json`. `web/public/demo/` contains the selected
synthetic evidence; original private files remain under ignored `backend/data/`.

React + TypeScript + Vite, with the existing plum/lavender/off-white design. Recordings, compilation, human skill review and replay use real API calls. No production fixtures, simulated outcomes, API secrets or automatic approvals.

For the integrated checkout on `feat/integration`, use [the complete system startup and demo guide](../docs/integration.md). SO-INT-007 verified this UI against the existing populated backend database: recording, real AI draft, confirmed skill, parameterized preflight and completed replay logs. Fresh compilation, confirmation and replay mutations were not performed during integration.

## Windows PowerShell

Use Node 22.12+ (verified with Node 22.20.0). From the repository root:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\web'
npm ci
npm test
npm run build
npm run dev
```

In another PowerShell window:

```powershell
Start-Process 'http://127.0.0.1:5174'
Invoke-RestMethod 'http://127.0.0.1:8000/health' | ConvertTo-Json -Compress
Invoke-RestMethod 'http://127.0.0.1:5174/health' | ConvertTo-Json -Compress
$apiContract = Invoke-RestMethod 'http://127.0.0.1:5174/openapi.json'
$apiContract.paths.PSObject.Properties.Name
```

The integrated **replay backend** must already be running on loopback port 8000 with the existing recordings/database and provider configuration. See [the integration guide](../docs/integration.md) for exact commands. Use one backend worker without reload while replaying.

The Control Center uses **5174**, with `strictPort`; ShadowBank remains **5173**. `/api`, `/health` and `/openapi.json` proxy to `http://127.0.0.1:8000`. For requests originating from this local UI (`http://127.0.0.1:5174` or `http://localhost:5174`), the API proxy forwards the backend origin, as required by its loopback-only replay policy. Other supplied origins remain unchanged and are rejected by that policy. Keep this dev proxy on loopback; it is not authentication for a public deployment.

Health must return `{"status":"ok","service":"shadowops-backend"}`. Health is not proof of active recording, available compiler credentials or replay success. It refreshes every 30 seconds. If FastAPI is absent, the UI reports **Backend unavailable** and preserves actionable API errors.

### Installation locks on Windows

Stop this web app's dev/preview server with Ctrl+C **before** `npm ci`. The confirmed installation blockers during this task were the Vite process under `web/node_modules` and its esbuild child. Only those two identified development processes were stopped; clean installation and build then succeeded. Other application processes were left alone.

To inspect a remaining lock, without killing anything indiscriminately:

```powershell
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -like '*shadowops\shadowops\web\node_modules*' -or
    $_.ExecutablePath -like '*shadowops\shadowops\web\node_modules*'
  } |
  Select-Object ProcessId, ParentProcessId, Name, ExecutablePath, CommandLine
```

Verify the path and parent-child relationship before stopping a specific process. Do not kill all Node, Python or Chrome processes or remove the lockfile to work around a lock.

## Verified API contract

Integration is based on teammate branch **`origin/feat/replay`**, commit **`4bc5a8af37a2f221660e3511fc7be6b475be1cd2`**. The actual compiler/replay Pydantic models, routes, evidence validators, preflight policy and runner were inspected read-only. The generated OpenAPI from an unchanged, isolated copy of that commit was also retrieved and its confirmation/start/resume fields checked. Preflight has no detailed OpenAPI response model; its response fields come from the actual `preflight` function.

`src/api/contracts.ts` defines TypeScript types and runtime Zod validation. `src/api/workflows.ts` owns typed review/replay calls. Evidence, privacy, allowed origins and live locator validation remain the backend's responsibility; client validation does not replace them. Malformed responses or mismatched resource IDs produce errors rather than invented status/results.

| Operation      | Actual request/response                                                                                                                                                                            |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Compile        | `POST /api/skills/compile`, `{session_id, task_description}` → `DraftRecord`; client waits up to 310 seconds for the backend's 300-second local inference timeout                                  |
| Retrieve draft | `GET /api/skill-drafts/{draft_id}` → `DraftRecord` with `skill`, source event IDs and model                                                                                                        |
| Confirm        | `POST /api/skill-drafts/{draft_id}/confirm`, `{confirmed: true, skill: <complete corrected SkillDraft>}` → `SavedSkill`                                                                            |
| Retrieve skill | `GET /api/skills/{skill_id}` → confirmed `SavedSkill`                                                                                                                                              |
| Preflight      | `POST /api/replays/preflight`, `{skill_id, parameters, context_selection, step_contexts, approved_steps}` → actual readiness, errors, warnings, missing parameters, resolved steps and origins     |
| Start          | `POST /api/replays`, the preflight request plus explicitly selected `approved: true` → `ReplayRecord`                                                                                              |
| Status / steps | `GET /api/replays/{id}` / `GET /api/replays/{id}/steps` → record / ordered attempt logs                                                                                                            |
| Resume         | `POST /api/replays/{id}/resume`, explicitly supplied corrections/approval only: `parameters`, `step_contexts`, `approved_steps`, `human_verified_step`, `acknowledged_step`, or `outcome_verified` |
| Stop           | `POST /api/replays/{id}/stop`, no body → `{id, stop_requested: true}`; actual final status comes from subsequent retrieval                                                                         |

The backend exposes states `pending`, `running`, `paused`, `failed`, `completed`. A successful step is not a successful business outcome. Stop requests do not undo completed actions. Replay mutation requests are never retried automatically. If a timeout/transport error loses a mutation response, inspect backend state before retrying.

## Live demonstration walkthrough

1. In **Recordings**, enter an actual session ID and select **Load recording**. Inspect the ordered events, target metadata, input values/checked state when supplied, and raw JSON. An unknown/empty session returns `[]`, which is shown as no events, not a successful demonstration.
2. In **Skills**, submit that session ID and a task description using **Compile skill**, or enter an existing **Draft ID** and select **Retrieve draft**.
3. Inspect every workflow step, variable, target/semantic locator, uncertainty, omitted event and success condition. Correct the exposed supported fields: skill name/description, step descriptions, fill values/templates, checked booleans, questions/uncertainties, variable descriptions/defaults and success-condition descriptions. Recorded URLs/targets/action types/event IDs/example values remain attached to their evidence. Structural/evidence restrictions are enforced and errors displayed.
4. Select the human-review checkbox, then **Confirm skill**. Any edit clears that approval. Only an actual `SavedSkill` response displays confirmation and the saved skill ID. Confirmation does not run anything; duplicate confirmation may return 409.
5. In **Agent Activity**, enter the **Skill ID** and select **Load skill**, or choose **Use recently confirmed skill**. Runtime values start empty; examples/defaults are never copied into runtime input.
6. Enter the actual new variable values. If the demonstrated workflow began with a selected context, supply **Optional setup context** using the real simple CSS selector and visible text; this explicit setup click is logged as step 0. Do not assume changing a transaction variable changes the selected customer. Individual step scopes accept JSON keyed by actual one-based step numbers with `{selector, text?}` values.
7. Leave click approvals unchecked to inspect each click at its pause, or explicitly approve particular clicks only after reviewing their effect. Select **Run preflight** and inspect warnings/errors and the resolved response. Editing runtime values, scope or approvals invalidates the result and requires another preflight. Start requires the current report to be confirmed, ready, executable and error-free.
8. Select the separate replay-start approval checkbox, then **Start Replay**. This starts a real browser; it is a state-changing action. The timeline shows actual status and attempts, polling every 2.5 seconds while active. Navigating between pages keeps review/replay state and monitoring; reloading the browser clears frontend memory, so retain the replay ID and retrieve it again.
9. At a pause, inspect the visible replay browser and actual backend review evidence. The screenshot field is a path on the backend host; no screenshot-serving route exists. The UI does not turn that local path into a fabricated image URL.
10. Supply missing parameters only at step 0, or correct an ambiguous step's context with **Submit corrections and resume**. A separate unchecked approval control handles the current click, checked=true attestation, or `ask_human` acknowledgment. It never approves other steps. A status retrieval failure disables approvals and clears prior approval; last displayed state is labeled stale.
11. After all steps, independently inspect every saved success condition. Select the outcome-verification checkbox and **Verify outcome and complete**. The UI displays `completed` only if the backend actually returns it. For failures, inspect the message/logs rather than repeating possibly completed actions. **Stop replay** sends a stop request and waits for actual worker state.

## Historical frontend branch verification for SO-UI-FINAL

- Initial installation: stopped only identified web Vite/esbuild blockers; `npm ci` and production build succeeded.
- Strict TypeScript check and **14 API tests** passed. Tests cover exact payloads, checked=false, explicit confirmation/start, no implicit parameter defaults/approvals, identity/contract mismatches, error lists, cancellation, ordered paused attempts, resume and stop semantics.
- Browser plugin unavailable; used temporary Playwright with installed Chrome at **1440×1000** and **390×844**. Meaningful pages rendered, no Vite overlay or JavaScript runtime errors occurred, and no horizontal overflow occurred. Draft/replay lookup and connected/error UI were exercised against the actual isolated backend.
- Isolated browser protocol fixtures verified correction clearing review approval; exact complete confirmation payload; blank runtime values; stale preflight invalidation; explicit start/click approval; navigation retention; attestation/question/outcome approvals; ambiguity correction; stale-state blocking; and stop-request semantics. These fixtures exist only in temporary QA tooling, not in application source or backend data. They do **not** prove real AI compilation or replay success.
- Ran the unchanged teammate backend from a temporary extracted copy with pinned dependencies and a separate **empty SQLite database**. Direct/proxied health and proxied OpenAPI returned 200; empty events returned 200 []; missing drafts/skills/replays/preflight/resume/stop returned genuine 404; invalid confirmation/start returned genuine 422. The local UI origin passed the proxy policy, while an untrusted origin and a direct cross-origin replay request returned 403.
- No genuine populated draft/recording or saved skill was available in this isolated database. Successful AI compile, corrected confirmation, live preflight, browser actions, pause/resume and completion against the team's real Sam replay **remain unverified**. No real dispute creation or replay approval was performed by this task.
- Production build currently reports two non-fatal Rollup warnings about misplaced `@__PURE__` comment annotations in Zod. TypeScript checks remain enabled; no warnings are suppressed.

For acceptance, connect the teammate's real backend/database, use your actual draft/skill IDs and follow the walkthrough above. Compare the outcome with the visible ShadowBank state and the API logs. A successful frontend fixture test or health response is not acceptance evidence for the team's real replay.

## Architecture / limitations

Shared accessible panels, labels, notices, JSON views and review controls live under `src/components/`. API contracts are explicit and do not infer workflow behavior. Skills and replay are separate feature modules; no bank/customer-specific automation is embedded in the frontend. There is no active-recorder endpoint or replay-list endpoint, so current recording status and execution history are not invented. Settings remain read-only. Production hosting needs its own trusted API proxy; Vite's configuration is for local dev/preview.
