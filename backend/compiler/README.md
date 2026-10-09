# Real AI Skill Compiler — SO-AI-005

The compiler sends an existing demonstration and your task description to your
configured local Ollama or cloud model. The result is a **draft**, not an executed or proven skill.
It is validated before storage and requires explicit human review before saving
as a confirmed skill. No frontend, browser replay, or model fallback is included.

## Install (Windows PowerShell)

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo'
git branch --show-current
Set-Location .\backend
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
.\.venv\Scripts\python.exe -m playwright install chromium
```

Expect `feat/recorder` and `Python 3.11.x`. Installation ends with `Successfully
installed ...` or `Requirement already satisfied ...`. Chromium is needed for
the existing recorder tests, not for compiling stored events. No activation or
execution-policy change is necessary.

## Configure your cloud model

For this machine's installed `qwen3-vl:4b`, use the **local Ollama** instructions
below. `SHADOWOPS_LLM_PROVIDER=openai` selects the cloud-compatible provider;
`SHADOWOPS_LLM_PROVIDER=ollama` selects local structured output handling.

Use a provider with HTTPS, Bearer API-key authentication, and OpenAI-compatible
`POST /chat/completions` supporting `response_format: {"type":"json_object"}`.
Enter the API base URL **including its version path**, usually `/v1`; do not
include `/chat/completions`. Enter the exact model ID supplied by your provider.
There is no default provider, model, or key.

In the same PowerShell window that will run the backend:

```powershell
$env:SHADOWOPS_LLM_PROVIDER = 'openai'
$env:SHADOWOPS_LLM_BASE_URL = Read-Host 'Cloud API base URL (HTTPS, including version path)'
$env:SHADOWOPS_LLM_MODEL = Read-Host 'Model ID from your provider'
$llmSecret = Read-Host 'Cloud API key' -AsSecureString
$env:SHADOWOPS_LLM_API_KEY = [System.Net.NetworkCredential]::new('', $llmSecret).Password
Remove-Variable llmSecret
$env:SHADOWOPS_ENV = 'development'
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The key is entered privately without putting it in PowerShell command history.
Expect `Uvicorn running on http://127.0.0.1:8000` and `Application startup complete`.
Keep this window open. If another backend is running, stop it with Ctrl+C first
and restart with these settings; environment variables belong to this process.

Alternatively, copy `.env.example` to **backend/.env**, then edit that local file:

```powershell
Copy-Item .\.env.example .\.env
notepad .\.env
```

Fill in the three values, save, and run the same Uvicorn command. `.env` is read
at compile time, and environment variables take precedence. Do not overwrite
an existing `.env` with the example. `.env`, databases and review files in `data/`
are ignored by Git. Never share or commit your credentials.

The task description, semantic target metadata and already recorded field values
are transmitted to this configured provider. The recorder's existing local
allowlist/privacy filtering is unchanged; compilation does not read more browser
data or infer redacted values.

## Local Ollama (SO-AI-005-FIX)

The local `.env` was configured for this task. It is ignored by Git and contains
the harmless placeholder key `ollama`, not a cloud credential. For a fresh setup,
copy `.env.ollama.example` to `.env` only if `.env` does not exist:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
if (-not (Test-Path -LiteralPath .\.env)) {
    Copy-Item .\.env.ollama.example .\.env
}
```

The configuration is:

```dotenv
SHADOWOPS_LLM_PROVIDER=ollama
SHADOWOPS_LLM_BASE_URL=http://127.0.0.1:11434/v1
SHADOWOPS_LLM_API_KEY=ollama
SHADOWOPS_LLM_MODEL=qwen3-vl:4b
```

No model name or key is hardcoded in Python. HTTP is accepted only for exactly
`127.0.0.1` or `localhost`. Remote inference requires HTTPS. Ollama mode itself
is restricted to these loopback hosts. Redirects are not followed and request
bodies cannot change the configured inference endpoint.

**The working services are left running after verification.** The following are
startup commands for a later restart, when the corresponding port is free.
They set process environment variables only, not Windows system settings.

First PowerShell window, for Ollama:

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_CONTEXT_LENGTH = '16384'
$env:OLLAMA_NUM_PARALLEL = '1'
& 'C:\Users\kar1m0vf\AppData\Local\Programs\Ollama\ollama.exe' serve
```

