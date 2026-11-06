# Phase 03B — persistent students and secure guest sessions

## 1. Implementation summary

Persistent students, opaque guest authentication and minimal security auditing are
implemented in the existing synchronous FastAPI/SQLAlchemy application. No accounts,
passwords, emails or PINs are required. A guest credential establishes continuity of
the submitted student record; it does **not** verify phone ownership/person identity,
payment, promotional eligibility or exam authorization.

The existing PostgreSQL cluster at **127.0.0.1:55432**, its development/test databases,
roles and configuration were retained. No second cluster or dependency upgrade was
introduced. Frontend source/configuration and the accepted baseline migration are
unchanged; integrity evidence is saved under `docs/evidence/phase03b/`.

## 2. Files created and modified

Created:

- `backend/app/api/v1/student_sessions.py`
- `backend/app/core/session_security.py`
- `backend/app/models/student_sessions.py`
- `backend/app/repositories/student_sessions.py`
- `backend/app/schemas/student_sessions.py`
- `backend/app/services/student_sessions.py`
- `backend/alembic/versions/20261104_0002_student_guest_sessions.py`
- `backend/tests/unit/test_guest_security.py`
- `backend/tests/integration/test_student_sessions.py`
- `backend/scripts/verify_guest_sessions.py`
- This report and sanitized Phase 03B evidence.

Modified:

- Backend `app/main.py`, `core/config.py`, `db/session.py`, `api/v1/router.py`,
  `models/__init__.py`, `alembic/env.py` for configuration, routing, security handling,
  metadata registration and connection-level UTC/READ COMMITTED behavior.
- Backend `tests/unit/test_api.py`, `tests/integration/test_migrations.py` to retain
  health/readiness coverage while accounting for credentialed CORS, the approved new
  routes and new migration head.
- Backend `scripts/verify_foundation.py`, `scripts/audit_local_secrets.py` for current
  schema/API expectations and current-phase evidence.
- `backend/.env.example`, `backend/README.md`, `docs/phase02-api-contract.md`.

No frontend file, dependency manifest/lock or PostgreSQL provisioning script was
changed. Existing ignored credentials were reused, not printed or rotated. This
checkout has no Git metadata; no commit was made.
All **44** recorded frontend/configuration and baseline-migration hashes match their
pre-work values: [integrity result](evidence/phase03b/integrity-check.json).

## 3. Database schema

| Table | Columns | Constraints / indexes |
| --- | --- | --- |
| students | UUID id; full_name VARCHAR(120); phone_number VARCHAR(13); created_at, updated_at TIMESTAMPTZ | Name length/trim/control/digit/angle-bracket/spacing guards; exact canonical Rwanda mobile regex; timestamp ordering; non-unique phone index |
| guest_sessions | UUID id; UUID student_id; token_hash VARCHAR(64); created_at, expires_at, last_activity_at, nullable revoked_at TIMESTAMPTZ | Student FK with CASCADE; unique 64-lowercase-hex verifier; timestamp ordering; student and expiry indexes |
| student_activity_events | UUID id; nullable student_id / guest_session_id FKs; event_type VARCHAR(32); created_at TIMESTAMPTZ | Four allowed event types; unique session/event pair; FK lookup indexes; event_type/created_at index for the distributed creation budget |

Student names receive stricter Unicode letter/mark/separator validation in Pydantic
in addition to the database's coarse format guards. Whitespace is collapsed and
Unicode normalized to NFC. Full names and phone numbers are **not unique**. Two
submissions with the same values create distinct students; no phone-based identity
merging or enumeration response exists.

Phone formats normalize to E.164 `+2507XXXXXXXX`, covering 72/73/77/78/79 mobile
ranges independently of wallet provider. Session/audit IDs are informational UUIDs,
not credentials. All timestamp columns are timezone-aware, connections use UTC and
API expiration values serialize as UTC ISO 8601.

Audit rows contain no token, token hash, name, phone number, PIN or IP. Only
STUDENT_CREATED, SESSION_CREATED, SESSION_REVOKED and SESSION_EXPIRED are accepted.
Deleting a student removes its sessions and nulls audit identity references while
preserving minimal events. That behavior is tested; no deletion API/job was added.

## 4. Alembic migration and data preservation

`20261104_0002` is additive and revises the unchanged `20261104_0001` baseline.
No normal schema path uses `create_all()`.

