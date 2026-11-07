# Road Rules API — Phase 04B

Separate synchronous FastAPI backend with health checks, persistent student guest
sessions, administrator authentication and dashboard reporting. Student onboarding
requires no account, email or password; guest identity does not grant payment, exam
or administrator authorization. The Next.js admin UI integrates through server-only
requests. See [Phase 03B](../docs/phase03b-student-sessions.md) for guest sessions and
[Phase 04A](../docs/phase04a-admin-dashboard.md) for administrator setup and verification.

## Verified environment and dependencies

Python **3.12.14**, PostgreSQL **18.6**, Windows PowerShell. Python 3.11+ is required;
this environment uses the available bundled Python 3.12 rather than the Windows
Store launcher alias. Runtime/QA dependencies resolved as follows:

| Dependency | Version |
| --- | --- |
| FastAPI | 0.162.0 |
| Uvicorn | 0.54.0 |
| SQLAlchemy | 2.0.57 |
| Psycopg / psycopg-binary | 3.3.8 |
| Alembic | 1.20.1 |
| Pydantic | 2.14.2 |
| pydantic-settings | 2.16.2 |
| Pytest | 9.2.0 |
| HTTPX | 0.28.1 |
| Ruff | 0.17.3 |

[`requirements-lock.txt`](requirements-lock.txt) pins the complete resolved runtime
and QA dependency graph. `pyproject.toml` declares compatible major-version ranges
and setuptools package discovery. The app package installs independently of the frontend.

## Create and install the environment