Expect `Listening on 127.0.0.1:11434`. The original 4,096-token context left only
102 output tokens for the compiler request and produced `finish_reason: length`.
Use 16,384 for this demonstration. Opening Ollama through its app later may
restore the app's own context setting; set its context slider to 16k if using it
instead of the command above. No installed models are removed or replaced.

Second PowerShell window, for the backend:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
$env:SHADOWOPS_ENV = 'development'
$env:SHADOWOPS_LLM_PROVIDER = 'ollama'
$env:SHADOWOPS_LLM_BASE_URL = 'http://127.0.0.1:11434/v1'
$env:SHADOWOPS_LLM_API_KEY = 'ollama'
$env:SHADOWOPS_LLM_MODEL = 'qwen3-vl:4b'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Expect `Application startup complete`. Local inference has a 300-second timeout
to allow model loading and generation. The cloud provider retains its 90-second
timeout. Actual speed varies with GPU load.

Ollama mode uses `/v1/chat/completions` with JSON Schema output, temperature zero,
and `reasoning_effort: none`. A complete JSON object returned in `message.reasoning`
or `reasoning_content` is accepted only when `content` is empty and
`finish_reason` is `stop`. This handles the observed Qwen/Ollama channel mismatch.
Prose, partial JSON, refusals and truncated answers remain errors. Cloud mode
continues to read `message.content` only.

The model's generation schema now fixes recorded IDs, target metadata and checked
states to their evidence, requires the appropriate action parameters, and asks
for input variables. The model still chooses the workflow, variable
names, explanations and uncertainties. The API's existing SkillDraft schema and
independent strict Pydantic/evidence validation are preserved. Human review can
still correct literal fill values, defaults and checkbox states. Supported events
are initially preserved, including intermediate checkbox toggles. Only unsupported
events may be omitted during generation; the reviewer can simplify the resulting
draft with explicit omissions later.

## Compile the existing recording

Open a **second** PowerShell window:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
$api = 'http://127.0.0.1:8000'
$sessionId = 'teach-ebf67b9d-591b-481e-82f6-bebb2fa6f4b3'
$events = @(Invoke-RestMethod "$api/api/events/$sessionId")
$events.Count

$compileBody = @{
    session_id = $sessionId
    task_description = 'Investigate a transaction, review its details, create a dispute case and return to the inbox.'
} | ConvertTo-Json
$draft = Invoke-RestMethod -Method Post -Uri "$api/api/skills/compile" `
    -ContentType 'application/json; charset=utf-8' `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($compileBody)) -TimeoutSec 330
$draft.id
$draft.skill | ConvertTo-Json -Depth 30
```

The session above is a pre-existing actual local nine-event recording. It includes
the input `TXN-81001` and checkbox states `true`, `false`, `true`. Raw recordings
are local and not included in Git. For a new session, get its ID from the recorder
terminal or use `(Get-Content .\data\last_session.txt -Encoding utf8).Trim()`.
Check that your chosen recording contains an input value before testing variable
extraction; earlier recordings without values cannot recover them.

On successful real inference, the POST returns HTTP **201**, an ID like `draft-...`,
`status: pending_review`, model ID, source event IDs and a strictly validated
`skill` object. Each observed step references a recorded `source_event_id`.
Steps remain in recording order. Every omitted event must have an explicit reason.
Input examples may become variables, for example `transaction_id` used as
`{{transaction_id}}`, with `source: human_input` and `requires_human_input: true`.
The exact name and grouping are proposed by the model, not hardcoded by ShadowOps.
Possible success conditions require human verification. No skill is saved yet.

Retrieve the same draft and inspect its evidence:

```powershell
$draft = Invoke-RestMethod "$api/api/skill-drafts/$($draft.id)"
$draft.skill.variables | ConvertTo-Json -Depth 10
$draft.skill.steps | ConvertTo-Json -Depth 30
$draft.skill.uncertainties
$draft.skill.omitted_events | ConvertTo-Json -Depth 10
$draft.skill.success_conditions | ConvertTo-Json -Depth 10
```

For the real acceptance check, verify that the model proposes a transaction-ID
variable whose example is `TXN-81001`; that its fill step preserves `#transaction-id`
and all locator candidates; that clicks/check states are preserved or explicitly
omitted with a meaningful reason; and that unknown variable source, checkbox
verification claims and unobserved success are clearly called out as uncertain.
A successful HTTP request alone does not prove the workflow's business correctness.