- Test DB: upgrade, downgrade to the baseline, upgrade, repeat upgrade, revision
  inspection and `alembic check` succeeded. Invalid revision requests fail explicitly.
- Downgrade testing runs only as `roadrules_test_app` in `roadrules_test`, after
  checking the approved table set and that the new tables are empty. It drops only
  the three Phase 03B tables. Unknown tables cause failure rather than a destructive reset.
- Development: saved [pre-upgrade state](evidence/phase03b/development-before.json),
  then ran **upgrade only**. The previous state was baseline-only. No development
  downgrade, truncation or student deletion occurred.
- Development is now `20261104_0002 (head)` with no metadata drift;
  [upgrade evidence](evidence/phase03b/development-upgrade.log).

Integration fixtures verify both the configured and connected database/role before
writes. They clean only the three approved **test** tables with no CASCADE, reject
unknown table sets, and leave the schema at head. Required integration prerequisites
fail the suite rather than silently skipping tests.

## 5. API request/response contracts

### POST /api/v1/students/sessions

Request (only these two fields are accepted):

```json
{"fullName":"Jean Claude","phoneNumber":"0781234567"}
```

201 response shape:

```json
{
  "studentId": "<student UUID>",
  "sessionReference": "<informational session UUID>",
  "fullName": "Jean Claude",
  "maskedPhoneNumber": "+25078*****67",
  "expiresAt": "<absolute expiration in UTC>",
  "accessGranted": false
}
```

The student, guest session and creation audit events commit atomically. An injected
audit failure after both entity flushes rolls the entire operation back and issues
no cookie. A client-selected token or student ID is not accepted. The raw credential
is issued only in Set-Cookie **after** a successful commit, never in JSON.

### GET /api/v1/students/sessions/me

Authenticates only the opaque cookie and returns the same safe summary. A UUID,
Authorization header, query parameter or supplied student ID cannot authenticate.
Missing, malformed, unknown, expired and revoked credentials receive the same 401:

```json
{"error":{"code":"GUEST_SESSION_REQUIRED","message":"A valid guest session is required."}}
```

### POST /api/v1/students/sessions/revoke

204 on current-session revocation; records SESSION_REVOKED, commits, then deletes
the matching cookie. Replaying an already revoked credential is an idempotent 204
for logout but cannot read `/me`. Repeating logout after cookie deletion (no
credential) is also a no-op 204, with CSRF protection still required. Unknown/invalid
or expired credentials return 401. A failed revocation transaction cannot claim
success or partially revoke; that rollback case is tested.

Other safe status outcomes: 422 invalid input, 403 origin/CSRF/TLS rejection, 429
creation budget exhaustion/contention with Retry-After, and generic 500/503 for
internal/database failures. Session responses, including errors, are no-store;
raw phones, raw tokens and verifiers are never response JSON fields.

## 6. Session lifecycle and authority

- New tokens use `secrets.token_urlsafe(32)`: **256 CSPRNG bits**, encoded as 43
  URL-safe characters. PostgreSQL stores only a SHA-256 verifier with a unique index.
  Test coverage confirms randomness input size, token shape, hashing and database
  rejection of raw tokens, duplicate verifiers and orphaned sessions.
- PostgreSQL state and `clock_timestamp()` sampled **after** acquiring the session
  row lock are authoritative. There is no in-memory authentication authority or
  browser timer. A fresh application instance authenticates the same active cookie.
- Default absolute lifetime: **7200 seconds**, never extended by reads.
- Default inactivity timeout: **1800 seconds** from persisted last activity.
- Default activity-write interval: **60 seconds**. Reads update last activity only
  when due. This conservatively allows up to one interval of earlier inactivity
  expiry relative to a recent unpersisted read; it never extends absolute lifetime.
- Row locks serialize touches, expiry observation and revocation. Session timestamp
  updates are throttled, although authenticated reads still incur DB transactions
  and row-lock work. Revoked/expired sessions cannot be resurrected by a touch.
- SESSION_EXPIRED is recorded once on first attempted use after either timeout.
  Repeated/concurrent expiry replay does not duplicate the event. Unused expired
  sessions need no job to become invalid; background cleanup/audit census is not implemented.

Each creation makes a new independent student/session; clients should resume via
`/me` rather than recreate records to preserve identity continuity. Creating another
session replaces the browser cookie but does not merge identities or bulk-revoke
other independent credentials based on a shared phone number.

## 7. Security design and creation abuse protection

