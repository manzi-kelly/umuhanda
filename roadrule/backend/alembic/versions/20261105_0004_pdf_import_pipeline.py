"""pdf_import_pipeline

Revision ID: 20261105_0004
Revises: 20261105_0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261105_0004"
down_revision = "20261105_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_admin_audit_events_event_type"), "admin_audit_events", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_admin_audit_events_event_type"),
        "admin_audit_events",
        "event_type IN ('PDF_UPLOAD_ATTEMPT','ADMIN_BOOTSTRAPPED','AD"
        "MIN_LOGIN_ATTEMPT','ADMIN_LOGIN_SUCCEEDED','ADMIN_LOGIN_FAIL"
        "ED','ADMIN_LOGOUT','ADMIN_SESSION_EXPIRED','ADMIN_SESSION_RE"
        "VOKED')",
    )
    op.create_table(
        "pdf_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=150), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_admin_id", sa.UUID(), nullable=False),
        sa.Column("import_status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "import_status IN ('QUEUED','PROCESSING','COMPLETED','COMPLET"
            "ED_WITH_WARNINGS','FAILED')",
            name=op.f("ck_pdf_documents_status"),
        ),
        sa.CheckConstraint(
            "sha256_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_pdf_documents_hash_shape")
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND page_count > 0", name=op.f("ck_pdf_documents_positive_size")
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_admin_id"],
            ["admin_users.id"],
            name=op.f("fk_pdf_documents_uploaded_by_admin_id_admin_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pdf_documents")),
        sa.UniqueConstraint("sha256_hash", name=op.f("uq_pdf_documents_sha256_hash")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_pdf_documents_storage_key")),
    )
    op.create_index(
        op.f("ix_pdf_documents_created_at"), "pdf_documents", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_pdf_documents_uploaded_by_admin_id"),
        "pdf_documents",
        ["uploaded_by_admin_id"],
        unique=False,
    )
    op.create_table(
        "pdf_import_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=False),
        sa.Column("processed_pages", sa.Integer(), nullable=False),
        sa.Column("extracted_question_count", sa.Integer(), nullable=False),
        sa.Column("review_required_count", sa.Integer(), nullable=False),
        sa.Column("failed_item_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "status IN ('QUEUED','PROCESSING','COMPLETED','COMPLETED_WITH_WARNINGS','FAILED')",
            name=op.f("ck_pdf_import_jobs_status"),
        ),
        sa.CheckConstraint(
            "total_pages > 0 AND processed_pages BETWEEN 0 AND total_page"
            "s AND extracted_question_count >= 0 AND review_required_coun"
            "t >= 0 AND failed_item_count >= 0",
            name=op.f("ck_pdf_import_jobs_counts"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["pdf_documents.id"],
            name=op.f("fk_pdf_import_jobs_document_id_pdf_documents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pdf_import_jobs")),
        sa.UniqueConstraint("document_id", name=op.f("uq_pdf_import_jobs_document_id")),
        sa.UniqueConstraint("id", "document_id", name=op.f("uq_pdf_import_jobs_id")),
    )
    op.create_index(op.f("ix_pdf_import_jobs_status"), "pdf_import_jobs", ["status"], unique=False)
    op.create_table(
        "question_drafts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("import_job_id", sa.UUID(), nullable=False),
        sa.Column("source_order", sa.Integer(), nullable=False),
        sa.Column("source_question_number", sa.String(length=20), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("difficulty", sa.String(length=30), nullable=True),
        sa.Column("answer_status", sa.String(length=32), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("source_page_number", sa.Integer(), nullable=False),
        sa.Column("source_location", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "answer_status IN ('ANSWER_NOT_FOUND','NEEDS_REVIEW','EXTRACTED_UNVERIFIED')",
            name=op.f("ck_question_drafts_answer_status"),
        ),
        sa.CheckConstraint(
            "extraction_status IN ('EXTRACTED_UNVERIFIED','NEEDS_REVIEW')",
            name=op.f("ck_question_drafts_extraction_status"),
        ),
        sa.CheckConstraint(
            "source_page_number > 0 AND source_order > 0",
            name=op.f("ck_question_drafts_source_order"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["pdf_documents.id"],
            name=op.f("fk_question_drafts_document_id_pdf_documents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id", "document_id"],
            ["pdf_import_jobs.id", "pdf_import_jobs.document_id"],
            name="fk_draft_job_document",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["import_job_id"],
            ["pdf_import_jobs.id"],
            name=op.f("fk_question_drafts_import_job_id_pdf_import_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_drafts")),
        sa.UniqueConstraint("id", "document_id", name=op.f("uq_question_drafts_id")),
        sa.UniqueConstraint(
            "import_job_id", "source_order", name=op.f("uq_question_drafts_import_job_id")
        ),
    )
    op.create_index(
        op.f("ix_question_drafts_document_id"), "question_drafts", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_question_drafts_import_job_id"), "question_drafts", ["import_job_id"], unique=False
    )
    op.create_table(
        "question_draft_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("question_draft_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(length=150), nullable=False),
        sa.Column("asset_type", sa.String(length=40), nullable=False),
        sa.Column("source_page_number", sa.Integer(), nullable=False),
        sa.Column("source_location", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["pdf_documents.id"],
            name=op.f("fk_question_draft_assets_document_id_pdf_documents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["question_draft_id"],
            ["question_drafts.id"],
            name=op.f("fk_question_draft_assets_question_draft_id_question_drafts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_draft_assets")),
        sa.UniqueConstraint(
            "question_draft_id",
            "source_page_number",
            "source_location",
            name=op.f("uq_question_draft_assets_question_draft_id"),
        ),
    )
    op.create_index(
        op.f("ix_question_draft_assets_document_id"),
        "question_draft_assets",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_draft_assets_question_draft_id"),
        "question_draft_assets",
        ["question_draft_id"],
        unique=False,
    )
    op.create_table(
        "question_draft_options",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("question_draft_id", sa.UUID(), nullable=False),
        sa.Column("option_label", sa.String(length=10), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("source_page_number", sa.Integer(), nullable=False),
        sa.Column("source_location", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_draft_id"],
            ["question_drafts.id"],
            name=op.f("fk_question_draft_options_question_draft_id_question_drafts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_draft_options")),
        sa.UniqueConstraint("id", "question_draft_id", name=op.f("uq_question_draft_options_id")),
        sa.UniqueConstraint(
            "question_draft_id",
            "display_order",
            name=op.f("uq_question_draft_options_question_draft_id"),
        ),
    )
    op.create_index(
        op.f("ix_question_draft_options_question_draft_id"),
        "question_draft_options",
        ["question_draft_id"],
        unique=False,
    )
    op.create_table(
        "question_draft_answers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("question_draft_id", sa.UUID(), nullable=False),
        sa.Column("selected_option_id", sa.UUID(), nullable=True),
        sa.Column("raw_answer_text", sa.Text(), nullable=True),
        sa.Column("evidence_page_number", sa.Integer(), nullable=True),
        sa.Column("evidence_location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('ANSWER_NOT_FOUND','NEEDS_REVIEW','EXTRACTED_UNVERIFIED')",
            name=op.f("ck_question_draft_answers_verification_status"),
        ),
        sa.ForeignKeyConstraint(
            ["question_draft_id"],
            ["question_drafts.id"],
            name=op.f("fk_question_draft_answers_question_draft_id_question_drafts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["selected_option_id", "question_draft_id"],
            ["question_draft_options.id", "question_draft_options.question_draft_id"],
            name="fk_answer_option_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["selected_option_id"],
            ["question_draft_options.id"],
            name=op.f("fk_question_draft_answers_selected_option_id_question_draft_options"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_draft_answers")),
        sa.UniqueConstraint(
            "question_draft_id", name=op.f("uq_question_draft_answers_question_draft_id")
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # Refuse loss or misclassification of retained PDF audit events.
    if (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM admin_audit_events WHERE event_type='PDF_UPLOAD_ATTEMPT'")
        )
        .scalar_one()
    ):
        raise RuntimeError("Retained PDF upload audit events prevent downgrade.")
    op.drop_constraint(
        op.f("ck_admin_audit_events_event_type"), "admin_audit_events", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_admin_audit_events_event_type"),
        "admin_audit_events",
        "event_type IN ('ADMIN_BOOTSTRAPPED','ADMIN_LOGIN_ATTEMPT','A"
        "DMIN_LOGIN_SUCCEEDED','ADMIN_LOGIN_FAILED','ADMIN_LOGOUT','A"
        "DMIN_SESSION_EXPIRED','ADMIN_SESSION_REVOKED')",
    )
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("question_draft_answers")
    op.drop_index(
        op.f("ix_question_draft_options_question_draft_id"), table_name="question_draft_options"
    )
    op.drop_table("question_draft_options")
    op.drop_index(
        op.f("ix_question_draft_assets_question_draft_id"), table_name="question_draft_assets"
    )
    op.drop_index(op.f("ix_question_draft_assets_document_id"), table_name="question_draft_assets")
    op.drop_table("question_draft_assets")
    op.drop_index(op.f("ix_question_drafts_import_job_id"), table_name="question_drafts")
    op.drop_index(op.f("ix_question_drafts_document_id"), table_name="question_drafts")
    op.drop_table("question_drafts")
    op.drop_index(op.f("ix_pdf_import_jobs_status"), table_name="pdf_import_jobs")
    op.drop_table("pdf_import_jobs")
    op.drop_index(op.f("ix_pdf_documents_uploaded_by_admin_id"), table_name="pdf_documents")
    op.drop_index(op.f("ix_pdf_documents_created_at"), table_name="pdf_documents")
    op.drop_table("pdf_documents")
    # ### end Alembic commands ###