## Review and confirm

Swagger is available at <http://127.0.0.1:8000/docs>, under **Skill Compiler**.
Use `POST /api/skills/compile` and `GET /api/skill-drafts/{draft_id}` to inspect the
result. For `POST /api/skill-drafts/{draft_id}/confirm`, send:

```json
{
  "confirmed": true,
  "skill": { "...": "paste the COMPLETE corrected skill object here" }
}
```

The snippet above illustrates the envelope only; the placeholder is not a valid
skill. `confirmed` must be the JSON boolean `true`, and `skill` must contain the
entire corrected object. For PowerShell, edit a review file first:

```powershell
$reviewPath = Join-Path (Get-Location) 'data\skill-review.json'
$draft.skill | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $reviewPath -Encoding utf8
notepad $reviewPath
```

Review the steps and uncertainties in Notepad, make corrections, save and close.
You can correct names, descriptions, fill values, variable names/templates,
variable `default_value` and checkbox states. If you replace a variable template
with a literal fill value, remove the now-unused variable. Examples remain the original
evidence. Unknown sources must still require human input. Keep source IDs, target
metadata and candidate locators intact. To omit a step, include its event ID and
a reason in `omitted_events`. Proposed `assert_visible` checks can only use
previously recorded targets and must include uncertainty. `ask_human` can request
clarification without pretending the request was observed.

Only after inspecting and correcting the file, run:

```powershell
$approval = Read-Host 'Type CONFIRM only after reviewing the complete skill'
if ($approval -ceq 'CONFIRM') {
    $corrected = Get-Content -LiteralPath $reviewPath -Raw -Encoding utf8 | ConvertFrom-Json
    $confirmBody = @{ confirmed = $true; skill = $corrected } | ConvertTo-Json -Depth 30
    $saved = Invoke-RestMethod -Method Post -Uri "$api/api/skill-drafts/$($draft.id)/confirm" `
        -ContentType 'application/json; charset=utf-8' `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($confirmBody))
    $saved | ConvertTo-Json -Depth 30
    Invoke-RestMethod "$api/api/skills/$($saved.id)" | ConvertTo-Json -Depth 30
}
```

Expect HTTP **201**, an ID like `skill-...` and `status: confirmed`. Confirmation
means **human reviewed**, not replayed, tested, or learned by a model. Confirmation
does not call the LLM. It stores the corrected skill in the separate `skills`
table, while retaining the original draft and its compilation-time evidence
snapshot in `skill_drafts`. Raw `events` are unchanged. A second confirmation of
the same draft returns **409**; compile again to create a new revision.

## Endpoints and errors

| Endpoint | Purpose |
| --- | --- |
| `POST /api/skills/compile` | Real inference from `session_id` and `task_description`; returns draft |
| `GET /api/skill-drafts/{draft_id}` | Retrieve original draft for inspection |
| `POST /api/skill-drafts/{draft_id}/confirm` | Confirm the complete corrected skill |
| `GET /api/skills/{skill_id}` | Retrieve the saved human-confirmed skill |

The existing `/health` and `/api/events` endpoints and stored event schema stay
compatible. SQLite creates the extra tables automatically; no migration command
is needed. A draft remains the original pending-review proposal even after its
corrected counterpart is saved as a confirmed skill.

- **404:** unknown/empty session, unknown draft or saved skill.
- **422:** invalid input or corrected skill, missing explicit confirmation.
- **413:** over 500 events or 256 KB of serialized compiler input; no truncation.
- **503:** missing settings, rejected credentials, connection/quota/storage error.
- **504:** inference timeout (90 seconds cloud / 300 seconds local Ollama).
- **502:** unsupported provider request, malformed/incomplete/refused JSON, schema
  failure, invented evidence, reordered steps or lost locators. Nothing is saved.

