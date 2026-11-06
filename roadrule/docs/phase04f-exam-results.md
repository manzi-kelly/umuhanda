# Phase 04F examination grading and results

## Implementation

- The Phase 04E completion path closes the final response, persists completion and grades in one PostgreSQL transaction. The authenticated guest and timed attempt are locked before advancing or reconciling. A failed database write rolls the transaction back, so a subsequent request can retry.
- The grading service loads the twenty ordered snapshot items and their referenced immutable bank questions. It checks the revision, eligibility, answer evidence, option bounds and response finalization. Correct responses earn one point each. Incorrect and unanswered responses earn zero. A score of 12/20 passes, and the percentage is five times the score.
- The result preserves the student name from the attempt's student record, completion and grading timestamps, answer counts and grading version. The score, percentage and pass status are derived from the stored counts. The attempt remains the source for ownership and completion reason.
- A malformed snapshot records an administrator-visible grading integrity marker. The completed attempt is preserved and the student sees an unavailable result. A database error is handled separately and rolls back both completion and grading.
- The Next.js completion screen links to a Kinyarwanda result page. The page fetches through the student bridge using its existing HttpOnly guest cookie. The try-again link reuses that session, takes the student through authorization and only offers exam start when there is an available grant. The original entitlement cannot create a second attempt.

## Migration

`20261105_0008` adds `exam_results` and `exam_grading_failures`. Both use an attempt foreign key as the primary key. The result has a count constraint and completion-date index. Database triggers prevent edits and deletes. The downgrade is allowed on an empty grading schema and rejects a downgrade that would discard retained grades or integrity markers.

Development and test were at `20261105_0007` before implementation. The development database contained zero timed attempts before migration. Both local databases were upgraded to `20261105_0008`. Untimed attempts from older phases remain visible to administrators as historical attempts without grades. Existing completed timed attempts on other installations can be graded on their first authorized result request.

## API contracts

| GET endpoint | Scope and behavior |
| --- | --- |
| `/api/v1/exams/{attempt_id}/result` | Owning guest. Reconciles a due attempt, returns 409 for an active attempt, 404 for an unknown or foreign attempt, and 503 for a grading integrity failure. |
| `/api/v1/students/exams/history` | Owning guest. Returns saved results in reverse completion order. Supports `limit` and `offset`. |
| `/api/v1/admin/exam-results` | Administrator. Supports student-name search, status, inclusive UTC start-date range, limit and offset. |
| `/api/v1/admin/exam-results/{attempt_id}` | Administrator. Returns the stored attempt and result, or an integrity marker when grading could not produce a score. |
| `/api/v1/admin/exam-results/stats` | Administrator. Supports all-time, daily, weekly, monthly and yearly periods. Weeks start Monday UTC. Period membership uses attempt start time. |

The student result includes attempt ID, historical student name, start and completion time, completion reason, counts, score, total, percentage and status. It excludes contact details, correct-option values, PDF evidence and storage paths. The admin statistics count attempts, including active, completed, expired, passed and failed. Pass percentage and average score use graded attempts as the denominator. The statistics use stored states, which update when an attempt synchronizes.

## Changed files

- Backend models and services under `backend/app/models` and `backend/app/services`, results router and security middleware under `backend/app/api` and `backend/app/main.py`, and migration `backend/alembic/versions/20261105_0008_exam_results.py`.
- Student bridge, onboarding and payment controls, timed exam completion, result route and panel, and the protected admin examination page under `src`.
- PostgreSQL regression tests and fixtures, browser suites and their evidence configuration, and local verification scripts.
- This report and the backend README.

## Credential handling and operational limits

The existing interactive bootstrap command is `.venv/Scripts/python.exe scripts/bootstrap_admin.py --confirm-first-admin`, run from the backend directory. The login page has no embedded credentials. Result requests use the existing guest and administrator authorization boundaries. There are no public result writes or score inputs. Grading error responses carry a safe error code. Browser fixtures use synthetic data and the existing development-only mock settlement helper.

Retakes preserve question exclusion within the authenticated guest session. Independent or expired guest sessions have no verified identity link. The existing mock and promo authorization rules apply, and availability can be limited by the remaining eligible question bank. Student history contains saved grades, so older timed completions on another installation appear after an authorized result read. Admin reports reflect stored state and do not run an expiration worker.

