# Phase 04B — PDF import and question drafts

2026-11-05 · `D:/Roadrules/roadrule`

## Architecture

The administrator uploads from `/admin/pdf-uploads`. A same-origin Next.js route
handler under `/admin/pdf-api` verifies the existing HttpOnly admin session, enforces
the frontend Origin on mutations, and forwards only allowlisted PDF API paths to
FastAPI. FastAPI independently enforces the active admin session and the existing
Origin/custom-header CSRF policy. The browser reports bytes sent separately from
persisted worker page progress. The workspace uses Kinyarwanda labels and has
paginated document and draft views, source answer evidence, and private PNG previews.

The API streams the raw PDF into a private temporary file, hashes it, checks its
structure in a time- and memory-limited child process, and inserts a document and
queued job. The original file is retained byte for byte. A separate Python worker
reads queued jobs and saves unpublished questions, options, answers, and assets.
The HTTP upload response returns after validation and queueing.

## Data and migration

`20261105_0004_pdf_import_pipeline.py` adds `pdf_documents`, `pdf_import_jobs`,
`question_drafts`, `question_draft_options`, `question_draft_answers`, and
`question_draft_assets`. The migration extends the existing admin audit event
constraint with `PDF_UPLOAD_ATTEMPT`. It does not replace earlier revisions.

Document hashes and document/job ownership are unique. Draft order is unique per
job, and a composite foreign key prevents an answer from selecting an option from
another draft. Deleting a parent document or job is restricted while dependent
records remain. Draft-owned rows are cleaned in a defined order on retry. Repeated
image bytes share a storage key while separate association rows preserve location.
No general deletion API is exposed. The migration downgrade restores the old audit
constraint and refuses to proceed while PDF upload audit events are retained.

The existing PostgreSQL cluster at `127.0.0.1:55432` and its development/test roles
were reused. Development revision advanced from `20261105_0003` to `20261105_0004`
with student and administrator row counts preserved. No synthetic uploads or test
administrators were added to development. [Migration evidence](evidence/phase04b/development-migration.json)

## API contracts

All routes below use prefix `/api/v1/admin` and require an active administrator.
POST requests require an exact configured Origin and `X-CSRF-Protection: 1`.
JSON errors use the existing sanitized `{error: {code, message}}` envelope.

| Method and relative path | Response |
| --- | --- |
| `POST /pdf-documents` | `202` with `{document, duplicate}`. Send the original binary bytes as `application/pdf` and the percent-encoded filename in `X-PDF-Filename`. A duplicate returns the existing record and job. |
| `GET /pdf-documents` | `{items, total, page, page_size}` sorted by most recent upload. |
| `GET /pdf-documents/{document_id}` | Document metadata, SHA-256, page count and status. |
| `GET /pdf-documents/{document_id}/jobs` | The document's persisted import job. |
| `GET /pdf-import-jobs/{job_id}` | State, progress, counters and sanitized diagnostic codes. |
| `POST /pdf-import-jobs/{job_id}/retry` | `202` queues a failed or abandoned job using the same identifier. `409` if active or ineligible. |
| `GET /question-drafts` | Paginated draft records with options, answers and assets. Optional `document_id`. |
| `GET /question-drafts/{draft_id}` | One draft with its source evidence. |
| `GET /question-draft-assets/{asset_id}` | Authorized PNG crop, checked against its stored hash. |
| `GET /pdf-documents/{document_id}/pages/{page_number}` | Authorized, bounded PNG page preview. Page numbers are 1-based. |

`page` defaults to 1. `page_size` defaults to 20 and is capped at 50. The API uses
401 for missing/invalid admin sessions, 403 for origin/CSRF rejection, 404 for
unknown records or pages, 413 for an oversized upload, 415 for wrong media type,
422 for unsupported PDF structure, and 429 for the durable upload budget.
Storage paths and source PDFs are not returned by these routes.

## Supported input and extraction

The default `NumberedChoiceStrategy` supports selectable text in a mostly single
column, numbered prompts such as `1. …` or `1) …`, and two or more distinct A–D
option labels. The question and option regexes can be configured with
`PDF_QUESTION_PATTERN` and `PDF_OPTION_PATTERN`, with two capture groups for label
and text. The parsing strategy interface supports future format-specific parsers.
It preserves text spans and line breaks without translation or paraphrase. Reading
order uses page and text coordinates. A continuing question or option can span
pages. Each source segment stores its page, bounding box, extraction method and text.

