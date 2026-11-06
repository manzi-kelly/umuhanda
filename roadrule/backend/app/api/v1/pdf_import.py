import hashlib
import tempfile
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import func, select

from app.api.v1.admin import DatabaseSession, require_admin
from app.models.pdf_import import (
    PdfDocument,
    PdfImportJob,
    QuestionDraft,
    QuestionDraftAnswer,
    QuestionDraftAsset,
    QuestionDraftOption,
)
from app.schemas.admin import AdminIdentity
from app.schemas.pdf_import import (
    AnswerResponse,
    AssetResponse,
    DocumentPage,
    DraftPage,
    DraftResponse,
    OptionResponse,
    PdfDocumentResponse,
    PdfJobResponse,
)
from app.services.pdf.jobs import reset_drafts, try_lock, unlock
from app.services.pdf.storage import PdfError, PdfStorage
from app.services.pdf.uploads import accept_upload, inspect_source

router = APIRouter(prefix="/admin", tags=["admin-pdf"], dependencies=[Depends(require_admin)])
Admin = Annotated[AdminIdentity, Depends(require_admin)]
Page = Annotated[int, Query(ge=1, le=100000)]
Size = Annotated[int, Query(ge=1, le=50)]


def required(session, model, identifier):
    row = session.get(model, identifier)
    if row is None:
        raise PdfError("NOT_FOUND", 404)
    return row


def draft_response(session, draft):
    options = session.scalars(
        select(QuestionDraftOption)
        .where(QuestionDraftOption.question_draft_id == draft.id)
        .order_by(QuestionDraftOption.display_order)
    ).all()
    answer = session.scalar(
        select(QuestionDraftAnswer).where(QuestionDraftAnswer.question_draft_id == draft.id)
    )
    assets = session.scalars(
        select(QuestionDraftAsset).where(QuestionDraftAsset.question_draft_id == draft.id)
    ).all()
    values = {
        field: getattr(draft, field)
        for field in DraftResponse.model_fields
        if field not in {"options", "answer", "assets"}
    }
    return DraftResponse(
        **values,
        options=[OptionResponse.model_validate(o) for o in options],
        answer=AnswerResponse.model_validate(answer) if answer else None,
        assets=[AssetResponse.model_validate(a) for a in assets],
    )


@router.post("/pdf-documents", status_code=202)
async def upload(
    request: Request,
    session: DatabaseSession,
    admin: Admin,
    filename: Annotated[str, Header(alias="X-PDF-Filename", min_length=1, max_length=3060)],
):
    identifier, duplicate = await accept_upload(request, session, admin, filename)
    return {
        "document": PdfDocumentResponse.model_validate(required(session, PdfDocument, identifier)),
        "duplicate": duplicate,
    }


@router.get("/pdf-documents", response_model=DocumentPage)
def documents(session: DatabaseSession, page: Page = 1, page_size: Size = 20):
    total = session.scalar(select(func.count()).select_from(PdfDocument))
    rows = session.scalars(
        select(PdfDocument)
        .order_by(PdfDocument.created_at.desc(), PdfDocument.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return DocumentPage(
        items=[PdfDocumentResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/pdf-documents/{document_id}", response_model=PdfDocumentResponse)
def document(document_id: UUID, session: DatabaseSession):
    return required(session, PdfDocument, document_id)


@router.get("/pdf-documents/{document_id}/jobs", response_model=list[PdfJobResponse])
def document_jobs(document_id: UUID, session: DatabaseSession):
    required(session, PdfDocument, document_id)
    return session.scalars(
        select(PdfImportJob).where(PdfImportJob.document_id == document_id)
    ).all()


@router.get("/pdf-import-jobs/{job_id}", response_model=PdfJobResponse)
def job(job_id: UUID, session: DatabaseSession):
    return required(session, PdfImportJob, job_id)


@router.post("/pdf-import-jobs/{job_id}/retry", status_code=202)
def retry(job_id: UUID, request: Request, session: DatabaseSession):
    # A dead worker's database connection releases its lock. A live job cannot be reset.
    connection = request.app.state.database.engine.connect()
    try:
        if not try_lock(connection, job_id):
            raise PdfError("IMPORT_ALREADY_RUNNING", 409)
        try:
            with session.begin():
                row = required(session, PdfImportJob, job_id)
                if row.status not in {
                    "FAILED",
                    "PROCESSING",
                    "COMPLETED",
                    "COMPLETED_WITH_WARNINGS",
                }:
                    raise PdfError("IMPORT_NOT_RETRYABLE", 409)
                reset_drafts(session, row.id)
                row.status = "QUEUED"
                row.processed_pages = row.extracted_question_count = 0
                row.review_required_count = row.failed_item_count = 0
                row.started_at = row.completed_at = None
                row.diagnostics = []
                document = required(session, PdfDocument, row.document_id)
                document.import_status = "QUEUED"
                document.error_summary = None
                document.processed_at = None
            return {"status": "QUEUED"}
        finally:
            unlock(connection, job_id)
    finally:
        connection.close()


@router.get("/question-drafts", response_model=DraftPage)
def drafts(
    session: DatabaseSession, document_id: UUID | None = None, page: Page = 1, page_size: Size = 20
):
    query = select(QuestionDraft)
    count = select(func.count()).select_from(QuestionDraft)
    if document_id:
        query = query.where(QuestionDraft.document_id == document_id)
        count = count.where(QuestionDraft.document_id == document_id)
    total = session.scalar(count)
    rows = session.scalars(
        query.order_by(QuestionDraft.document_id, QuestionDraft.source_order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return DraftPage(
        items=[draft_response(session, row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/question-drafts/{draft_id}", response_model=DraftResponse)
def draft(draft_id: UUID, session: DatabaseSession):
    return draft_response(session, required(session, QuestionDraft, draft_id))


@router.get("/question-draft-assets/{asset_id}")
def asset(asset_id: UUID, request: Request, session: DatabaseSession):
    row = required(session, QuestionDraftAsset, asset_id)
    data = PdfStorage(request.app.state.settings).path(row.storage_key).read_bytes()
    if hashlib.sha256(data).hexdigest() != row.sha256_hash:
        raise PdfError("ASSET_INTEGRITY_FAILURE", 503)
    return Response(data, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})


@router.get("/pdf-documents/{document_id}/pages/{page_number}")
def page_preview(document_id: UUID, page_number: int, request: Request, session: DatabaseSession):
    row = required(session, PdfDocument, document_id)
    if not 1 <= page_number <= row.page_count:
        raise PdfError("PAGE_NOT_FOUND", 404)
    settings = request.app.state.settings
    storage = PdfStorage(settings)
    path = storage.source(row.storage_key, row.sha256_hash, row.file_size_bytes)
    with tempfile.TemporaryDirectory(dir=storage.root / "incoming") as directory:
        output = Path(directory) / "preview.png"
        inspect_source(path, settings, page_number, output)
        data = output.read_bytes()
    return Response(data, media_type="image/png", headers={"X-Content-Type-Options": "nosniff"})
