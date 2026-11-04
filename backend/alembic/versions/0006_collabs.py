"""collaborations + agreement_version

Revision ID: 0006_collaborations_agreements
Revises: 0005_applications
Create Date: 2026-10-28 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_collabs"
down_revision = "0005_applications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    collaboration_status = postgresql.ENUM(
        "pending_agreement",
        "agreement_signed",
        "funding_initiated",
        "funded",
        "in_progress",
        "in_review",
        "approved",
        "completed",
        "disputed",
        "cancelled",
        name="collaboration_status_enum",
    )
    collaboration_status.create(op.get_bind(), checkfirst=True)

    funding_status = postgresql.ENUM(
        "not_funded",
        "funding_initiated",
        "funding_confirmed",
        "funding_failed",
        name="funding_status_enum",
    )
    funding_status.create(op.get_bind(), checkfirst=True)

    payout_status = postgresql.ENUM(
        "none",
        "pending",
        "processing",
        "paid",
        "failed",
        name="payout_status_enum",
    )
    payout_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "collaborations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending_agreement",
                "agreement_signed",
                "funding_initiated",
                "funded",
                "in_progress",
                "in_review",
                "approved",
                "completed",
                "disputed",
                "cancelled",
                name="collaboration_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'pending_agreement'"),
        ),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column(
            "funding_status",
            postgresql.ENUM(
                "not_funded",
                "funding_initiated",
                "funding_confirmed",
                "funding_failed",
                name="funding_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'not_funded'"),
        ),
        sa.Column(
            "payout_status",
            postgresql.ENUM(
                "none",
                "pending",
                "processing",
                "paid",
                "failed",
                name="payout_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collaborations"),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_collaborations_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["campaign_applications.id"],
            name="fk_collaborations_application_id_campaign_applications",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brand_profiles.id"],
            name="fk_collaborations_brand_id_brand_profiles",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator_profiles.id"],
            name="fk_collaborations_creator_id_creator_profiles",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "application_id", name="uq_collaborations_application_id"
        ),
        sa.CheckConstraint(
            "currency = 'INR'",
            name="ck_collaborations_currency_inr_only",
        ),
        sa.CheckConstraint(
            "price_paise >= 0",
            name="ck_collaborations_price_paise_non_negative",
        ),
    )
    op.create_index(
        "ix_collaborations_brand_id_status",
        "collaborations",
        ["brand_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_collaborations_creator_id_status",
        "collaborations",
        ["creator_id", "status"],
        unique=False,
    )

    op.create_table(
        "agreement_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collaboration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column(
            "deliverable_spec",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revision_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("usage_rights", sa.Text(), nullable=True),
        sa.Column(
            "disclosure_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("brand_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creator_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agreement_version"),
        sa.ForeignKeyConstraint(
            ["collaboration_id"],
            ["collaborations.id"],
            name="fk_agreement_version_collaboration_id_collaborations",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "collaboration_id",
            "version_number",
            name="uq_agreement_version_collaboration_id_version_number",
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name="ck_agreement_version_version_number_positive",
        ),
        sa.CheckConstraint(
            "revision_limit >= 0",
            name="ck_agreement_version_revision_limit_non_negative",
        ),
        sa.CheckConstraint(
            "price_paise >= 0",
            name="ck_agreement_version_price_paise_non_negative",
        ),
        sa.CheckConstraint(
            "currency = 'INR'",
            name="ck_agreement_version_currency_inr_only",
        ),
    )

    # Partial unique index: exactly one current (superseded_at IS NULL) agreement.
    op.execute(
        "CREATE UNIQUE INDEX ux_agreement_current "
        "ON agreement_version (collaboration_id) "
        "WHERE superseded_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_agreement_current")
    op.drop_table("agreement_version")
    op.drop_index(
        "ix_collaborations_creator_id_status", table_name="collaborations"
    )
    op.drop_index(
        "ix_collaborations_brand_id_status", table_name="collaborations"
    )
    op.drop_table("collaborations")
    postgresql.ENUM(name="payout_status_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="funding_status_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="collaboration_status_enum").drop(
        op.get_bind(), checkfirst=True
    )