No student password/email, JWT, payment PIN, payment-success simulation or exam
authorization was introduced. Student IDs and session UUIDs are never authentication
inputs. The server resolves the student from the verified cookie/hash join.
`accessGranted` is a response literal false. Payment, promo and exam routes do not
exist and tests assert their absence.

Creation uses a **durable PostgreSQL-wide** sliding budget: default 30 successful
creations per 60 seconds across all app instances sharing this database. A transaction
advisory lock serializes quota checking with entity/audit creation; contention rejects
quickly with 429 instead of queuing unbounded creation work. READ COMMITTED ensures
the next creator observes prior committed events. An event-type/time index supports
the count. Rolled-back attempts do not create incomplete identities or events.

The limiter uses no IP address or client-supplied forwarding header. Tests cover
independent app instances, simultaneous creations, spoofed headers and deterministic
database-window recovery. Revocation does not reset the budget. Minimal events survive
identity deletion, so deleting a student does not remove its recent creation count.

This is not an in-memory limiter advertised as distributed protection. Its limitation
is **global fairness/availability**: one actor can exhaust the budget for everyone.
Before public deployment, add reviewed edge per-client request/body-size controls,
retain a shared authoritative budget, and tune pool/worker counts for PostgreSQL.
Do not derive per-client keys from arbitrary X-Forwarded-For/X-Real-IP values.

## 8. Cookie, CORS, CSRF and proxy policy

| Setting | Policy |
| --- | --- |
| Cookie name | development/testing `roadrules_guest`; production `__Secure-roadrules_guest` |
| HttpOnly | Always enabled |
| Secure | Always enabled in production; production session HTTP requests are rejected |
| SameSite | Lax default; configurable Strict; None rejected |
| Path / Domain | `/api/v1`; no Domain, host-only |
| Expiration | Absolute DB expiration plus Max-Age; server still enforces idle/absolute timeouts |
| Cookie deletion | Same name, path, HttpOnly, Secure and SameSite attributes |
| CORS | Exact configured origins, credentials allowed, GET/POST and approved headers only; no wildcard |
| POST CSRF | Exact single approved Origin plus single `X-CSRF-Protection: 1`; no missing/null fallback |

Cross-site Fetch Metadata and untrusted Origins are rejected on session requests.
The custom header is a non-secret AJAX/CSRF guard, not a bearer token. A foreign
website cannot add it through a successful credentialed CORS preflight. Duplicate
credential cookies are rejected rather than ambiguously selecting a value.

For local browser integration, use **localhost consistently** for port 3000 frontend
and port 8000 API; the ports are cross-origin but same-site. Browser fetch must use
`credentials: "include"`; the browser supplies Origin and the application supplies
the custom POST header. Do not mix localhost/127.0.0.1 as browser cookie hosts.
Cookies are not isolated by port. Production expects same-site HTTPS app/API hosts;
unrelated-site third-party-cookie deployments are intentionally unsupported.

The default run command disables access/proxy headers. With TLS termination,
configure only known trusted proxy IPs to supply scheme information; never wildcard
proxy trust. Session Origin is compared with configured origins, not inferred from
Host/Forwarded headers. Proxy/APM logging must redact Cookie, Set-Cookie, authorization
headers and bodies. Production settings cannot disable the derived Secure policy.

## 9. Executed validation and evidence

Commands use `backend/.venv/Scripts/python.exe` (or activated `python`) from backend:

| Command / verification | Result | Evidence |
| --- | --- | --- |
| `python -m pytest tests/unit -q` | 104 passed | [unit log](evidence/phase03b/unit-tests.log) |
| `python -m pytest tests/integration -q` | 41 passed, real roadrules_test | [integration log](evidence/phase03b/integration-tests.log) |
| `python -m pytest -q` | 145 passed, 0 failed, 0 skipped | [full log](evidence/phase03b/all-tests.log) |
| `python -m ruff check .` | Passed | [Ruff log](evidence/phase03b/ruff.log) |
| `python -m ruff format --check .` | Passed | [format log](evidence/phase03b/format.log) |
| Development `alembic upgrade head/current/check` | Head 0002; no drift | [migration log](evidence/phase03b/development-upgrade.log) |
| `python scripts/verify_foundation.py` | Live health 200; ready 200/503; clean shutdown; roles/schema checked | [foundation JSON](evidence/phase03b/foundation-verification.json) |
| `python scripts/verify_guest_sessions.py` | Live 201 creation, 200 authenticated me, 204 logout/repeat, 401 replay/missing, 403 missing CSRF; no token in JSON/observed logs; synthetic data removed | [live JSON](evidence/phase03b/live-sessions.json) |
| `python scripts/audit_local_secrets.py` | No DB-password matches in checked source/logs; no active credential matches to historical diagnostics | [audit JSON](evidence/phase03b/security-audit.json) |

