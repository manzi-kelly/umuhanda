# Phase 02.5 — build recovery and browser verification

Verified on 4 November 2026 (Africa/Johannesburg), in `D:\Roadrules\roadrule`.
No Phase 03 work was implemented.

## 1. Root cause findings

Environment inspected: Node.js **v24.22.1**, npm **11.19.1**, installed Next.js
**16.4.5**, React/React DOM **19.3.0**, Tailwind CSS **4.3.4**. Next.js's bundled
CLI documentation explicitly supports `next build --webpack`.

### Turbopack worker communication was denied by the restricted execution environment

The complete original failure is retained in
[turbopack-original.log](evidence/turbopack-original.log). Its key chain was:

```text
Failed to write app endpoint /page
[project]/src/app/globals.css.css [app-client] (css)
creating new process
node process exited before we could connect to it with exit code: 0
```

An opt-in Node diagnostic preload recorded the otherwise hidden socket error:

```json
{"code":"EACCES","syscall":"connect","address":"127.0.0.1"}
```

See [worker socket observations](evidence/worker-socket-errors.jsonl) and
[diagnostic build log](evidence/turbopack-probe.log). Multiple worker processes
started but could not connect to the parent's local IPC port. This is a worker
handshake permission failure, rather than a TypeScript or CSS source diagnostic.
The probe logs only PID, error code, syscall, address and port; it is never enabled
by ordinary build/test scripts.

A clean build with normal local process/socket access succeeded with the original
Turbopack configuration, before the PostCSS configuration change. A subsequent
restricted-environment retry reproduced the failure. This A/B result, together
with EACCES, identifies the execution restriction as the confirmed blocker.

### Process and cache investigation

Two existing Roadrules development processes (PIDs 6224 and 2268) were identified
by their project-specific command lines and stopped. Their commands are retained
in [stopped-project-processes.json](evidence/stopped-project-processes.json).
An unrelated application owned the service responding on port 3000 and was left
alone. The Roadrules dev registry had also advertised port 3000, making that port
an unreliable test target. All browser tests instead used `127.0.0.1:3100`.

The resolved cache deletion target was checked to equal
`D:\Roadrules\roadrule\.next` and checked not to be a reparse point before removal.
Only that generated cache was cleared. Deletion and subsequent regeneration
succeeded; no persistent filesystem write/lock failure was found. Stale dev state
and caches were cleaned, but their presence alone is not claimed as the root cause.

### Separate certificate trust issue

The first Webpack attempt could not fetch the existing Inter and Plus Jakarta
Sans fonts: `UNABLE_TO_VERIFY_LEAF_SIGNATURE`. Package installation initially
encountered the same Node certificate trust problem. Using Node 24's supported
system trust store (`NODE_USE_SYSTEM_CA=1`) resolved both. TLS certificate checking
remained enabled; no Windows security setting or certificate protection was disabled.
See [initial Webpack log](evidence/webpack-initial.log).

## 2. Files modified or created

Modified:

- `next.config.ts`: removed the Turbopack-specific Tailwind loader rule.
- `package.json` / `package-lock.json`: added Playwright 1.64.1 and matching
  Tailwind PostCSS 4.3.4; removed the superseded Tailwind Turbopack loader;
  added `build:webpack`, `test` and `test:browser` scripts.
- `.gitignore`: ignores disposable Playwright traces/results and HTML reports.
- `README.md`: documented scripts, test prerequisites, local port and environment fixes.
- `docs/phase02-report.md`: linked this subsequent verification report.

Created:

- `postcss.config.mjs`: shared official Tailwind v4 integration for both bundlers.
- `playwright.config.ts`: installed-Chrome production tests at the three widths.
- `tests/browser/phase02.spec.ts`: executed end-to-end and no-JavaScript tests.
- `tests/turbopack-worker-probe.mjs`: opt-in diagnostic socket error recorder.
- This report and the logs, JSON reports and screenshots under `docs/evidence/`.

No application source under `src/` was changed in Phase 02.5. Existing Next.js,
React, TypeScript and Tailwind versions and all student-facing features were retained.
No TypeScript/ESLint bypass was introduced. This checkout has no Git metadata;
the file inventory is based on the changes made in this verification session.

## 3. Changes and selected build strategy

