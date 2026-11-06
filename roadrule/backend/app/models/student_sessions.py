import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        CheckConstraint(
            "char_length(full_name) BETWEEN 1 AND 120 AND full_name = btrim(full_name) "
            "AND full_name !~ '[[:cntrl:]0-9<>]' AND full_name NOT LIKE '%  %'",
            name="name_shape",
        ),
        CheckConstraint(r"phone_number ~ '^\+2507[23789][0-9]{7}$'", name="phone_format"),
        CheckConstraint("updated_at >= created_at", name="timestamp_order"),
        Index("ix_students_phone_number", "phone_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    phone_number: Mapped[str] = mapped_column(String(13))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GuestSession(Base):
    __tablename__ = "guest_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_guest_sessions_token_hash"),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="token_hash_format"),
        CheckConstraint(
            "expires_at > created_at AND last_activity_at >= created_at "
            "AND last_activity_at <= expires_at "
            "AND (revoked_at IS NULL OR revoked_at >= created_at)",
            name="timestamp_order",
        ),
        Index("ix_guest_sessions_student_id", "student_id"),
        Index("ix_guest_sessions_expires_at", "expires_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudentActivityEvent(Base):
    __tablename__ = "student_activity_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('STUDENT_CREATED','SESSION_CREATED',"
            "'SESSION_REVOKED','SESSION_EXPIRED')",
            name="event_type",
        ),
        UniqueConstraint("guest_session_id", "event_type", name="uq_session_activity_type"),
        Index("ix_student_activity_events_student_id", "student_id"),
        Index("ix_student_activity_events_guest_session_id", "guest_session_id"),
        Index("ix_student_activity_events_type_created", "event_type", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL")
    )
    guest_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("guest_sessions.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