Unstructured text and incomplete choice blocks do not become valid draft questions.
Unsupported structures and detected column layouts produce review diagnostics.
The default layout excludes a narrow page margin. Complex columns, unusual fonts,
repeated headers inside the body, tables, dense answer grids, and uncertain page
continuations require document-specific calibration and administrator review.

Structural validation checks PDF signature and parser structure, page bounds, size,
encryption, repair state, embedded files, forms and common action-bearing objects.
The native parser runs without executing PDF actions. Optional local OCR uses
PyMuPDF's Tesseract adapter with explicitly supplied trained data via
`PDF_OCR_TESSDATA` and `PDF_OCR_LANGUAGE`. Missing OCR or an unreadable scan produces
review diagnostics. OCR text is marked as uncertain and cannot automatically select
an option. No OCR language data or representative scan was available for acceptance.

## Images and answers

Raster images are identified from displayed PDF image bounds. Nearby vector drawing
components can form a crop. An asset must fit inside the question's geometric
region. Header graphics outside that region are excluded. Crops are rasterized to
PNG at a bounded scale, preserving aspect ratio and page coordinates. Every asset
association remains subject to review. Geometry cannot establish the semantic role
of a figure, especially on complex layouts.

An explicit inline `Igisubizo: B` or `Answer: B`, or a numbered row in an explicit
`Ibisubizo`/`Answer key` section, can support an answer. The worker records raw key
text, source page and coordinates. A selected option requires a unique question
number, one unambiguous source label, and exactly one matching option. Conflicting
keys, missing options, duplicate numbers and OCR uncertainty prevent selection.
`ANSWER_NOT_FOUND` has no selected option or answer evidence. `NEEDS_REVIEW`
retains ambiguous evidence without selecting an option. `EXTRACTED_UNVERIFIED`
retains a source-backed selection pending human approval. No status publishes a draft.

The future student delivery path should use separately approved, question-scoped
asset identifiers and authorization against a published exam version. Student
requests have no path to unpublished crops or full source PDFs in this phase.

## Worker and operations

Install the existing backend project dependencies, apply the migration, and start
FastAPI as documented in the backend README. Run the worker in a separate terminal.

```powershell
.venv/Scripts/python.exe scripts/pdf_worker.py
```

`--once` drains the current queue. Use the same database and private storage root for
API and worker. Default ingress limits are 25 MiB and 600 pages. The Next ingress
cap is independently configurable with `PDF_MAX_FILE_BYTES`. The browser currently
has a 25 MiB input guard. The worker defaults to a 300-second job timeout and a
512 MiB child-process memory ceiling. Validation/preview children have 15-second
limits and two concurrent slots per API process. Review all limits in the backend
`.env.example` when operating with larger sources.

Job lifecycle is `QUEUED → PROCESSING → COMPLETED`, `COMPLETED_WITH_WARNINGS`, or
`FAILED`. The worker updates pages in short transactions, then commits each complete
draft with its options, answer and asset references. A coordinator lock bounds one
worker per database and a job lock prevents concurrent processing or retry. A timeout
or child exit produces a sanitized failure. If the coordinator dies, a job can
remain `PROCESSING`. Once its connection releases the lock, an administrator may
retry it. Retry clears the old draft set and counters, preserves the original file,
and reuses the job ID. Earlier committed drafts can be visible during a failed run.

This is a local execution model. Production needs a supervised durable queue with
leases/heartbeats, timeout and retry policy, separate low-privilege parser identity,
monitored private storage, quotas, access controls and a cleanup plan for abandoned
incoming files and unreferenced content hashes. A database/filesystem crash window
can leave an orphaned file. There is no claim of automatic crash recovery.

## Security

