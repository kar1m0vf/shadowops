# ShadowOps integration (SO-INT-007)

Use `feat/integration`. It starts from `origin/feat/replay` (`4bc5a8a`)
and includes `origin/feat/control-center` (`aeabe33`) and `origin/feat/qa`
(`57ce5fb`). Both branches merged without conflicts. The merge is deliberately
uncommitted; `main` is unchanged. No push or deployment was performed.

## Start the existing system in Windows PowerShell

The four development services were left running. Open
<http://127.0.0.1:5174> for the Control Center. Check ports before launching:

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5173,5174,8000,11434 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess
Invoke-RestMethod 'http://127.0.0.1:8000/health' | ConvertTo-Json -Compress
Invoke-RestMethod 'http://127.0.0.1:5174/health' | ConvertTo-Json -Compress
```

Health should return `{"status":"ok","service":"shadowops-backend"}`
directly and through the Control Center proxy. Start only missing services,
each in a separate PowerShell window. Keep their windows open. Reuse existing
environments, installed dependencies and database; do not recreate/reset them.

Ollama (only if port 11434 is free):

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_CONTEXT_LENGTH = '16384'
$env:OLLAMA_NUM_PARALLEL = '1'
ollama serve
```

FastAPI (only if port 8000 is free):

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
$env:SHADOWOPS_ENV = 'development'
$env:SHADOWOPS_LLM_PROVIDER = 'ollama'
$env:SHADOWOPS_LLM_BASE_URL = 'http://127.0.0.1:11434/v1'
$env:SHADOWOPS_LLM_API_KEY = 'ollama'
$env:SHADOWOPS_LLM_MODEL = 'qwen3-vl:4b'
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

`ollama` is the local compatibility API's dummy key, not a cloud credential.
The provider also reads the existing ignored `backend/.env`; environment
variables override it. Keep actual cloud credentials out of source control.
Expected: `Application startup complete` and the Uvicorn URL. Use one worker
without `--reload` during replay. Swagger is <http://127.0.0.1:8000/docs>.

ShadowBank (only if port 5173 is free):

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\sandbox'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Control Center (only if port 5174 is free):

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\web'
npm run dev
```

Expected Vite URLs: `http://127.0.0.1:5173/` and `http://127.0.0.1:5174/`.
The Control Center proxies `/api`, `/health` and `/openapi.json` to IPv4
loopback port 8000. It needs no frontend API key or additional environment
variables. The installed Ollama model was checked via `/api/tags`.

## Reproduce the verified read-only demo

1. Open the Control Center. The header should say **Backend connected**.
2. In **Recordings**, load session
   `teach-ebf67b9d-591b-481e-82f6-bebb2fa6f4b3`. There are nine actual events,
   IDs 26–34, including recorded `TXN-81001` and boolean checked states.
3. In **Skills**, retrieve draft
   `draft-76800ab1-b73d-410f-a7fe-01e66d7ecc2a`. Inspect its nine steps,
   `transaction_id` variable, evidence and uncertainty. This is the previously
   generated real Qwen draft; confirmation is a separate human action.
4. In **Agent Activity**, load confirmed skill
   `skill-a2415f35-36b5-4d27-a86e-13cf5fe2679b`. Its reviewed event-31
   description explains unchecking; the original `checked=false` is preserved.
   Expand **Inspect the saved workflow** to inspect the confirmed version.
5. Enter runtime `transaction_id = TXN-81002`. Enable **Select a context after
   the initial navigation (step 0)**, enter selector `.request-item` and visible
   text `Sam Rivera`. Leave click approvals unchecked. Run **preflight**.
   The actual backend returns structurally ready with nine resolved steps.
   Static preflight does not prove live locator uniqueness or business success.
   Do not start a new replay during read-only inspection.
6. Load completed replay
   `replay-97072aef-1e0c-471d-a6c5-8acd0748e398` in **Execution timeline**.
   Expect `completed`, `Outcome verified: yes`, and 14 ordered attempts,
   including historical pauses and subsequent successes. This is the earlier
   human-approved replay, not a replay performed by integration testing.

The earlier dispute confirmation is preserved under
`backend/data/replay-97072aef-1e0c-471d-a6c5-8acd0748e398/`, including screenshots,
full logs and final verification evidence for DSP-1002 (Sam Rivera, CUS-3072,
TXN-81002, $48.50 USD). The API exposes saved status/logs, not a live query of
dispute state. Browser screenshot paths are backend-host files, not image URLs.
ShadowBank keeps its demo state in browser memory; closing the earlier replay
browser ended that session. No reset was performed. Present the archived
confirmation as evidence of that completed run rather than expecting a newly
opened sandbox browser to retain DSP-1002.

To start a new recording later, when a new demonstration is intended:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
.\.venv\Scripts\python.exe -m recorder
```

Record in the visible Chromium it opens. Keep the printed `Session ID`; press
Enter in that terminal to stop and flush events. No active-recorder control API
exists, so the Control Center provides the terminal command and session lookup.
Do not reset ShadowBank data or create another dispute without human approval.

## Validation and remaining limits

- Full backend suite: **152 passed, 1 existing Starlette deprecation warning**.
- Frontend: strict TypeScript check, **14 automated API tests**, production build passed.
- ShadowBank production build passed.
- Visible real Chromium at 1440×1000 and 390×844: real health, recording,
  AI draft, local draft edits, confirmed skill, missing/supplied parameter
  preflight, completed replay and all 14 logs displayed successfully. Approval
  gating and input edits invalidating preflight were checked. No unexpected
  console/runtime errors, Vite overlays or mobile horizontal overflow.
- A genuine missing-draft 404 was displayed correctly. Other API mutations
  were blocked by temporary QA tooling and none was attempted. No responses
  were mocked during this real UI check.
- Direct and proxied replay requests with an untrusted Origin both returned 403;
  the intended local Control Center Origin passed real preflight.
- SQLite was backed up before integration. All rows still match that backup:
  **34 events, 1 draft, 1 confirmed skill, 1 replay**. Secrets/databases remain ignored.
- Fixed event order (preserve API insertion order), locator candidate display,
  compiler client timeout
  (310 seconds), IPv4 proxy, stale Teach Mode instructions, and the existing
  demo verifier's selection of the confirmation status region. The verifier
  regression test uses isolated HTML and rejects duplicate confirmation regions.
- Fresh AI compilation, saving another confirmation, live replay start,
  pause/resume/stop and a new final business outcome through this frontend remain
  **unverified**. Existing automated LLM/protocol fixtures do not prove those live
  operations. They require an explicitly approved demonstration.
- Non-fatal build warnings: two Rollup annotations in dependency Zod.
  No dependencies were changed to suppress them.

The application is ready to present the verified saved-data workflow and real
preflight. A fresh full frontend Teach → Compile → Confirm → Replay run still
needs human authorization and live verification.

Integration fixes modify `backend/replay/shadowbank.py`,
`backend/tests/test_replay.py`, its verification HTML fixture, `backend/README.md`,
`web/src/api/client.ts`, its API test, `web/vite.config.ts`, `web/README.md`, and
the Recordings, Skills, System and TeachMode pages. This guide is new. The other
frontend, sandbox interface and QA plan changes are preserved branch imports.

Regression commands (separate windows are optional):

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
.\.venv\Scripts\python.exe -m pytest -q
Set-Location '..\web'
npm run typecheck
npm test
npm run build
Set-Location '..\sandbox'
npm run build
```
