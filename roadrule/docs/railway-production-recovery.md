# Railway production recovery runbook

Status: **diagnosis and repository fixes only. Live recovery is not verified.**
The production API will stay unhealthy until the configuration changes below are
applied and the fixed code is deployed. Do not claim recovery from a local test.

## 1. Recorded production evidence (2026-11-08)

| Check | Result |
| --- | --- |
| `GET https://umuhanda-production.up.railway.app/api/v1/health` | `200 {"status":"ok"}` |
| `GET .../api/v1/health/ready` | `503 DATABASE_UNAVAILABLE` |
| `GET .../docs` and `.../openapi.json` | `200` |
| OpenAPI cookie names | `roadrules_guest` / `roadrules_admin` (not `__Secure-...`) |
| Invalid-shaped admin login | `503`, not `401` |
| `/ready` latency minus `/health` latency | about `0.14 ms` |

What this proves:

- The API process, listener, router and liveness path are healthy.
- Every database-backed route fails, including admin login, so this is not a
  missing-table or migration-readiness symptom.
- The near-zero added latency indicates an immediate connection failure
  (refused/DNS/auth/TLS), not a PostgreSQL connect timeout.
- The live deployment is running non-production settings because docs are
  enabled and cookies are not `__Secure-`. `APP_ENV` is therefore not
  `production` (most likely `development`, the default).

What is still unknown: the exact `DATABASE_URL` host/port/role/TLS error. The
public 503 response is intentionally generic and there is no Railway environment
or log access from this workstation. Do **not** guess the final cause before
running the diagnostic in section 7.

A leading hypothesis is that the Railway service inherited local development
values (for example a DSN pointing at `127.0.0.1:55432`). That reproduces the
same immediate-refusal shape, but it is not confirmed.

## 2. Repository fixes included with this runbook

- `TrustedHostMiddleware` is enabled again using only validated
  `settings.allowed_hosts`. Hardcoded `*.vercel.app` and localhost entries were
  removed.
- CORS uses only `settings.cors_allowed_origins`. Hardcoded Vercel and localhost
  origins were removed.
- Session/admin Origin checks use only `settings.cors_allowed_origins`; the
  hardcoded Vercel domain was removed.
- SQLAlchemy failures now log sanitized routing/error-class/SQLSTATE diagnostics
  (never exception text, DSNs or credentials).
- `backend/scripts/diagnose_database.py` performs a read-only connectivity check.
- `backend/scripts/diagnose_database.py` and `backend/scripts/pdf_worker.py` add
  the backend root to `sys.path`, so direct `python scripts/<name>.py` commands
  resolve the `app` package without relying on an editable install.
- Unit and integration tests cover strict trusted hosts, strict CORS, sanitized
  logging, and the PDF worker restart path.

These changes take effect only after they are committed, pushed and deployed.
They do not by themselves repair the database connection.

## 3. Exact Railway variables for the API service

> **Deployment-order warning.** The fixed code re-enables strict host
> validation. If the current non-production deployment has no explicit
> `ALLOWED_HOSTS`, deploying the code first makes every public request return
> `400 Invalid host header`, including the health check. Set `ALLOWED_HOSTS`
> (and the other variables below) **before** pushing/deploying the fixed code.

Set these in the **API service** (not the PostgreSQL service):

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `DATABASE_URL` | `postgresql+psycopg://roadrules_runtime:<URL_ENCODED_PASSWORD>@<PRIVATE_DB_HOST>:5432/<PROD_DB>?sslmode=verify-full&sslrootcert=certs/railway-postgres-root.crt` |
| `ALLOWED_HOSTS` | `umuhanda-production.up.railway.app,healthcheck.railway.app` |
| `CORS_ALLOWED_ORIGINS` | `https://umuhanda.vercel.app` |
| `ENABLE_DOCS` | `false` |
| `MOCK_PAYMENTS_ENABLED` | `false` |
| `PDF_STORAGE_ROOT` | The persistent private volume used by both API and PDF worker, if PDF imports are enabled |

Rules for `DATABASE_URL`:

