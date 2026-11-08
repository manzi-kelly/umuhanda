# Railway production setup

The workflow targets the existing PostgreSQL 18 database `railway` at
`postgres.railway.internal:5432`. It preserves database ownership and data.
The PowerShell entry point has four separate checkpoints. An API deploy and
a guest-session write are separate operator approvals.

## Prerequisites

- Confirm the backup is restorable and record the production project and environment.
- Use an approved, running Railway operator service in the same environment as
  PostgreSQL. Its working directory must be the backend directory, with the
  reviewed source, Alembic migrations and backend dependencies installed. A
  crash-looping API is unsuitable for the initial SSH session. An operator
  service or release containing the script requires approval before provisioning
  or deployment.
- Provide the verified public root CA at the same absolute path in the operator
  and API containers. Confirm the certificate matches
  `postgres.railway.internal`. Keep database credentials in the operator's
  secret manager. Use an interactive terminal without recording or shell tracing.
  Review database statement/audit logging before provisioning because role DDL
  carries a sensitive SCRAM verifier, although the plaintext stays out of SQL.
- Choose two distinct dedicated role names and two distinct strong passwords.
  Use the same passwords on reruns. Existing unmanaged roles or objects with
  conflicting ownership require manual review. Keep the PostgreSQL operator
  password and migration password out of the API service.

## Run from PowerShell 7

```powershell
Set-Location D:/Roadrules/roadrule
railway --version
railway login

$setup = @{
    ProjectId = '<RAILWAY_PROJECT_ID>'
    Environment = 'production'
    ApiService = '<API_SERVICE_NAME>'
    OperatorService = '<RUNNING_OPERATOR_SERVICE_NAME>'
    RuntimeRole = 'roadrules_runtime'
    MigrationRole = 'roadrules_migrator'
    CaPath = '<ABSOLUTE_CA_PATH_IN_BOTH_CONTAINERS>'
    ApiHost = 'umuhanda-production.up.railway.app'
    FrontendOrigin = 'https://umuhanda.vercel.app'
}
railway link --project $setup.ProjectId --environment $setup.Environment --service $setup.ApiService
railway status
./backend/scripts/Invoke-RailwayProductionSetup.ps1 @setup -Phase Inspect
```

Inspect connects with the operator login and verified TLS, then reports database
identity, role presence, and the current revision and repository head. A fresh
installation must have an empty public relation inventory. A rerun expects a
known Alembic revision and public relations owned by the chosen migration role.
Unexpected state stops the workflow without writes.

After database changes have been approved, run:

```powershell
./backend/scripts/Invoke-RailwayProductionSetup.ps1 @setup -Phase Apply
```

Type `APPLY railway` only after checking the backup and target. The script
serializes approved runs with a PostgreSQL advisory lock. It creates only
missing managed logins with SCRAM credentials and no elevated role attributes
or memberships. It grants both roles database CONNECT, grants the migration
role CREATE and USAGE on public, and grants the runtime role USAGE only on
the application schema. PostgreSQL normally grants TEMP and execution of some large-object creation
functions through PUBLIC. If those defaults are still present, Apply stops
unless the operator approves removing the relevant inherited privileges:

```powershell
./backend/scripts/Invoke-RailwayProductionSetup.ps1 @setup -Phase Apply -RevokePublicTemp -RevokePublicLargeObjects
```

Each switch requires its own confirmation phrase. These changes revoke
inherited TEMP and large-object creation access for every role on this
database. Review other database users first and pass only the switches the
DBA has approved. The application does not use PostgreSQL large objects. The workflow does not remove PUBLIC CREATE or other unexpected grants
automatically. It checks effective runtime privileges across all schemas and
fails if the role has CREATE, TEMP, owned objects, or executable non-system
security-definer routines. Runtime may still manage its own login password
under PostgreSQL's ordinary role rules.

Runtime SELECT and INSERT are limited to the audited application tables. The
reserved refund table has no active application access and receives no grants. UPDATE is limited to
tables with mutable state or row-locking queries. Direct DELETE is limited to
question drafts and draft answers. Draft options and assets use foreign-key
cascades. Runtime has no grants on the Alembic version table. The current UUID
schema needs zero sequence grants. An unexpected sequence stops setup so its
ownership and actual use can be reviewed. Existing effective ACLs, including
PUBLIC grants, must agree with the audited policy.

Role setup is a separate committed checkpoint. Alembic upgrade, metadata
drift check, ownership checks, and runtime grants share one PostgreSQL
transaction. The current migration chain uses transactional DDL. Review any
future migration that needs autocommit before using this workflow. The
migration login owns the new tables and trigger functions. The production
database and schema owners are retained.

If the schema checkpoint fails, its transaction rolls back and the script
reads the persisted revision over the operator connection. Role changes may
already have committed. Review the persisted state, fix the underlying cause,
and rerun Inspect followed by approved Apply using the same role names and
passwords. If the connection was lost around commit, confirm the persisted
revision and ACLs before deciding whether anything needs retrying. Do not
stamp, reset, or downgrade to force a rerun. Stage only after Apply confirms
the repository head and the ownership and privilege checks pass.

After the Railway variable change is approved, confirm the CLI link and run:

```powershell
railway status
./backend/scripts/Invoke-RailwayProductionSetup.ps1 @setup -Phase Stage
```

Type `STAGE railway` to save the API variables with `--skip-deploys`.
The wrapper sends each value on stdin and keeps the password out of command
arguments. Review any partial updates before a release. Remove an existing
`TEST_DATABASE_URL` using a separately approved staged change. Confirm
`PDF_STORAGE_ROOT` separately if PDF ingestion is deployed. Retain the same
private storage configuration for the API and worker.

The API receives the runtime URL in this shape:

```text
postgresql+psycopg://<runtime-role>:<encoded-password>@postgres.railway.internal:5432/railway?sslmode=verify-full&sslrootcert=<encoded-absolute-ca-path>
```

Set the Railway health check path to `/api/v1/health`. Use the reviewed
production startup command with trusted proxy headers as described in the
[Phase 1 handoff](railway-phase1-handoff.md). Vercel must send student traffic
through the existing Next.js `/student-api` handler. Confirm the production
server-side origin configuration and review both repository and Vercel project
routing for rewrites that would shadow this handler.

After explicit release approval and deployment, run:

```powershell
./backend/scripts/Invoke-RailwayProductionSetup.ps1 @setup -Phase Verify
```

Verify requires the configured runtime identity, a TLS connection, both
health responses, and an HTTP 401 from the unauthenticated student proxy.
HTTP 401 alone cannot prove cookie creation. With separate approval for a
production guest write, use the Vercel onboarding form with designated test
details, confirm the Secure and HttpOnly student cookie in the browser, and
confirm the session reads back through the same proxy. Avoid promo redemption
or payment actions during this smoke test. If a first administrator is needed,
authorize it separately and run the existing interactive
`python scripts/bootstrap_admin.py` from the backend directory.

### Equivalent Railway SSH commands

From the same PowerShell session:

```powershell
railway ssh --project $setup.ProjectId --environment $setup.Environment --service $setup.OperatorService -- python -m scripts.setup_railway_production --ca $setup.CaPath --runtime $setup.RuntimeRole --migrator $setup.MigrationRole
railway ssh --project $setup.ProjectId --environment $setup.Environment --service $setup.ApiService -- python scripts/diagnose_database.py
```

The first command is read-only. Use the PowerShell Apply and Stage phases for
changes so the confirmation gates remain in place.
