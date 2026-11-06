import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminUser(Base):
    __tablename__ = "admin_users"
    __table_args__ = (
        CheckConstraint(
            "email = lower(email) AND email ~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$'",
            name="email_shape",
        ),
        CheckConstraint(
            "char_length(full_name) BETWEEN 1 AND 120 AND full_name=btrim(full_name)",
            name="name_shape",
        ),
        CheckConstraint(
            "password_hash LIKE '$argon2id$%' AND char_length(password_hash) BETWEEN 50 AND 512",
            name="password_verifier",
        ),
        CheckConstraint("role = 'ADMIN'", name="role"),
        CheckConstraint("updated_at >= created_at", name="timestamp_order"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(20), server_default="ADMIN")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.clock_timestamp()
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="verifier_shape"),
        CheckConstraint(
            "expires_at > created_at AND last_activity_at >= created_at AND last_ac"
            "tivity_at <= expires_at AND (revoked_at IS NULL OR revoked_at >= creat"
            "ed_at)",
            name="timestamp_order",
        ),
        Index("ix_admin_sessions_admin_id", "admin_id"),
        Index("ix_admin_sessions_expires_at", "expires_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AdminAuditEvent(Base):
    __tablename__ = "admin_audit_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('PDF_UPLOAD_ATTEMPT','ADMIN_BOOTSTRAPPED','ADMIN_LOGIN_ATTEMPT',"
            "'ADMIN_LOGIN"
            "_SUCCEEDED','ADMIN_LOGIN_FAILED','ADMIN_LOGOUT','ADMIN_SESSION_EXPIRED"
            "','ADMIN_SESSION_REVOKED')",
            name="event_type",
        ),
        CheckConstraint(
            "jsonb_typeof(sanitized_metadata)='object' AND sanitized_metadata - 're"
            "sult' - 'reason' = '{}'::jsonb AND (NOT sanitized_metadata ? 'result' "
            "OR sanitized_metadata->>'result' IN ('success','denied','expired','rev"
            "oked')) AND (NOT sanitized_metadata ? 'reason' OR sanitized_metadata->"
            ">'reason' IN ('credentials','lifetime','inactivity','disabled'))",
            name="metadata_shape",
        ),
        Index("ix_admin_audit_events_actor_admin_id", "actor_admin_id"),
        Index("ix_admin_audit_events_type_created", "event_type", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sanitized_metadata: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
