# Phase 03A — FastAPI and PostgreSQL foundation

## Acceptance decision

**Phase 03A backend foundation is accepted.** Real PostgreSQL and live HTTP checks
pass; the backend suite has **30 unit tests and 8 integration tests**, with no skips.
The existing frontend source and configuration are unchanged. No next-phase business
endpoint or frontend/backend integration was implemented.

The isolated local PostgreSQL cluster remains running at `127.0.0.1:55432` for development.
API smoke servers shut down cleanly after verification. See
[backend setup/run instructions](../backend/README.md).

## Files created and modified

Created under `backend/`:

- `pyproject.toml`, `requirements-lock.txt`, `.env.example`, `README.md`, `alembic.ini`.
- `app/main.py`: factory, lifespan, safe errors, controlled CORS and trusted hosts.
- `app/api/v1/router.py`, `health.py`: two versioned health endpoints.
- `app/core/config.py`: validated environment selection and secrets.
- `app/db/base.py`, `session.py`: SQLAlchemy 2 metadata, synchronous engine/pool/session DI.
- `app/schemas/health.py`: typed success/error contracts.
- Package initializers for app/api/core/db/schemas/models/repositories/services;
  business-layer packages are reserved boundaries, not implementations.
- `alembic/env.py`, `script.py.mako`, `versions/20261104_0001_baseline.py`.
- `scripts/local_postgres.py`, `setup_databases.py`: isolated cluster and preflighted,
  idempotent role/database setup; no database deletion/reset behavior.
- `scripts/verify_foundation.py`: read-only database audit plus real Uvicorn HTTP checks.
- `scripts/audit_local_secrets.py`: local credential/source/log audit without revealing secrets.
- `tests/conftest.py`, unit configuration/API/session tests and real PostgreSQL
  integration/migration tests.

Also created this report and sanitized evidence under `docs/evidence/phase03a/`.
The only existing source/control file intentionally edited is root `.gitignore`, adding backend caches, virtual
environment/data/secret exclusions and allowing the credential-free `.env.example`.
No frontend source, package dependencies or configuration was changed. Existing generated
browser screenshots/results were refreshed by the regression command; its Phase 03A
execution log and JSON result were saved separately.

Generated **ignored local state**, not source deliverables: `backend/.venv/`,
`backend/.env`, and `backend/.local/` containing the dedicated cluster and random
local credentials. No real credentials are included in this report or example files.
This workspace has no Git metadata; no commit was made. Ignore rules were added
explicitly, and public source/evidence were audited for the generated credential values.

## Installed dependencies and versions

Python **3.12.14** and PostgreSQL **18.6** were already available. The Windows Store
`python` alias was not used; a project virtual environment was created with the
available real Python interpreter.

| Dependency | Resolved version |
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

The complete transitive set is pinned in
[requirements-lock.txt](../backend/requirements-lock.txt). `pip check` reports no
broken requirements. Editable package metadata was refreshed after module creation.
Dependencies were installed through verified PyPI HTTPS without disabling TLS.

## Database setup and isolation

An isolated cluster was chosen to avoid changing the pre-existing PostgreSQL
installation and unrelated databases. The helper initializes only
`backend/.local/pgdata`, using UTF-8 and SCRAM authentication, loopback-only port
55432. A Windows subprocess-output inheritance issue was resolved by capturing
utility output in a file rather than a pipe; clean stop/start was then executed
successfully and database state survived.

| Database | Login role | Owner role (NOLOGIN) | State |
| --- | --- | --- | --- |
| roadrules_dev | roadrules_dev_app | roadrules_dev_owner | UTF8; baseline only |
| roadrules_test | roadrules_test_app | roadrules_test_owner | UTF8; baseline only |

Both login roles were verified to lack SUPERUSER, CREATEDB, CREATEROLE,
REPLICATION and BYPASSRLS. They are not members of database-owner roles. Each
receives CONNECT/TEMPORARY only on its own database and USAGE/CREATE only on its
application schema for local migrations. PUBLIC access is revoked on these
dedicated resources. Read-only checks confirm neither login can connect to the
other database. No existing database was dropped, overwritten or adopted.

Setup is repeatable for resources it owns, uses ownership/comment markers and
refuses unrecognized existing resources. It does not rotate existing passwords or
overwrite `.env`. See [repeat-setup result](evidence/phase03a/database-setup-repeat.log).

SQLAlchemy is synchronous throughout, uses pre-ping, bounded pooling, connect/pool/
statement timeouts and hidden SQL parameters. Engines do not connect at app startup,
so liveness survives an unavailable DB. Per-request sessions close and roll back
uncommitted work; exceptions trigger rollback and are re-raised into safe handling.
Future services must deliberately commit approved writes.

## Health, readiness and live startup results

Real Uvicorn listeners were started, queried over TCP through HTTPX and shut down
gracefully. This supplements TestClient coverage; it is not a mocked startup claim.

| Condition | GET /api/v1/health | GET /api/v1/health/ready |
| --- | --- | --- |
| PostgreSQL available | 200 `{"status":"ok"}` | 200 `{"status":"ready"}` after SELECT 1 |
| PostgreSQL unavailable (reserved, non-listening port) | 200 `{"status":"ok"}` | 503 safe DATABASE_UNAVAILABLE envelope |

`/docs` and `/openapi.json` returned 200 in development/testing. OpenAPI exposes
only the two health paths. Production docs are disabled by default. No credential,
driver traceback or request input is reflected in safe 422/500/503 responses.

Live/database/version evidence:
[foundation-verification.json](evidence/phase03a/foundation-verification.json).

## Alembic results

