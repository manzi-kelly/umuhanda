# Phase 04E — Secure timed examination

## Architecture and migration

The student confirms start on `/exam` after FastAPI reports a valid grant and an
exam-ready bank. Start reuses the existing immutable Phase 04C selection. A single
transaction selects 20 questions, creates the attempt and first question window,
and consumes the Phase 04D entitlement. The API projects one current question
from that snapshot. Correct options, source-answer evidence, future questions
and storage paths stay server-side.

Revision `20261105_0007` adds `exam_timing` and `exam_responses`. The former
holds the immutable global deadline, position and completion reason. The latter
uses a composite foreign key to a snapshot item and records the question window,
selected option, version, save time and finalization. A null selection means
unanswered. NEXT, DEADLINE and GLOBAL distinguish how a question closed.
Existing attempts and ordering are preserved. Legacy attempts created without
timing remain historical. The migration refuses to drop retained timed data.
Database triggers protect deadlines, finalized responses and forward progress.

## Timer and advancement

PostgreSQL supplies UTC time. Start records a 20-minute global window. Each
question opens for up to 60 seconds, capped by the original global deadline.
Early Next closes the question at the database time sampled after obtaining
the guest and attempt locks and immediately
opens the next question. A deadline closes at its stored instant. Each subsequent
offline window starts at the preceding deadline, so multiple missed windows
are reconciled without awarding extra time. At the exact deadline, expiration
wins over answer and Next requests. Existing saved selections remain intact.

Question 20 completes the exam. Completion at the global deadline is recorded
as GLOBAL_TIME_EXPIRED. Completion before it uses ALL_QUESTIONS_FINISHED.
Read and mutation requests reconcile under the guest and attempt locks before
returning a state. Offline completion is materialized on the next authorized
access. There is no background expiry daemon. Until reconciliation, stored
admin counts can include attempts whose logical deadline has already passed.
A request can never use that delay to submit an expired answer.

## API contracts

Paths below are relative to `/api/v1`. Student routes use the existing guest
cookie. Mutations require the existing Origin and CSRF checks. The same-origin
Next.js bridge forwards only these paths and uses private, no-store responses.

| Method and path | Body and behavior |
| --- | --- |
| POST /exams/start | `{entitlementId}`. Uses the authenticated guest's available grant. Retrying a consumed grant returns the same timed attempt. |
| GET /exams/me | Most recent timed attempt for recovery, or `{exam:null}`. |
| GET /exams/{id}/current | Reconciles and returns the current projection. Cross-session IDs return 404. |
| PUT /exams/{id}/answer | `{position, optionId, answerVersion}`. Saves only a valid option on the active question before its deadline. |
| POST /exams/{id}/next | `{position}`. Finalizes and advances once. A stale position returns 409 and the client synchronizes. |
| GET /exams/{id}/media/{position}/{index} | Current-question-only PNG. Server resolves the immutable asset, verifies its hash and bounds the response size. |
| GET /admin/exam-execution/summary | Protected counts of stored active/completed/time-expired attempts and unavailable starts. |

Successful student JSON has an `exam` object with attempt ID, status, position,
total, server time, timestamps, completion reason, and the current question
or null on completion. Options carry an ordinal, label and text. The projection
includes the saved selection and version. It includes no correctness fields.
Structured errors include EXAM_UNAVAILABLE, ENTITLEMENT_REQUIRED, STALE_QUESTION,
STALE_ANSWER, EXAM_COMPLETED and MEDIA_UNAVAILABLE. An unavailable bank never
consumes a grant.

## Concurrency, persistence and recovery

The existing guest row lock serializes interactions and prevents concurrent
timed starts for that guest. The grant lock and unique entitlement reference
keep retries idempotent. An attempt cannot be opened without its grant and
existing 20-item snapshot. An answer version protects against a delayed retry
overwriting a newer selection. A retry of the same saved answer is safe.
Finalized rows cannot be modified. Next requires the expected position, so a
duplicate request cannot skip an extra question. Lock order begins with the
guest before the grant or attempt.

The browser displays one Kinyarwanda question at a time. It waits for save
confirmation before enabling another interaction. The countdown estimates
server time from the latest response and elapsed browser monotonic time. At
18 minutes it changes to red. On expiry, return to a visible tab, or restored
connectivity, the browser requests synchronization. The backend is authoritative.
Refresh or reopening the page uses the existing attempt rather than issuing a
new start. Network errors allow a retry without resending an old position
blindly. Missing illustrations can be retried individually. Guest expiry and
revocation remain in effect, and an expired credential cannot recover an exam.
History and recovery stay within the authenticated guest session. Cross-session
identity linking requires a separate verification mechanism.

## Files changed

- Backend: timed execution models, service and API router, revision 0007,
  exam generation/entitlement integration, and CSRF/CORS route configuration.
- Frontend: exam entry and active question components, student bridge and API
  client, protected examinations monitor, public launch copy, and browser regression coverage.
- Verification: deterministic PostgreSQL tests, updated migration and API
  expectations, and a test-fixture-only clock for Chrome. Production does not
  load this fixture or accept a client clock input.

## Validation

| Check | Executed result |
| --- | --- |
| Ruff lint and format | Passed |
| Backend Pytest | 220 passed, including five deterministic timed execution tests |
| Alembic and live database audit | Test upgrade/downgrade and schema checks passed. Development advanced from 0006 to 0007 with prior row counts preserved. |
| ESLint, TypeScript, Next.js 16.4.5 Turbopack production build | Passed on final public copy |
| Frontend unit | 5 passed |
| Student Chrome | 6 passed at 390px, 834px and 1440px |
| Admin Chrome | 12 passed at the same widths |
| Final 390px smoke | 2 passed on the final build after updating public copy |

The backend run retained the TestClient deprecation and a Pydantic schema
warning during concurrent client setup. Timed tests used an injected fixture
clock, preserved saved answers at exact boundaries and verified locked
snapshot order, grant preservation on unavailable start, scoped media and
safe output fields.

Execution evidence. [Backend tests](evidence/phase04e/pytest.log) ·
[Migration](evidence/phase04e/development-migration.json) ·
[Live API audit](evidence/phase04e/foundation-verification.json) ·
[Student Chrome](evidence/phase04e/public-browser-full-results.json) ·
[Admin Chrome](evidence/phase04e/admin-browser-results.json) ·
[Mobile red timer](evidence/phase04e/browser/390px-warning.png) ·
[Production build](evidence/phase04e/build.log) ·
[Final mobile smoke](evidence/phase04e/public-browser-final-smoke.json) ·
[Fixture cleanup](evidence/phase04e/fixture-cleanup.json).

Chrome used the isolated synthetic PDF fixture and independent server/browser
test clocks. It verified confirmed access and start, current-only questions,
answer network failure and retry, saved selection after refresh, Next, automatic
advancement, the red 18-minute warning, completion, and the locked
no-JavaScript entry. The admin suite covered the protected attempt monitor
alongside the prior session, promo and PDF workflows.


## Phase 04F readiness

Immutable question versions and finalized responses are available for a future
server-side scoring service. The student completion screen confirms that
responses were stored. Scoring, pass/fail results and answer explanations are
outside this phase. Browser fixtures use synthetic PDF content, so accuracy
of the intended examination source still requires the representative PDF.
