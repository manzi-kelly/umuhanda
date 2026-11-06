from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ExamResult(Base):
    __tablename__ = "exam_results"
    __table_args__ = (
        CheckConstraint(
            "correct BETWEEN 0 AND 20 AND incorrect BETWEEN 0 AND 20 "
            "AND unanswered BETWEEN 0 AND 20 AND correct + incorrect + unanswered = 20",
            name="answer_counts",
        ),
    )

    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="RESTRICT"), primary_key=True
    )
    student_name: Mapped[str] = mapped_column(String(255))
    correct: Mapped[int]
    incorrect: Mapped[int]
    unanswered: Mapped[int]
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    graded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    grading_version: Mapped[int]


class ExamGradingFailure(Base):
    __tablename__ = "exam_grading_failures"

    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="RESTRICT"), primary_key=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
