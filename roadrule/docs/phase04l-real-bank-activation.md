# Phase 04L real-bank activation

## Isolated source and readiness

The local 149-page Road rules PDF was uploaded to the test application and processed against PostgreSQL `roadrules_test`. The worker activated the revision under `CATEGORY_BALANCED` with two road-sign and 18 general questions. The existing development bank and production settings were outside this activation.

| Measure | Phase 04K | Phase 04L |
| --- | ---: | ---: |
| Extracted drafts | 394 | 394 |
| Eligible | 235 | 235 |
| Ineligible drafts | 159 | 159 |
| Eligible road signs | 7 | 7 |
| Eligible general questions | 228 | 228 |
| Structural warnings | 10 | 10 |
| Blocking structural warnings under the tested policy | 10 | 0 |
| Eligible parenthesized answers | 203 | 203 |
| Eligible green-marked answers | 32 | 32 |
| Recovered image-only options | 20 | 20 |

The 159 rejected drafts consist of 80 extraction errors, 50 image errors, 13 incomplete options, 11 ambiguous answers and five missing answers. The ten unsupported-label rows are recorded separately from the drafts. [Pilot worker and API evidence](evidence/phase04l/final-pilot.log)

## Structural warning audit

All duplicate labels below are printed in the source. Each row remains excluded in full, including its answer marks. Even where a green or parenthesized marker identifies a printed label, the repeated label leaves the exam option identity ambiguous.

| Printed question | PDF page | Printed labels | Boundary evidence |
| --- | ---: | --- | --- |
| 228 | 64 | AABC | One ruled cell above 229 |
| 229 | 64 | ABBC | Separate cell after 228, ending before the next stem |
| 256 | 75 | AABC | One ruled cell |
| 265 | 78–79 | AABC | Last ruled cell continues into the first matching cell on the next page |
| 267 | 79 | ABBC | Last ruled cell. The next page begins a new question in the matching first cell |
| 270 | 80–81 | AABC | Last ruled cell continues into the first matching cell on the next page |
| 294 | 91–92 | ACCD | Last ruled cell continues into the first matching cell on the next page |
| 299 | 93 | AABC | Separate ruled cell before 300 |
| 300 | 93 | ABBC | Separate ruled cell after 299 |
| 395 | 133 | AACD | One ruled cell |

The parser records the bounding box and page for each certified cell. Certification requires four detected options with three distinct labels, source text confined to the proven cell or matching adjacent-page continuation, and no other numbered start inside the certified regions. An otherwise extracted row that crosses ruled cells on one page is flagged as uncertain. Uncertified or unrecorded failures still block activation. The worker log includes the exact regions.

Page 63 contains two distinct printed 227 rows, the first with an inline number at approximately y=328 points and the second beginning with a stand-alone number at approximately y=425 points. Both retain their original printed identifier and separate source positions and internal IDs. Both are excluded because the duplicate source identifier leaves answer mapping unresolved.

## Policy and integrity

- `DIFFICULTY_BALANCED` requires verified classifications and selects 7 hard, 4 medium and 9 easy. The authentic source contains zero verified difficulty labels. The strict policy reports insufficient classified questions for an otherwise eligible unclassified pool.
- `CATEGORY_BALANCED` selects exactly 20 distinct, source-backed eligible questions. Set `EXAM_CATEGORY_ROAD_SIGN_COUNT` to configure the road-sign count. Its default is one, the smallest mix containing both categories. The pilot explicitly configured two. The general count is the remainder to 20.
- Category targets are stored with the immutable bank revision. Selection randomizes each category and the final order. It excludes fingerprints already issued to the same guest session. No selection path switches policy after a shortage.
- Seven signs and 228 general questions allow at most three disjoint attempts under the tested 2/18 mix against this revision. Two starts and the third pool's availability were verified. Separate guest sessions have separate histories.
- Only the category policy can accept certified row-local warnings. Source answer evidence, source images, eligibility, immutable revisions and transactional replacement continue to govern readiness. A shortage test kept the existing healthy bank active.
- The student API returns the current question and permitted images without answer-key metadata. Grading uses the persisted server-side key. The backend pilot exercised a server-controlled timeout, scored 19/20 from 19 saved correct answers, stored the result in PostgreSQL, and confirmed it remained unchanged after a disjoint retake.

## Changed files and schema

Backend changes are in `app/core/config.py`, `app/services/pdf/parsing.py`, `app/services/pdf/jobs.py`, `app/services/exam_bank.py` and `app/services/exam_generation.py` under `backend`. The backend example environment and README document configuration. Admin changes are in `src/components/admin/questions/BankMonitor.tsx` and `src/features/admin/server.ts`. Acceptance coverage is in `backend/tests/integration/test_category_policy.py` and `tests/browser/phase04l-real-pilot.spec.ts`. The browser found that a newly opened question could return a null answer version in the Next response before the database default ran. `backend/app/services/exam_execution.py` now initializes the version to zero at creation. `backend/tests/integration/test_exam_execution.py` asserts the version directly on the Next response. Phase 04L adds no migration. Category targets fit the existing immutable JSON metadata. The first pilot ran at `20261105_0009`. The workspace gained the separate promo migration `20261106_0010` during verification. Alembic reported that revision at head with no schema drift.