From `D:\Roadrules\roadrule\backend` with an installed Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python -m pip install -e ".[dev]" --no-deps
python -m pip check
```

The Python actually available and used on this machine is:

```powershell
$PythonExe = 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $PythonExe -m venv .venv
```

Do not recreate an existing working environment just to activate it. If PowerShell
blocks activation, call `.\.venv\Scripts\python.exe` directly for every command;
no execution-policy change is needed. For a new deployment, use its own maintained
Python installation and recreate the virtual environment there.

## Dedicated local PostgreSQL setup

The optional helper uses PostgreSQL binaries already installed at
`C:\Program Files\PostgreSQL\18\bin`; override `POSTGRES_BIN` for another installation.
It manages only `backend/.local/pgdata`, bound to **127.0.0.1:55432**, with SCRAM
password authentication and UTF-8 encoding. It does not register a Windows service
or change the existing PostgreSQL installation/service/database cluster.

```powershell
python scripts/local_postgres.py start
python scripts/setup_databases.py
# Both commands are safe to repeat for resources created by these helpers.
python scripts/local_postgres.py status
```

The first start generates a random bootstrap administrator password in ignored
`.local/admin.json`. Setup generates separate random application passwords in
ignored `.local/application-passwords.json` and writes `.env` only if absent.
There are no default real passwords and no password-bearing command-line arguments.
The temporary `initdb` password file is removed after initialization.
Existing `.env` content and existing role passwords are preserved. If those local
credential files are lost, deliberate administrator recovery/rotation is required;
the helper does not silently reset passwords.

Setup preflights names and ownership markers. Unrecognized existing databases or
roles cause a failure, not adoption, deletion or overwrite. It never drops databases.
An interrupted partial setup can be rerun; unknown/nonempty cluster directories
are deliberately not cleared automatically.

For an existing server instead, a PostgreSQL administrator may supply an admin URL
through the process environment and run the same preflighted database setup:

```powershell
# PowerShell 7: keeps input out of terminal echo/history. Never paste credentials into source.
$env:ADMIN_DATABASE_URL = Read-Host -MaskInput 'Administrative PostgreSQL URL'
python scripts/setup_databases.py
Remove-Item Env:ADMIN_DATABASE_URL
```

Use only an authorized development server. Check its statement/audit logging policy
before provisioning role credentials; the provided isolated cluster disables SQL
statement logging. This alternative was not used for the verified installation.
Local helper start/stop always applies only to the project cluster, not that server.

### Database and role permissions

| Database | Backend/migration login | Database/schema owner |
| --- | --- | --- |
| roadrules_dev | roadrules_dev_app | roadrules_dev_owner (NOLOGIN) |
| roadrules_test | roadrules_test_app | roadrules_test_owner (NOLOGIN) |

Application roles have CONNECT and TEMPORARY on their own database and USAGE/CREATE
on its public schema for local Alembic development. They have no SUPERUSER,
CREATEDB, CREATEROLE, REPLICATION or BYPASSRLS and no membership in owner roles.
PUBLIC database and schema privileges are revoked on these two dedicated databases;
each application role is unable to connect to the other database. No unrelated
database ACL is modified. The bootstrap administrator is never an application DSN.

These are local development/migration grants. Before production, provision separate
migrator and runtime roles, removing DDL privileges from the runtime role and
granting only approved table/sequence access. Production database ownership and
credential rotation are deployment responsibilities, not an implemented admin API.

## Configuration

For manual setup, copy `.env.example` to `.env` and fill in dedicated URLs.
The helper-generated `.env` is already ready for local use. Never print or commit it.
Settings load `backend/.env` regardless of working directory; process environment
variables override it. Unknown `.env` fields and invalid settings fail validation.

| Variable | Behavior |
| --- | --- |
| APP_ENV | development (default), testing, production |
| APP_NAME | API title; default Road Rules API |
| DATABASE_URL | Required for development/production, `postgresql+psycopg://...` |
| TEST_DATABASE_URL | Required in testing; only roadrules_test as roadrules_test_app |
| CORS_ALLOWED_ORIGINS | Comma-separated or JSON array; default empty; explicit HTTP(S) origins only |
| ALLOWED_HOSTS | Comma-separated or JSON array; default localhost,127.0.0.1; no wildcard |
| ENABLE_DOCS | Optional explicit bool; defaults true outside production, false in production |
| DB_POOL_SIZE / DB_MAX_OVERFLOW | Default 5 / 5, bounded at 20 each |
| DB_POOL_TIMEOUT | Default 5 seconds |
| DB_CONNECT_TIMEOUT | Default 3 seconds |
| DB_STATEMENT_TIMEOUT_MS | Default 5000 milliseconds |
| GUEST_SESSION_LIFETIME_SECONDS | Absolute lifetime, default 7200 (60–86400) |
| GUEST_SESSION_IDLE_SECONDS | Persisted inactivity limit, default 1800 (30–86400) |
| GUEST_SESSION_TOUCH_SECONDS | Minimum activity-write interval, default 60 (1–300); must be below idle limit |
| GUEST_COOKIE_SAMESITE | lax (default) or strict; none is rejected |
| SESSION_CREATION_LIMIT | Database-wide session budget per window, default 30 |
| SESSION_CREATION_WINDOW_SECONDS | Sliding creation window, default 60 seconds |

In testing, the selected DSN is always TEST_DATABASE_URL; DATABASE_URL is never a
fallback. URL query parameters cannot override the database, role or host: only
explicit TLS options are allowed. Integration fixtures check the *connected*
database/user before any migration or test writes. Missing integration prerequisites
fail tests rather than skip them.

Production rejects development/test database names, requires `sslmode=verify-full`,
explicit non-local allowed hosts and non-local HTTPS CORS origins if any are enabled.
It never inherits a permissive localhost CORS allowlist or debug mode. Configure a
trusted PostgreSQL CA via `sslrootcert` where needed. Database secrets use SecretStr,
are excluded from settings repr and are not included in validation error text.

## Run and inspect the API

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log --no-proxy-headers
```

`--no-access-log` avoids recording future sensitive query strings unnecessarily.
The application never logs raw database exceptions, URLs, request input or credentials.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
# Open http://127.0.0.1:8000/docs or /redoc in development.
```

