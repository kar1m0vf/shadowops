# Teach Mode browser recorder (SO-REC-003 / SO-REC-004)

Python Playwright launches a visible, isolated Chromium browser and observes
human interaction through browser-context instrumentation. Recording is active
in the browser it opens, not in your regular Chrome windows. No recording code
is added to the website's source.

This records demonstrations only. It does not learn a skill, compile a workflow,
run AI, or replay actions.

## 1. Install in Windows PowerShell

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

Expect branch `feat/recorder` and Python `3.11.x`. Virtual environment creation
is usually silent. Pip prints `Successfully installed ...` or
`Requirement already satisfied ...`. Playwright downloads Chromium and prints
its installation location inside `.venv`. No environment activation is needed.
The recorder defaults `PLAYWRIGHT_BROWSERS_PATH` to `0`, so later terminals find
the browser inside the same virtual environment.

## 2. Start the backend in its own PowerShell window

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
$env:SHADOWOPS_ENV = 'development'
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Expect `Uvicorn running on http://127.0.0.1:8000` and
`Application startup complete.` Keep this window open.

## 3. Start the existing ShadowBank app in another PowerShell window

Use the existing sandbox lockfile to install its dependencies once, then start
its existing development server (skip `npm ci` if dependencies are installed):

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\sandbox'
npm ci
npm run dev -- --port 5173 --strictPort
```

Expect `http://127.0.0.1:5173/` in Vite's output. `--strictPort` prevents Vite from
silently moving to a port the recorder has not been configured to allow.
Keep this window open. No sandbox source changes are required.

## 4. Start recording in a third PowerShell window

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
.\.venv\Scripts\python.exe -m recorder
```

Chromium opens <http://127.0.0.1:5173>. The terminal prints:

```text
Session ID: teach-<unique UUID>
Teach Mode is recording. Return to this terminal and press ENTER to stop.
Field values are OFF unless explicitly allowlisted.
```

Use this Chromium window to demonstrate interactions. Button and link clicks,
completed text changes, native dropdown selections, checkbox/radio changes,
and initial/full-page/history navigation are recorded. Typing does not generate
an event for every character. Text changes are committed on blur, submission,
navigation where possible, or a normal stop.

React can create or replace controls without reinstalling the recorder. Document
event delegation handles new controls; the init script is reapplied after full
navigation. History changes are observed without changing the site's source.

## 5. Stop recording

Return to the recorder terminal and press **Enter**. This flushes the active edit
and queued events, closes Chromium, and prints:

```text
Session ID: teach-<same UUID>
Confirmed saved events: <number>
```

An API delivery failure stops recording and prints an error and the number of
events not confirmed saved. The program exits with a nonzero status. Events are
sent one at a time in captured order. It does not automatically retry a failed
POST, because the API has no idempotency key and a retry could duplicate an event.

Use Enter for a graceful stop. Ctrl+C or closing Chromium can interrupt a pending
edit/navigation; events already committed in SQLite remain available.

## 6. Retrieve the recorded session

The session ID is printed at start and stop, and is also saved in
`backend/data/last_session.txt`. With the backend still running:

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\backend'
$sessionId = (Get-Content .\data\last_session.txt -Raw).Trim()
$sessionId
$response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/api/events/$sessionId"
$json = [System.Text.Encoding]::UTF8.GetString($response.RawContentStream.ToArray())
$events = $json | ConvertFrom-Json
$events | ConvertTo-Json -Depth 8
```

The API returns a JSON array ordered by increasing recording ID. Events contain the
session ID, UTC timestamp, sanitized page URL, action, and target metadata.
The explicit UTF-8 decoding avoids Windows PowerShell 5.1 misinterpreting
non-ASCII JSON when the response has no charset parameter. PowerShell may unwrap
a one-element array when formatting it; the API itself still returns an array.
To see a shorter readable summary:

```powershell
$events | Select-Object id, action, value, checked, @{Name='label'; Expression={$_.target.label}}
```

For an older session, set `$sessionId = 'teach-UUID-FROM-THAT-SESSION'` instead.

## Local origins and privacy

`backend/recorder_config.json` explicitly configures the start URL, local API,
allowed browser origins, and optional value allowlist. The supplied policy is:

```json
{
  "start_url": "http://127.0.0.1:5173",
  "api_url": "http://127.0.0.1:8000",
  "allowed_origins": ["http://127.0.0.1:5173"],
  "value_allowlist": [
    {
      "origin": "http://127.0.0.1:5173",
      "selector": "#transaction-id",
      "synthetic_identifier": true
    }
  ]
}
```

An allowed origin permits paths on that origin. `localhost` and `127.0.0.1`
are distinct: add the exact origin you need. Configured hosts must be explicit
loopback hosts; wildcards, remote hosts and URL credentials are rejected. HTTP(S)
requests and WebSockets to other origins are blocked. Service workers are blocked
so they cannot bypass request routing. External resources may consequently fail
to load; use self-contained local test sites.

Only the explicit synthetic Transaction ID field is permitted by the supplied
configuration, on exactly `http://127.0.0.1:5173`. The implementation does not
contain bank-specific selectors or workflows. Other field values are omitted.
An empty value allowlist still omits **all text/selection values**. Password, hidden, file,
email, telephone, authentication/token controls, and login forms are excluded.
Other controls may still produce metadata-only change events. The recorder never
reads cookies, storage, request bodies, screenshots, or input values to construct
labels/locators. URL queries and fragments are stripped, and obvious secret-like
path segments and metadata are redacted.

