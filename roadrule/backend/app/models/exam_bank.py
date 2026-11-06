"""Immutable question versions and ordered exam snapshots."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BankRevision(Base):
    __tablename__ = "exam_bank_revisions"
    __table_args__ = (
        Index("uq_one_active_exam_bank", "active", unique=True, postgresql_where=text("active")),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pdf_documents.id", ondelete="RESTRICT"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pdf_import_jobs.id", ondelete="RESTRICT"), index=True
    )
    source_sha256: Mapped[str] = mapped_column(String(64))
    policy: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(40))
    counts: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BankQuestion(Base):
    __tablename__ = "exam_bank_questions"
    __table_args__ = (
        UniqueConstraint("revision_id", "source_order"),
        Index("ix_bank_selection", "revision_id", "eligibility", "difficulty", "category"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_bank_revisions.id", ondelete="RESTRICT")
    )
    fingerprint: Mapped[str] = mapped_column(String(64))
    source_order: Mapped[int] = mapped_column(Integer)
    source_page: Mapped[int] = mapped_column(Integer)
    source_location: Mapped[dict] = mapped_column(JSONB)
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSONB)
    answer_evidence: Mapped[dict | None] = mapped_column(JSONB)
    correct_index: Mapped[int | None] = mapped_column(Integer)
    assets: Mapped[list] = mapped_column(JSONB)
    category: Mapped[str] = mapped_column(String(16))
    difficulty: Mapped[str | None] = mapped_column(String(8))
    eligibility: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    guest_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="RESTRICT"), index=True
    )
    entitlement_id: Mapped[uuid.UUID] = mapped_column(UUID, unique=True)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_bank_revisions.id", ondelete="RESTRICT")
    )
    policy: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(16), default="STARTED")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExamItem(Base):
    __tablename__ = "exam_attempt_items"
    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 20", name="position_range"),
        UniqueConstraint("attempt_id", "question_id"),
    )
    attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_bank_questions.id", ondelete="RESTRICT")
    )


class ExamOperationalEvent(Base):
    __tablename__ = "exam_operational_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
