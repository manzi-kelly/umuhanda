"""Mutable execution state kept separately from immutable exam questions."""

from datetime import datetime
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExamTiming(Base):
    __tablename__ = "exam_timing"
    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 20", name="position_range"),
        CheckConstraint(
            "completion_reason IN ('ALL_QUESTIONS_FINISHED','GLOBAL_TIME_EXPIRED')",
            name="completion_reason",
        ),
    )
    attempt_id: Mapped[UUIDType] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="RESTRICT"), primary_key=True
    )
    global_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    position: Mapped[int] = mapped_column(Integer, default=1)
    completion_reason: Mapped[str | None] = mapped_column(String(32))


class ExamResponse(Base):
    __tablename__ = "exam_responses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "position"],
            ["exam_attempt_items.attempt_id", "exam_attempt_items.position"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("selected_option BETWEEN 0 AND 3", name="option_range"),
        CheckConstraint("(selected_option IS NULL) = (saved_at IS NULL)", name="saved_pair"),
        CheckConstraint(
            "deadline > started_at AND deadline <= started_at + interval '60 seconds'",
            name="duration",
        ),
        CheckConstraint("saved_at >= started_at AND saved_at < deadline", name="save_window"),
        CheckConstraint(
            "finalized_at >= started_at AND finalized_at <= deadline", name="finalization_window"
        ),
        CheckConstraint("finalized_at >= saved_at", name="save_before_finalize"),
        CheckConstraint("closed_by IN ('NEXT','DEADLINE','GLOBAL')", name="closed_by"),
        CheckConstraint("(closed_by IS NULL) = (finalized_at IS NULL)", name="finalized_pair"),
        CheckConstraint("answer_version >= 0", name="answer_version"),
    )
    attempt_id: Mapped[UUIDType] = mapped_column(UUID, primary_key=True)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    selected_option: Mapped[int | None] = mapped_column(Integer)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(String(12))
    answer_version: Mapped[int] = mapped_column(Integer, default=0)