Settings select the migration target; no URL is embedded in `alembic.ini` or printed.
The baseline `20261104_0001` intentionally contains no business DDL. The only table
present in each database is `alembic_version`, recording that revision.
`Base.metadata.create_all()` is never used for application schema management.

Executed against `roadrules_test`:

- `python -m alembic upgrade head` and repeated upgrade: successful.
- `python -m alembic current`: `20261104_0001 (head)`.
- Integration roundtrip: downgrade to base, upgrade, repeat upgrade, check revision,
  `alembic check`, downgrade and restore head: successful.
- Invalid revision request: raises CommandError and leaves the baseline intact.

The dedicated development database was separately initialized with the empty
baseline as a setup operation; tests never select it for migrations or writes.
Testing always selects TEST_DATABASE_URL and checks both URL and connected identity.
URL parameters cannot override database/host/user. Missing integration settings or
an incorrect identity fail explicitly. Temporary rollback probes are connection-local
and are cleaned up; no persistent test data/business tables remain.

The current empty baseline downgrade removes the version row without deleting a
database. No safety claim is made for future data-bearing downgrades.

## Automated validation

Commands below were executed from `backend/` with `.venv/Scripts/python.exe`:

| Command | Result | Evidence |
| --- | --- | --- |
| `python -m pytest tests/unit -q` | 30 passed | [unit log](evidence/phase03a/unit-tests.log) |
| `python -m pytest tests/integration -q` | 8 passed; real PostgreSQL | [integration log](evidence/phase03a/integration-tests.log) |
| `python -m pytest -q` | 38 passed, 0 skipped | [combined log](evidence/phase03a/all-tests.log) |
| `python -m ruff check .` | Passed | [Ruff log](evidence/phase03a/ruff.log) |
| `python -m ruff format --check .` | Passed | [format log](evidence/phase03a/ruff-format.log) |
| `python -m pip check` | No broken requirements | [dependency log](evidence/phase03a/dependency-check.log) |
| `python scripts/verify_foundation.py` | Live HTTP and DB audit passed | [JSON evidence](evidence/phase03a/foundation-verification.json) |

Coverage includes health independence, real readiness success and failure, safe
response contracts, input/error sanitization, CORS allow/deny/method behavior,
trusted hosts, environment validation and secret redaction, production defaults,
session lifecycle/disposal, real rollback on both exception and uncommitted success,
database identity/encoding/permissions and Alembic state/repeatability/failure.

One reported, unsuppressed warning comes from Starlette 1.10.0's TestClient:
HTTPX-based transport is deprecated in favor of HTTPX2. HTTPX 0.28.1 is installed
as requested and all tests pass. This is not an application exception or a skipped
integration test. The restricted Windows runner stalled the initial TestClient run;
the completed suites used reviewed local socket/process access.

## Frontend regression verification

Forty frontend source/configuration files were SHA-256 hashed before backend work;
all forty hashes remain identical. See
[frontend-integrity.json](evidence/phase03a/frontend-integrity.json) and its baseline.

From the frontend project root:

- `npm test`: 5 passed; [log](evidence/phase03a/frontend-unit-tests.log).
- `npm run build`: successful Next.js production build with TypeScript enabled;
  `/`, `/tangira` and `/exam` prerendered; [log](evidence/phase03a/frontend-build.log).
- `npm run test:browser`: all 6 existing production browser tests passed at 390px,
  834px and 1440px; no skipped or flaky cases, console/application/network error arrays
  empty; [log](evidence/phase03a/frontend-browser.log),
  [JSON results](evidence/phase03a/frontend-browser-results.json).

No browser request to the backend was added. The student payment/promo adapters
remain unavailable and exam entry remains locked as in Phase 02.

## Security verification

- Dedicated SCRAM-authenticated local application roles; no superuser runtime DSN.
- Separate test credentials and explicit test target validation; no dev fallback.
- SecretStr configuration, redacted validation, hidden SQL parameters, no DSN logging.
- Safe handled errors including unexpected errors before raw server traceback logging.
- Explicit origins, trusted hosts, no credentialed CORS or wildcard origin access.
- Production requires certificate-verified PostgreSQL TLS, non-local explicit hosts
  and HTTPS CORS origins; local development defaults cannot silently authorize production.
- No PIN, JWT, administrator login, payment authorization or frontend access grant.
- Generated real credentials live only in ignored `.env`/`.local` files. A local audit
  checks their actual values against public source/documentation and saved logs without
  printing them: **zero plaintext credential matches** in the audited files;
  [sanitized audit](evidence/phase03a/security-audit.json).

Local NTFS permissions and backups must protect `.env` and `.local`; no production
secrets are provisioned by this foundation. Application roles have local DDL permission
for Alembic; production needs separately provisioned runtime/migrator privileges.

## Known limitations and recommended Phase 03B

This is a local, production-oriented foundation, not a deployed production service.
The alternative existing-server provisioning path and other operating systems were
documented but not executed. PostgreSQL on loopback uses SCRAM without TLS locally;
production requires verified TLS. The optional cluster remains running for development;
its stop command preserves data. API verification servers were stopped cleanly.

Starlette's test-transport deprecation is the only reported test warning. No required
integration tests were skipped. No authentication, business tables, student sessions,
payment integration, exam engine, admin interface or frontend integration is present.

Recommended separately approved Phase 03B: design the student-session schema and
API contract, expiry/scope rules, input validation and abuse controls, then implement
them through reviewed migrations and isolated integration tests. Payment, promo and
exam authorization must remain unavailable until their own server verification is
approved and implemented. No subsequent phase has been started.
