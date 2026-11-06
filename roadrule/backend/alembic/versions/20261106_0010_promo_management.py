"""promo management

Revision ID: 20261106_0010
Revises: 20261105_0009
"""

import sqlalchemy as sa

from alembic import op

revision = "20261106_0010"
down_revision = "20261105_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promo_codes", sa.Column("code", sa.String(length=80), nullable=True))
    op.add_column(
        "promo_codes", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "promo_codes",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "promo_codes", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    # Existing rows were created as published, 24-hour codes.
    op.execute("UPDATE promo_codes SET published_at = created_at WHERE published_at IS NULL")
    op.execute("UPDATE promo_codes SET updated_at = created_at WHERE updated_at IS NULL")
    op.drop_constraint(op.f("ck_promo_codes_expiry"), "promo_codes", type_="check")
    op.drop_constraint(op.f("uq_promo_codes_verifier"), "promo_codes", type_="unique")
    op.create_check_constraint(
        op.f("ck_promo_codes_code_length"),
        "promo_codes",
        "code IS NULL OR char_length(btrim(code)) BETWEEN 1 AND 80",
    )
    op.create_index(
        "uq_promo_codes_code_active",
        "promo_codes",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND code IS NOT NULL"),
    )
    op.create_index(
        "uq_promo_codes_verifier_active",
        "promo_codes",
        ["verifier"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_promo_codes_expires_at", "promo_codes", ["expires_at"], unique=False)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM promo_codes WHERE expires_at <> "
            "created_at + interval '24 hours')"
        )
    ):
        raise RuntimeError("Custom promo expiries prevent downgrade.")
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT verifier FROM promo_codes WHERE deleted_at IS NULL "
            "GROUP BY verifier HAVING count(*) > 1)"
        )
    ) or connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT code FROM promo_codes WHERE deleted_at IS NULL "
            "AND code IS NOT NULL GROUP BY code HAVING count(*) > 1)"
        )
    ):
        raise RuntimeError("Duplicate active promo codes prevent downgrade.")

    op.drop_index("ix_promo_codes_expires_at", table_name="promo_codes")
    op.drop_index("uq_promo_codes_verifier_active", table_name="promo_codes")
    op.drop_index("uq_promo_codes_code_active", table_name="promo_codes")
    op.drop_constraint(op.f("ck_promo_codes_code_length"), "promo_codes", type_="check")
    op.create_unique_constraint(op.f("uq_promo_codes_verifier"), "promo_codes", ["verifier"])
    op.drop_column("promo_codes", "deleted_at")
    op.drop_column("promo_codes", "updated_at")
    op.drop_column("promo_codes", "published_at")
    op.drop_column("promo_codes", "code")
    op.create_check_constraint(
        op.f("ck_promo_codes_expiry"),
        "promo_codes",
        "expires_at = created_at + interval '24 hours'",
    )