| Endpoint | Success | Database unavailable |
| --- | --- | --- |
| GET /api/v1/health | 200 `{"status":"ok"}` | Still 200; no DB access |
| GET /api/v1/health/ready | 200 `{"status":"ready"}` after real SELECT 1 | 503 `{"error":{"code":"DATABASE_UNAVAILABLE","message":"Database service is unavailable."}}` |

OpenAPI is available at `/openapi.json` when docs are enabled. Request validation
uses Pydantic and a safe 422 error envelope. Unexpected errors return a safe 500
without raw exception detail or server traceback leakage. CORS allows GET/POST,
only explicit origins, and credentialed requests for the guest cookie.
Allowed error responses receive CORS headers as well. CORS is not authentication.

## Alembic schema management

No startup `create_all()` is used. `db/base.py` owns declarative metadata;
`alembic/env.py` selects a validated environment-specific DSN without writing it
into Alembic configuration or logs. The intentionally empty `20261104_0001`
baseline remains unchanged. The additive `20261104_0002` migration adds only
`students`, `guest_sessions` and `student_activity_events`. Models are registered
through `app/models/__init__.py` for metadata comparison.

```powershell
# Development upgrade only: no automatic downgrade or data deletion:
$env:APP_ENV = 'development'
python -m alembic upgrade head
python -m alembic current

# Test-only migration verification:
$env:APP_ENV = 'testing'
python -m alembic upgrade head
python -m alembic current
python -m alembic check
# DESTRUCTIVE verification only on the disposable test DB with empty approved tables:
python -m alembic downgrade 20261104_0001
python -m alembic upgrade head
Remove-Item Env:APP_ENV
```

Downgrading Phase 03B drops its three tables. Never run that command on development
data without explicit authorization and backups. The integration suite guards the
connected test identity, approved table set and empty tables before roundtrips.
Failure produces a nonzero command exit; do not continue or stamp a failed migration
as successful. Integration tests verify downgrade/upgrade/repeat-upgrade and metadata
state against roadrules_test and refuse the roundtrip if an unexpected table exists.

## Tests and quality checks

```powershell
python -m pytest tests/unit -q
python -m pytest tests/integration -q
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m pip check
python scripts/verify_foundation.py
python scripts/verify_guest_sessions.py
python scripts/audit_local_secrets.py
```

The verification command performs a real HTTP Uvicorn smoke check (healthy and refused DB
connection), read-only audits of both dedicated databases, and graceful server
shutdown. It saves sanitized evidence in `docs/evidence/phase03a/`. Test data uses
connection-local temporary tables and rollback plus explicit test-only cleanup of the
three approved tables; tests do not modify the development database. Cleanup has no
CASCADE and rejects unknown tables. Migration tests leave revision `20261104_0002`
at head with the three empty approved tables in roadrules_test. The guest verification
script uses synthetic test records, deletes only those records and records no tokens.
The audit command checks actual generated credential values against public source
and saved logs, emits no secrets, and fails if it finds a match outside intended storage.
It also checks historical credential-shaped PostgreSQL diagnostics against active
guest verifiers, reporting counts only. Constraint-negative tests use non-credential
sentinels so rejected-row DETAIL diagnostics never receive a live test token.

On this Codex Windows host, test-client event loops, PostgreSQL and server tests
need normal local socket/process access. Use reviewed execution permission when
the restricted runner denies it; do not weaken Windows security or PostgreSQL auth.

The installed Starlette test client emits a deprecation warning for HTTPX 0.28.1
and recommends HTTPX2. The requested HTTPX-based suite currently passes; the warning
is reported, not suppressed. Revisit that test transport in a future dependency update.

After development, stop only the optional project cluster if desired:

```powershell
python scripts/local_postgres.py stop
```

Stopping preserves all data. No automatic deletion/reset command is supplied.

## Architecture and security boundaries

