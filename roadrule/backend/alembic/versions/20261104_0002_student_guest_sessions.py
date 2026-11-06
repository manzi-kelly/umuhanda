"""student_guest_sessions

Revision ID: 20261104_0002
Revises: 20261104_0001
"""

import sqlalchemy as sa

from alembic import op

revision = "20261104_0002"
down_revision = "20261104_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reviewed additive migration; the accepted baseline remains unchanged.
    op.create_table(
        "students",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("phone_number", sa.String(length=13), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(full_name) BETWEEN 1 AND 120 AND full_name = btrim(full_name) "
            "AND full_name !~ '[[:cntrl:]0-9<>]' AND full_name NOT LIKE '%  %'",
            name=op.f("ck_students_name_shape"),
        ),
        sa.CheckConstraint(
            "phone_number ~ '^\\+2507[23789][0-9]{7}$'", name=op.f("ck_students_phone_format")
        ),
        sa.CheckConstraint("updated_at >= created_at", name=op.f("ck_students_timestamp_order")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
    )
    op.create_index("ix_students_phone_number", "students", ["phone_number"], unique=False)
    op.create_table(
        "guest_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_guest_sessions_token_hash_format")
        ),
        sa.CheckConstraint(
            "expires_at > created_at AND last_activity_at >= created_at "
            "AND last_activity_at <= expires_at "
            "AND (revoked_at IS NULL OR revoked_at >= created_at)",
            name=op.f("ck_guest_sessions_timestamp_order"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_guest_sessions_student_id_students"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guest_sessions")),
        sa.UniqueConstraint("token_hash", name="uq_guest_sessions_token_hash"),
    )
    op.create_index("ix_guest_sessions_expires_at", "guest_sessions", ["expires_at"], unique=False)
    op.create_index("ix_guest_sessions_student_id", "guest_sessions", ["student_id"], unique=False)
    op.create_table(
        "student_activity_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=True),
        sa.Column("guest_session_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('STUDENT_CREATED','SESSION_CREATED',"
            "'SESSION_REVOKED','SESSION_EXPIRED')",
            name=op.f("ck_student_activity_events_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["guest_session_id"],
            ["guest_sessions.id"],
            name=op.f("fk_student_activity_events_guest_session_id_guest_sessions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_student_activity_events_student_id_students"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_activity_events")),
        sa.UniqueConstraint("guest_session_id", "event_type", name="uq_session_activity_type"),
    )
    op.create_index(
        "ix_student_activity_events_guest_session_id",
        "student_activity_events",
        ["guest_session_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_activity_events_student_id",
        "student_activity_events",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_activity_events_type_created",
        "student_activity_events",
        ["event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Destructive: exercise only against empty, isolated test data; never auto-run on dev.
    op.drop_index("ix_student_activity_events_type_created", table_name="student_activity_events")
    op.drop_index("ix_student_activity_events_student_id", table_name="student_activity_events")
    op.drop_index(
        "ix_student_activity_events_guest_session_id", table_name="student_activity_events"
    )
    op.drop_table("student_activity_events")
    op.drop_index("ix_guest_sessions_student_id", table_name="guest_sessions")
    op.drop_index("ix_guest_sessions_expires_at", table_name="guest_sessions")
    op.drop_table("guest_sessions")
    op.drop_index("ix_students_phone_number", table_name="students")
    op.drop_table("students")
