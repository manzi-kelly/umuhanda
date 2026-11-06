# Phase 04D — Mock payments, promos and exam entitlements

## Architecture

The existing student form creates a FastAPI guest session. Next.js forwards
a small allowlist of same-origin student requests and maps the backend opaque
credential to a host-scoped HttpOnly browser cookie. The credential is never
returned to JavaScript or saved to browser storage. The bridge verifies the
configured Origin on mutations. FastAPI independently checks Origin and the
accepted CSRF header. The authenticated API returns the name, bank readiness,
and entitlement state for that session.

`/tangira` supports promo redemption and, when enabled by the backend, MTN
and Airtel synthetic payments. `/exam` displays server-confirmed access and
the exam rules. The Start Exam control stays disabled during this phase.
The protected admin pages manage promo codes and show separate mock counts.

## Database and lifecycle

Migration `20261105_0006` adds `payment_transactions`, `promo_codes`,
`promo_attempts`, and `exam_entitlements`. Amounts use PostgreSQL
`NUMERIC(12,0)` in RWF. Each payment is uniquely identified by a generated
reference and by its guest-scoped idempotency key. Triggers enforce a pending
initial state and a single transition to SUCCESSFUL, FAILED or CANCELLED.
Recorded source fields and final payment states are immutable.

An entitlement belongs to a guest and student and references exactly one
payment or promo. A unique payment reference prevents repeated settlement
from issuing additional access. A unique guest/promo pair makes successful
redemption retries idempotent. A grant is AVAILABLE until consumed by an
immutable exam attempt or revoked by a trusted future resolution workflow.
The transaction itself is the reservation boundary. There is no committed
intermediate reservation state. A database trigger checks ownership and
the attempt reference and prevents rewriting consumed authorization history.
Downgrade refuses to discard retained authorization evidence.

## Mock payment operations

Set `MOCK_PAYMENTS_ENABLED=true` explicitly in the development or test
backend environment to show mock methods. The default is false.
`MOCK_EXAM_AMOUNT_RWF` supplies the amount and defaults to 500. Production
refuses initiation and settlement even if the flag is true. A client can
initiate a pending transaction and query its own status. It has no route
for marking success. An operator with local database access can use:

```powershell
.venv/Scripts/python.exe scripts/mock_payment.py <displayed-MOCK-reference-or-UUID> SUCCESSFUL
```

The command accepts FAILED and CANCELLED for failure tests. Success checks
the guest and active bank again, then settles and issues one entitlement in
the same transaction. Repeating the same outcome returns the same record.
A temporary bank failure leaves the pending payment available to retry.
The UI shows the synthetic reference and the required Kinyarwanda test
notice. Payment handling accepts no PIN and makes no provider call. Admin
mock counts are separate from the unavailable verified revenue metric.

## Promo operations

Admins create codes with 128 bits of random entropy. The raw code appears
only in the creation response. PostgreSQL stores a domain-separated SHA-256
verifier, timestamps, usage limit and disable state. The server creates the
expiry exactly 24 hours after creation using UTC timestamps. The default
limit is one and the accepted range is 1–100. List responses show ACTIVE,
EXPIRED, DISABLED or EXHAUSTED based on current database time and usage.
Disabling a code prevents new redemptions. Previously issued grants retain
their own lifecycle.

Redemption checks the authenticated guest, durable rate budget, code
verifier, disable/expiry state, remaining usage and bank readiness. The
transaction locks the code row and persists the entitlement atomically.
Previously redeemed codes return the original grant within the request
budget. The budget is eight attempts per guest and 100 per database in a
rolling five-minute window, including unsuccessful guesses. The API returns
a generic invalid response for unknown, expired, disabled and exhausted
codes. The administrator can view redemption status and timestamps without
raw codes, guest credentials or student contact details.

## API contracts

All paths have prefix `/api/v1`. Cookie mutations require an allowlisted
Origin and `X-CSRF-Protection: 1`.

