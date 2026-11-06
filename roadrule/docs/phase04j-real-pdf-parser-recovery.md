# Phase 04J real road-rules PDF parser recovery

## Source and diagnosis

The original 149-page development import was located through the local PDF storage and the PostgreSQL document record for `Road rules.pdf`. The text is embedded. The inspected early, middle, late and sign pages use ruled table cells with wrapped lines and questions that can continue across page boundaries. Several later question numbers have no intervening space after the period. Some numbers stand alone. Page footers and section labels are separate from question wording. The available source has no verified difficulty classification.

The file uses two explicit answer conventions. Some options start with a parenthesized label such as `(a)`. Other pages use bright-green filled rectangles over embedded option text, visible in a normal rendering. The scan found 88 green drawing fills, with multiple fills on some wrapped answers. The catalog had no optional-content properties and PyMuPDF reported zero ordinary annotations. The inspection did not establish a hover-dependent answer mechanism. A color fill by itself is insufficient unless it is aligned to a recognized option in the identified source layout.

### Original development bank

| Reason | Rows |
| --- | ---: |
| Incomplete options | 168 |
| Missing usable answer | 55 |
| Extraction error | 41 |
| Image error | 9 |
| Eligible | 0 |

A read-only check of all 273 original bank rows found that all 41 extraction-error rows shared their question-text fingerprint with another row. The import also recorded 50 unsupported-structure diagnostics, which are separate from persisted bank-row counts. None of the original rows contained a JSON answer-evidence object. The earlier count of 273 included JSON null values and overstated the evidence.

The old option pattern excluded parenthesized labels and labels without a space after the separator. The old question pattern missed later numbers such as `338.` followed immediately by text. Missing question boundaries combined unrelated choices, producing extra or duplicate labels. The old answer parser recognized explicit answer lines and answer-key rows but did not recognize the parentheses or the green source marks. The broad drawing crop strategy could also treat ruled layout graphics as image candidates. Some source rows still have duplicate labels or image-only choices with no option text. Examples include duplicate labels on page 64 and image-only choices on page 67. These cases require reliable disambiguation before they can enter an exam.

## Parser and evidence

- The existing parsing strategy now recognizes the marked table layout using embedded header text and multiple explicit parenthesized options on its first page. The original strategy remains the default for other documents.
- The marked layout recognizes parenthesized answer labels and compact number and option syntax. The bank validator ties each marker to the same option label, wording, page and bounding box. Exact bright-green rectangles are accepted only when a single rectangle covers a recognized option line within bounded geometric tolerances. Competing labels are ambiguous. Bare option labels are treated as uncertain.
- Marked table imports use raster crops within the question region. The parser excludes crops that overlap embedded words and omits table vector decorations. The existing vector-crop strategy remains available for other layouts. Source page 71, question 246, was visually checked against its raster sign and parenthesized B option. The crop candidate lies within the question region with its original aspect ratio. Page 110, question 338, was visually checked against its green A option. Parser spot checks also cover questions 1, 2 and 427.
- The bank monitor adds Kinyarwanda counts for evidence-backed answers, parentheses, green marks, incomplete choices and extraction errors. These counts describe eligible evidence and do not change grading or activation.
- Changes are in `backend/app/services/pdf/{parsing,jobs,images}.py`, `backend/app/services/exam_bank.py`, `src/components/admin/questions/BankMonitor.tsx`, and parser and browser verification tests. No migration is needed.

## Readiness rules

Automatic activation still requires a supported import without blocking diagnostics, at least twenty usable questions, and a sign/general mix. The configured difficulty policy still requires reliable source difficulty labels when quotas are enabled. A failed replacement leaves the active bank intact. The development record was read-only during this phase. The updated source was re-uploaded and processed in the isolated browser database with unstratified selection. The test uses that policy to avoid implying an unsupported difficulty mix.

The selected labels record what the source explicitly marks. The validation does not independently establish the factual correctness of the source's answer choices.

## Automated validation

- Backend Pytest passed all 244 tests with the local source path supplied, including PostgreSQL, the migration round trip and the two new marker and real-source spot checks. Ruff lint and format checks passed. The database remains at `20261105_0009` with no schema drift. The first regression pass caught extra zero-count keys on generic PDFs. The final implementation preserves the previous payload for those imports. [Backend log](evidence/phase04j/final-pytest.log)
- ESLint, TypeScript, all five frontend unit tests and the Turbopack production build passed. The initial type check identified the missing diagnostic keys in the frontend type, which was updated before the successful rebuild. [Build log](evidence/phase04j/build.log)
- Chrome passed 6 student and 12 administrator checks at 390px, 834px and 1440px. The synthetic student runs retained normal exam scoring, server-authorized access, a 12/20 pass and retake history. The first result remained unchanged and the two attempts shared zero fingerprints within each guest session. [Student runs](evidence/phase04j/student-browser.json) [Admin runs](evidence/phase04j/admin-browser.json)
- The first end-to-end source run with green detection found that the bank validator rejected green options whose underlying text had trailing whitespace. The follow-up change normalizes whitespace only for matching the source-marked option. The raw text and page coordinates remain in the evidence. A targeted test verifies eligibility for that case.

## Final isolated reimport

| Measure | Original development import | Updated isolated import |
| --- | ---: | ---: |
| Processed pages | 149 | 149 |
| Extracted drafts | 273 | 381 |
| Eligible bank questions | 0 | 229 |
| Ineligible bank questions | 273 | 152 |
| Eligible parenthesized answers | 0 | 197 |
| Eligible green-marked answers | 0 | 32 |
| Eligible road-sign questions | 0 | 2 |
| Unsupported-structure diagnostics | 50 | 19 |

The updated worker persisted 362 answer-evidence objects and associated raster images with 17 bank rows. Of the 152 rejected rows, 77 had extraction errors, 45 image errors, 13 incomplete choices, 11 ambiguous answers and 6 missing answers. The 19 diagnostics concern unsupported source rows and are distinct from the rejected bank rows.

The follow-up run passed nine targeted backend checks after the whitespace correction and both dedicated desktop PDF browser checks. Its real-import test asserted positive green, parentheses and eligible road-sign counts. The 42-question synthetic control activated automatically. The real revision ended as `EXTRACTION_IMPROVEMENTS_REQUIRED` and the synthetic bank remained active. [Final focused tests](evidence/phase04j/final-focused.log) [Final PDF browser and worker evidence](evidence/phase04j/verified-green-pdf.json)

## Pilot decision

**The real-PDF pilot remains blocked.** The import can now recover both explicit answer formats and some safe sign crops. Nineteen unresolved structural warnings still prevent activation, including cases with image-only choices, duplicate labels and ambiguous boundaries. The source also lacks supported difficulty metadata for the configured quota policy. A real-source exam was therefore outside the readiness condition. The synthetic student exam and retake path passed across all three widths. No real payment activity was observed.
