# Phase 02 implementation report

Historical implementation-stage report. See [Phase 02.5 verification](phase02-verification.md)
for subsequent build recovery, executed browser tests and the current acceptance decision.

## Files created

- `src/app/exam/page.tsx`
- `src/components/exam/ExamEntryShell.tsx`
- `src/components/student/StudentInformationForm.tsx`
- `src/components/student/StudentStepIndicator.tsx`
- `src/components/payment/PaymentMethodSelector.tsx`
- `src/components/payment/PaymentStatus.tsx`
- `src/components/payment/PromoCodeForm.tsx`
- `src/features/onboarding/OnboardingFlow.tsx`
- `src/features/onboarding/types.ts`
- `src/features/onboarding/validation.ts`
- `src/features/payment/types.ts`
- `src/features/payment/api.ts`
- `src/features/promo/types.ts`
- `src/features/promo/api.ts`
- `src/lib/phone.ts`
- `tests/phase02.test.mjs`
- `docs/phase02-api-contract.md`
- `docs/phase02-report.md`

## Files modified

- `src/app/tangira/page.tsx`: replaced the placeholder with onboarding.
- `src/app/globals.css`: added shared field, error and button styles using existing tokens.
- `README.md`: documented current flow, routes, validation and next phase.

Homepage components, theme tokens, typography, dependencies and Next.js configuration
were preserved. This checkout has no Git metadata, so no Git-based baseline diff is available.

## Student flow

Required name and Rwanda mobile input, Unicode-aware name validation, whitespace
normalization and E.164 phone normalization. Allocated mobile ranges include 077;
provider is selected explicitly and is not inferred from the phone prefix.
Syntax validation does not claim phone ownership verification.

Invalid submission focuses the first invalid field; labels, required flags,
aria-invalid and described errors support assistive technology. Two numbered steps
announce their current step; heading focus moves on transitions. Returning to edit
preserves student details in parent React state. No account, email or password.
Details are not persisted across reloads or leaving the page.

## Payment and promo UI

Native radio selection offers MTN MoMo, Airtel Money and promo code. The normalized
number and name appear with an edit action. Mobile payment authorization is explained
as a future phone-only action. No PIN input exists.

Reusable PaymentStatus covers IDLE, INITIATING, PENDING, SUCCESS, FAILED, CANCELLED,
EXPIRED and VERIFICATION_UNAVAILABLE. Only IDLE and VERIFICATION_UNAVAILABLE are
reachable through the current offline flow. Busy flags disable actions during adapter
calls without introducing fake waiting periods or simulated gateway requests.

Promo input rejects empty/whitespace submissions, focuses its error, preserves the code
when switching payment methods, and sends nonempty input only to the offline adapter.
No code is declared valid or redeemed; unavailable verification is not presented as
an invalid-code verdict.

## API readiness and security boundaries

See [planned contracts](phase02-api-contract.md) for the four proposed FastAPI endpoints,
request/response types, server verification and short-lived exam session requirements.
There are no implemented API endpoints, network requests, payment references,
successful transactions, stored credentials or promo redemptions.

`/exam` always shows the existing examination rules, a student-name placeholder and
a disabled Start Exam confirmation. No handler, questions or timer is present. It
reads no browser storage, query parameters or payment state. Displayed SUCCESS is
not connected to authorization. Actual protection of future exam data must occur
on the backend for entry and every subsequent exam request.

## Validation

- `npm run typecheck`: passed.
- `node --test tests/phase02.test.mjs`: five tests passed. Coverage includes supported
  number formats and ranges, invalid/foreign/reserved/landline rejection, required
  fields, Unicode names, whitespace normalization, and both payment providers and
  arbitrary promo code returning unavailable with no network calls or access grant.
- `npm run lint`: passed, including the final test harness.
- Direct Tailwind CSS compilation: passed, including the new shared form styles.
- `npm run build`: failed in Turbopack while spawning the CSS loader worker:
  “node process exited before we could connect to it with exit code: 0”. The same
  failure occurred outside the sandbox. No successful production build is claimed.
- Browser checks could not be completed. The in-app browser failed to attach;
  Windows Computer Use then stopped because it could not determine the browser URL
  confidently enough to enforce policy. No further UI automation was performed.
- Mobile responsiveness, keyboard behavior, step transitions and homepage rendering
  received source review, but remain unverified in a rendered browser. The responsive
  layout uses existing container widths, stacked mobile options, 16px inputs, 48px
  primary actions and global focus-visible styles.

## Limitations and next phase

Implementation is in place; full acceptance remains pending a successful production
build and browser verification. No backend, PostgreSQL, gateway, promo verification,
exam authorization, exam engine or results processing has been started.

Recommended next phase after validation: FastAPI student sessions and server-side
authorization, followed by verified gateway integration and atomic promo redemption.
Begin backend/database work only after explicit approval.
