"""One import per worker; session advisory locks protect processing and retry."""

import hashlib
from datetime import UTC, datetime
from uuid import UUID

import pymupdf
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.session import Database
from app.models.exam_bank import BankRevision
from app.models.pdf_import import (
    PdfDocument,
    PdfImportJob,
    QuestionDraft,
    QuestionDraftAnswer,
    QuestionDraftAsset,
    QuestionDraftOption,
)
from app.services.exam_bank import finalize_bank
from app.services.pdf.images import question_images
from app.services.pdf.ocr import ocr_lines
from app.services.pdf.parsing import (
    NumberedChoiceStrategy,
    apply_green_highlights,
    evidence,
    has_marked_table_layout,
    mark_table_rows,
    page_lines,
)
from app.services.pdf.storage import PdfError, PdfStorage


def lock_number(identifier: UUID):
    return int.from_bytes(hashlib.sha256(identifier.bytes).digest()[:8], "big", signed=True)


def try_lock(connection, identifier):
    acquired = connection.scalar(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_number(identifier)}
    )
    connection.commit()
    return acquired


def unlock(connection, identifier):
    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_number(identifier)})
    connection.commit()


def reset_drafts(session, job_id):
    ids = select(QuestionDraft.id).where(QuestionDraft.import_job_id == job_id)
    # Answers reference options; remove them first, then cascade the other children.
    session.execute(
        delete(QuestionDraftAnswer).where(QuestionDraftAnswer.question_draft_id.in_(ids))
    )
    session.execute(delete(QuestionDraft).where(QuestionDraft.import_job_id == job_id))


def fail_job(database, identifier, code="PROCESSING_FAILED", *, include_queued=False):
    with database.session_factory.begin() as session:
        job = session.get(PdfImportJob, identifier)
        if job and (job.status == "PROCESSING" or include_queued and job.status == "QUEUED"):
            job.status = "FAILED"
            job.completed_at = datetime.now(UTC)
            job.failed_item_count = max(1, job.failed_item_count)
            job.diagnostics = [{"code": code}]
            document = session.get(PdfDocument, job.document_id)
            document.import_status = "FAILED"
            document.error_summary = code