Provider bodies and raw model-validation inputs are not exposed in these errors.
There is no silent substitution, JSON repair, automatic retry, generated code
execution, or browser execution. Retry compilation after fixing the settings or
choose a model supporting the required compatible JSON request format. Generation
errors report failing field paths; evidence errors report the failed rule without
including raw model output or input values.

## Tests and current acceptance status

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
.\.venv\Scripts\python.exe -m pytest -q
```

The full suite covers the existing API and actual Chromium recorder, draft
validation, variable contracts, recording order, locator preservation, malformed
provider output, missing credentials, explicit human review, corrections and
separate persistent skill storage. LLM calls in automated tests are mocked and
clearly named test-only. They cannot establish real AI acceptance.

The real local acceptance test succeeded on 2026-10-09: Ollama 0.34.2 with
`qwen3-vl:4b` received the real request from FastAPI, and the compile endpoint
returned **201** after approximately 85 seconds. The saved draft is
`draft-76800ab1-b73d-410f-a7fe-01e66d7ecc2a`, with `status: pending_review`.
The original nine events (IDs 26–34), every semantic target/locator and checkbox
states `true`, `false`, `true` are preserved. Qwen proposed:

```json
{
  "name": "transaction_id",
  "source_event_id": 28,
  "example_value": "TXN-81001",
  "source": "human_input",
  "requires_human_input": true,
  "default_value": null
}
```

Its matching fill uses `{{transaction_id}}`. Qwen marked verification as requiring
human input/confirmation and marked its possible success condition as requiring
human verification. This is real inference, not an automated-test mock. No human
confirmation was submitted and no replay was performed. Raw session events were
independently compared before/after and are unchanged.

The full API response is saved locally in the ignored
`data/ollama-acceptance-draft.json`; the independent checks are in
`data/ollama-acceptance-verification.json`. Inspect and retrieve it:

```powershell
$draft = Invoke-RestMethod 'http://127.0.0.1:8000/api/skill-drafts/draft-76800ab1-b73d-410f-a7fe-01e66d7ecc2a'
$draft.skill | ConvertTo-Json -Depth 30
```

Review limitation: the model's description of the **uncheck** step calls it a
confirmation of verification. That wording needs correction. A checkbox state
does not establish whether business details were actually verified. The observed
boolean itself is correctly recorded as `false`. Structural checks cannot establish
the truth of natural-language explanations, which is why the draft remains pending review.

Optional development debugging: set `SHADOWOPS_LLM_DEBUG=1` together with
`SHADOWOPS_ENV=development` before launching the backend. Only then is the raw
model JSON written to ignored `data/last-llm-output.json` for diagnosis. Credentials
and HTTP headers are not included. Debugging was disabled on the final running backend.

## Limitations

- One demonstration can suggest variables; it cannot establish their future
  source, robust branching, business correctness, or a verified success condition.
- Evidence checks protect structured actions/values/locators, but natural-language
  descriptions and explanations still need human review.
- Locators describe the recorded DOM. Repeated controls, changed DOM and unknown
  locator counts may require review; no locator is tested against a live browser.
- Dropdown changes use a proposed `fill` with explicit uncertainty; native select
  versus text entry must be resolved before a later replay implementation.
- Assertions only reference recorded targets; the recorder captures no full DOM
  result snapshot, so it cannot prove unseen result headings or final outcomes.
- Cloud inference uses compatible HTTPS Chat Completions JSON mode. Local Ollama
  uses its compatible Chat Completions JSON Schema mode. Provider-specific cloud
  authentication or Azure-style deployment/query endpoints are not included.
- Recordings are bounded to 500 events / 256 KB. No replay, automatic confirmation,
  fine-tuning, training, Skill Compiler frontend or workflow execution is included.

Request-format reference: [OpenAI Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
Local references: [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
and [context length](https://docs.ollama.com/context-length).
