from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Student
from app.models.exam_bank import BankRevision, ExamOperationalEvent
from app.models.pdf_import import PdfDocument
from app.schemas.admin import DashboardSummary


def dashboard_summary(session: Session) -> DashboardSummary:
    return DashboardSummary(totalStudents=session.scalar(select(func.count()).select_from(Student)))


def exam_bank_status(session: Session) -> dict:
    active = session.scalar(select(BankRevision).where(BankRevision.active))
    recent = session.execute(
        select(PdfDocument, BankRevision)
        .outerjoin(
            BankRevision,
            BankRevision.id
            == select(BankRevision.id)
            .where(BankRevision.document_id == PdfDocument.id)
            .order_by(BankRevision.created_at.desc(), BankRevision.id.desc())
            .limit(1)
            .correlate(PdfDocument)
            .scalar_subquery(),
        )
        .order_by(PdfDocument.created_at.desc(), PdfDocument.id.desc())
        .limit(20)
    ).all()
    last = session.scalar(select(func.max(BankRevision.created_at)))
    unavailable = session.scalar(select(func.count()).select_from(ExamOperationalEvent))
    return {
        "ready": active is not None,
        "activeRevisionId": active.id if active else None,
        "activeDocumentId": active.document_id if active else None,
        "policy": active.policy if active else None,
        "lastProcessedAt": last,
        "unavailableEvents": unavailable,
        "documents": [
            {
                "id": document.id,
                "filename": document.original_filename,
                "processingStatus": document.import_status,
                "errorCode": document.error_summary,
                "bankStatus": revision.status if revision else None,
                "counts": revision.counts if revision else None,
            }
            for document, revision in recent
        ],
    }
