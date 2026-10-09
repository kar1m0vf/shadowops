# ShadowOps Control Center

React + TypeScript + Vite frontend for the ShadowOps hackathon. Responsive plum (#6D28D9), lavender (#C4B5FD) and off-white (#FAF7FF) UI with Lucide icons, shared components and CSS tokens. No AI implementation, sample recordings, production mock transport, API secrets or fabricated execution results.

## Run in Windows PowerShell

Use Node 22.12+ (tested with Node 22.20.0) and npm. From the repository root:

```powershell
Set-Location C:\Users\user\shadowops\shadowops\web
npm ci
npm run dev
```

In another PowerShell window:

```powershell
Start-Process 'http://127.0.0.1:5174'
```

Vite always uses **5174** with `strictPort`; it fails instead of taking ShadowBank's **5173**. Both `/api` and `/health` are proxied to `http://localhost:8000`. Preview uses the same proxy and port. There is no need to change backend CORS for local proxied requests.

With your teammate's FastAPI running on port 8000, verify both direct and proxied access:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/health' | ConvertTo-Json -Compress
Invoke-RestMethod 'http://127.0.0.1:5174/health' | ConvertTo-Json -Compress

$recordingSession = Read-Host 'Enter your actual recorder session ID'
$encodedSession = [Uri]::EscapeDataString($recordingSession.Trim())
Invoke-RestMethod "http://127.0.0.1:5174/api/events/$encodedSession" | ConvertTo-Json -Depth 10
```

Health should return `{"status":"ok","service":"shadowops-backend"}`. If FastAPI is stopped, the proxy returns a server error and the app reports **Backend unavailable**. The status is a health check, not proof that recording or compilation is active. It refreshes every 30 seconds or via the refresh control.

```powershell
npm run typecheck
npm test
npm run build
npm run preview
```

Stop the dev server with Ctrl+C before running preview on the same port. A static production deployment needs its own reverse proxy for `/api` and `/health`; Vite's proxy is for dev/preview only.

## Screens and real contracts

| Screen         | Behavior                                                                                                                                                                                                      |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Overview       | Health status; last successfully loaded API response with session ID, event count, first/last event and fetch time. Current recording session is **Not available** because no active-session endpoint exists. |
| Teach Mode     | Instructions for using the teammate's Python recorder and opening ShadowBank. No Start Recording button. The recorder script/launch contract is absent here; get the verified command from its owner.         |
| Recordings     | User supplies an ID; `GET /api/events/{session_id}` returns an array. Timeline sorts by timestamp, then ID. Loading, invalid ID, server error and empty-array states are explicit.                            |
| Skills         | Real `POST /api/skills/compile` with exactly `session_id` and `task_description`. Shows the original returned JSON or server error; does not execute anything.                                                |
| Agent Activity | Empty state marked coming soon; no claimed executions.                                                                                                                                                        |
| Settings       | Read-only connection details; preference editing is disabled and marked coming soon.                                                                                                                          |

The existing event model is `{ id, session_id, timestamp, url, action, target: { tag, role, label, selector } }`. Target fields may be null. Role, label and selector provide locator information. Raw JSON is available per event; URL strings are displayed as text rather than executed or opened automatically.

The current backend rejects extra event fields and does **not** store input values or checkbox state. The viewer shows **Not supplied** for missing data. If a future backend actually returns `value`/`input_value`, boolean `checked`, or `semantic_locator` on an event or target, the viewer can display them, including empty input strings and false checked state. These are provisional read-only extensions, not a confirmed recorder contract; raw JSON retains other metadata. No values or locator success are inferred from the action name.

Unknown session IDs currently return `200 []`. The UI explains that an unknown session and a session without events cannot be distinguished. IDs must be nonempty, at most 128 characters and safe as a single URL path segment. Requests are URL-encoded. Server validation errors retain their detail; network, timeout, non-JSON and malformed-contract errors are shown without inventing results.

### Compiler integration pending

The local backend has none of these compiler routes yet:

| Endpoint                                    | Frontend readiness                                                                              |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `POST /api/skills/compile`                  | Connected form; actual local response is HTTP 404.                                              |
| `GET /api/skill-drafts/{draft_id}`          | API function prepared with `unknown` response until schema is provided; no draft lookup UI yet. |
| `POST /api/skill-drafts/{draft_id}/confirm` | Disabled UI; no request function or payload guessed.                                            |
| `GET /api/skills/{skill_id}`                | API function prepared with `unknown` response; skill browsing pending.                          |

The compiler response is displayed without treating an assumed property as a draft, skill or success state. Confirmation needs the teammate's real body schema and approval semantics. Replay has no endpoint integration yet.

## Verification performed

- Dependencies installed; strict TypeScript check and production build passed.
- Five API unit tests passed: session validation, event ordering/contract checks, server errors/non-JSON health, exact compile payload, and empty retrieval. Tests use isolated fixtures; the application does not.
- Ran the **unchanged** FastAPI code with its pinned dependencies using an isolated SQLite database under `web/.qa/`. Verified direct/proxied health `200`, unknown-session retrieval `200 []`, and real compilation `404 {"detail":"Not Found"}`.
- Playwright/Chrome verified connected and unavailable states, actual empty retrieval and actual compile errors. Browser plugin was unavailable. Desktop 1440×1000 and mobile 390×844 were inspected; no horizontal overflow or JavaScript runtime errors occurred.
- Separate browser fixtures verified populated chronological timelines, optional input/checkbox/locator display, loading, compile payload, and raw response rendering. These checks do **not** establish recorder or successful compiler integration. Expected HTTP errors occur in negative tests.
- No populated Python-recorder session, compiled draft, confirmation or replay was available for genuine end-to-end verification. Those integrations remain pending. Temporary QA tooling/storage was removed after testing.

## Manual integration check

1. Start FastAPI and this frontend. Confirm **Backend connected**; refresh checks `/health`.
2. In **Recordings**, enter a real Python-recorder ID and click **Load recording**. Compare the count, timeline, target metadata and raw events with the API response.
3. Try an ID with a slash: a clear local validation error should appear. Try an unknown ID: expect **No events returned**, not a successful demonstration.
4. In **Skills**, enter a session and task, then click **Compile skill**. With the current backend, expect **Not Found (HTTP 404)**. With the compiler branch connected, compare the displayed JSON to its actual response; do not confirm a draft until its contract is integrated.
5. Stop FastAPI and refresh the connection. Expect **Backend unavailable** and actionable errors on retrieval/compile attempts.

## Architecture

`src/api/client.ts` owns typed API calls, timeouts, runtime response validation and chronological sorting. `src/hooks/useBackend.ts` handles cancellable health polling. `src/components/ui.tsx` provides shared panels, status/error/empty states and JSON display. Feature pages live in `src/pages/`; `App.tsx` holds navigation and the last real responses. State stays in memory and clears on reload. Replay can be added as a feature module when its real contract is ready.

