# Phase 04I local end-to-end acceptance

## Environment and scope

- Workspace `D:\Roadrules\roadrule` on Windows 11 build 26300 with PowerShell, Python 3.12.14, FastAPI 0.162.0, PostgreSQL 18.6 and headless Chrome 157.0.8103.38. Node.js 24.22.1, npm 11.19.1 and Next.js 16.4.5 with Turbopack.
- Local PostgreSQL on `127.0.0.1:55432`, with separate development and isolated test databases and distinct application roles. The acceptance build served Next.js on `127.0.0.1:3100` and FastAPI on `127.0.0.1:8310`. Browser cookies were issued and verified through the normal Next.js bridges.
- Browser fixtures provisioned disposable operator credentials and used the isolated test role. Exam browser tests used a test-only backend clock to exercise deadlines without waiting twenty wall-clock minutes. The app enforced deadlines from backend time. Local mock settlement used the existing operator fixture. No real payment was initiated.
- Phase 04I changes are acceptance tests and evidence only. There are no application behavior changes or schema migrations.

## Readiness and automated regression

| Command | Observed result |
| --- | --- |
| `.venv/Scripts/python.exe -m alembic current` and `-m alembic check` | `20261105_0009`, no drift. |
| `.venv/Scripts/python.exe -m scripts.verify_foundation` | Live FastAPI health and readiness audit, unavailable-database response and role isolation passed. |
| `.venv/Scripts/python.exe -m pytest -q` with `APP_ENV=testing` | 242 passed, no failures or skips. Includes PostgreSQL and migration round trips. One Starlette test-client deprecation warning. |
| `npm run lint`, `npm run typecheck`, `npm test` | ESLint and TypeScript passed. Five frontend unit tests passed. |
| `npm run build` with `NODE_USE_SYSTEM_CA=1` | Production build passed. [Build evidence](evidence/phase04i/production-build.log) |

## PDF sources and test method

A hidden-storage scan found the existing 149-page `Road rules.pdf` in the development database, initially QUEUED. Final read-only verification found that the development worker had processed it to COMPLETED_WITH_WARNINGS. The development outcome is recorded separately from the isolated browser upload. The browser acceptance run uploads its bytes through the protected admin UI into isolated test storage. It also uploads a clearly labeled 42-question synthetic fixture with road-sign graphics and explicit answer evidence. The PDF worker is exercised as a separate one-shot coordinator and child process, using the normal extraction pipeline. The synthetic upload is the deterministic activation control.

## Exam and security test method

The student workflow uses the production browser UI for onboarding, promo redemption, starting the first attempt and entering a retake. It checks answer recovery after reload, manual Next, auto-next and server-driven global expiry. The retake walks all twenty questions through the same authenticated student bridge, with twelve correct and eight incorrect answers. Direct, read-only PostgreSQL queries compare both snapshots and the consumed entitlements. Student result editing and cross-session reads are probed through the actual bridge.

The administrator browser comparison reads the private analytics endpoint and compares its metrics with independently counted PostgreSQL rows. This includes student records, exam outcomes, promo grants, mock transactions and the Kigali reporting boundary. The regression suite covers mock isolation, missing credentials and CSRF, failed PDF import handling and immutable snapshots and results.

## Performance method

Access timing uses the dedicated Phase 04I performance probe over the local production bridge. The first creation and promo sample is excluded as warmup. Exam timings use the warm retake starts and the current, answer, next and result requests from the three browser runs. End-to-end request timings include loopback and application handling. They do not represent a network SLA or concurrent load test.

## Browser and database results

- `npm run test:browser -- phase02.spec.ts` passed all 6 student checks at 390px, 834px and 1440px. The final runs recorded zero unexpected console errors, page errors, failed requests or HTTP errors. [Student evidence](evidence/phase04i/public-browser-results.json)
- `npm run test:browser:admin -- admin.spec.ts` passed all 12 administrator checks at those widths, including authentication, dashboard refresh, period switching, PDF failure handling and monitoring. [Admin evidence](evidence/phase04i/admin-browser-results.json)
- The dedicated 1440px run of `phase04i-pdf.spec.ts` passed 2 checks. The synthetic upload progressed from zero to seven processed pages, extracted 42 eligible questions including 21 road signs, displayed a loaded sign image and answer evidence, and became the active bank. [PDF browser evidence](evidence/phase04i/pdf-browser-results.json)
- Each student run persisted a 1/20 failed first attempt and a 12/20 passed retake. The retake saved 12 correct and 8 incorrect answers and finalized all 20. Each pair had two distinct consumed entitlements and zero shared question fingerprints. Replaying the second start returned the same attempt. The first result stayed unchanged.
- After the final viewport, analytics matched the database counts for six attempts, three passes, three failures, three promo grants and six mock transactions. The student count also included the separate cross-session test identities. Verified revenue remained unavailable, and the weekly Kigali window started at 22:00 UTC.
- An unauthenticated result lookup was denied. A different authenticated guest received 404 for the attempt and result. The score-edit request was rejected, and current-question payloads excluded full question lists and answer keys. Existing integration tests also covered result immutability, production mock restrictions and CSRF.
- Ruff lint and formatting passed. Both databases were at `20261105_0009`. The test database ended with no uploaded PDFs, attempts, results or payments, and temporary browser files were absent. [Readiness audit](evidence/phase04i/foundation-verification.json)

## Representative PDF outcome

The worker processed all **149 pages** of `Road rules.pdf` in about **47 seconds**. It persisted **273 extracted drafts**, reported **50 failed items** and completed with warnings. The revision recorded answer-evidence structures for 273 drafts and image associations for 127, but **zero questions passed eligibility**. The recorded reasons were 168 incomplete option sets, 55 missing usable answers, 41 extraction errors and 9 image errors. The revision was marked `EXTRACTION_IMPROVEMENTS_REQUIRED` and the isolated test retained its healthy synthetic bank. Development independently recorded the same non-ready outcome. [Development PDF outcome](evidence/phase04i/dev-pdf-outcome.json)

## Observed local latency

| Operation | Samples | Median | Slower tail |
| --- | ---: | ---: | ---: |
| Guest session creation | 2 warm | 42 ms | 43 ms max |
| Promo redemption | 2 warm | 53 ms | 53.4 ms max |
| Entitlement lookup | 5 | 35 ms | 43 ms max |
| Retake start | 3 | 94 ms | 101 ms max |
| Current question | 60 | 34 ms | 51 ms p95 |
| Save answer | 60 | 41.5 ms | 65 ms p95 |
| Next question | 60 | 41 ms | 61 ms p95 |
| Result retrieval | 15 | 29 ms | 71 ms max |

The p95 values use nearest rank. Smaller samples use maximums. The access probe recorded the individual durations. The student report contains per-viewport exam timings. [Access performance samples](evidence/phase04i/performance.json)

## Findings and pilot decision

Early browser attempts exposed a synthetic worker-policy mismatch and test fixture startup and cleanup failures. The synthetic run was aligned to the fixture policy, and the final serial run reports passed. No application or schema fix was made to override source eligibility. The real PDF reached a terminal worker state and remained ineligible in both environments.

**The platform passed local workflow checks with the synthetic bank. A pilot using the supplied road-rules PDF is blocked** until its question structure, options and answer evidence can be extracted and validated into an eligible bank. Question exclusion is verified within one authenticated guest session. Independent guest sessions have no verified identity link. The worker test exercised bounded one-shot execution, and the timing sample does not establish performance under load.