- `main.py`: application factory, resource lifespan, safe errors, CORS and trusted hosts.
- `api/v1`: versioned health endpoints; synchronous handlers for database work.
- `core/config.py`: environment validation and secret-safe DSN selection.
- `db/session.py`: synchronous Psycopg SQLAlchemy engine, bounded pre-ping pool,
  session dependency, rollback on exceptions and close/rollback on uncommitted success.
  Services must explicitly commit intended future writes; no automatic request commit.
- `models/student_sessions.py`: approved tables and constraints.
- `repositories/student_sessions.py`: synchronous queries and database locks.
- `services/student_sessions.py`: atomic creation, lifecycle and shared creation budget.
- `core/session_security.py`: opaque credentials, cookie policy and origin/CSRF guards.
- `schemas`: response contracts; Alembic owns schema changes.

`.env`, `.venv`, `.local` (including credentials, data and PG logs), Python caches and
package artifacts are ignored. Only `.env.example` is allowed as a template. Protect
local files with appropriate NTFS access permissions and do not share their contents.
There are no production secrets or API keys in the supplied source.

This phase authenticates possession of a guest credential only. It does not verify
phone ownership/person identity, verify payments or
provide protected exam content. The frontend remains unavailable/locked as before.

## Guest session API and browser security

| Endpoint | Behavior |
| --- | --- |
| POST /api/v1/students/sessions | 201; atomically creates a new student/session and two audit events, then sets cookie |
| GET /api/v1/students/sessions/me | 200 with authenticated student summary; otherwise generic 401 |
| POST /api/v1/students/sessions/revoke | 204, revokes current session and deletes matching cookie |

Creation accepts only `fullName` and `phoneNumber`. Names normalize Unicode/whitespace
and permit letters, combining marks and name separators, at most 120 normalized
characters. Phones normalize to `+2507XXXXXXXX`; supported mobile ranges are
72/73/77/78/79, independently of payment provider. Same name/phone submissions create
distinct student records. They are not proof of the same person.

Creation and `/me` return `studentId`, `sessionReference`, `fullName`,
`maskedPhoneNumber`, absolute `expiresAt` and `accessGranted: false`. IDs never
authenticate. Raw phone numbers, credentials and token hashes are not returned.
All session responses, including errors, are `Cache-Control: no-store`.

Tokens are 32 CSPRNG bytes encoded as 43 URL-safe characters. Only SHA-256 verifiers
are stored in PostgreSQL. Creation issues the credential only after commit. Cookies
are HttpOnly, host-only, Path `/api/v1`, SameSite=Lax by default. Production uses
`__Secure-roadrules_guest` with Secure; development uses `roadrules_guest` on local
HTTP. Production session requests over HTTP are rejected. Deletion uses identical
cookie scope/security attributes. No token appears in JSON, URLs or browser storage.

Use **localhost consistently** for frontend `http://localhost:3000` and API
`http://localhost:8000`. Different ports are cross-origin but same-site; do not mix
localhost and 127.0.0.1 as browser hosts. Cookies are not isolated by port. Production
expects same-site HTTPS app/API hosts and a host-only API cookie; unrelated-site
third-party-cookie deployment is intentionally unsupported. No Domain is set.

Future browser requests must use `credentials: "include"`. Every POST requires an
exact allowlisted `Origin` and `X-CSRF-Protection: 1`; cross-site Fetch Metadata,
missing/null/untrusted/duplicate origins and ambiguous CSRF headers are rejected
before service execution. The header is a non-secret custom-header CSRF mechanism,
not a bearer credential. CORS permits that header only to the strict allowlist.
GET `/me` rejects untrusted Origins/cross-site metadata as well. This policy must
be extended deliberately to future payment routers; guest identity alone grants no
payment/exam privilege. Origin is never inferred from untrusted proxy/Host headers.

PowerShell example against a running local API (use synthetic data):

```powershell
$headers = @{ Origin = 'http://localhost:3000'; 'X-CSRF-Protection' = '1' }
$payload = @{ fullName = 'Jean Claude'; phoneNumber = '0781234567' } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/v1/students/sessions -Method Post `
  -Headers $headers -ContentType 'application/json' -Body $payload -SessionVariable Guest
