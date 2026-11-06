# Phase 02 — planned FastAPI contract

Phase 03B implements the student-session routes described below in the separate backend.
Payment and promo endpoints remain proposals. Current frontend adapters are offline and
return `VERIFICATION_UNAVAILABLE` with `accessGranted: false`; they never generate references,
send payment requests, validate codes, or issue access.

| Endpoint | Request type | Response type |
| --- | --- | --- |
| POST /api/v1/students/sessions | StudentSessionRequest | StudentSessionResponse |
| POST /api/v1/payments/initiate | PaymentInitiationRequest | PaymentInitiationResponse |
| GET /api/v1/payments/{reference}/status | Server-scoped payment reference | PaymentVerificationResponse |
| POST /api/v1/promos/redeem | PromoValidationRequest | PromoValidationResponse |

## Phase 03B student-session contract

POST `/api/v1/students/sessions` accepts `{ fullName, phoneNumber }` and returns 201:
`{ studentId, sessionReference, fullName, maskedPhoneNumber, expiresAt, accessGranted: false }`.
The existing `sessionReference: string` and `expiresAt: string` fields are preserved;
the other fields extend the planned TypeScript shape. No frontend types/integration
were changed. SessionReference is an informational UUID, never an authorization token.

The credential is issued only as a host-only HttpOnly cookie at Path `/api/v1`:
development `roadrules_guest`; production `__Secure-roadrules_guest` with Secure.
SameSite defaults to Lax for same-site frontend/API hosts. Browser fetch must use
`credentials: "include"`; POSTs require an exact allowed Origin plus
`X-CSRF-Protection: 1`. GET `/api/v1/students/sessions/me` returns the same summary;
POST `/api/v1/students/sessions/revoke` returns 204 and clears/revokes the cookie.
Missing/invalid/expired/revoked `/me` sessions get the same generic 401. Creation can
return 422 for invalid input, 403 for origin/CSRF rejection, 429 for the shared budget,
or a safe 500/503 on internal/database failure. No raw token/hash/full phone is JSON.

The guest session proves continuity of a bearer credential, not phone ownership,
payment or exam access. Future payment handlers must resolve the student from the
verified server cookie and check ownership; never authorize a client-supplied
student/session UUID. A distinct future exam-scoped access session still requires
confirmed payment or valid promo redemption. See [Phase 03B](phase03b-student-sessions.md)
for lifecycle, cookie/CSRF and deployment requirements. Frontend adapters remain offline.

Types live under `src/features/{onboarding,payment,promo}/types.ts`.
Phone numbers use E.164 (`+250781234567`). Names are trimmed and repeated whitespace collapsed.
Session/expiration timestamps should use ISO 8601 UTC. Payment status is distinct from verification
and exam authorization; a displayed SUCCESS must never authorize exam entry.

The backend must validate all inputs, bind references to the current server session, choose
the payable amount itself, authenticate gateway callbacks, verify payment server-to-server,
handle initiation/redemption idempotently, and redeem promo codes atomically. Responses must
not disclose unrelated student sessions or payment references. Rate limit sensitive endpoints.
Do not log PINs, credentials, or raw student data unnecessarily.

Use a consistent future error envelope, e.g. `{ error: { code, message, fieldErrors? } }`;
map transport failures, timeouts and 503 responses to VERIFICATION_UNAVAILABLE. Unknown or
malformed responses must fail closed. No arbitrary promo should be declared valid or invalid
when the verification service cannot be reached.

Only confirmed payment or valid promotional redemption may cause the backend to issue a
short-lived, exam-scoped access session through a Secure, HttpOnly, SameSite cookie. Apply
CSRF protection as appropriate. Check that session server-side for exam entry and every
future question/result endpoint. Never accept accessGranted, status, student/session references,
browser storage or URL parameters supplied by a client as proof of authorization.

Current `/exam` is a public rules/locked shell with no questions, timer or start handler.
It ignores all client state and URL parameters. Student name is deliberately a placeholder
until a server-verified identity exists. The Start Exam confirmation button is disabled.

Onboarding details are held only in React memory while navigating its steps; leaving or
reloading the page clears them. Number syntax validation does not prove ownership, reachability,
wallet registration or selected provider. No OTP verification is claimed.

Number ranges follow [RURA's June 2023 numbering plan](https://www.rura.rw/index.php?eID=dumpFile&f=93222&t=f&token=fee41c7a965517a12c3a1f70eafb25dc07400148):
72, 73, 77, 78 and 79 with a nine-digit national significant number. Keep this policy under
review as allocations change. Never infer the wallet provider from the prefix.

Next phase: implement FastAPI session and authorization boundaries, followed by gateway
verification and transactional promo redemption. No backend, database or exam engine is
included in Phase 02.
