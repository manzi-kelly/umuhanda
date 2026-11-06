# Phase 04H payment flow and loading

## Promo diagnosis

Before changing the application, a production Next.js build forwarded requests from an authenticated disposable session to FastAPI. The browser alias cookie remained HttpOnly and the bridge supplied the approved Origin and CSRF header. The loopback browser fixture uses port 3100, with the same bridge as the reported localhost:3000 request. The original report did not include a request payload or response body, so its exact cause cannot be determined from the HTTP status alone.

| Request sent before changes | Response |
| --- | --- |
| `{"code":"ARBITRARY-QA-CODE"}` | 422, `PROMO_INVALID`, “Access request could not be completed.” |
| `{"promoCode":"PLACEHOLDER"}` | 422, `VALIDATION_ERROR`, “Request validation failed.” |
| `{"code":" <authorized lowercase code> "}` | 200 on three disposable sessions. |

The baseline student form sent the correct JSON key. A known-valid request did not reproduce a defect. The first 422 comes from business validation in `redeem`, and the second comes from FastAPI request validation because `code` is missing and `promoCode` is unexpected. Missing session and rejected Origin or CSRF context use separate 401 and 403 responses.

The authoritative request is `POST /student-api/promos/redeem` with `Content-Type: application/json` and a single string field named `code`. FastAPI bounds the field to 80 characters and rejects extra fields. The UI trims the code before submission, rejects whitespace-only input locally, and displays distinct messages for contract validation, invalid promos, rate limits, expired sessions and timeouts. The server still normalizes case and whitespace and verifies promo expiry, capacity and ownership. The one-use locking and entitlement uniqueness rules remain in force.

## Payment and loading changes

- MTN Mobile Money, Airtel Money and Kode ya promo are mutually exclusive choices. Selection changes the form immediately without initiating payment. Promo is the initial choice and works independently.
- MTN and Airtel show the session phone as an editable starting value. The mock-only payer field stays in the form and is validated using the existing Rwanda normalization. The mock API has no payer-phone field. The authenticated session's original student data is preserved.
- Mock initiation requires an explicit action and produces a pending transaction. The existing authorized local operator can settle it. Student status checks refresh access only after successful settlement. Promo redemption refreshes access after a server grant. Exam start still requires user confirmation and backend authorization.
- Student and payment submissions display pending feedback and use a synchronous duplicate guard. Pending input is preserved after failures. Retrying a failed access lookup after a successful session creation reuses that session. A timed-out or disconnected creation request can still have an ambiguous outcome if the response never arrives.
- The bridge preserves upstream status and safe bodies, requires JSON for writes, and times out at ten seconds. The browser has a twelve-second fallback that also covers reading the response body. Security headers, allowlisting and cookie scope are preserved.
- Readiness counts eligible unused questions by category and difficulty rather than randomly sorting and materializing a full set of questions. Actual exam start retains the original selection algorithm. The access response lists available grants before other statuses and uses that bounded list for its readiness check.

## Timing method

The diagnostic repeats three requests against the production browser bridge and the isolated PostgreSQL test database. Warm medians exclude the first sample. These are local fixture measurements, including loopback and driver overhead where noted. The initial UI combined selecting a provider with initiating a mock payment, so there is no comparable selection-only baseline. The updated browser checks measure the click and first request with Resource Timing where available. Promo browser timings include the duplicate-submission test interception and are separate from the warm API timing.

The raw baseline samples in milliseconds were 251/100/56 for session creation, 128/68/68 for initial access, 121/112/203 for valid redemption, 61/70/52 for post-redemption access, and 1260/469/413 for navigation. The baseline warm medians were 78 ms for session creation, 68 ms for the first access lookup, 157.5 ms for valid redemption, 61 ms for access lookup after redemption and 441 ms for full exam-ready navigation. The first exam navigation took 1260 ms. This separates initial route loading from endpoint latency. Readiness and exam recovery can still incur separate authenticated requests, and network conditions or a larger bank may change latency.

## Files and validation

- Backend files include `backend/app/main.py`, `backend/app/api/v1/exam_access.py`, and `backend/app/services/exam_access.py` and `exam_generation.py`.
- Frontend files include `src/app/student-api/[...path]/route.ts`, `src/features/onboarding/access-client.ts` and `OnboardingFlow.tsx`, `src/components/student/StudentInformationForm.tsx`, and `src/components/payment/PaymentMethodSelector.tsx`.
- Tests include `backend/tests/integration/test_exam_access.py`, `tests/browser/phase02.spec.ts`, and `tests/browser/phase04h-diagnostic.spec.ts`. The Playwright reporters and screenshot paths now write Phase 04H evidence.

No schema migration is required. Both local databases are at `20261105_0009` and Alembic detected no drift.

