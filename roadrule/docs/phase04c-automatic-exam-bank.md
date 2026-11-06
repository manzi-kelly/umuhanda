# Phase 04C — Automatic exam bank

The existing admin upload, private storage, PDF worker, draft extraction and
source previews remain the input pipeline. After extraction, the worker assesses
every draft and writes a separate immutable bank revision. A successful import
can have zero eligible questions. The administrator can monitor processing and
readiness and reprocess a source after changing policy or fixing extraction.
Eligibility and activation run automatically without an approval step.

## Eligibility and evidence

| State | Meaning |
| --- | --- |
| `ELIGIBLE` | Text, contiguous A–D options, unique source-backed answer, and required images pass validation. |
| `INELIGIBLE_MISSING_ANSWER` | The worker found no explicit answer. |
| `INELIGIBLE_AMBIGUOUS_ANSWER` | Evidence is conflicting, uncertain, mismatched, or unsupported. |
| `INELIGIBLE_INCOMPLETE_OPTIONS` | Option count, labels, association, text, or source evidence are invalid. |
| `INELIGIBLE_IMAGE_ERROR` | A required figure is missing or a referenced crop failed source or integrity checks. |
| `INELIGIBLE_EXTRACTION_ERROR` | Invalid source evidence, a normalized duplicate prompt, residual answer-marker text, or extraction uncertainty. |

The validator checks source pages and bounding boxes, reconstructs text from
the captured text-layer evidence, and confirms the answer option belongs to the
draft. Supported answer forms are an explicit `Answer: A` / `Igisubizo: A` line
or a numbered answer row parsed under an explicit key heading. The row's
question number and option must agree. A bare option label, OCR text, or a
conflicting answer does not supply reliable evidence. It checks that images
remain in the draft's captured page regions and verifies the stored PNG hash.
Recognized road-sign or illustration wording requires an image. This is a
conservative text and geometry rule. It does not identify the meaning of
graphics or validate the PDF author's answer semantically. Any parser diagnostic
for an unsupported structure blocks activation for the whole revision.

Difficulty comes only from explicit, unambiguous text-layer metadata such as
`Difficulty: HARD` or `Urwego: EASY`. Unknown difficulty stays null. The default
`EXAM_SELECTION_POLICY=DIFFICULTY_QUOTAS` requires 7 HARD, 4 MEDIUM, 9 EASY.
Set `EXAM_SELECTION_POLICY=UNSTRATIFIED` on the worker to explicitly accept
a source without reliable difficulty metadata. Both policies require at least
one eligible road-sign and one eligible general question in every exam.
Policy is frozen per revision and displayed to administrators.

## Storage and activation

Migration `20261105_0005` adds five tables to the existing database.
`exam_bank_revisions` records document, job, SHA-256, policy, validation totals,
and readiness. `exam_bank_questions` retains original text, options, source
coordinates, answer evidence, answer index, image references, category,
difficulty and eligibility. `exam_attempts` and `exam_attempt_items` store
entitlement identity, guest/student references, revision, question IDs, ordering
and timestamps. `exam_operational_events` records sanitized unavailability reasons.

A transaction advisory lock serializes activation. A partial unique index allows
one active revision. A valid newer source replaces the pointer atomically.
Pending, failed, empty and unsupported replacements leave the current active
bank available. Older uploads cannot supersede a newer active source. A
reprocessed source may acquire a new immutable revision while the previous
revision remains available to existing attempts. The worker also reprocesses
completed Phase 04B jobs that lack a bank revision. A migration downgrade refuses
to discard recorded bank or operational evidence.

The normal worker command is unchanged. Run it from the backend directory with
the same database and private storage configuration as FastAPI.

```powershell
.venv/Scripts/python.exe scripts/pdf_worker.py
```

## Exam generation and authorization

The internal `start_exam` service takes a guest credential, an entitlement
reference, and a mandatory trusted server-side entitlement verifier. The service
checks the guest token, revocation and expiry in PostgreSQL. The verifier must
confirm the grant is valid and bound to that guest. A committed attempt is the
consumption record. The verifier must leave the grant untouched on a failed
attempt and support an authorized, idempotent read of a prior attempt.

Selection reads the active revision without reparsing the PDF. SQL excludes
fingerprints already used by the same guest session, including across bank
versions. It sorts eligible candidates by a per-request secret-derived key,
fetches bounded selections for each quota, guarantees both categories when
possible, and shuffles the final order with the OS-backed random generator.
The guest lock serializes history checks. The entitlement lock and unique key
prevent duplicate consumption. A deferred database trigger requires exactly
20 eligible items from the attempt's revision. Immutable history triggers
block edits and deletions of versioned questions and attempt ordering through
ordinary row writes. Student-shaped output includes question IDs, ordering,
text, option labels/text and image counts. Answer evidence, correct indices
and private storage keys stay server-side. Future exam execution will need an
authorized, attempt-scoped asset delivery route.

