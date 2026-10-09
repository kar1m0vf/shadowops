# Local browser replay (SO-EXEC-006)

The executor runs **confirmed** skills in visible Chromium. It uses the existing
six `SkillStep` actions and recorded semantic locators, with no LLM calls, generated
code, hidden example-value fallback or changes to the compiler/recorder API.

Run everything on `feat/replay`. No new dependencies were added.

## Install and run (Windows PowerShell)

Terminal 1, backend:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
.\.venv\Scripts\python.exe -m playwright install chromium
$env:SHADOWOPS_ENV = 'development'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Skip creating/installing the environment if it already exists. No activation or
PowerShell execution-policy change is needed. Stop an older backend with Ctrl+C
in its own terminal before starting another on port 8000. Use one worker and no
`--reload` during a replay; a backend restart loses the live browser and marks an
unfinished replay failed rather than repeating possibly completed actions.

Expected: `Application startup complete`, `Uvicorn running on
http://127.0.0.1:8000`. Swagger: http://127.0.0.1:8000/docs.

Terminal 2, local demo (no source changes):

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\sandbox'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Use the already running demo if port 5173 is occupied. Its expected URL is
`http://127.0.0.1:5173/`. The browser must use that exact origin; `localhost` is
a different origin. The origin/value allowlist is the existing
`backend/recorder_config.json`. Passwords, hidden fields, auth/token inputs and
sensitive values remain forbidden even if a field is allowlisted.

Terminal 3, tests:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
.\.venv\Scripts\python.exe -m pytest -q
```

Tests launch real headless Chromium on an isolated generic HTML fixture and
temporary SQLite databases. Test skill/confirmation data is explicitly test-only;
this does not establish a real ShadowBank acceptance replay or AI learning.

## Inspect and review the actual Qwen draft

Terminal 3:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
$api = 'http://127.0.0.1:8000'
$draftId = 'draft-76800ab1-b73d-410f-a7fe-01e66d7ecc2a'
$draft = Invoke-RestMethod "$api/api/skill-drafts/$draftId"
$draft.skill | ConvertTo-Json -Depth 40
$draft.skill.steps | Select-Object action,source_event_id,description,checked,value | Format-Table -Wrap
New-Item -ItemType Directory -Force .\data | Out-Null
$reviewFile = Join-Path (Get-Location) 'data\reviewed-skill.json'
$draft.skill | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $reviewFile -Encoding UTF8
notepad.exe $reviewFile
```

This exports a review file; **it does not confirm anything**. Inspect all steps,
locators, variables, uncertainties and success conditions. Event **31** / step
**6** says "Uncheck ... to confirm ...", which is a semantic error. A suggested
human correction is: `Uncheck the verification checkbox; this clears the
attestation and does not confirm verification.` Make that edit yourself if you
agree. Preserve `checked: false`, target metadata, IDs and the recorded
`true -> false -> true` sequence. Do not silently turn Alex's example into a
future default. Save the file. The raw events and original pending draft are
immutable through this workflow.

**Only after you have reviewed and approved the complete file**, confirm it:

```powershell
$reviewed = Get-Content -LiteralPath $reviewFile -Raw -Encoding UTF8 | ConvertFrom-Json
$confirmJson = @{ confirmed = $true; skill = $reviewed } | ConvertTo-Json -Depth 40
$saved = Invoke-RestMethod -Method Post "$api/api/skill-drafts/$draftId/confirm" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($confirmJson))
$skillId = $saved.id
$skillId
Invoke-RestMethod "$api/api/skills/$skillId" | ConvertTo-Json -Depth 40
```

Expected: `skill-<uuid>` with `status: confirmed`. A second confirmation of the
same draft returns 409; reuse the saved ID. The original draft still shows
`pending_review` because it remains the original model proposal.

## New parameters and read-only preflight

The demonstration begins with Alex already selected. That selection was **not**
recorded. Changing only `transaction_id` cannot select Sam. `context_selection`
is an explicit human-supplied setup click after the first navigation, logged as
step **0**, separate from demonstration steps. The generic executor has no
customer names, IDs or bank workflow embedded in it.

Create the new request:

