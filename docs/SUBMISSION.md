# ShadowOps — Hackathon submission

**Public demo:** https://shadowops-verified-demo.vercel.app

**Repository:** https://github.com/kar1m0vf/shadowops

**Submission branch:** https://github.com/kar1m0vf/shadowops/tree/feat/integration

## Project description

ShadowOps is a learning-by-demonstration automation MVP. A human teaches a
workflow in a visible browser; ShadowOps records semantic interactions, uses a
real AI model to propose a reusable workflow, and requires human review before
controlled Playwright replay. It preserves evidence, variables, uncertainty,
step logs and explicit approvals instead of treating a generated plan or a
successful click as proof of business success.

## Demo instructions — no installation needed

1. Open the public HTTPS website. Every page is labeled
   **Archived Verified Demo — Read Only**. No login or local backend is required.
2. Open **Demonstration** to inspect the original nine recorded events, their
   semantic locators, allowed synthetic transaction value and checked states.
3. Open **AI Skill** to inspect the actual Qwen-generated draft and its
   `transaction_id` variable, recorded example `TXN-81001`, human input source,
   workflow steps and uncertainties.
4. Open **Human Review** to compare the original proposal with the confirmed
   workflow. Event 31 was corrected to explain that unchecking clears the
   attestation; its recorded `checked=false` was preserved. Approval and final
   human verification evidence are included.
5. Open **Replay & Result** to inspect the real Sam Rivera replay with runtime
   parameter `TXN-81002`, explicit customer selection, all 14 ordered execution
   attempts, pauses, approvals and the actual confirmation screenshot.
6. Open **Limitations** for scope, provenance hashes and downloadable sanitized
   evidence. Public controls for recording, compilation, confirmation and replay
   are disabled. The website displays an archived real execution, not live
   remote browser automation and not a mocked demonstration.

## Teach → Record → AI Compile → Human Review → Replay

- **Teach:** A human demonstrates in visible Chromium against a configured local
  test website, without injecting recorder code into the website source.
- **Record:** Playwright instrumentation captures meaningful completed inputs,
  clicks, selections and navigation. FastAPI validates and stores events in
  insertion order in SQLite. Sensitive values are blocked; non-sensitive values
  require an explicit origin/field allowlist.
- **AI Compile:** Real Qwen3-VL 4B through local Ollama proposes a strictly
  validated SkillDraft, preserving event evidence and locator candidates.
  Unknown variable sources require human input. Invalid responses fail safely.
- **Human Review:** A user inspects and corrects the complete draft, then
  explicitly confirms it. Confirmed skills are stored separately from recordings.
- **Replay:** The confirmed workflow runs in real visible Chromium. Preflight,
  explicit parameters, unique visible targets and approval pauses constrain
  execution. Visible facts are independently compared before attestations;
  human outcome verification is retained with the full attempt history.

## Verified outcome

The real synthetic ShadowBank replay created **DSP-1002** for **Sam Rivera**:

| Field | Verified value |
|---|---|
| Customer ID | CUS-3072 |
| Transaction | TXN-81002 |
| Amount | $48.50 |
| Currency | USD |
| Saved replay status | completed |
| Saved outcome verification | true |

Customer ID, transaction ID, amount and currency matched the request before
attestation. The engine paused before dispute creation; the user explicitly
approved the click and later confirmed the successful outcome.

- Recording: `teach-ebf67b9d-591b-481e-82f6-bebb2fa6f4b3`
- Real AI draft: `draft-76800ab1-b73d-410f-a7fe-01e66d7ecc2a`
- Confirmed skill: `skill-a2415f35-36b5-4d27-a86e-13cf5fe2679b`
- Replay: `replay-97072aef-1e0c-471d-a6c5-8acd0748e398`

## Technology stack

React 19, TypeScript, Vite, Python 3.11, FastAPI, Pydantic, SQLite, Python
Playwright/Chromium, Ollama and real Qwen3-VL 4B. The modular compiler also
supports configured OpenAI-compatible providers. Only the static frontend and
selected synthetic archive assets are deployed to Vercel; FastAPI and Ollama
remain local and are not exposed publicly.

## Validation

- **152 backend tests passed** during full integration regression testing.
- **17 frontend tests passed** for submission: the original 14 API tests plus
  three tests validating the actual archive, evidence identity/amount checks,
  human verification and sanitization.
- **42 real Chromium integration checks passed** against populated local data.
- Strict TypeScript checks and the live/archive React production builds passed.
  The ShadowBank production build passed during integration.
- **15 standalone archive browser checks passed locally** without backend calls.
- **15 public HTTPS browser checks passed**, using an unauthenticated browser at
  desktop 1440×1000 and mobile 390×844. They checked all navigation, nine events,
  14 logs, real screenshot loading, direct hash navigation, mobile overflow and
  absence of console errors, localhost API requests or periodic backend polling.
- Vercel production deployment `dpl_ESGxQ72zPyD5iNLfw73kUPvfo1qT` is READY;
  deployed application commit: `6370f51`.

Automated LLM mocks remain isolated test fixtures. The published AI draft and
successful execution come from the real recorded acceptance run.

## Security, preservation and limits

- Only nine original synthetic events, the real draft, reviewed skill, selected
  verification evidence, real logs and two inspected synthetic screenshots were
  published. Machine paths were removed. No SQLite, `.env`, API credentials,
  virtual environments, node_modules or unrelated local evidence was published.
- Original local data, screenshots and execution evidence remain intact.
  `main` was not changed. No new dispute was created for submission.
- The public demo is an archive. Live inference and browser automation require
  the local services and explicit human approvals; no remote desktop, device
  pairing or cloud executor is implemented.
- Replay supports a small action vocabulary and explicitly configured local test
  origins. Broad reliability across arbitrary websites has not been established.
- ShadowBank state lives in browser memory; closing its browser ends that session.
  The saved confirmation and logs preserve evidence of the earlier execution.
- Fresh full Teach → Compile → Confirm → Replay through the Control Center was
  not repeated during integration/submission. Real backend acceptance and real
  saved-data frontend/preflight integration were verified separately.
- Existing non-fatal warnings: Starlette test-client deprecation and Zod Rollup
  annotation warnings. They did not cause test or build failures.

## Local live mode and archive build

See [the exact local startup guide](integration.md). Existing local services
remain running on ports 5173, 5174, 8000 and 11434.

```powershell
Set-Location 'C:\Users\kar1m0vf\Desktop\shadowops-repo\web'
npm run dev        # Existing local live mode on port 5174
npm test
npm run build:demo # Standalone read-only public build in dist/
```

Vercel uses `web/` as its project directory and `web/vercel.json` builds demo
mode. No public frontend secrets or live backend URL are required.