Invoke-RestMethod http://localhost:8000/api/v1/students/sessions/me -WebSession $Guest -Headers $headers
Invoke-WebRequest http://localhost:8000/api/v1/students/sessions/revoke `
  -Method Post -WebSession $Guest -Headers $headers
```

The cookie stays in the client cookie jar; do not print it or store it in source.
Swagger POST testing also needs these headers; to use Swagger's own browser origin,
add its exact origin explicitly to the allowlist rather than weakening the guard.

PostgreSQL `clock_timestamp()` after session row locking is authoritative. Absolute
expiry is immutable; inactive sessions expire after their persisted activity timeout.
Valid reads touch activity at most once per configured interval; this can expire an
idle session up to one touch interval earlier than its last unpersisted read, never
later than the absolute deadline. Row locks serialize touches/revokes and prevent
state resurrection. No frontend timer is trusted. Expiration audit events are written
once on first observed expiry, not by a background job.

Missing credentials on repeat logout are a no-op 204; already-revoked valid credentials
also return 204. Invalid credentials and expired credentials receive 401. `/me` always
rejects revoked/expired credentials. A fresh application instance can resolve the same
active credential from PostgreSQL; there is no in-memory authentication authority.

## Abuse prevention, audit and retention

Creation has a **durable, global database-wide** sliding budget backed by indexed
SESSION_CREATED audit events and a PostgreSQL transaction advisory lock. It applies
across independent application instances/workers. Contention or exhaustion returns
429 with Retry-After. Transactions use READ COMMITTED so the count sees the preceding
committed creator; quota checking, student/session creation and events commit together.
Revocation and deleting identities cannot reset the current event budget. No IP or
client-supplied forwarded header is used for quota keys.

The global cap protects against unlimited database growth rate but does not provide
per-client fairness: one attacker can consume the whole budget. Production still
needs edge request/body-size limits and a reviewed per-client policy. If deploying
behind a proxy, trust only explicitly configured proxy addresses and reject spoofed
forwarded headers at the edge; never use wildcard forwarded-header trust. Keep
pool/worker counts within PostgreSQL capacity. No in-memory limiter is presented as
distributed protection.

Audit rows contain only UUID references, one of STUDENT_CREATED/SESSION_CREATED/
SESSION_REVOKED/SESSION_EXPIRED and a UTC timestamp. No token, token hash, phone,
name, PIN or IP is an audit field. Student deletion cascades its sessions and nulls
audit references while preserving minimal events. No automatic PII retention/deletion
job is implemented. Approve retention/erasure policies before production, including
student records, expired verifiers and audit rows; preserve SESSION_CREATED events
for at least the active rate window so cleanup cannot reset protection. Session
expiration is enforced without waiting for a cleanup job.

Do not log request bodies, Cookie, Set-Cookie, authorization headers or raw database
errors in application/proxy/APM configuration. Runtime verification checks that its
credential is absent from JSON and observed local logs. No new packages or secrets
were needed in Phase 03B.

Primary references: [FastAPI yield dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/),
[SQLAlchemy session transactions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html),
[Psycopg installation](https://www.psycopg.org/psycopg3/docs/basic/install.html),
[Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).

## Phase 04A admin foundation

Run migrations against the configured existing database, then create the first
administrator from an interactive local terminal:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe scripts/bootstrap_admin.py --confirm-first-admin
```

Supply your own name, email and passphrase (15–256 characters). The password is
hidden, confirmed and hashed with Argon2id; no default account exists. Bootstrap is
one-time, serialized and remains consumed even after administrator deletion.
Do not delete audit markers to bypass it. There is no signup or second-admin API.

