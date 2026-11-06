# Phase 04K real PDF structural recovery and activation

## Original warning audit

The original Phase 04J result had 381 drafts, 229 eligible questions, two eligible sign questions and 19 structural warnings. The table uses the original parser's affected identifier, which can differ from the number actually printed on the following source row. Evidence is summarized by option-label sequence and page location. The source itself stays in local protected PDF storage.

| ID | Page | Original identifier | Extracted structure | Original source evidence and cause | Neighbor or boundary effect | Correction and outcome |
| --- | ---: | --- | --- | --- | --- | --- |
| W01 | 6 | 19 | ABCDABCD | Ruled next row starts with a separate 20. and a stem on the same line | Options from 20 joined 19 | Recover both rows from the separate number and ruling |
| W02 | 7 | 24 | No options | Within the same cell, the next source line starts with 4. after a length ending in cm | A false question boundary separated the stem from its choices | Preserve the numeric clause inside 24 |
| W03 | 62 | 223 | ABCDABCD | A new ruled cell starts with 225 immediately followed by letters, with no period | Options from 225 joined 223 | Recognize compact numbering only at a ruling |
| W04 | 63 | 227 | ABCDABCD | A separate ruled cell repeats 227 as a stand-alone printed number | Two distinct stems were merged | Split the rows and retain duplicate-number ambiguity. Neither gets an inferred key |
| W05 | 64 | 228 | AABC | Two source options start with A in one row | Local label collision | Preserve diagnostic and reject |
| W06 | 64 | 229 | ABBC | Two source options start with B in one row | Local label collision | Preserve diagnostic and reject |
| W07 | 67 | 235 | No text options | A through D are printed beside four shapes in a two-column cell | Local image associations | Recover four source crops with printed labels |
| W08 | 67 | 236 | No text options | Four visual choices have bare printed labels | Local image associations | Recover crops only for unique geometric matches |
| W09 | 72 | 249 | No text options | Four visual choices sit above or to the right of their labels | Local image associations | Recover crops only for unique geometric matches |
| W10 | 75 | 256 | AABC | The printed labels repeat A | Local label collision | Preserve diagnostic and reject |
| W11 | 78 | 265 | AABC | The printed labels repeat A | Local label collision | Preserve diagnostic and reject |
| W12 | 79 | 266 | No text options | Four separate sign images are paired with bare labels | Local image associations | Recover crops only for unique geometric matches |
| W13 | 79 | 267 | ABBC | The printed labels repeat B | Local label collision | Preserve diagnostic and reject |
| W14 | 80 | 270 | AABC | The printed labels repeat A | Local label collision | Preserve diagnostic and reject |
| W15 | 91 | 294 | ACCD | The printed labels repeat C | Local label collision | Preserve diagnostic and reject |
| W16 | 93 | 299 | AABC | The first marked A is followed by another printed A in the same row | Local label collision | Preserve both source labels as evidence and reject |
| W17 | 93 | 300 | ABBC | The marked B is followed by another printed B in the same row | Local label collision | Preserve both source labels as evidence and reject |
| W18 | 133 | 395 | AACD | The printed labels repeat A | Local label collision | Preserve diagnostic and reject |
| W19 | 138 | 405 | ABCDABCD | A separate ruled cell shows 406 with a space before its period and its own sign | Options from 406 joined 405 | Recover the next numbered row and preserve both sign associations |

The recoveries also expose question 224, whose printed identifier is separate from the stem and whose options are images. No warning was discarded to force activation. The duplicate-number case remains an answer-mapping ambiguity even when it no longer presents as a merged-row warning.

## Parser and activation

The marked-table strategy now uses nearby horizontal rules to recognize bare numbers and compact numbering. Ordinary numbered questions still work when a source rule is absent. A narrow continuation check preserves the length clause on page 7. Parenthesized and green answer evidence continues to require one source-backed option. Conflicts and duplicate identifiers remain ineligible.

For image-only rows, printed anchors must map to distinct, non-overlapping crops within their question bounds. Raster candidates are preferred when the source provides them. A compact vector candidate can be used when it is uniquely placed and free of text contamination. The worker preserves the original page, bounding box and PNG hash. A sub-point trim removes only a font-box sliver at a crop's left edge. It rejects a substantive word overlap. The bank verifies the labels, source locations, PNG integrity and distinct crops before accepting any image-only row. Ambiguous associations emit a blocking diagnostic. Exam views use the existing authenticated current-question image route, with each image under its option. Option-image metadata does not expose any answer marker.

The existing automatic activation transaction and immutable revisions remain in place. The bank still blocks activation on unresolved diagnostics. It also checks for a pool of 20 questions, a sign/general mix and the configured difficulty requirements. The real-document check uses the isolated unstratified policy to test readiness without claiming nonexistent difficulty labels. No manual approval route was added.

The admin views display image-only option counts and source question identifiers and labels on structural warnings. Draft preview captions identify associated choices. Changes are confined to the PDF parser, worker and crop service, bank validation, authenticated exam presentation, admin diagnostics and regression tests. No migration is needed.

## Performance and regression evidence

