# Phase 04A â€” Admin authentication and dashboard foundation

Date: 2026-11-05. Project: `D:/Roadrules/roadrule`.

## Architecture and scope

FastAPI/PostgreSQL are the authentication authority. Next.js provides the admin UI
and server-only API integration. Public pages moved unchanged beneath the `(public)`
route group so their original header/footer and URLs remain intact. Admin pages have
a separate responsive shell, mobile navigation, verified identity header and logout.

The Next.js data-access layer verifies `/auth/me` for every protected page, including
direct and client navigations. Layout verification is supplementary. React `cache`
only deduplicates verification within a render; backend fetches use `no-store`.
Partial prerendering emits a generic verification fallback and fetches protected
content at request time. Admin responses have private/no-store headers.

No frontend role, localStorage value, UUID, query parameter or guest session grants
administrator access. The summary API independently verifies the admin session.
No PDF upload, OCR, extraction, question publication, exam generation, payment
integration, promo generation or Phase 04B functionality was implemented.

## Database migration

`20261105_0003_admin_foundation.py` revises the existing `20261104_0002` migration.
It adds only `admin_users`, `admin_sessions` and `admin_audit_events`, including UUID
keys, foreign keys, indexes, UTC timestamps and validation constraints. Previous
migrations and existing student tables remain in place. Downgrade drops only the
three admin tables. Migration upgrade/downgrade/repeat-upgrade and Alembic metadata
checks execute against the isolated existing test database only.

The existing PostgreSQL cluster remains at `127.0.0.1:55432`, with `roadrules_dev`
and `roadrules_test` and their dedicated least-privileged application roles. No new
cluster/database or privileged application role was created. The additive development
upgrade preserved all three student table row counts; see
[evidence](evidence/phase04a/development-migration.json). The development database
contains zero admin accounts: no operator credentials were supplied or invented.

## First administrator setup