Both bundlers now use the same Tailwind PostCSS configuration recommended in the
installed Next.js CSS guide. The change enables a meaningful Webpack comparison
without dropping Tailwind styles or replacing the design system. It does not
remove the need for normal worker socket access in Turbopack.

**Keep `npm run build` (Turbopack) as the default.** `npm run build:webpack` is the
supported alternative. Builds/tests requiring local sockets run outside Codex's
restricted Windows process environment through reviewed execution permission.
This does not require weakening host security settings.

For the managed machine's Node certificate chain when necessary:

```powershell
$env:NODE_USE_SYSTEM_CA = '1'
npm run build:webpack
```

The test runner launches `npm run start -- --hostname 127.0.0.1 --port 3100`, refuses
to reuse another server, and stops its own server when complete. Chrome is the
already installed browser; no separate browser binary was downloaded.

## 4. Turbopack production result

| Exact command / context | Exit | Result / evidence |
| --- | --- | --- |
| `npm run build`, original restricted run | 1 | Worker handshake failure; [full log](evidence/turbopack-original.log) |
| `npm run build`, clean cache, normal socket access, original loader config | 0 | All routes built; [clean recovery](evidence/turbopack-clean.log) |
| `npm run build`, restricted retry | 1 | Same failure; [repeat log](evidence/turbopack-repeat.log) |
| `npm run build` with opt-in diagnostic preload, restricted | 1 | EACCES confirmed; [probe log](evidence/turbopack-probe.log) |
| `npm run build`, final shared PostCSS config, normal socket access | 0 | Compiled, TypeScript checked and routes prerendered; [final log](evidence/turbopack-final.log) |

The successful final build generated `/`, `/tangira`, `/exam`, `/_not-found` and
`/icon.svg`. Restricted execution remains an environment limitation, not a claim
that builds can succeed with local IPC denied.

## 5. Webpack production result

| Exact command / context | Exit | Result / evidence |
| --- | --- | --- |
| `npm run build:webpack` | 1 | Google Fonts certificate trust failure; [initial log](evidence/webpack-initial.log) |
| `$env:NODE_USE_SYSTEM_CA = '1'; npm run build:webpack`, normal socket access | 0 | Compiled, TypeScript checked and same routes prerendered; [final log](evidence/webpack-final.log) |

Both supported bundlers succeed. Webpack's initial failure was a verified font
download trust issue, distinct from Turbopack's restricted IPC error. Neither
required removing features, fonts, checks or upgrading Next.js.

## 6. Browser verification evidence

Real headless Google Chrome (156.0.8078.80 recorded in the Webpack run) was automated through Playwright against production
output, as an alternative to the earlier unreliable desktop/browser automation.
These are executed browser tests, not source-review substitutes.

| Production output | Viewports | Tests | Evidence |
| --- | --- | --- | --- |
| Turbopack | 390×844, 834×1112, 1440×1000 | **6 passed**, 0 failed/skipped/flaky | [execution log](evidence/browser-turbopack.log), [JSON results](evidence/browser-results-turbopack.json) |
| Webpack | Same | **6 passed**, 0 failed/skipped/flaky | [execution log](evidence/browser-webpack.log), [JSON results](evidence/browser-results-webpack.json) |

At every width, the flow test executed and asserted:

1. `/` returns 200, shows the Phase 01 hero and expected theme styling.
2. Desktop header anchors work; on mobile/tablet the menu opens by keyboard,
   closes with Escape, follows the rules anchor and closes after selection.
   Header/mobile CTA navigates to `/tangira`.
3. Empty/whitespace fields, numeric names and invalid landline numbers are rejected.
   Visible associated errors appear and the first invalid input receives focus.
4. Tab/Enter advances valid student details. Names normalize whitespace;
   `0781234567` becomes `+250781234567`. Editing preserves both fields;
   `+250 (73) 123-4567` becomes `+250731234567`.
5. MTN is selectable, Airtel is selectable by radio keyboard navigation, and
   both actions show verification unavailable without a successful payment.
6. Empty/whitespace promo submission errors; an arbitrary code remains unverified.
   Its value survives switching methods. No PIN/password input exists.