The in-memory source profile measured 4.34 seconds for page reading and structural parsing over 149 pages. Per-page median, p95 and maximum were 24.1 ms, 55.6 ms and 120.4 ms. Rendering and hashing 37 crop candidates took 7.87 seconds. The profile excludes database transactions and file storage. [Source profile](evidence/phase04k/source-profile.json)

The full backend suite passed 246 tests with no failures or skips, including PostgreSQL, the source regression and the ruled-boundary case. Ruff lint and formatting passed. Alembic remains at `20261105_0009` with no schema drift. The dedicated vector integration and mobile browser checks run separately. [Backend log](evidence/phase04k/pytest.log)

ESLint, TypeScript, five frontend unit tests and the Turbopack production build passed. [Build log](evidence/phase04k/build.log)

Changed implementation files include `backend/app/services/pdf/parsing.py`, `images.py`, `jobs.py`, `backend/app/services/exam_bank.py`, `backend/app/services/exam_execution.py`, `src/components/exam/TimedExam.tsx`, the admin PDF workspace, draft preview and bank monitor, and their frontend types. New and extended tests cover source rows, marks, vector choices, immutable bank activation and browser image presentation.

## Isolated real-PDF result

| Measure | Phase 04J | Phase 04K |
| --- | ---: | ---: |
| Processed pages | 149 | 149 |
| Extracted drafts | 381 | 394 |
| Eligible questions | 229 | 235 |
| Rejected drafts | 152 | 159 |
| Eligible road-sign questions | 2 | 7 |
| Eligible parenthesized answers | 197 | 203 |
| Eligible green-marked answers | 32 | 32 |
| Recovered image-only options | 0 | 20 |
| Structural warnings | 19 | 10 |

The 149-page upload completed with warnings. PostgreSQL recorded 375 answer-evidence objects and 22 bank rows with associated images. Rejections among the 394 drafts were 80 extraction errors, 50 image errors, 13 incomplete options, 11 ambiguous answers and 5 missing answers. The 10 unsupported-label warnings are additional to those row counts. The worker took 45.7 seconds end to end, including image storage and database transactions. The separate instrumented worker run below measures insertion and bank finalization. The real revision did not activate. [Real PDF and activation-control browser run](evidence/phase04k/real-pdf.json)

## Pilot decision

**The real PDF remains blocked for pilot use.** Its revision is `EXTRACTION_IMPROVEMENTS_REQUIRED`. Ten source rows still have genuine duplicate labels, and the repeated identifier 227 remains ambiguous. The original healthy synthetic bank stayed active after the real import. The source also lacks verified difficulty metadata for the configured quota policy. No real-document exam was started. There was no production bank replacement or real-money activity.

The six student Chrome checks passed at 390px, 834px and 1440px. Each completed a failed first attempt and a passing retake, with two distinct consumed entitlements and zero shared question fingerprints within its guest session. The three local synthetic retake starts measured 124, 131 and 133 ms, with a 131 ms median. This is response timing on a small local fixture. Exam start uses immutable bank rows and performs no PDF parsing. [Student browser evidence](evidence/phase04k/student-browser.json)

The 12 administrator Chrome regressions passed at all three widths. They covered authorization, expired sessions, operational views, PDF recovery and private source previews. The separate desktop worker run passed both the synthetic activation and real-source outcome checks. [Administrator browser evidence](evidence/phase04k/admin-browser.json)

Remaining extraction limits include mixed text/image choice rows, ambiguous or overlapping crops, and green highlights that lack a supported text-option anchor. The text-fingerprint duplicate policy is conservative for repeated sign prompts even when source images differ. Some real rows can therefore remain ineligible despite having source imagery. These limits do not require manual administrator approval to activate a bank that satisfies the configured policy.

## Dedicated image-choice checks and worker stage timing

The corrected synthetic vector fixture passed its dedicated PostgreSQL test. It activated a 20-question bank, generated an authorized exam, and served all four option PNGs over the current-question route. The dedicated 390px Chrome run passed and verified that all four option images loaded in order without horizontal overflow. The first browser run failed because its fixture repeated identical marker text and did not meet the layout signature. The fixture now supplies distinct markers. [Vector backend log](evidence/phase04k/vector-backend.log) [Vector mobile run](evidence/phase04k/vector-student.json) [Mobile screenshot](evidence/phase04k/vector-options-390px.png)

| Worker stage | Synthetic vector bank | Real source |
| --- | ---: | ---: |
| Image rendering and storage | 80 ms | 3,287 ms |
| PostgreSQL INSERT cursor time | 144 ms across 85 statements | 3,610 ms across 2,373 statements |
| Bank finalization call | 100 ms, activation selected | 576 ms, activation rejected |
| In-process worker total | 853 ms | 26,564 ms |

The stage sample is a separate local instrumented worker run against isolated PostgreSQL. INSERT time includes driver round trips, and the finalization call includes its internal inserts. The two figures overlap. Final transaction commit and coordinator startup are outside the finalization call. The real-source browser coordinator run took 45.7 seconds. [Worker-stage evidence](evidence/phase04k/worker-stage-profile.json)