## Verification
| Check | Observed result |
| --- | --- |
| `.venv/Scripts/python.exe -m ruff check .` and `-m ruff format --check .` | Passed. |
| `.venv/Scripts/python.exe -m pytest -q` in the testing environment | 230 passed in the final full suite, with zero failures and zero skips. The first full run passed 225 before the final integrity regression and four projection tests were added. |
| `.venv/Scripts/python.exe -m pytest -q tests/integration/test_exam_execution.py -k 'corrupt_snapshot or exact_deadlines'` | 2 passed, 9 deselected. |
| `.venv/Scripts/python.exe -m pytest -q tests/unit/test_exam_results.py` | 4 passed. |
| `.venv/Scripts/python.exe -m alembic upgrade head`, `current`, and `check` | Development reached `20261105_0008`. No schema drift. The PostgreSQL suite verified empty test schema upgrade, downgrade and repeat upgrade. |
| `npm run lint`, `npm run typecheck`, `npm test` | ESLint and TypeScript passed. All 5 frontend unit tests passed. |
| `npm run build` with `NODE_USE_SYSTEM_CA=1` | Next.js 16.4.5 Turbopack production build passed. The result page and protected admin report were included. |

The PostgreSQL tests verified 0/20, 11/20, 12/20 and 20/20, wrong and unanswered counts, ownership, result immutability, rollback, duplicate result rejection, concurrent completion and scoring, and stored admin aggregates. The final full run reported one Starlette HTTPX test-client deprecation warning. An earlier run also reported a Pydantic field metadata warning.

The [live foundation audit](evidence/phase04f/foundation-verification.json) passed. It checked route registration, API behavior with and without a database connection, the schema revision in both databases, and separation between the development and test application roles.

### Chrome administrator suite

`npm run test:browser:admin` passed 12 of 12 tests at 390px, 834px and 1440px. It checked the protected examination report, weekly filter, empty-state data, menu navigation, session expiry and logout, and existing PDF operations. PostgreSQL integration tests verified populated reporting with real stored grades. See the [final admin run](evidence/phase04f/admin-browser-results.json). The [initial run](evidence/phase04f/admin-browser-initial-results.json) retains two mobile menu timing failures from the test following a native form reload.

### Chrome student suite

`npm run test:browser` passed 6 of 6 tests at 390px, 834px and 1440px. The suite used the production Next.js build, PostgreSQL and synthetic PDF-backed questions. It verified the loading state, unauthorized result view, missing-result response, a 1/20 failing result and a 12/20 passing retake. The retake used a second available entitlement in the same guest session. The original result stayed unchanged, and both grades appeared in history. The existing student flow and exam lock also passed at all three widths. Chrome 157.0.8103.38 recorded zero unexpected console errors, page errors, failed requests or HTTP errors at each width.

- [Final student run](evidence/phase04f/public-browser-results.json)
- [390px passing result](evidence/phase04f/browser/390px-passed-result.png) and [390px failing result](evidence/phase04f/browser/390px-failed-result.png)
- [834px passing result](evidence/phase04f/browser/834px-passed-result.png) and [834px failing result](evidence/phase04f/browser/834px-failed-result.png)
- [1440px passing result](evidence/phase04f/browser/1440px-passed-result.png) and [1440px failing result](evidence/phase04f/browser/1440px-failed-result.png)

The [first student run](evidence/phase04f/public-browser-initial-results.json) exposed a transition locator and an image request racing the test clock. The [loading-state rerun](evidence/phase04f/public-browser-loading-rerun.json) matched both the expected error and Next.js's route announcer. The final run waited for the image and scoped assertions to the visible page content.

## Acceptance and readiness

Phase 04F passed the local acceptance checks. The supported production build, migration round trip, final PostgreSQL suite and both production Chrome suites passed. The test database was checked after cleanup and contained zero synthetic attempts, results, grading integrity markers and entitlements. The temporary browser credentials, PDF storage and test clock were removed.

The [production build log](evidence/phase04f/production-build.log) records the final Next.js build. Phase 04G can begin as a separate task. Real payment integrations remain outside Phase 04F.