```powershell
$request = @{
    skill_id = $draftId
    parameters = @{ transaction_id = 'TXN-81002' }
    context_selection = @{ selector = '.request-item'; text = 'Sam Rivera' }
    step_contexts = @{}
    approved_steps = @()
}
$preflightJson = $request | ConvertTo-Json -Depth 40
$report = Invoke-RestMethod -Method Post "$api/api/replays/preflight" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($preflightJson))
$report | ConvertTo-Json -Depth 40
```

For the **pending draft** expect `confirmed: false`, `ready: false`,
`can_start: false`, a human-review error, the resolved new value `TXN-81002` and
the checkbox-description warning. This preview does not launch a browser or
perform clicks. It never makes an unconfirmed draft executable.

After human confirmation, replace the ID and repeat preflight:

```powershell
$request.skill_id = $skillId
$preflightJson = $request | ConvertTo-Json -Depth 40
$report = Invoke-RestMethod -Method Post "$api/api/replays/preflight" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($preflightJson))
$report | ConvertTo-Json -Depth 40
```

Expected `ready: true`, `can_start: true`, no errors. Structural readiness is
not evidence of live uniqueness or a successful business outcome. Click approval
and checkbox verification are still enforced in the live browser.

## Start an explicitly approved real replay

**Do not run this block until you approve the state-changing replay.** The
unchanged nine-step skill has clicks at steps **2, 4, 8, 9**. Step **8** creates
a dispute. Step **0** selects the requested context. Approval is intentionally
conservative: every click requires explicit approval, including setup/navigation
buttons, because a generic engine cannot know whether a button changes state.

Approve steps 0, 2, 4 and 9 first; **leave step 8 unapproved** to inspect the
visible verified data before creating a case:

```powershell
$request.approved_steps = @(0, 2, 4, 9)
$start = @{
    skill_id = $request.skill_id
    parameters = $request.parameters
    context_selection = $request.context_selection
    step_contexts = $request.step_contexts
    approved_steps = $request.approved_steps
    approved = $true
}
$startJson = $start | ConvertTo-Json -Depth 40
$run = Invoke-RestMethod -Method Post "$api/api/replays" -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($startJson))
$replayId = $run.id
$replayId
```

Expected: HTTP 202, `replay-<uuid>`, then visible Chromium. Inspect status/logs:

```powershell
Invoke-RestMethod "$api/api/replays/$replayId" | ConvertTo-Json -Depth 40
Invoke-RestMethod "$api/api/replays/$replayId/steps" | Format-Table step,action,status,detail -Wrap
```

For this exact skill, the engine should pause before step **8** until you approve
it. The isolated ShadowBank adapter compares the **visible** selected-request and
transaction ID, customer ID, amount and currency before each checked=true step.
It also checks the application's visible validation message, and respects
disabled controls. It never reads seeded React data or bypasses app validation.
An unsupported or changed DOM/currency causes a human-verification pause.

After inspecting the correct request and payment, **explicitly approve creating
the dispute**:

```powershell
$approvalJson = @{ approved_steps = @(8) } | ConvertTo-Json
Invoke-RestMethod -Method Post "$api/api/replays/$replayId/resume" -ContentType 'application/json' -Body $approvalJson
```

After the final action, the browser stays open for final review. The adapter logs
a verified confirmation/case ID if it actually sees matching visible data.
Every saved success condition still requires human review, so the final status
is `paused`, at step **10** for this nine-step skill, until you independently
inspect the result and confirm that all success conditions are satisfied:

```powershell
Invoke-RestMethod "$api/api/replays/$replayId/steps" | Format-Table step,action,status,detail -Wrap
$outcomeJson = @{ outcome_verified = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post "$api/api/replays/$replayId/resume" -ContentType 'application/json' -Body $outcomeJson
Invoke-RestMethod "$api/api/replays/$replayId" | ConvertTo-Json -Depth 40
```

Only then expect `status: completed`, `outcome_verified: true`, successful step
logs and a closed browser. Clicking alone never produces `completed`.

## Other pauses, errors and stopping

Missing required variables pause at step 0 **before a browser opens**, even if
the skill includes an example/default. Supply an explicit new value:

