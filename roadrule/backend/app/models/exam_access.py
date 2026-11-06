"""Payment test records, promo verifiers and one-use grants."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        UniqueConstraint("guest_session_id", "idempotency_key"),
        CheckConstraint("provider IN ('MTN','AIRTEL') AND mode = 'MOCK'", name="mock_provider"),
        CheckConstraint("amount > 0 AND currency = 'RWF'", name="money"),
        CheckConstraint("status IN ('PENDING','SUCCESSFUL','FAILED','CANCELLED')", name="status"),
        CheckConstraint("(status = 'PENDING') = (completed_at IS NULL)", name="completion"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    guest_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="RESTRICT")
    )
    provider: Mapped[str] = mapped_column(String(8))
    mode: Mapped[str] = mapped_column(String(8), default="MOCK")
    reference: Mapped[str] = mapped_column(String(48), unique=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 0))
    currency: Mapped[str] = mapped_column(String(3), default="RWF")
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PromoCode(Base):
    __tablename__ = "promo_codes"
    __table_args__ = (
        CheckConstraint("usage_limit BETWEEN 1 AND 100", name="limit"),
        CheckConstraint(
            "code IS NULL OR char_length(btrim(code)) BETWEEN 1 AND 80", name="code_length"
        ),
        Index(
            "uq_promo_codes_code_active",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND code IS NOT NULL"),
        ),
        Index(
            "uq_promo_codes_verifier_active",
            "verifier",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_promo_codes_expires_at", "expires_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    # New codes keep the administrator-entered value. Legacy rows only kept a hash.
    code: Mapped[str | None] = mapped_column(String(80))
    verifier: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id", ondelete="RESTRICT"))
    usage_limit: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExamEntitlement(Base):
    __tablename__ = "exam_entitlements"
    __table_args__ = (
        UniqueConstraint("guest_session_id", "promo_id"),
        CheckConstraint("(promo_id IS NULL) <> (payment_id IS NULL)", name="source"),
        CheckConstraint("status IN ('AVAILABLE','CONSUMED','REVOKED')", name="status"),
        CheckConstraint(
            "(status = 'CONSUMED') = (attempt_id IS NOT NULL AND consumed_at IS NOT NULL)",
            name="consumption",
        ),
        CheckConstraint("(attempt_id IS NULL) = (consumed_at IS NULL)", name="consumption_pair"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    guest_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="RESTRICT"), index=True
    )
    promo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="RESTRICT"), index=True
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="RESTRICT"), unique=True
    )
    status: Mapped[str] = mapped_column(String(16), default="AVAILABLE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exam_attempts.id", ondelete="RESTRICT"), unique=True
    )


class PromoAttempt(Base):
    __tablename__ = "promo_attempts"
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    guest_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