No public start endpoint is registered. No production entitlement issuer is
connected and the student exam remains locked. Test grants exist only in test
code. The implementation links history only within a verified guest session.
Cross-session history requires an authenticated account or a server-verified
identity claim with consent and a stable identity key. Name or guest-entered
phone similarity is insufficient. Fingerprints use normalized prompt text
and detect exact textual repeats. They do not infer semantic duplicates.

If the bank is absent or unused candidates cannot supply a full exam, the
service returns `ExamUnavailable(code="EXAM_UNAVAILABLE", reason=...)`, records
a sanitized operational event, and creates no attempt or consumption record.

## Admin contract and future refunds

`GET /api/v1/admin/exam-bank/status` requires an active admin session. It returns
readiness, the active revision and source IDs, policy, last successful processing,
unavailability count and up to 20 recent source rows with per-state totals.
The dashboard and Questions workspace show these values. Existing protected
PDF previews and retry controls remain available for diagnostics.

A future refund request can accept a payment transaction reference and
idempotency key from an authenticated claimant. The backend must resolve
ownership, settlement, entitlement linkage and prior refund state using
trusted records and provider verification. It can then create a pending
refund request for a separate execution workflow. A submitted phone number
alone is insufficient. Phase 04C adds no refund endpoint or execution.

## Validation

| Check | Executed result |
| --- | --- |
| Ruff lint and formatting | Passed |
| Backend Pytest | 209 passed, including six Phase 04C integration tests. The existing Starlette TestClient deprecation warning remains. |
| Alembic | Test upgrade, downgrade, repeatability and metadata checks passed. Development upgraded to `20261105_0005` with previous table counts preserved. |
| Live API/database audit | Passed |
| ESLint, TypeScript and Next.js 16.4.5 Turbopack production build | Passed |
| Frontend unit | 5 passed |
| Public Chrome regressions | 6 passed at 390px, 834px and 1440px. Exam remained locked even without JavaScript. |
| Admin Chrome regressions | 12 distinct checks verified across the initial and focused runs at 390px, 834px and 1440px. |

The eligibility fixture had 40 extracted items and 33 eligible items. It excluded
missing and conflicting answers, invalid option labels, a missing image, two
duplicate prompts and residual answer-marker text. Additional runs proved the
7/4/9 mix, explicit unstratified reprocessing, failed replacement preservation,
cross-revision history exclusion, same-grant concurrency and immutable snapshots.

[Backend results](evidence/phase04c/pytest.log) ·
[Build](evidence/phase04c/build.log) ·
[Migration](evidence/phase04c/development-migration.json) ·
[Public browser results](evidence/phase04c/public-browser-results.json) ·
[Initial admin browser run](evidence/phase04c/admin-browser-initial-results.json) ·
[Corrected admin browser run](evidence/phase04c/admin-browser-results.json) ·
[Mobile bank monitor](evidence/phase04c/browser/390px-exam-bank.png) ·
[Fixture cleanup](evidence/phase04c/fixture-cleanup.json)

Six initial admin checks passed. Six stopped at a Playwright selector that
matched the visible Questions page and the hidden dashboard retained during
client navigation. All six affected checks passed after scoping the assertion
to visible content. The browser verified that a completed synthetic import with
two eligible questions remained unready for a 20-question exam.

## Files and limitations

- Backend services: `app/services/exam_bank.py`, `app/services/exam_generation.py`,
  `app/services/pdf/jobs.py`, `app/services/pdf/parsing.py` and `app/services/admin_reporting.py`.
- Data and API: `app/models/exam_bank.py`, model registration, revision 0005,
  `app/api/v1/admin.py`, `app/api/v1/pdf_import.py` and worker policy configuration.
- Operations: `scripts/pdf_worker.py`, `scripts/verify_foundation.py`, environment
  example and both READMEs.
- Frontend: `BankMonitor.tsx`, the protected Dashboard, Questions and PDF pages,
  `PdfWorkspace.tsx`, `DraftPreview.tsx` and the server-side admin client.
- Verification: `tests/integration/test_exam_bank.py`, existing migration, schema
  and API assertions, the isolated browser fixture, and the admin Chrome suite.

No representative exam PDF was supplied. Supported-layout infrastructure can
be verified with fixtures, while real-source answer and image association still
requires evaluation against that PDF. Unrecognized layouts, answer formats and
difficulty metadata should be handled by a documented extraction strategy.
The existing local worker is supervised separately and retains its Phase 04B
crash-retry and private-storage operational limits.
