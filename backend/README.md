# ShadowOps backend

A minimal Python 3.11 FastAPI API that records generic browser interaction events
in SQLite. The Skill Compiler uses a configured real local or cloud LLM to propose workflow
drafts for human review. It does not execute workflows or replay browser actions.

See [compiler/README.md](compiler/README.md) to configure inference, compile an
existing recording, review it, and save a confirmed skill using Swagger or PowerShell.

## Set up in Windows PowerShell

Run these commands from a PowerShell window:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo'
git branch --show-current
Set-Location .\backend
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

The branch for the recorder task must be `feat/recorder`. `python --version` must report `Python 3.11.x`
(this machine has Python 3.11.9). Creating the virtual environment usually produces
no output. Installation ends with `Successfully installed ...` or reports
`Requirement already satisfied ...` if the packages are installed already.

These commands use the virtual environment's Python directly, so no activation
or PowerShell execution-policy change is needed.

## Launch locally

From the `backend` folder:

```powershell
$env:SHADOWOPS_ENV = 'development'
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Expect log lines containing:

```text
Uvicorn running on http://127.0.0.1:8000
Application startup complete.
```

Keep this window open. Press Ctrl+C to stop the server. The API documentation is
at <http://127.0.0.1:8000/docs>; you can use **Try it out** there.

SQLite creates `backend/data/events.sqlite3` automatically on startup. Events
remain after a server restart. There is no separate database service to install.

CORS allows exactly `http://localhost:5173` only when `SHADOWOPS_ENV` is
`development`. If the variable is unset or has another value, CORS is disabled.
To disable it in the same PowerShell window, stop the server, run
`Remove-Item Env:SHADOWOPS_ENV -ErrorAction SilentlyContinue`, and restart the server.

## Check the API

In a second PowerShell window, with the server running:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' | ConvertTo-Json -Compress
```

Expected output:

```json
{"status":"ok","service":"shadowops-backend"}
```

Record an event:

```powershell
$event = @{
    session_id = 'demo-session'
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    url = 'https://example.com/settings'
    action = 'click'
    target = @{
        tag = 'button'
        role = 'button'
        label = 'Save'
        selector = '#save'
    }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/events' -ContentType 'application/json' -Body $event | ConvertTo-Json -Depth 3
(Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/events/demo-session').Content
```

The POST returns HTTP **201** and the recorded event with a numeric `id`.
The GET returns HTTP **200** and an array of that session's events, ordered by
recording ID, rather than by timestamp. An unknown session returns `[]`.

`session_id`, `timestamp`, `url`, `action`, and the `target` object are required.
The timestamp must include a timezone, such as `2026-10-09T12:00:00Z`.
`session_id` and `action` must be nonempty strings of at most 128 characters;
`url` must be a nonempty string of at most 4096 characters. URL strings also support
browser-internal pages such as `about:blank`.
Within `target`, `tag`, `role`, `label`, and `selector` are optional strings or null.
Their maximum lengths are 64, 128, 1024, and 4096 characters, respectively.
Unknown fields are rejected to catch misspelled input names.

Invalid input returns HTTP **422** with a JSON `detail` list identifying the
invalid fields. A SQLite failure during a request returns HTTP **503** with
`{"detail":"Event storage is temporarily unavailable. Try again."}`.

## Run tests

Use a second PowerShell window; the server does not need to be running:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
.\.venv\Scripts\python.exe -m pytest -q
```

Expected output ends with `109 passed, 1 warning` (the elapsed time varies). Install
Chromium using the Teach Mode instructions below before running all tests. The
installed Starlette test client emits a deprecation warning about `httpx`;
it does not cause a test failure. Tests cover health,
recording order, session isolation, persistence, validation, local development
CORS, and storage errors. They use temporary SQLite files under `.pytest-tmp/`,
so the development database is not used. Compiler tests use explicitly marked
test-only LLM responses; they do not prove real inference or real learning.

The backend's `.gitignore` excludes virtual environments, Python/test caches,
SQLite files, `.env` files, and common secret files. No commit is created by these
setup commands.

## Teach Mode browser recorder

See [recorder/README.md](recorder/README.md) for Chromium installation, starting
and stopping Teach Mode, inspecting a session, the value allowlist, and limitations.
The recorder sends events to the same `/api/events` API and SQLite database.
Optional target placeholder, locator candidates, surrounding `context`, locator
`match_count`, and event `value`/boolean `checked` fields extend the schema.
Older payloads and stored events remain compatible;
the new fields are omitted when absent. The existing endpoints are unchanged.

Reference documentation: [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/),
[FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), and
[Python 3.11 SQLite](https://docs.python.org/3.11/library/sqlite3.html).