## Remaining limits

The source still contains the ten excluded repeated-label rows, both excluded 227 rows, and other ineligible drafts. The isolated activation supports a category-balanced exam pilot. Difficulty-balanced activation requires verified classification evidence. Production payment integration remains a separate scope. All Phase 04L exam grants use test workflows.

## Executed verification

Windows ran Python 3.12.14, PostgreSQL 18, Node.js 24.22.1, npm 11.19.1 and headless Chrome via Playwright. The production frontend ran locally at `127.0.0.1:3100` with the isolated FastAPI fixture at `127.0.0.1:8310`. The student Chrome suite passed all six checks at 390px, 834px and 1440px. It covered navigation, payment and promo gates, direct unauthorized entry with JavaScript disabled, timed exam behavior, results and guest-session retakes. Synthetic starts measured 102, 105 and 125 ms with a 105 ms median. The sample is too small to characterize tail latency. The focused PostgreSQL/API suite passed three tests in 31.09 seconds, including setup, real import, API exam and retake. [Chrome regression evidence](evidence/phase04l/responsive.json) [API pilot log](evidence/phase04l/final-pilot.log)

ESLint, TypeScript and five frontend unit tests passed. `npm run build` succeeded with Next.js 16.4.5 and Turbopack. [Production build log](evidence/phase04l/final-build.log)

The initial full suite sharing the existing test database returned 197 passes, 32 failures and 23 errors. A second pytest process was observed on the same checkout. PostgreSQL reported fixture deadlocks, and the browser fixture observed an administrator disappearing between its insert and a foreign-key check. These runs are retained as failed attempts. Independent acceptance clusters used dedicated loopback ports and separately scoped browser artifacts. The development database remained outside all of these runs.

The fresh Chrome run reproduced a 404 for the upload before the worker could start. The admin bridge's POST allowlist had omitted `pdf-documents` during the separate promo changes. Phase 04L restored that exact route, preserving the existing admin authentication, same-origin check, file type validation and size limits. The full Ruff lint check passed. At the time of the check, the repo-wide format check flagged five files from the concurrent promo changes. The Phase 04L Python files passed their formatting checks.

The independent backend command `python -m pytest -q --tb=short` exercised 252 tests and passed 251, including the category and exact difficulty-policy cases, the real source exam, duplicate 227 identities, and the immediate answer version after Next. Its sole failure was the database-role test because the fresh cluster had only a test database. The read-only test passed on the provisioned cluster with both expected database names. This gives passing evidence for all 252 tests across the two runs. The isolated Alembic checks confirmed `20261106_0010 (head)` and no schema drift. [Full isolated run](evidence/phase04l/pytest-isolated.log) [Role isolation rerun](evidence/phase04l/postgres-role.log)

The changed browser fixture supports separate local artifact storage through `PHASE04L_ISOLATED_BROWSER=1`. Changes to browser tests also align promo creation with the current explicit-code contract. Admin console verification found an invalid HTML pattern in both promo input fields. Escaping the hyphen restores Chrome validation while keeping the same supported characters.

## Real-document Chrome pilot

The corrected 1440px Chrome test passed. An authorized admin uploaded the real PDF through the Next.js bridge, the worker activated it, and the monitoring page displayed the active source and category policy. The student created a guest session, redeemed a test promo, followed the automatic redirect, started the exam, saved an answer on all 20 questions and opened the results page. The student responses exposed one question at a time and no answer key. Five source images loaded. There were no unexpected browser console or page errors.

PostgreSQL recorded 20 distinct questions, two road signs, 18 general questions and zero payment transactions. Selecting the first option throughout scored 5/20. The UI, result API and independent snapshot calculation agreed. The expected failing grade complements the separate 19/20 passing API run with a server-enforced timeout. The worker invocation took 48.408 seconds, including process startup and persistence. The browser exam-start response took 230 ms in this single sample. [Real PDF Chrome pilot](evidence/phase04l/real-pilot-redirect.json)

A separate 390px Chrome test passed for authenticated image-only options and checked that all four images rendered. [Mobile image-only run](evidence/phase04l/vector-mobile.json)

## Browser regression and acceptance

The corrected admin suite passed 11 of 12 checks at 390px, 834px and 1440px. The one 834px test located the same published code in two visible elements. After scoping the locator to the publication status, the targeted admin checks passed at 834px and 1440px. Across runs, all 12 admin cases have passing evidence. This covers authentication, expired sessions, navigation, promo operations, private PDF upload and preview, and duplicate upload recovery. [Admin suite](evidence/phase04l/admin-corrected.json) [Targeted rerun](evidence/phase04l/admin-promo-rerun.json)

**Phase 04L is accepted for the isolated category-balanced pilot.** The authentic bank met every readiness check under the tested 2/18 configuration. The browser and API exam pilots completed with persisted grades. The strict difficulty policy passed its classified fixture and remains unsuitable for this source until verified difficulty labels exist. The development bank was outside the test activation. Production payment integration and live settlement remain outside this acceptance.

Additional files changed during verification include the admin PDF bridge route, the promo form, the isolated browser fixture and the student and admin browser regressions. The verification changes preserve existing authorization and API validation.