Unit/integration coverage includes validation and normalization, atomicity and failure
rollback, verifier security, missing/invalid/UUID credentials, replay and revocation,
absolute/inactivity expiry without sleeps, throttled activity, concurrent expiry,
cookie attributes, CORS/origin/CSRF, shared quotas, DB constraints and migration state.
All existing health/readiness/session-lifecycle/configuration tests remain exercised.
No required integration test was skipped.

The existing Starlette 1.10.0 test client emits one non-failing HTTPX-to-HTTPX2
deprecation warning; it was not suppressed or fixed through unrelated upgrades.
Live verification used real Uvicorn listeners and HTTPX, not a claim of browser or
frontend integration testing. Test servers shut down and synthetic records were removed.

## 10. Retention, findings and limitations

- No cleanup job was added. Approve retention/erasure rules for student PII, expired
  verifiers and security audits before production. Preserve SESSION_CREATED rows for
  at least the active limiter window; purging them early resets abuse protection.
  Nullable audit FKs allow de-identification without storing additional personal data.
- Global limiting works across processes using the same primary DB, but per-client
  fairness, ingress body/concurrency limits and production observability remain deployment work.
- Guest authentication verifies credential possession, not the supplied phone/person.
- Local HTTP is intentionally limited to development; production TLS, trusted proxy
  configuration and separate runtime/migrator grants remain deployment prerequisites.
- The Phase 03A test-client deprecation warning remains. No new dependency was installed.
- No automated development-data deletion, second cluster, gateway, admin authentication,
  exam content or Next.js integration was introduced.

Credential-source/log audit and preserved-file hashes are recorded in the evidence
directory. No raw token was added to JSON, application logs or persisted database fields.
Generated DB credentials remain in the existing ignored local files.

Security review identified and corrected a **test-only** diagnostic risk: the initial
negative verifier-constraint test passed a live synthetic credential as the rejected
database value. PostgreSQL's rejected-row DETAIL diagnostics can record such values,
even with SQL statement logging disabled. That test now uses a non-credential sentinel.
The isolated records were removed by fixture cleanup; the read-only audit found two
historical credential-shaped values and **zero matching active guest credentials**.
The final corrected test run left that historical count unchanged at two; no active
credential matched either value before or after the run.
No real student or production credential was involved. Existing private PostgreSQL
logs were not silently deleted or rewritten. See
[sanitized audit counts](evidence/phase03b/security-audit.json). Application code always
inserts only verifiers, and live-runtime verification confirmed its token was absent
from observed logs. Production database diagnostic logs must remain access-controlled.

## 11. Future frontend integration and Phase 03C readiness

The previous `sessionReference`/`expiresAt` TypeScript response fields remain present;
new safe summary fields extend the contract. Frontend types and adapters were not
changed. [Phase 02 contract notes](phase02-api-contract.md) now describe the implemented
backend routes while keeping payment/promo endpoints planned and frontend adapters offline.

Future approved integration should create once, then resume via `/me`, use browser
credentials and the CSRF header, handle generic 401 by restarting onboarding, handle
429 with Retry-After, and never put a credential in storage, URLs or JSON. Public
UUIDs must never substitute for the guest cookie. Extend CSRF handling deliberately
to any future state-changing routers.

The identity foundation is ready for a separately reviewed Phase 03C payment design:
resolve student identity from the server-side guest session and bind any future
payment references to it. Payment verification and a distinct short-lived exam access
session remain prerequisites for exam authorization. No payment implementation or
subsequent phase was started.

**Acceptance:** Phase 03B is accepted for its backend-only scope: persistent guest
sessions, server-enforced lifecycle, approved migrations, safe cookie/origin handling
and real PostgreSQL tests are verified. Production ingress fairness, retention and
deployment prerequisites above remain explicit; no payment or exam permission is granted.

Primary design references: [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[OWASP CSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html),
[cookie attributes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie),
[PostgreSQL locks](https://www.postgresql.org/docs/18/explicit-locking.html),
[database clocks](https://www.postgresql.org/docs/18/functions-datetime.html).