```powershell
$resumeJson = @{ parameters = @{ transaction_id = 'TXN-81002' } } | ConvertTo-Json
Invoke-RestMethod -Method Post "$api/api/replays/$replayId/resume" -ContentType 'application/json' -Body $resumeJson
```

Parameters cannot change once browser execution starts. Stop and start a new
replay instead. For ambiguous targets, `step_contexts` narrows a target to a
**unique** container using simple CSS plus optional literal visible text; for
example, for an actual paused step 2 with repeated controls:

```powershell
$contextJson = @{ step_contexts = @{ '2' = @{ selector = '.request-row'; text = 'REQ-EXAMPLE' } } } | ConvertTo-Json -Depth 10
```

Use a selector/text from the actual website, not this placeholder. Submit that
JSON to the resume endpoint. The current ShadowBank has one investigation button
for the selected request, so selecting the request explicitly is necessary;
scoping that button alone cannot change the selected customer. Recorded counts
are not trusted as current counts. Conflicting candidates also pause; the engine
does not use `first()` or positional selection to guess.

For an actual attestation pause, inspect the visible UI yourself, then send the
**current** checked=true step number as `human_verified_step`. For `ask_human`,
answer the question through `acknowledged_step` for the current step. These are
explicit human acknowledgments, not automatic model decisions:

```powershell
$state = Invoke-RestMethod "$api/api/replays/$replayId"
$verificationJson = @{ human_verified_step = $state.current_step } | ConvertTo-Json
# Submit only after personally verifying the attestation's details:
Invoke-RestMethod -Method Post "$api/api/replays/$replayId/resume" -ContentType 'application/json' -Body $verificationJson
```

Stop a live replay:

```powershell
Invoke-RestMethod -Method Post "$api/api/replays/$replayId/stop"
```

The worker closes Chromium and marks the run `failed` with a stop reason.
Missing elements, action/assertion failures and unexpected browser errors stop
execution and are logged. No potentially completed action is retried after an
error. Paused actions have not been performed; only that step is retried after
explicit human input. Pauses expire after 15 minutes. Statuses are `pending`,
`running`, `paused`, `failed`, `completed`; logs preserve attempts in order.

## API and limits

| Endpoint | Purpose |
| --- | --- |
| `POST /api/replays/preflight` | Read-only confirmed-skill validation or explicitly non-executable pending-draft preview |
| `POST /api/replays` | Start a confirmed, explicitly approved replay |
| `GET /api/replays/{id}` | Durable status, sanitized inputs, approvals, context and results |
| `GET /api/replays/{id}/steps` | Ordered step attempt logs |
| `POST /api/replays/{id}/resume` | Explicit input, scope, approval, attestation or outcome response |
| `POST /api/replays/{id}/stop` | Close the live run safely |

Replay endpoints reject remote clients, non-loopback Host values and cross-origin
browser requests. Run Uvicorn on `127.0.0.1`, never `0.0.0.0`. Only explicitly
allowlisted local origins are requested, external resources and all HTTP
redirects are blocked, service workers/downloads/popups are disabled and dialogs
are dismissed. Use trusted synthetic local apps; this is not a public automation
service and has no authentication for other local users.

One live replay per backend process, one top-level page, no iframe workflows,
branching, scrolling-by-coordinates, generated JS/code, cloud browser, credentials
or secret fields. CSS support is deliberately limited to simple stable selectors;
invalid/positional/custom-engine selectors are rejected. Native dropdown values
use `select_option`, text fields use `fill`, and final values/states are checked.
SPA updates are awaited through live locators and Playwright actionability.
An assertion can establish visibility only; arbitrary prose success conditions
require final human verification. Closing the browser or restarting the backend
cannot preserve app state; failed runs are never automatically resumed/replayed.

The isolated ShadowBank verifier supports this demo's visible USD format and DOM
at exact origin `http://127.0.0.1:5173`; other formats/sites require human checks
or their own verifier. It supplies no steps or customer/transaction parameters.
The real pending draft has not been automatically corrected/confirmed, and a
real Sam dispute replay must be separately approved and observed before claiming
acceptance success.

References: [Playwright locators](https://playwright.dev/python/docs/locators),
[actionability](https://playwright.dev/python/docs/actionability).
