# ShadowBank Lite

Fictional payment dispute workspace for the ShadowOps AI hackathon. React, TypeScript and Vite; no backend, network data requests, login or AI automation. All customer identities and records are synthetic. State lives in this tab's React memory, with no local storage. Reloading or clicking **Reset Demo Data** restores all seeds.

## Run

From the repository root in PowerShell:

```powershell
cd sandbox
npm install
npm run dev
```

Open the URL printed by Vite (normally http://127.0.0.1:5173).

For an existing checkout with a lockfile, use `npm ci` instead of `npm install` for a reproducible installation. Stop any running Vite server with Ctrl+C before reinstalling: Windows can prevent npm from replacing the running `esbuild.exe` binary.

```powershell
npm test
npm run build
npm run preview
```

## Manual workflow

1. In Inbox, select **Alex Morgan**. Read the request: customer `CUS-2041`, transaction `TXN-81001`, amount `$129.99 USD`.
2. Click **Investigate transaction**. Enter `TXN-81001` in the labeled Transaction ID field and click **Search transaction**. Search trims whitespace and accepts lowercase IDs.
3. Check the returned merchant, transaction ID, customer ID, amount and currency against the request. The deterministic validator must show **Validation passed**. Creation is disabled until you check the verification checkbox.
4. Check the box and click **Create dispute case**. Confirm success with case `DSP-1001` and the correct customer, transaction and amount. Return to Inbox; Alex's request now says **Case created**. Revisiting it shows the existing case.
5. Select **Sam Rivera** and repeat using `TXN-81002`, customer `CUS-3072`, `$48.50 USD`. Expect `DSP-1002`.
6. Select **Jordan Lee** and search `TXN-99999`. Expect **No transaction found** and no creation control. The request remains open.
7. Click **Reset Demo Data**. All three requests should return to **Needs review**, Inbox should be selected and search/verification/cases cleared.

### Negative checks and accessibility

- With Alex selected, search `TXN-81002`. You should see a validation failure; the checkbox and create button are disabled. Then search the correct ID to recover.
- Edit a searched ID: the previous result and verification immediately clear, requiring another search.
- Empty/whitespace or unknown searches cannot create a case. Empty input uses native required-field validation; whitespace produces a not-found result.
- Use Tab, Shift+Tab, Enter and Space throughout the workflow. Controls have visible focus, form labels, selection state and live result/success announcements.
- Check a narrow mobile viewport: navigation, request list and review sections stack; inputs and controls remain usable.

`src/domain.ts` contains synthetic seeds and pure deterministic validation/case creation. `npm test` covers successful cases, nonexistent and mismatched transactions, altered amounts/currencies/customers, missing verification and duplicates.

## TypeScript and editor troubleshooting

`src/vite-env.d.ts` loads Vite's client declarations, including CSS imports. The configuration enables `strict` and `noUncheckedSideEffectImports`; import errors are checked during the build.

If VS Code still reports missing React, JSX or Node types after installation, open a file in `sandbox/src`, run **TypeScript: Select TypeScript Version → Use Workspace Version**, then **TypeScript: Restart TS Server**. If the workspace version is unavailable when opening the repository root, open `sandbox` as the VS Code folder. Check the command-line diagnostics with:

```powershell
npx --no-install tsc --noEmit --pretty false
```

Use Node 22.12+ (verified with Node 22.20.0), or another version supported by Vite 7. A `spawn EPERM` from an execution sandbox indicates a blocked subprocess; it is separate from TypeScript source diagnostics.