def process_job(settings, identifier: UUID):
    database = Database(settings)
    try:
        with database.engine.connect() as connection:
            if not try_lock(connection, identifier):
                return False
            try:
                with Session(connection, expire_on_commit=False) as session:
                    with session.begin():
                        job = session.get(PdfImportJob, identifier)
                        if not job:
                            return False
                        if job.status not in {"QUEUED", "PROCESSING"}:
                            completed = job.status in {"COMPLETED", "COMPLETED_WITH_WARNINGS"}
                            revised = session.scalar(
                                select(BankRevision.id)
                                .where(BankRevision.job_id == job.id)
                                .limit(1)
                            )
                            if not completed or revised:
                                return False
                        document = session.get(PdfDocument, job.document_id)
                        reset_drafts(session, job.id)
                        job.status = document.import_status = "PROCESSING"
                        job.started_at = datetime.now(UTC)
                        job.completed_at = None
                        job.processed_pages = job.extracted_question_count = 0
                        job.review_required_count = job.failed_item_count = 0
                        job.diagnostics = []
                        document.error_summary = None
                        document_id = document.id
                    storage = PdfStorage(settings)
                    path = storage.source(
                        document.storage_key, document.sha256_hash, document.file_size_bytes
                    )
                    pymupdf.TOOLS.mupdf_display_errors(False)
                    pymupdf.TOOLS.mupdf_display_warnings(False)
                    strategy = NumberedChoiceStrategy(
                        settings.pdf_question_pattern,
                        settings.pdf_option_pattern,
                        settings.pdf_max_questions,
                    )
                    with pymupdf.open(path) as pdf:
                        strategy.marked_table = has_marked_table_layout(
                            page_lines(pdf[0], settings.pdf_max_page_chars)
                        )
                        for page in pdf:
                            strategy.page = page.number + 1
                            lines = page_lines(page, settings.pdf_max_page_chars)
                            if not lines:
                                lines = ocr_lines(page, settings)
                                if lines:
                                    strategy.diagnostics.append(
                                        {"code": "OCR_UNVERIFIED", "page": page.number + 1}
                                    )
                            if strategy.marked_table:
                                mark_table_rows(page, lines)
                                apply_green_highlights(page, lines)
                            strategy.feed(
                                lines,
                                page.rect.width,
                                page.rect.height,
                            )
                            with session.begin():
                                job.processed_pages = page.number + 1
                        questions = strategy.finish()
                        for order, question in enumerate(questions, 1):
                            # Evidence text must still occur verbatim on its claimed source page.
                            lines = (
                                question.lines
                                + [line for option in question.options for line in option.lines]
                                + question.answers
                                + ([question.difficulty] if question.difficulty else [])
                            )
                            for line in lines:
                                if not line.ocr and line.text not in pdf[line.page - 1].get_text():
                                    raise PdfError("SOURCE_EVIDENCE_MISMATCH")
                            anchors = [
                                (o.label, o.lines[0]) for o in question.options if o.image_only
                            ]
                            assets = list(
                                question_images(
                                    pdf,
                                    question.regions,
                                    storage,
                                    raster_only=strategy.marked_table,
                                    option_anchors=anchors,
                                )
                            )
                            if anchors and (
                                len(anchors) != len(question.options)
                                or sorted(
                                    asset["source_location"].get("option_label") for asset in assets
                                )
                                != sorted(label for label, _ in anchors)
                            ):
                                question.uncertain = True
                                strategy.diagnostics.append(
                                    {
                                        "code": "AMBIGUOUS_OPTION_IMAGE",
                                        "page": question.lines[0].page,
                                        "question": question.number,
                                    }
                                )
                            with session.begin():
                                draft = QuestionDraft(
                                    document_id=document_id,
                                    import_job_id=identifier,
                                    source_order=order,
                                    source_question_number=question.number,
                                    question_text=question.text,
                                    source_page_number=question.lines[0].page,
                                    source_location={
                                        **evidence(question.lines),
                                        "regions": question.regions,
                                        "difficulty": evidence([question.difficulty])
                                        if question.difficulty
                                        else None,
                                    },
                                    answer_status=question.status,
                                    extraction_status="NEEDS_REVIEW"
                                    if question.uncertain
                                    else "EXTRACTED_UNVERIFIED",
                                )
                                session.add(draft)
                                session.flush()
                                selected = None
                                for index, option in enumerate(question.options):
                                    row = QuestionDraftOption(
                                        question_draft_id=draft.id,
                                        option_label=option.label,
                                        option_text=option.text,
                                        display_order=index,
                                        source_page_number=option.lines[0].page,
                                        source_location=evidence(option.lines),
                                    )
                                    session.add(row)
                                    session.flush()
                                    if option.label == question.selected_label:
                                        selected = row.id
                                session.add(
                                    QuestionDraftAnswer(
                                        question_draft_id=draft.id,
                                        selected_option_id=selected,
                                        raw_answer_text="\n".join(
                                            line.text for line in question.answers
                                        )
                                        or None,
                                        evidence_page_number=question.answers[0].page
                                        if question.answers
                                        else None,
                                        evidence_location=evidence(question.answers)
                                        if question.answers
                                        else None,
                                        verification_status=question.status,
                                    )
                                )
                                for asset in assets:
                                    session.add(
                                        QuestionDraftAsset(
                                            question_draft_id=draft.id,
                                            document_id=document_id,
                                            **asset,
                                        )
                                    )
                                job.extracted_question_count = order
                                job.review_required_count = (
                                    order  # Extraction is never final approval.
                                )
                    with session.begin():
                        diagnostics = strategy.diagnostics[:1000]
                        if not questions:
                            diagnostics.append({"code": "NO_SUPPORTED_QUESTIONS"})
                        status = (
                            "COMPLETED_WITH_WARNINGS"
                            if diagnostics
                            or any(
                                q.status != "EXTRACTED_UNVERIFIED" or q.uncertain for q in questions
                            )
                            else "COMPLETED"
                        )
                        job.status = document.import_status = status
                        job.diagnostics = diagnostics
                        job.failed_item_count = len(strategy.diagnostics)
                        job.completed_at = document.processed_at = datetime.now(UTC)
                        finalize_bank(
                            session,
                            job,
                            document,
                            storage,
                            settings.exam_selection_policy,
                            road_sign_count=settings.exam_category_road_sign_count,
                        )
                    return True
            except Exception as error:
                connection.rollback()
                fail_job(
                    database,
                    identifier,
                    error.code if isinstance(error, PdfError) else "PROCESSING_FAILED",
                )
                return False
            finally:
                unlock(connection, identifier)
    finally:
        database.dispose()