Admin API: POST `/api/v1/admin/auth/login`, GET `/api/v1/admin/auth/me`, POST
`/api/v1/admin/auth/logout`, GET `/api/v1/admin/dashboard/summary`. POSTs require
an allowed exact Origin and `X-CSRF-Protection: 1`. The separate admin cookie has
path `/api/v1/admin`, HttpOnly, SameSite Strict and Secure in production. Opaque
sessions are database verified with eight-hour absolute and 30-minute idle expiry.
Login has a durable global budget of 20 attempts/minute, including failures.

Only `totalStudents` is implemented; other summary fields are null. Payment, promo, exam generation and public administration remain outside this API.
See [Phase 04A report](../docs/phase04a-admin-dashboard.md) for architecture,
frontend server-only integration, test evidence and deployment limitations.

## Phase 04B PDF import

Install `.[dev]` again in the existing environment to add PyMuPDF, then run
`python -m alembic upgrade head`. Start the API and run
`python scripts/pdf_worker.py` in a second terminal. Both use the same private
`PDF_STORAGE_ROOT` and existing database. The default storage is `.local/pdf-storage`.
For deployment, mount the same persistent private volume at `PDF_STORAGE_ROOT`
for both the API and a supervised worker running `python scripts/pdf_worker.py`.
Persist PostgreSQL separately and back up the database and storage together.
Keep the storage directory outside web roots and restrict writes to the API
and worker service accounts. Configure the volume once per environment.

Each successful admin upload writes a generated storage key and a durable
import job. The worker discovers registered sources automatically, repairs
missing job records, and resumes interrupted imports after restart. It checks
the registered file's length and SHA-256 before extraction. Files placed on
disk without an authenticated upload record are ignored. A matching admin
re-upload restores missing or damaged bytes under the original key. New
documents create new revisions and the existing readiness checks govern bank
replacement. Historical source files must remain on the persistent volume.
The upload and repair entry point requires an authenticated administrator.
There is no destructive source-file deletion endpoint.

Use `--once` to drain currently queued jobs and exit. Review uploads and drafts at
`/admin/pdf-uploads`. See [API and operations details](../docs/phase04b-pdf-import.md).

## Automatic exam bank

The PDF worker automatically validates source evidence and activates ready banks.
The default `DIFFICULTY_BALANCED` policy requires source difficulty labels for
the 7 hard, 4 medium, and 9 easy selection. For a category mix, configure
`EXAM_SELECTION_POLICY=CATEGORY_BALANCED` and
`EXAM_CATEGORY_ROAD_SIGN_COUNT` on the worker. The minimum default is one sign
question. The other questions fill the 20-item exam. These counts are fixed in
each new bank revision. Legacy policy names remain valid for older revisions.
The protected dashboard reports bank readiness. The timed exam starts with a verified entitlement. [Phase 04C report](../docs/phase04c-automatic-exam-bank.md)


## Development payments and promo codes

The backend can issue single-exam grants from an administrator promo code
or a local synthetic payment. Mock payments are off by default. The Phase 04D
report describes configuration, settlement and security checks.
[Phase 04D report](../docs/phase04d-mock-payments-promos.md)


## Timed examination

Students can confirm an exam from a verified grant and resume the same
attempt on refresh. PostgreSQL controls deadlines and finalization.
[Phase 04E report](../docs/phase04e-timed-examination.md)
## Phase 04F exam results

Upgrade the configured database before starting the new backend:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic check
```

Exam completion and grading share one transaction. The backend scores the retained
PDF-backed questions and finalized selections, and stores an immutable result.
Use the authenticated result endpoint for an individual timed attempt and the
authenticated history endpoint for that guest session's saved grades. The admin
reporting endpoints use the existing administrator cookie. See
[Phase 04F verification](../docs/phase04f-exam-results.md) for contracts and evidence.

On a fresh installation, create the first administrator from an interactive local
terminal in the backend directory after applying migrations:

```powershell
.venv/Scripts/python.exe scripts/bootstrap_admin.py --confirm-first-admin
```

Enter your administrator name, email and passphrase at the prompts. The passphrase
entry is hidden and confirmed interactively. Existing installations keep their
administrator records. Keep operator credentials and local environment files private.
