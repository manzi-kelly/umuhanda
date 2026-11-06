"""Unpublished source documents and evidence-backed question drafts only."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

STATES = "'QUEUED','PROCESSING','COMPLETED','COMPLETED_WITH_WARNINGS','FAILED'"


class PdfDocument(Base):
    __tablename__ = "pdf_documents"
    __table_args__ = (
        CheckConstraint(f"import_status IN ({STATES})", name="status"),
        CheckConstraint("file_size_bytes > 0 AND page_count > 0", name="positive_size"),
        CheckConstraint("sha256_hash ~ '^[0-9a-f]{64}$'", name="hash_shape"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(150), unique=True)
    sha256_hash: Mapped[str] = mapped_column(String(64), unique=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer)
    uploaded_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admin_users.id", ondelete="RESTRICT"), index=True
    )
    import_status: Mapped[str] = mapped_column(String(32), default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[str | None] = mapped_column(String(500))


class PdfImportJob(Base):
    __tablename__ = "pdf_import_jobs"
    __table_args__ = (
        UniqueConstraint("id", "document_id"),
        CheckConstraint(f"status IN ({STATES})", name="status"),
        CheckConstraint(
            "total_pages > 0 AND processed_pages BETWEEN 0 AND total_page"
            "s AND extracted_question_count >= 0 AND review_required_coun"
            "t >= 0 AND failed_item_count >= 0",
            name="counts",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pdf_documents.id", ondelete="RESTRICT"), unique=True
    )
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    total_pages: Mapped[int] = mapped_column(Integer)
    processed_pages: Mapped[int] = mapped_column(Integer, default=0)
    extracted_question_count: Mapped[int] = mapped_column(Integer, default=0)
    review_required_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_item_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    diagnostics: Mapped[list] = mapped_column(JSONB, default=list)


class QuestionDraft(Base):
    __tablename__ = "question_drafts"
    __table_args__ = (
        UniqueConstraint("import_job_id", "source_order"),
        UniqueConstraint("id", "document_id"),
        ForeignKeyConstraint(
            ["import_job_id", "document_id"],
            ["pdf_import_jobs.id", "pdf_import_jobs.document_id"],
            name="fk_draft_job_document",
            ondelete="RESTRICT",
        ),
        CheckConstraint("source_page_number > 0 AND source_order > 0", name="source_order"),
        CheckConstraint(
            "answer_status IN ('ANSWER_NOT_FOUND','NEEDS_REVIEW','EXTRACTED_UNVERIFIED')",
            name="answer_status",
        ),
        CheckConstraint(
            "extraction_status IN ('EXTRACTED_UNVERIFIED','NEEDS_REVIEW')", name="extraction_status"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pdf_documents.id", ondelete="RESTRICT"), index=True
    )
    import_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pdf_import_jobs.id", ondelete="RESTRICT"), index=True
    )
    source_order: Mapped[int] = mapped_column(Integer)
    source_question_number: Mapped[str] = mapped_column(String(20))
    question_text: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    difficulty: Mapped[str | None] = mapped_column(String(30))
    answer_status: Mapped[str] = mapped_column(String(32))
    extraction_status: Mapped[str] = mapped_column(String(32))
    source_page_number: Mapped[int] = mapped_column(Integer)
    source_location: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuestionDraftOption(Base):
    __tablename__ = "question_draft_options"
    __table_args__ = (
        UniqueConstraint("question_draft_id", "display_order"),
        UniqueConstraint("id", "question_draft_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    question_draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_drafts.id", ondelete="CASCADE"), index=True
    )
    option_label: Mapped[str] = mapped_column(String(10))
    option_text: Mapped[str] = mapped_column(Text)
    source_page_number: Mapped[int] = mapped_column(Integer)
    source_location: Mapped[dict] = mapped_column(JSONB)
    display_order: Mapped[int] = mapped_column(Integer)


class QuestionDraftAnswer(Base):
    __tablename__ = "question_draft_answers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["selected_option_id", "question_draft_id"],
            ["question_draft_options.id", "question_draft_options.question_draft_id"],
            name="fk_answer_option_owner",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "verification_status IN ('ANSWER_NOT_FOUND','NEEDS_REVIEW','EXTRACTED_UNVERIFIED')",
            name="verification_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    question_draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_drafts.id", ondelete="CASCADE"), unique=True
    )
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("question_draft_options.id", ondelete="RESTRICT")
    )
    raw_answer_text: Mapped[str | None] = mapped_column(Text)
    evidence_page_number: Mapped[int | None] = mapped_column(Integer)
    evidence_location: Mapped[dict | None] = mapped_column(JSONB)
    verification_status: Mapped[str] = mapped_column(String(32))


class QuestionDraftAsset(Base):
    __tablename__ = "question_draft_assets"
    __table_args__ = (
        UniqueConstraint("question_draft_id", "source_page_number", "source_location"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    question_draft_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question_drafts.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pdf_documents.id", ondelete="RESTRICT"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(150))
    asset_type: Mapped[str] = mapped_column(String(40))
    source_page_number: Mapped[int] = mapped_column(Integer)
    source_location: Mapped[dict] = mapped_column(JSONB)
    sha256_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