The private storage root must be outside static/public directories and writable only
by the service account. Generated UUID/content-hash keys are validated and resolved
beneath that root. Original filenames are metadata and travel in a header to keep
them out of URL access logs. Neither parser nor diagnostics emits source text,
filenames or credentials. The API and bridge return private, no-store responses.
Use existing production TLS/admin-cookie configuration and disable header/body logging
at proxies. Parser subprocess resource limits are not a substitute for deployment
isolation. The upload budget is global and durable, with 10 admitted attempts/hour by
default. Invalid uploads also consume the budget.

## Files

- Backend model, schemas and API in `app/models/pdf_import.py`,
  `app/schemas/pdf_import.py`, and `app/api/v1/pdf_import.py`.
- Storage, probing, parsing, OCR, image extraction, limits, uploads and job execution
  in `app/services/pdf/`. Worker entry point in `scripts/pdf_worker.py`.
- Migration 0004, config/env/lock updates, admin audit event, router and sanitized
  error integration. Existing schema/API and browser fixture expectations were updated.
- Frontend `src/components/admin/pdf/`, `src/features/admin/pdf-types.ts`, the protected
  PDF page and the allowlisted `src/app/admin/pdf-api/[...path]/route.ts` bridge.
- Synthetic PDF generators, unit/integration tests and Chrome browser flows under
  the existing test directories. Both READMEs describe the new worker setup.

## Validation and acceptance

| Check | Executed result |
| --- | --- |
| `python -m ruff check backend` | Passed |
| `python -m ruff format --check backend` | All 70 files formatted |
| `python -m pytest -q` from `backend` | 203 passed in 132.81 seconds, one existing Starlette TestClient HTTPX deprecation warning |
| `python -m alembic upgrade head` and `python -m alembic check` | Passed on the test database. Full tests also covered downgrade and repeat upgrade. Development upgraded additively. |
| `python scripts/verify_foundation.py` from `backend` | Passed the live health/readiness and database audit, including readiness 503 with unavailable PostgreSQL |
| `python -m pip check` | No broken requirements |
| `npm run lint` and `npm run typecheck` | Passed |
| `npm test` | 5 passed |
| `npm run build` | Passed with Next.js 16.4.5 Turbopack |
| `npm run test:browser` | 6 passed across 390px, 834px and 1440px |
| `npm run test:browser:admin` | 12 passed across the same widths |
| `npm run test:browser:admin -- --grep 'private PDF upload'` | 3 passed on the final build, including the original answer-evidence page preview |

The 27 new backend tests include a 50-page fixture whose 400 actual drafts
persisted in PostgreSQL, and a three-page fixture with two questions, one raster
crop, one vector crop and explicit answer evidence. Tests also exercised
missing/conflicting answers, source-byte preservation, rollback, duplicate uploads,
private previews, worker failure/retry, pagination, CSRF and guest isolation.

The full Chrome admin run exercised the normal login/session flow, unauthorized
access and the actual browser upload → PostgreSQL queue → worker subprocess →
draft/image review path. The browser tested malformed-file feedback and duplicate
upload notices. It denied unauthenticated image access and cross-origin mutation.
Screenshots use synthetic content and the temporary fixture account.

Execution evidence. [Backend tests](evidence/phase04b/pytest.log),
[production build](evidence/phase04b/build.log),
[public browser results](evidence/phase04b/public-browser-results.json),
[admin browser results](evidence/phase04b/admin-browser-full-results.json),
[final PDF browser results](evidence/phase04b/pdf-browser-results.json),
[mobile draft preview](evidence/phase04b/browser/390px-draft-preview.png),
[fixture cleanup](evidence/phase04b/fixture-cleanup.json).

A preliminary migration attempt exposed Alembic's constraint naming convention.
The corrected migration uses `op.f` for the existing constraint name. A sandbox-only
unit rerun could not create the Windows pytest temporary directory. The full final
suite passed using normal local access. The PostgreSQL service was restarted from
its existing data directory after the pause.

Phase 04B infrastructure is accepted on the verified synthetic fixtures. Accuracy for the intended road
rules PDF remains open because no representative source was supplied. Phase 04C can
build review and publishing on these draft records after calibration with the real
source. Publishing, examination generation and payment flows are outside this phase.

Parser implementation references. [PyMuPDF Page API](https://pymupdf.readthedocs.io/en/latest/page.html) · [PyMuPDF Document API](https://pymupdf.readthedocs.io/en/latest/document.html)