For a different local site with a known, synthetic, non-sensitive field, an
explicit rule can look like:

```json
"value_allowlist": [
  {"origin": "http://127.0.0.1:5173", "selector": "#demo-note"}
]
```

This is an example for a field on another test site, not a ShadowBank selector.
Use narrow selectors. `synthetic_identifier` defaults to false. Setting it to true
permits metadata describing a transaction identifier, but only values matching
a short letter-prefixed identifier (letters, digits, hyphens and underscores;
up to 64 characters), or the empty string when clearing a field. It never overrides
password, hidden, token/authentication, card, account, customer, email, phone,
address, payment amount or other hard privacy checks. Sensitive field/type/autocomplete
hints and credential/PII value patterns still override the allowlist. Do not allowlist real financial,
identity, authentication, or arbitrary real-user free-text fields. Use synthetic
test data only: heuristic redaction cannot identify every possible private string
embedded in a site's labels, URL paths, or an explicitly permitted field.

Native non-sensitive checkbox/radio change events carry a separate JSON boolean:
`"checked": true` or `"checked": false`. This describes UI state and does not read
or copy the input's text `value` attribute. It does not require a text-value
allowlist entry. Sensitive/authentication controls remain excluded. Radio events
describe the interacted control; the browser implicitly unchecks its group peer,
without inventing another human interaction event for that peer.

Target metadata includes HTML tag, explicit or common inferred role, associated
label/ARIA name, placeholder, and locator candidates using role/name, label,
placeholder, test ID or unique stable-looking CSS attributes. It also records
the nearest named/stably identified form, region, group or navigation context.
Role/name candidates have a current DOM `match_count`; unique CSS candidates
have `match_count: 1`. If a container has a stable selector and only one control
of the target tag, a scoped CSS candidate can distinguish repeated buttons.
No coordinates,
field values, or positional DOM indexes are used to build locators. Candidates
are hints; some may be ambiguous and no replay is implemented. Two buttons with
the same name in the same context and no stable identifiers remain ambiguous:
their role candidate will show multiple matches, rather than an invented positional
locator. Names containing live counts or other dynamic text may also change later.

## Label and encoding investigation

The earlier `Investigate transaction` label was stored correctly in SQLite as
`Investigate transaction \u2192`, with a Unicode arrow. Windows PowerShell 5.1's
`.Content` decoding reproduced the malformed display; decoding raw response bytes
as UTF-8 (above) fixes the display without rewriting older recordings.

There was also an accessible-name mismatch: the observer used `textContent`,
which included a decorative `<span aria-hidden="true">` arrow. Name extraction
now excludes hidden decorations, preserves Unicode, and prioritizes
`aria-labelledby` before `aria-label`. The new name is exactly
`Investigate transaction`, matching Chromium's accessible snapshot. This is a
best-effort implementation of common DOM name rules, not a complete accessibility
tree algorithm. No sandbox source changes were needed.

Old stored events are not migrated. Optional `checked`, target `context` and
locator `match_count` fields are omitted when absent. An earlier stored
`"value": "true"` remains a string; new checkbox recordings use `checked` booleans.

To use another explicitly configured local site:

```powershell
.\.venv\Scripts\python.exe -m recorder --config .\my_local_config.json
```

## Run tests

From `backend` after Chromium installation:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected summary: `28 passed, 1 warning`, with elapsed time varying. The existing
Starlette/httpx deprecation warning does not fail tests. Tests start isolated local
web/API servers and temporary SQLite databases; browser tests use real Chromium,
not mocked DOM events or mocked API recording. They exercise real typing, mouse
clicks, keyboard dropdown selections, Enter submission, SPA controls/history,
full navigation, stop flushing, event order, disallowed origins and sensitive
value exclusion. Additional checks cover synthetic identifier allowlists and
exact origins, cleared values, boolean checkbox/radio state, hidden decorations,
Unicode, repeated-button context/ambiguity, and legacy stored-event compatibility.
The original 7 API tests remain included.

To watch the browser tests:

```powershell
$env:SHADOWOPS_TEST_HEADED = '1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:SHADOWOPS_TEST_HEADED
```

## Known limitations

- Top-level DOM controls only; iframes, canvas, contenteditable editors, closed
  shadow roots and custom dropdown widgets are not fully supported.
- SPA view changes without URL changes appear as interaction events, not inferred
  navigation. Query/fragment routing details are intentionally absent from URLs.
- No screenshot/audio capture, scrolling, drag-and-drop, replay, authentication,
  AI learning, offline buffering, retries or cross-tab causal ordering.
- Force-closing a document can lose its last unfinished edit. Start recording in
  a fresh recorder browser; existing Chrome sessions are not attached.
- Locators and common implicit roles are best-effort DOM semantics, not a full
  accessibility-tree implementation. Broad text labels can be omitted by privacy
  checks; use synthetic local demonstrations.

Implementation reference: [Playwright browser-context init scripts and bindings](https://playwright.dev/python/docs/api/class-browsercontext),
which support instrumentation across navigations without editing website source.
