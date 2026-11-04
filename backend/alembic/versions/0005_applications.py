"""campaign_applications

Revision ID: 0005_applications
Revises: 0004_campaigns
Create Date: 2026-10-18 14:23:54.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_applications"
down_revision = "0004_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    application_status = postgresql.ENUM(
        "invited",
        "submitted",
        "shortlisted",
        "accepted",
        "rejected",
        "withdrawn",
        name="application_status_enum",
    )
    application_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "campaign_applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposed_price_paise", sa.BigInteger(), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column("pitch", sa.Text(), nullable=True),
        sa.Column(
            "portfolio_links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "invited",
                "submitted",
                "shortlisted",
                "accepted",
                "rejected",
                "withdrawn",
                name="application_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'submitted'"),
        ),
        sa.Column(
            "invited_by_brand",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
        sa.PrimaryKeyConstraint("id", name="pk_campaign_applications"),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name="fk_campaign_applications_campaign_id_campaigns",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator_profiles.id"],
            name="fk_campaign_applications_creator_id_creator_profiles",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "creator_id",
            name="uq_campaign_applications_campaign_id_creator_id",
        ),
        sa.CheckConstraint(
            "currency = 'INR'",
            name="ck_campaign_applications_currency_inr_only",
        ),
        sa.CheckConstraint(
            "proposed_price_paise IS NULL OR proposed_price_paise >= 0",
            name="ck_campaign_applications_proposed_price_paise_non_negative",
        ),
    )
    op.create_index(
        "ix_campaign_applications_campaign_id_status",
        "campaign_applications",
        ["campaign_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_applications_campaign_id_status",
        table_name="campaign_applications",
    )
    op.drop_table("campaign_applications")
    postgresql.ENUM(name="application_status_enum").drop(op.get_bind(), checkfirst=True)
