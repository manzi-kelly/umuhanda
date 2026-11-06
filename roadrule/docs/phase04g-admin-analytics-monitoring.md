# Phase 04G admin analytics, monitoring and refund preparation

## Architecture

The protected dashboard reads a private, no-store Next.js route. The route forwards only an approved reporting period and the existing HttpOnly administrator credential to FastAPI. FastAPI authenticates the session and calculates PostgreSQL aggregates under one read-only repeatable-read snapshot per request. Student records and exam attempts have separate denominators. No analytics endpoint changes student, exam, promo or payment state.

The dashboard and promo page refresh every 60 seconds by default. Set `ADMIN_ANALYTICS_REFRESH_SECONDS` to an integer from 30 through 300 for the dashboard deployment. The client uses a single scheduled refresh after the previous fetch settles, cancels on period changes and unmount, pauses scheduled requests in hidden or offline tabs, resumes on visibility or connectivity, and stops after a 401. It keeps the last successful timestamp visible during a transient error. The pass-rate meter appears when grades provide a denominator.

The system page is separate from business analytics. PDF uploads also show the existing bank readiness panel, which reports eligible, ineligible, missing-answer, ambiguous-answer and image-error counts from import revisions. Replacement imports continue to use the existing activation rules.

## Reporting definitions

Dates refer to Africa/Kigali civil dates. Kigali midnight currently corresponds to 22:00 UTC on the preceding date. The backend converts each boundary to UTC and uses `timestamp >= start AND timestamp < endExclusive`. Weekly periods start on Monday. The default period runs from its first Kigali date through the current Kigali date. Custom dates are inclusive civil dates and must be supplied as a pair, ordered, through today, and at most 366 days. The dashboard presents the four preset periods. The authenticated API accepts custom dates directly. Existing exam history filters remain labeled UTC.

| Measure | Definition |
| --- | --- |
| Student records and distinct IDs | All rows in the student table and distinct primary keys. A record does not establish a verified person. |
| Period registrations and activity | Student creation in the window and distinct student IDs whose guest session's last recorded activity falls within the window. This is a last-activity measure. |
| Exam attempts | Attempts started in the window, broken down by current persisted state. Expiration comes from timed completion reason. |
| Average, pass rate and unanswered | Mean score out of 20, passed divided by graded attempts, and sum of unanswered questions for grades in the attempt cohort. The API returns null for empty grade aggregates. The threshold remains 12/20. |
| Promo issuance and redemptions | Created codes and promo grants issued in the window. Durable grants count once, including across idempotent retries. Live inventory uses the existing disabled, expired, exhausted and active precedence. Remaining capacity covers active codes only. |
| Mock payments | Initiated mock transactions in the window by current stored state. The RWF amount sums successful simulated transactions. Real verified revenue is null and the UI displays Not Available. |

Current statuses can change as attempts synchronize, transactions settle or codes expire. These are operational cohort reports. They do not reconstruct historical status as of a past date.

## API contracts

- `GET /api/v1/admin/analytics/overview` accepts `period=daily|weekly|monthly|yearly` and optional paired ISO `start` and `end` dates. It returns the UTC boundaries, snapshot timestamp and student, examination, promo and payment metrics. Invalid ranges return 422.
- `GET /api/v1/admin/system` returns database and backend availability upon successful authenticated execution, PDF status counts, last observed worker job activity, last successful import, stale processing, active revision counts, and 24-hour exam-start and grading integrity warnings.
- `GET /admin/analytics-api` is the private same-origin browser bridge for the four presets. Existing exam history, promo redemption history, mock summaries and PDF APIs retain their contracts.
- `/admin/refunds` is a protected unavailable view. The project has no public or admin refund mutation endpoint.

## Health signals

The system reports DEGRADED when it detects a failed PDF import, processing older than 30 minutes, a missing active bank, or recent exam-start or grading issues. Worker status remains UNKNOWN when job history gives no proof of worker liveness. Stale processing is a degradation signal. A successful database query establishes database connectivity for that request. If the protected request fails after administrator authentication, the view shows UNAVAILABLE. When authentication itself cannot reach the database, the existing protected layout fails closed and the unauthenticated readiness probe remains the deployment signal.

## Migration and refund boundary

`20261105_0009` adds date indexes to exam attempts, payment transactions, promo codes and entitlements. It adds `refund_requests` with UUID relations, indexed status and creation time, bounded reason and review text, and a unique payment relation reserved for a future verified-payment workflow. A database check forbids linking any current payment. The schema stores no claimed phone, raw transaction reference or PIN. Its downgrade refuses to discard retained requests.

