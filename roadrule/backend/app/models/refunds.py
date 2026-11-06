from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefundRequest(Base):
    """Reserved for a future verified-real-payment workflow."""

    __tablename__ = "refund_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('SUBMITTED','AWAITING_PAYMENT_VERIFICATION','UNDER_REVIEW',"
            "'APPROVED_FOR_FUTURE_REFUND','REJECTED','CANCELLED','RESOLVED_EXTERNALLY')",
            name="status",
        ),
        CheckConstraint("payment_id IS NULL", name="verified_payment_unavailable"),
        CheckConstraint("char_length(btrim(reason)) BETWEEN 1 AND 500", name="reason"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    student_id: Mapped[UUID | None] = mapped_column(ForeignKey("students.id", ondelete="SET NULL"))
    guest_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="SET NULL")
    )
    payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"), unique=True
    )
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(40), server_default="AWAITING_PAYMENT_VERIFICATION", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_by_admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(String(1000))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