7. No non-GET request occurs during the flow. No code/payment unlocks an exam.
8. Fabricated SUCCESS/accessGranted/verified/student entries in localStorage and
   sessionStorage plus forged URL parameters do not authorize `/exam`. All eight
   rules remain visible, the student-name placeholder remains unverified, and
   Start Exam stays disabled after reload. Returning to onboarding clears details.
9. Every captured page/state fits the viewport without horizontal overflow.
10. Browser console errors, uncaught page errors, failed requests and HTTP errors
    are all asserted empty and attached as `browser-observations` in each JSON report.

A second test per width directly loads `/exam` with JavaScript disabled and a
forged access parameter: HTTP 200 for the public shell, with the Start Exam button
still disabled. HTTP 200 is not an authorization claim; no exam content exists.

Seven screenshots per width cover homepage, initial student form, validation,
payment selection, Airtel unavailable, promo unavailable and locked exam. The
current [screenshot directory](evidence/browser/) contains the latest browser run.
Examples: [mobile homepage](evidence/browser/390px-home.png),
[tablet form](evidence/browser/834px-student.png),
[desktop payment](evidence/browser/1440px-payment.png),
[mobile locked exam](evidence/browser/390px-exam-locked.png).
Representative screenshots were also visually inspected for layout and typography.
Captures reset scroll to the top to avoid sticky/fixed-header artifacts in full-page images.
The [machine-readable summary](evidence/verification-summary.json) records per-width
console/network observations and suite counts.

## 7. Automated validation and security review

| Exact command | Result | Evidence |
| --- | --- | --- |
| `npm run lint` | Passed, no warnings in final run | [lint.log](evidence/lint.log) |
| `npm run typecheck` | Passed | [typecheck.log](evidence/typecheck.log) |
| `npm test` | 5 passed, 0 failed | [unit-tests.log](evidence/unit-tests.log) |
| `npm run build` | Passed with normal socket access | [turbopack-final.log](evidence/turbopack-final.log) |
| `npm run build:webpack` with system CA | Passed | [webpack-final.log](evidence/webpack-final.log) |
| `npm run test:browser` against Turbopack output | 6 passed | [browser-turbopack.log](evidence/browser-turbopack.log) |
| `npm run test:browser` against Webpack output | 6 passed | [browser-webpack.log](evidence/browser-webpack.log) |

Unit coverage includes local/international formats across Rwanda mobile ranges,
reserved/landline/foreign/malformed rejection, required names, Unicode names,
whitespace normalization, and offline payment/promo adapters returning
`VERIFICATION_UNAVAILABLE` and `accessGranted: false` without network requests.

Source review found no browser-storage/cookie authorization, student console logging,
frontend API-secret/private-key patterns or password/PIN inputs. Both adapters always
return unavailable, create no references and store no successful transactions.
The exam route reads no request/client authorization data and renders only the locked
shell. See [security source review](evidence/security-source-review.txt). Browser
state tampering and no-JavaScript cases independently exercised that boundary.
All screenshots use synthetic QA student details; no real student data was used.

No backend protection is claimed for a future exam engine: server-verified,
short-lived exam sessions remain a prerequisite for any future protected content.

## 8. Remaining blockers and limits

No application/build blocker remains in a normal permitted execution environment.
Codex restricted Windows execution still denies worker loopback connections;
building in that environment without the required execution permission will fail.
Node font downloads may require the system trust store on this managed machine.
Both constraints and their original failures are retained above.
The test runner emitted a Node `NO_COLOR`/`FORCE_COLOR` environment warning;
the browser application error arrays remained empty.

Coverage is Google Chrome at the requested viewport widths, not physical-device,
Safari or Firefox certification. Current payment/promo services are intentionally
unavailable and the exam is intentionally locked. No real gateway, backend, database,
exam engine or Phase 03 module was added.

## 9. Final Phase 02 acceptance decision

**Phase 02 is accepted for its frontend-only scope**, based on the supported
production builds and both executed browser suites at all requested widths:
**5 unit tests plus 12 browser tests passed**, with final lint and typecheck clean.
Existing Phase 01 layout and navigation remain operational, and frontend-controlled
data cannot unlock an examination. The last generated production output is Webpack;
the default `npm run build` remains Turbopack. The test servers were automatically
stopped by Playwright after their runs. No Phase 03 implementation has begun.
