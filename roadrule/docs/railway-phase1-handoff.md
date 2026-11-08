# Railway production readiness handoff

Local changes only. Production deployment and connectivity remain unverified.

## Findings and local changes

The reported startup message comes from URL validation before a connection is attempted. Railway's documented stock URL uses the plain PostgreSQL scheme and the `postgres` role. Each independently fails the application's validator. Missing credentials or target fields, unsupported or repeated query options, and parse errors also fail. An HTTP 503 from readiness indicates a separate runtime connection failure. Its exact production cause needs a probe inside Railway.

The application accepts an existing dedicated role over the Railway private TCP network. Production still requires `sslmode=verify-full`. Startup now rejects explicit CA file paths that are relative, absent, unreadable, or invalid PEM. The SQLAlchemy production connection disables GSS encryption so libpq uses the configured TLS verification. The database diagnostic reports safe error categories and SQLSTATE instead of raw driver messages. No certificate or secret was added to the repository.

The existing Next.js route handler owns `/student-api/*` and translates secure guest cookies, applies origin and request controls, and forwards the API request. This checkout has no Vercel or Next.js rewrite. A regression test protects the checked-in routing. Verify project-level Vercel routing settings separately.

## Railway variables

Set these on the **production API service**, using the confirmed current public domains. The worker needs the same database and storage settings if deployed.

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | Use the format below |
| `ALLOWED_HOSTS` | `umuhanda-production.up.railway.app,healthcheck.railway.app` |
| `CORS_ALLOWED_ORIGINS` | `https://umuhanda.vercel.app` |
| `ENABLE_DOCS` | `false` |
| `MOCK_PAYMENTS_ENABLED` | `false` |
| `PDF_STORAGE_ROOT` | Existing persistent private storage path, if PDF imports are enabled |
| `TEST_DATABASE_URL` | Leave unset |

```text
postgresql+psycopg://<EXISTING_RUNTIME_ROLE>:<URL_ENCODED_PASSWORD>@<DB_PRIVATE_DNS>:<DB_PORT>/<EXISTING_PROD_DATABASE>?sslmode=verify-full&sslrootcert=<ENCODED_ABSOLUTE_CA_PATH>
```

Use a single private TCP hostname from the PostgreSQL service in the same Railway environment. Percent-encode reserved characters in credentials and the CA query value. Database names `roadrules_dev` and `roadrules_test` are reserved. Keep the URL in a secret variable. Check the effective URL in the deployed service without printing it. A stock database-service reference may still resolve to the default superuser and scheme.

Use an approved public CA bundle for the actual database certificate and supply it to the API, worker, and migration process at a stable, readable runtime path. Validate that the database certificate matches the chosen private hostname. An inherited libpq trust file or `sslrootcert=system` remains possible when explicitly verified inside the target runtime. Private DNS and Railway tunnel encryption alone do not establish database certificate trust. The example CA in the older runbook is absent from this checkout. Treat unavailable CA material or a hostname mismatch as a deployment blocker.

Railway's health check path should be `/api/v1/health`. Check database readiness separately at `/api/v1/health/ready`. Run Uvicorn with trusted forwarded headers for the actual Railway ingress and bind to `0.0.0.0:$PORT`. Restrict trusted proxy addresses to the deployment's ingress boundary. Production session and admin requests require HTTPS and an allowed Origin, and use Secure, HttpOnly cookies. Confirm Vercel has the intended backend and frontend origin values and serves the existing `/student-api` handler without a rewrite.

## Runtime role and migrations

Use an existing LOGIN runtime role with CONNECT to the existing database, USAGE on the application schema, and the SELECT, INSERT, UPDATE and DELETE privileges required on application tables. Grant sequence USAGE where needed and function EXECUTE where the deployment has removed the default privilege and the app requires the function. Arrange equivalent default privileges for future objects created by the migration owner. The runtime role should have no ownership, superuser, database or role creation, replication, or bypass-RLS privilege.

Use a separate authorized migration role with ownership or sufficient owner rights over the existing schema and objects. Preserve the existing database, history and migrations. If the runtime role, grants, or certificate are missing, have the operator review those changes separately. No role or database SQL is authorized by this local phase.

From the backend directory, using injected service variables, run:

```bash
python -c "from app.core.config import Settings; assert Settings().app_env == 'production'; print('Production settings valid')"
python scripts/diagnose_database.py
```

Require `connected=true` and `tls=True`, using the expected runtime role and database. Verify role privileges through the database operator. For migration review, inject the migrator's verified URL into a single release job. Take and verify a backup, then run `python -m alembic heads` and `python -m alembic current`. If behind, review the intervening migrations and run `python -m alembic upgrade head` only with release approval. Recheck `current` and run `python -m alembic check`. Never stamp or reset production to resolve a connectivity problem.

After an approved release, confirm liveness and readiness both return HTTP 200, docs are disabled, an unauthenticated student request is denied by the normal API path, and an approved session smoke test receives the Secure cookie. Keep credentials and session values out of logs.

## Git commands for the operator

```powershell
Set-Location D:/Roadrules/roadrule
git diff --check
git status --short
git add -- backend/app/core/config.py backend/app/db/session.py backend/scripts/diagnose_database.py backend/tests/unit/test_config.py tests/student-proxy.test.mjs tests/browser/phase02.spec.ts tests/browser/phase04k-image.spec.ts tests/browser/phase04l-real-pilot.spec.ts docs/railway-phase1-handoff.md docs/railway-production-recovery.md
git diff --cached --check
git diff --cached --stat
git commit -m "Harden Railway production database readiness"
# Run only after explicit approval. Pushing may trigger a deployment.
git push origin main
```

## Railway AI Agent brief

Inspect the existing production API variables and PostgreSQL target without printing secrets. Confirm the dedicated runtime login, grants, private DNS, existing database, and trusted CA path and hostname before preparing variable changes. Keep verified TLS and production host, origin, and cookie controls. Report the read-only diagnostic, migration revision, and any missing prerequisite. Stage and deploy only with explicit approval. Keep the existing Next.js student proxy in the request path.

## Local verification

- `python -m pytest -q --tb=short` passed all 261 backend tests against the isolated local PostgreSQL database, with the authentic source PDF available. The only warning was Starlette's TestClient deprecation.
- The final focused settings run passed 25 tests. It inspected the Psycopg connection arguments without opening a production connection.
- Ruff lint and formatting for the changed Python files passed. The full format check reported eight pre-existing files outside the change.
- `npm test` passed all 13 frontend tests. ESLint, `npm run typecheck`, and the Next.js 16.4.5 Turbopack production build passed. The build lists `/student-api/[...path]` as a dynamic route.
- The read-only diagnostic connected to `roadrules_test` as the local test role. That connection used the test environment's existing non-TLS configuration. It provides no evidence about the Railway CA, certificate hostname, or credentials.
- `python -m alembic heads` returned `20261106_0010`. Phase 1 adds no migration.
- At 1440px, all six admin Chrome cases passed in one run. All six student cases had passing evidence across the initial run and targeted reruns. Test fixes follow the current promo redirect, hide payment choices once access exists, read semantic exam progress, check the score and percentage separately, and scope the real pilot's no-payment assertion to its guest session. Student and admin application routes were unchanged.