The phase preserves guest ownership and CSRF checks, server-issued entitlements, the existing local mock settlement controls, the timed exam and grading lifecycle, and production mock restrictions. The payment form collects no Mobile Money PIN. Diagnostic output records statuses and durations without cookie values or issued promo codes.

| Validation | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m ruff check .` and `-m ruff format --check .` | Passed. |
| `.venv/Scripts/python.exe -m alembic current` and `-m alembic check` | Both databases at `20261105_0009`, with no metadata drift. |
| `.venv/Scripts/python.exe -m pytest -q` | 242 passed, zero failures and skips. Includes PostgreSQL and the migration round trip. The run reported four Starlette and Pydantic warnings. |
| `npm run lint`, `npm run typecheck`, `npm test` | ESLint and TypeScript passed. All five frontend unit tests passed. |
| `npm run build` with `NODE_USE_SYSTEM_CA=1` | Turbopack production build passed. [Build log](evidence/phase04h/production-build.log) |

The backend contract test covers missing body, missing and incorrect fields, whitespace-only input, normalized valid redemption and missing authentication. The existing PostgreSQL suite covers CSRF, disabled, expired and exhausted codes, duplicate and concurrent redemption, mock settlement restrictions and exam authorization.

## Measured results

| Local operation | Before warm median | After warm median | After FastAPI median | After Next bridge self time |
| --- | ---: | ---: | ---: | ---: |
| Create student session | 78 ms | 66.5 ms | 20.0 ms | 1.8 ms |
| Initial access lookup | 68 ms | 57.5 ms | 22.6 ms | 0.4 ms |
| Valid promo redemption | 157.5 ms | 75.5 ms | 41.7 ms | 2.0 ms |
| Access lookup after redemption | 61 ms | 49.5 ms | 21.1 ms | 0.3 ms |
| Full navigation to enabled exam start | 441 ms | 449 ms | — | — |

Warm medians use two samples each. The bridge self time is total Next handler time less the forwarded request duration. FastAPI middleware timing includes authentication, database access and response handling. The baseline lacked server timing headers. The first full exam navigation took 1260 ms before and 1184 ms after. Warm navigation did not improve in this sample.

On the same small, ready test bank and empty guest question history, PostgreSQL `EXPLAIN ANALYZE` measured a warm median of 0.674 ms for the previous random-selection query and 0.208 ms for the grouped readiness query. This compares SQL execution only and excludes planning, row transfer and ORM materialization. The measurements are directional because the fixture and sample are small.

The 390px diagnostic held an actual browser request open. The 12-second client timeout cleared the pending state, preserved the promo input, and enabled a retry. The retry reached FastAPI and displayed the normal invalid-code message for the diagnostic value. [Timing and recovery log](evidence/phase04h/payment-timing.log)

## Browser verification

`npm run test:browser -- phase02.spec.ts` passed 6 tests with zero failures or skips. Chrome checked the three payment choices, payer number normalization, method switching without a payment write, normalized promo JSON, one request during a held submission, mock authorization, exam and retake access, and existing results. It recorded zero unexpected console errors, page errors, failed requests or HTTP errors at 390px, 834px and 1440px. [Student Chrome evidence](evidence/phase04h/public-browser-results.json)

| Width | MTN click to payer field ready | Promo click to request | Promo browser request | Promo click to form cleared |
| --- | ---: | ---: | ---: | ---: |
| 390px | 153 ms | 2 ms | 225 ms | 342 ms |
| 834px | 52 ms | 2 ms | 199 ms | 299 ms |
| 1440px | 54 ms | 2 ms | 156 ms | 415 ms |

The MTN selection measurements include Playwright observing the updated form. Promo browser timing includes the intentional request hold used to test duplicate submission. Form-cleared time also includes the access refresh, rendering and Playwright observation. These measurements are separate from the unheld warm API benchmark.

- [390px payment choices](evidence/phase04h/browser/390px-payment.png)
- [834px payment choices](evidence/phase04h/browser/834px-payment.png)
- [1440px payment choices](evidence/phase04h/browser/1440px-payment.png)

`npm run test:browser:admin` passed 12 tests across the same widths. `npm run test:browser -- phase04h-diagnostic --project=390px --reporter=list` passed the timing and real client-timeout diagnostic. [Administrator Chrome evidence](evidence/phase04h/admin-browser-results.json)

## Acceptance and limitations

Phase 04H passed local acceptance. Valid promo redemption, invalid request handling, independent payment selection, pending-state cleanup, duplicate prevention, and server-authorized exam access were verified. The original 422 cannot be assigned to one rejection class without its response body. Local timings are fixture-specific, and the warmed exam navigation result was essentially unchanged. The editable payer field is scoped to mock form validation. Production payment collection remains outside this phase.