From an interactive terminal in `backend`, with its existing private `.env`:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/bootstrap_admin.py --confirm-first-admin
```

Supply your own name, email and passphrase (15â€“256 characters), confirming the
hidden passphrase. No password argument, piped password, public signup, default
credential or frontend secret exists. Bootstrap serializes with a PostgreSQL advisory
transaction lock and refuses if any admin account or ADMIN_BOOTSTRAPPED audit marker
exists. The marker survives account deletion, so deletion cannot reopen bootstrap.
Tests use random accounts exclusively in `roadrules_test`, then remove their fixtures.

## API contracts

All paths below start with `/api/v1/admin`. POST requests require an exact allowlisted
Origin and `X-CSRF-Protection: 1`; credentials are accepted only from the admin cookie.

| Method and path | Success | Rejection |
| --- | --- | --- |
| POST `/auth/login` | 200 identity and Set-Cookie | 401 generic credential error; 422 invalid input; 429 budget exhausted |
| GET `/auth/me` | 200 current verified identity | 401 missing/invalid/revoked/expired/disabled session |
| POST `/auth/logout` | 204 after revocation; repeat/missing logout is harmless | 401 invalid/expired credential; 403 invalid Origin/CSRF |
| GET `/dashboard/summary` | 200 summary after independent authentication | 401 unauthorized |

Identity fields: `id`, `fullName`, `email`, `role: ADMIN`, `expiresAt`. No password,
hash or raw session credential is returned in JSON. The summary returns a real
`COUNT(students)` as `totalStudents`; `totalExamAttempts`, `passedExams`, `failedExams`,
`totalVerifiedRevenue`, `activePromoCodes` are explicitly null. These appear as
Unavailable, never fabricated zero values or fake financial totals.

## Authentication and security

- Argon2id uses 64 MiB, three iterations and parallelism two with random salts.
  Unknown-email attempts verify a dummy hash; incorrect/inactive credentials share
  the same generic response. Password rehashing follows the configured parameters.
- Session credentials contain 32 random bytes (43 URL-safe characters). Only a
  domain-separated SHA-256 verifier is stored, distinct from guest session hashes.
- Eight-hour absolute expiry, 30-minute idle expiry and a 60-second persisted touch
  interval are enforced with PostgreSQL time and row locks. Touch throttling may
  expire a session up to one interval early; it never extends absolute expiry.
  Each request verifies current account activity/role. Logout revokes server state.
- API cookie: `roadrules_admin`, path `/api/v1/admin`, HttpOnly, SameSite Strict.
  Production uses `__Secure-roadrules_admin` and Secure. It is separate from guest
  cookies and rejects duplicate same-name credentials.
- Browser-facing Next.js cookie: `roadrules_admin_ui`, path `/admin`, same protections;
  production uses `__Secure-roadrules_admin_ui`. Next Server Actions alone translate
  this opaque credential into the backend cookie. The token is never exposed in
  client state, browser storage or action response JSON. Cookie paths limit sending;
  they are not treated as an authorization boundary.
- Next Server Actions use their built-in checks plus an exact configured Origin
  comparison. FastAPI repeats Origin/custom-header verification, exact credentialed
  CORS and existing production HTTPS checks. API-origin configuration is server-only.
- Login uses a durable global database budget of 20 attempts per 60 seconds with a
  transaction advisory lock; failures and successes consume the budget across app
  instances. This limits abuse but is not a per-user/per-IP fairness mechanism.
- Audit metadata accepts only enumerated result/reason values. No passwords,
  credentials, names, emails, phone numbers, IPs or request bodies are audit fields.
  Application errors are sanitized; access logs and browser traces are disabled for
  the synthetic authentication fixture. Never enable body/cookie logging in proxies/APM.
- No Mobile Money PIN collection, fake payment success, arbitrary promo approval,
  frontend-controlled examination authorization or public PDF endpoint was added.

The local source/log audit checks actual database credentials without printing them,
and checks historical credential-shaped PostgreSQL log values against currently active
admin/guest verifiers. Results are in [security-audit.json](evidence/phase04a/security-audit.json).
The pre-existing private database log retains two historical non-active guest-shaped
values from an earlier rejected-constraint test; it was not erased to conceal history.
No active credential matched those historical values.

## Running the frontend

Use the root `.env.example` as a guide for server-only `ADMIN_API_ORIGIN` and
`ADMIN_FRONTEND_ORIGIN`. Start FastAPI with the existing backend instructions and
run `npm run dev`. For loopback-only `next start`, explicitly set
`ADMIN_LOCAL_DEVELOPMENT=1`; both configured origins must be loopback addresses.
For a public production deployment remove this override and configure HTTPS for
both services, `APP_ENV=production`, allowed hosts and the exact frontend origin.
There are no `NEXT_PUBLIC` secrets. The local browser exercise is HTTP loopback;
it does not constitute deployment/TLS verification.

## Dashboard and navigation

`/admin/login` is public. These eight routes are protected:

- `/admin/dashboard`: six KPI cards, real student count, unavailable exam/finance/promo
  metrics, Daily/Weekly/Monthly/Yearly selectors and an explicitly unavailable chart.
- `/admin/pdf-uploads`: disabled upload action, no file input or upload endpoint;
  planned source-PDF workflow is visible without pretending it executes.
- `/admin/questions`, `/admin/students`, `/admin/exams`, `/admin/payments`,
  `/admin/promo-codes`, `/admin/settings`: clearly labeled unavailable workspaces.

Desktop sidebar and mobile toggle/Escape navigation support these same destinations.
Login provides field validation/focus, generic authentication errors and pending state.
Logout reports failure rather than claiming server revocation if the API is unavailable.

## Files created and modified

Backend additions: `app/core/admin_security.py`, `app/models/admin.py`,
`app/schemas/admin.py`, `app/repositories/admin.py`, `app/services/admin_auth.py`,
`app/services/admin_reporting.py`, `app/api/v1/admin.py`, migration 0003,
`scripts/bootstrap_admin.py`, `scripts/admin_browser_fixture.py`,
`tests/unit/test_admin_security.py`, `tests/integration/test_admin.py`.

Backend integration updates: config, model exports, API router, main middleware/error
handlers, existing API/migration/student test expectations, `pyproject.toml`, dependency
lock, `.env.example`, foundation/security audit scripts and README. Added Argon2 and
email-validation dependencies; existing application dependencies were not upgraded.

Frontend additions: `src/features/admin/{types,server,actions}.ts`, admin components
under `src/components/admin`, admin routes under `src/app/admin`, `(public)/layout.tsx`,
root `.env.example`, `playwright.admin.config.ts`, `tests/admin-browser/*`.
Public route files moved beneath `(public)`; root layout, Next security headers,
package scripts, ESLint generated-report exclusions and README updated. Evidence and this report were added under docs.

## Verification results

| Command (from project root unless noted) | Result |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m ruff check backend` | Passed; no violations |
| `.venv/Scripts/python.exe -m pytest -q` (backend directory) | 176 passed, no skips, 86.63 seconds; one existing dependency warning |
| `backend/.venv/Scripts/python.exe -m pip check` | No broken requirements |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm test` | 5 passed |
| `npm run build` | Passed, Next.js 16.4.5 Turbopack; TypeScript and all 15 pages generated |
| `npm run test:browser:admin` | 9 passed, 3.1 minutes; Chrome at 390/834/1440px |
| `npm run test:browser` | 6 passed, 1.8 minutes; all three widths |
| `.venv/Scripts/python.exe scripts/verify_foundation.py` (backend) | Passed live HTTP health/readiness 200; unavailable DB readiness 503; both schemas/roles/head verified |
| `.venv/Scripts/python.exe scripts/audit_local_secrets.py` (backend) | Passed; zero plaintext credential matches and zero active logged-credential matches |

The 31 new admin tests run alongside the existing 145 backend regressions. They
cover Argon2id and input validation, one-time/concurrent bootstrap, login success,
generic failures, inactive accounts, durable rate limits across instances, stored
verifiers, absolute/idle expiry, disabled-account revocation, logout/rotation, CSRF,
unauthorized/guest/UUID/forged-role requests, true student counts, null metrics,
absence of public signup/upload routes and schema upgrade/downgrade/metadata checks.

The existing Starlette TestClient warning recommends migrating from HTTPX to HTTPX2;
no warning was suppressed and no unrelated dependency upgrade was made. Next/Chrome
runners also emit harmless NO_COLOR/FORCE_COLOR environment warnings.

Admin browser evidence: [JSON results](evidence/phase04a/admin-browser-results.json).
At every width, executed tests cover all eight unauthorized routes, forged client
state/cookies, field validation/focus, generic bad-password error, real API login,
student count 1 from the synthetic database, unavailable metrics, period selectors,
all sidebar destinations, disabled PDF action/no file input, HttpOnly/Strict/path
cookie attributes, logout deletion/denial and server-side expiry overriding an
existing browser cookie. Console/page-error observations were empty in all three
complete navigation runs. Screenshot assertions also check no horizontal overflow.

Screenshots were taken only on empty login or authenticated pages; password entry,
raw credentials, traces and videos were not captured. Nine screenshots are under
`docs/evidence/phase04a/browser`. The 390px and 1440px dashboards and 834px PDF page
were visually inspected. Test users, sessions, events, seeded student and the ignored
temporary credential file were removed; see
[cleanup evidence](evidence/phase04a/fixture-cleanup.json).

Two preliminary full browser runs stopped on overly broad test locators: one also
matched Next.js's route announcer, the other matched retained hidden route content.
The assertions were scoped to the intended visible content; no application behavior
was weakened. Initial reports are preserved beside the final passing JSON. An
intermediate concurrent lint run hit ENOENT while Playwright replaced `test-results`;
generated Playwright directories now have explicit ESLint exclusions, and final lint
passed. These failures are distinguished from the final verified results.

Turbopack remains the supported default. No TypeScript or lint checks were disabled;
no functionality or Windows protection was removed. Webpack was not rerun in this
phase because the standard production build succeeded; Phase 02.5's comparison stays
in its original verification report.

## Known limitations and Phase 04B readiness

This is an admin foundation. MFA, password reset, additional-admin provisioning,
account-management UI, audit retention cleanup, edge request limits and per-client
rate-limit fairness are not implemented. An operator must create the first real
admin interactively; no deployment credentials were provided. Protect bootstrap host
access and audit records. Production proxy/HTTPS/cookie behavior still needs deployment
verification. Existing exam/payment/promo functions remain deliberately unavailable.

The protected PDF workspace is ready for a separately authorized Phase 04B. No PDF
processing or publishing work has started.

## Final acceptance decision

Phase 04A is accepted for the implemented local foundation. Secure bootstrap service,
admin authentication/revocation, protected API/pages, responsive navigation, truthful
dashboard states, migrations and existing regressions passed. All 196 automated tests
passed: 176 backend, five frontend unit, nine admin browser and six public browser
checks. The backend count includes its unit/integration tests.

No implementation blocker remains within Phase 04A. Operator first-admin creation
and public deployment verification remain setup responsibilities. Phase 04B remains
unimplemented and requires its own instruction.