| Route | Purpose |
| --- | --- |
| POST /students/sessions | Existing guest-session creation. |
| POST /payments/mock/initiate | Authenticated guest sends provider and UUID idempotencyKey. Returns a mock record. |
| GET /payments/{payment_id}/status | Owner-only mock status. |
| POST /promos/redeem | Authenticated guest sends code. Returns the existing or newly issued grant. |
| GET /exam-access/me | Authenticated name, bank and access state, and up to 50 recent grants. |
| POST /admin/promo-codes | Admin generates a code with optional usageLimit. Creation response includes the raw code. |
| GET /admin/promo-codes | Paginated admin metadata with usage and computed status. |
| POST /admin/promo-codes/{promo_id}/disable | Admin disables further redemption. |
| GET /admin/promo-codes/{promo_id}/redemptions | Admin redemption history. |
| GET /admin/mock-payments/summary | Synthetic counts grouped by state. |

Bank failures return `503 EXAM_UNAVAILABLE`. An existing AVAILABLE grant
survives unavailability and is displayed as retained. Bad codes return
`422 PROMO_INVALID`, rate exhaustion returns 429, and unauthorized access
is rejected by the existing authentication and CSRF middleware.

## Phase 04E boundary

`start_with_entitlement` is the internal entry point for future exam start.
It verifies the guest and grant, checks the active bank and unused-question
pool, and persists exactly 20 ordered immutable items. The same transaction
links the attempt and consumes the grant. Concurrent retry with the same
grant returns the existing snapshot. A failure creates no attempt and leaves
the grant available. The student-shaped snapshot excludes correct answers.
There is no HTTP exam-start route in this phase. Interactive questions,
timers and grading await the next phase.

History remains scoped to the authenticated guest session. Cross-session
continuity needs a verified identity mechanism. Names and self-entered phone
numbers cannot establish it. Real-source exam bank quality still depends on
testing the actual PDF. Browser verification uses synthetic source and
payment data in the isolated test database.

## Changed files

Backend changes cover the new exam-access model, migration, service, API
router and local mock operator command, plus guest/attempt integration,
configuration and the test fixtures. Frontend changes cover the student
API bridge, onboarding and exam readiness screens, admin promo workspace,
admin mock statistics and the protected admin bridge. Existing schema/API
expectations and browser tests were extended for the new flows.

## Validation

| Check | Executed result |
| --- | --- |
| Ruff lint and formatting | Passed |
| Pytest | 215 distinct checks verified across the full run and corrected regression. The full run passed 214 and exposed a legacy assertion that expected the newly required promo endpoint to be absent. |
| Corrected guest regression | Passed. CSRF and invalid codes do not authorize access, and the public exam-start path stays unavailable. |
| Production safety | HTTPS test request with production settings and the mock flag enabled returned `403 MOCK_DISABLED`. Direct settlement was also refused. |
| Migration and live API audit | Test upgrades, downgrades and metadata checks passed. Development advanced from 0005 to 0006 with previous row counts preserved. |
| Frontend lint, TypeScript, Turbopack build | Passed |
| Frontend unit | 5 passed |
| Public Chrome | 6 distinct checks verified at 390px, 834px and 1440px. |
| Admin Chrome | 12 passed at 390px, 834px and 1440px, including promo generation, one-time display, history, disabling, separate mock counts and PDF regressions. |

The initial public browser run passed three direct-entry checks without
JavaScript. The three onboarding assertions stopped when their alert selector
also matched Next.js's route announcer. After scoping it to the application
content, all three onboarding checks passed. They exercised the real API,
pending and operator-settled mock status, invalid and valid promo codes,
HttpOnly session state, and the exam-readiness page.

Execution evidence. [Full backend run](evidence/phase04d/pytest.log) ·
[Corrected guest regression](evidence/phase04d/guest-regression.log) ·
[Production build](evidence/phase04d/build.log) ·
[Development migration](evidence/phase04d/development-migration.json) ·
[Initial public browser checks](evidence/phase04d/public-browser-initial-results.json) ·
[Corrected student browser checks](evidence/phase04d/public-browser-results.json) ·
[Mobile authorized readiness](evidence/phase04d/browser/390px-exam-locked.png) ·
[Admin browser checks](evidence/phase04d/admin-browser-results.json) ·
[Fixture cleanup](evidence/phase04d/fixture-cleanup.json).