The brief permits an explicitly unavailable refund workflow. This implementation chooses that branch because the payment table is restricted to MOCK transactions. The student exam-unavailable state uses the requested Kinyarwanda text. A future workflow needs independently verified provider payment, payer ownership, unused entitlement checks, controlled review transitions with concurrency checks, and immutable audit events before allowing administrative approval. Financial execution and evidence of returned funds require a separate integration. The status set has no REFUNDED state. A future retention policy should minimize review notes and govern deletion independently of financial audit retention.

## Security and performance

Administrator session verification, private responses and existing CSRF protections remain in place. The new analytics reads use fixed ORM columns and parameterized predicates. The supported custom date window is bounded, the browser bridge accepts only presets, and the browser avoids concurrent refreshes. Admin bootstrap remains `.venv/Scripts/python.exe scripts/bootstrap_admin.py --confirm-first-admin` from the backend directory in an interactive local terminal.

Queries return aggregates and small projections. The time indexes support range scans. Existing pagination remains in the exam and promo management areas. Global student and promo inventory totals still read their relevant relations. Larger deployments can measure query plans, enforce gateway quotas and consider short-lived caching or materialized views. Worker heartbeats and multi-instance operational alerting remain future improvements.

## Files

- API and models under `backend/app` include `api/v1/admin_analytics.py`, `api/v1/router.py`, and `models/{__init__,exam_access,exam_bank,refunds}.py`.
- Migration `backend/alembic/versions/20261105_0009_analytics_refund_preparation.py` and the Windows timezone dependency declaration in `backend/pyproject.toml`.
- Protected pages `dashboard/page.tsx`, `system/page.tsx`, `refunds/page.tsx`, `promo-codes/page.tsx`, and `pdf-uploads/page.tsx` under `src/app/admin/(protected)`, plus `src/app/admin/analytics-api/route.ts`.
- UI components `AnalyticsPanel.tsx`, `AdminShell.tsx`, `ExamEntryShell.tsx` and `PaymentMethodSelector.tsx`, plus `src/features/onboarding/access-client.ts`.
- Backend test additions `test_reporting_periods.py` and `test_admin_analytics.py`, updated schema and API regression fixtures, `scripts/admin_browser_fixture.py`, and `scripts/verify_foundation.py`.
- Browser tests and evidence configuration in `tests/admin-browser/admin.spec.ts`, `tests/browser/phase02.spec.ts`, `playwright.config.ts`, and `playwright.admin.config.ts`.

## Verification

| Command | Observed result |
| --- | --- |
| `.venv/Scripts/python.exe -m ruff check .` | Passed. |
| `.venv/Scripts/python.exe -m ruff format --check .` | Passed. |
| `.venv/Scripts/python.exe -m alembic upgrade head`, `current`, and `check` | Local development and test upgraded from `20261105_0008` to `20261105_0009`. No metadata drift. |
| `.venv/Scripts/python.exe -m pytest -q` with `APP_ENV=testing` | 241 passed, 0 failed, 0 skipped. Includes PostgreSQL, empty-schema upgrade/downgrade/re-upgrade, reporting boundaries, stored grade aggregates, simulated payment isolation, and failed replacement monitoring. |
| `.venv/Scripts/python.exe -m scripts.verify_foundation` | Live API and least-privilege database audit passed. [Audit evidence](evidence/phase04g/foundation-verification.json) |
| `npm run lint` and `npm run typecheck` | Passed. |
| `npm test` | 5 passed, 0 failed, 0 skipped. |
| `npm run build` with `NODE_USE_SYSTEM_CA=1` | Next.js Turbopack production build passed. [Build log](evidence/phase04g/production-build.log) |
| `npm run test:browser:admin` | 12 passed, 0 failed, 0 skipped at 390px, 834px and 1440px. The suite verified the analytics bridge, period changes, a scheduled refresh, the empty-chart state, system warnings, protected refund status and existing admin flows. [Chrome evidence](evidence/phase04g/admin-browser-results.json) |
| `npm run test:browser` | 6 passed, 0 failed, 0 skipped at 390px, 834px and 1440px. This covered student onboarding, exam access, grading, retakes and existing security checks. A separate administrator context verified the pass-rate meter after grades were persisted. [Chrome evidence](evidence/phase04g/public-browser-results.json) |

The browser runs used isolated synthetic data and the production build. Chrome recorded no unexpected student application errors at the three widths. Earlier backend runs exposed test collection naming, missing fixture configuration and exam-clock expectation errors. The test files now use distinct names, enable mock payments only for the relevant synthetic fixture, and distinguish early completion from global expiry.

The final Python run emitted two dependency warnings from the Starlette HTTPX test client and Pydantic field metadata. The test database returned to revision `20261105_0009` with zero synthetic refunds, exam attempts, grades and payments. Browser credentials, PDF storage and test clock files were removed.

## Acceptance and next phase

Phase 04G passed the local acceptance checks. Refunds remain explicitly unavailable pending verified real-payment support. A separate future phase can define provider verification, reconciliation and payer ownership before enabling intake or settlement.