- Use the PostgreSQL service's **private** host (`<service>.railway.internal`),
  not the public TCP proxy. The private network avoids egress and is the host
  covered by Railway's database certificate.
- Convert Railway's `postgresql://` scheme to `postgresql+psycopg://`.
- Do **not** use the Railway `postgres` superuser or `root`. Create a dedicated
  role (section 5).
- URL-encode the password if it contains `@`, `/`, `:`, `#`, `?` or `%`.
- The database name must not be `roadrules_dev` or `roadrules_test`; production
  validation rejects those names.
- Do not set `TEST_DATABASE_URL` in production.
- `sslmode=verify-full` is mandatory and must not be relaxed to `require`,
  `verify-ca` or `disable` to work around a certificate problem.

Add `healthcheck.railway.app` to `ALLOWED_HOSTS`. Railway health checks use that
Host header; without it, the deploy fails with HTTP 400 even though the app is
healthy. Add every custom backend domain to the same list; wildcards and
localhost are rejected by production validation.

### Start command and proxy headers

Use a start command equivalent to:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
  --proxy-headers --forwarded-allow-ips="*" --no-access-log
```

`--proxy-headers` is required in production. Railway terminates TLS at its edge,
so the container sees HTTP unless it trusts the forwarded scheme. Without it,
production session and admin requests return `403 ORIGIN_REJECTED` because
`session_security.py` requires HTTPS when secure cookies are enabled.

`--forwarded-allow-ips="*"` is acceptable only because the API service is
reachable exclusively through Railway's proxy. If you expose the container
directly, replace `*` with the proxy addresses you control or remove direct
exposure. Never combine wildcard proxy trust with a publicly reachable container
port.

### Health check path

Configure the Railway health check path as **`/api/v1/health`**, not
`/api/v1/health/ready`. Liveness must not depend on PostgreSQL during a deploy;
otherwise a database maintenance window blocks every release.

## 4. Required host and origin values

`ALLOWED_HOSTS`:

```text
umuhanda-production.up.railway.app,healthcheck.railway.app
```

`CORS_ALLOWED_ORIGINS`:

```text
https://umuhanda.vercel.app
```

The same origin list is used by the session/admin CSRF guard. If the frontend
moves to a custom domain, add that exact HTTPS origin here and update the
frontend's `ADMIN_API_ORIGIN` / `STUDENT_API_ORIGIN`. Do not add paths,
wildcards, localhost or plain HTTP.

## 5. PostgreSQL roles, database name and CA

Run these steps in the Railway PostgreSQL service's shell/console. Use a
maintenance window and take a backup first. Never print or commit passwords.

### 5.1 Dedicated role

Fast recovery path (one dedicated, non-superuser role owns the database and runs
migrations):

```sql
CREATE ROLE roadrules_app LOGIN PASSWORD '<generated-strong-password>';
CREATE DATABASE roadrules OWNER roadrules_app;
```

For a hardened deployment, use separate roles instead:

```sql
CREATE ROLE roadrules_owner NOLOGIN;
CREATE ROLE roadrules_migrator LOGIN PASSWORD '<generated-strong-password>';
CREATE ROLE roadrules_runtime LOGIN PASSWORD '<generated-strong-password>';
GRANT roadrules_owner TO roadrules_migrator;
CREATE DATABASE roadrules OWNER roadrules_owner;
```

Run Alembic with `DATABASE_URL` for `roadrules_migrator`, then run the API with
`roadrules_runtime`. After migrations, grant runtime DML only:

```sql
\c roadrules
GRANT CONNECT ON DATABASE roadrules TO roadrules_runtime;
GRANT USAGE ON SCHEMA public TO roadrules_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO roadrules_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO roadrules_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE roadrules_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO roadrules_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE roadrules_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO roadrules_runtime;
```

Do not grant `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `REPLICATION` or
`BYPASSRLS` to runtime roles.

### 5.2 Existing data in a development-named database

Production validation rejects database names `roadrules_dev` and
`roadrules_test`. If production data currently lives in one of them, use one of
these options:

**Option A - rename (fast, preserves data).** Stop the API and any worker first,
take a backup, then:

```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'roadrules_dev' AND pid <> pg_backend_pid();
ALTER DATABASE roadrules_dev RENAME TO roadrules;
```

Verify ownership and the app role's existing grants afterwards. Renaming does
not change the role name.

**Option B - dump and restore (cleanest).** Take a custom-format backup and
restore it into the new database, then verify row counts and the Alembic
revision before cutover:

```bash
pg_dump -Fc -d "$OLD_DATABASE_URL" -f /tmp/roadrules-pre-cutover.dump
pg_restore --list /tmp/roadrules-pre-cutover.dump
pg_restore --no-owner --no-privileges -d "$NEW_DATABASE_URL" \
  /tmp/roadrules-pre-cutover.dump
```

If the database is already named something other than `roadrules_dev` or
`roadrules_test` (including Railway's default `railway`), no rename is needed;
only provision the dedicated role and update the DSN.

### 5.3 Export and trust the Railway CA

Railway PostgreSQL generates its own CA. `verify-full` requires that CA and a
server certificate whose SAN matches the host you dial:

```bash
railway ssh --service <postgres-service> -- export-ssl-ca > railway-postgres-root.crt
openssl x509 -in railway-postgres-root.crt -noout -subject -dates
```

The exported CA is public and is not a secret. Save it in the API repository at
`backend/certs/railway-postgres-root.crt` (create the directory if needed) and
keep `sslrootcert=certs/railway-postgres-root.crt` relative to the backend
working directory. If the Railway root directory is not `backend`, use the
absolute path that exists in the container instead.

Verify the server certificate SAN contains the private host you use:

```bash
railway ssh --service <postgres-service> -- \
  openssl x509 -in /var/lib/postgresql/data/certs/server.crt -noout -text \
  | grep -A1 "Subject Alternative Name"
```

If the SAN is only `DNS:localhost`, do **not** disable verification. Regenerate
the database certificate with the Railway private domain in its SAN (or use a
certificate whose SAN matches), update the exported CA, and redeploy clients.
The stock Railway image includes `RAILWAY_PRIVATE_DOMAIN` in the SAN on
certificate generation; older volumes may need deliberate certificate renewal.

## 6. Safe migration commands

Run from the backend directory with the production migrator DSN in the
environment. Take a backup first. Run only one migration job at a time.

```bash
cd backend
export APP_ENV=production
export DATABASE_URL='postgresql+psycopg://roadrules_migrator:<URL_ENCODED_PASSWORD>@<PRIVATE_DB_HOST>:5432/roadrules?sslmode=verify-full&sslrootcert=certs/railway-postgres-root.crt'

python -m alembic current          # record the revision before changing anything
python -m alembic upgrade head
python -m alembic current          # must match the checked-in head
python -m alembic check            # metadata drift check; must pass
```

Expected head in this repository: `20261106_0010`.

Safety rules:

- Never run `alembic stamp` to hide a failed migration.
- Never run `alembic downgrade` against production without explicit approval and
  a verified backup. Downgrades can drop tables.
- Do not auto-run migrations from every API replica. Use one release job or one
  operator shell.
- If `upgrade head` fails, stop. Keep the old deployment serving, inspect the
  error, and restore the backup/old revision deliberately.
- If `alembic current` already shows the head and `alembic check` passes, do not
  re-run destructive work.

Deployment order:

1. Take and verify a PostgreSQL backup.
2. Create the dedicated role/database and export the CA.
3. Set the API service variables in section 3 and the health check path.
4. Deploy the fixed code with the `/api/v1/health` health check.
5. Run `alembic current`; run `alembic upgrade head` only if behind.
6. Verify section 8 immediately.
7. If verification fails, keep or roll back to the previous deployment; do not
   weaken TLS, hosts, CORS or docs to make the check pass.

## 7. Diagnostic command

After the deployment has the new code and variables, run this inside the API
service. The service's root directory must be `backend`; otherwise use
`backend/scripts/diagnose_database.py` (or `cd backend` first):

```bash
railway ssh --service <api-service> -- python scripts/diagnose_database.py
```

It prints only `app_env`, `host:port/database`, `sslmode`, whether the CA file is
present, SQLSTATE/category, and a redacted driver detail. It never prints the
password or the full DSN.

Interpretation:

| SQLSTATE | Meaning | Likely action |
| --- | --- | --- |
| `08001` / `08006` | Cannot connect / connection failure | Check host, port, private networking, TLS/CA and that PostgreSQL is running |
| `28P01` | Invalid password | Rotate the role password and update `DATABASE_URL` |
| `28000` | Authorization rejected | Check `pg_hba.conf`, role membership and grants |
| `3D000` | Database does not exist | Create it or correct the database name |
| `42501` | Insufficient privilege | Grant only the required table/sequence access |
| `53300` | Too many connections | Reduce pool sizes or raise `max_connections` |
| `57014` | Statement timeout | Inspect the query or raise the timeout deliberately |

The API log now emits one sanitized warning per database failure:

```text
database_unavailable error=OperationalError driver_error=OperationalError \
sqlstate=08006 category=connection_failure target=<host>:5432/<db> \
ssl_mode=verify-full connection_invalidated=true
```

If the log says `sqlstate=unknown`, inspect the driver detail from the diagnostic
script; the app log deliberately omits raw exception text.

## 8. Verification after deployment

Run these against production only after the new deployment is active:

```bash
curl -sS -i https://umuhanda-production.up.railway.app/api/v1/health
curl -sS -i https://umuhanda-production.up.railway.app/api/v1/health/ready
curl -sS -o /dev/null -w '%{http_code}\n' https://umuhanda-production.up.railway.app/docs
curl -sS -o /dev/null -w '%{http_code}\n' https://umuhanda-production.up.railway.app/openapi.json
```

Expected:

- `/api/v1/health` -> `200 {"status":"ok"}`
- `/api/v1/health/ready` -> `200 {"status":"ready"}`
- `/docs` and `/openapi.json` -> `404` (production docs disabled)
- No `DATABASE_UNAVAILABLE` response on any database-backed route
- Railway logs show no `database_unavailable` warnings

Confirm the proxy scheme and CSRF path without creating business data:

```bash
curl -sS -i -X POST \
  https://umuhanda-production.up.railway.app/api/v1/admin/auth/login \
  -H 'Origin: https://umuhanda.vercel.app' \
  -H 'X-CSRF-Protection: 1' \
  -H 'Content-Type: application/json' \
  --data '{"email":"nobody@example.com","password":"not-a-real-password"}'
```

Expected: a normal authentication failure (`401`), or `429` if rate-limited. A
`503` means the database is still unavailable; a `403 ORIGIN_REJECTED` means the
production CORS origin or proxy-header scheme is still wrong.

On the first successful guest/admin login response, confirm the cookies are
`__Secure-roadrules_guest` / `__Secure-roadrules_admin` and include `Secure`.
Do not create a synthetic production student record just to test readiness.

Finally, confirm the unchanged Next.js student proxy still reaches the API:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  https://umuhanda.vercel.app/student-api/students/sessions/me
```

Expected: `401` (no guest cookie), not `503`. The proxy code must not be
modified.

## 9. Rollback

- Prefer Railway's deployment rollback to the previous known build.
- Keep the pre-cutover database backup until production verification passes.
- If a database was renamed, stop all clients and rename it back only after
  confirming the rollback target uses the old name.
- Do not downgrade migrations unless the migration itself is proven destructive
  and an approved backup/restore plan exists.
- Do not restore permissive hosts, CORS or TLS settings as a rollback shortcut.

## 10. Security invariants

- `ALLOWED_HOSTS` is explicit; no wildcards, no localhost in production.
- `CORS_ALLOWED_ORIGINS` is explicit HTTPS only; no Vercel/localhost hardcoding
  in code.
- `sslmode=verify-full` plus a trusted Railway CA; never downgrade to plaintext.
- Production docs/OpenAPI stay disabled.
- Proxy headers are trusted only because the container is behind Railway's edge.
- Secrets stay in Railway variables; the CA certificate is public, private keys
  never leave the database service.
- The Next.js student/admin proxy remains unchanged.
