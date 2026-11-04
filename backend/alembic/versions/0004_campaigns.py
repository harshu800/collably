"""campaigns

Revision ID: 0004_campaigns
Revises: 0003_profiles_files
Create Date: 2026-10-18 14:23:53.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_campaigns"
down_revision = "0003_profiles_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    campaign_type = postgresql.ENUM(
        "ugc",
        "influencer",
        "hybrid",
        name="campaign_type_enum",
    )
    campaign_type.create(op.get_bind(), checkfirst=True)

    campaign_status = postgresql.ENUM(
        "draft",
        "open",
        "closed",
        "archived",
        name="campaign_status_enum",
    )
    campaign_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "type",
            postgresql.ENUM(
                "ugc",
                "influencer",
                "hybrid",
                name="campaign_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "niches",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "platforms",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "locations",
            postgresql.ARRAY(sa.String(length=120)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("budget_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column(
            "number_of_creators",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "deliverable_spec",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("submission_deadline", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column(
            "eligibility_filters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "open",
                "closed",
                "archived",
                name="campaign_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_campaigns"),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brand_profiles.id"],
            name="fk_campaigns_brand_id_brand_profiles",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "revision_limit >= 0",
            name="ck_campaigns_revision_limit_non_negative",
        ),
        sa.CheckConstraint(
            "number_of_creators >= 1",
            name="ck_campaigns_number_of_creators_positive",
        ),
        sa.CheckConstraint(
            "budget_paise >= 0",
            name="ck_campaigns_budget_paise_non_negative",
        ),
        sa.CheckConstraint("currency = 'INR'", name="ck_campaigns_currency_inr_only"),
    )
    op.create_index(
        "ix_campaigns_brand_id_status",
        "campaigns",
        ["brand_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_campaigns_status_type",
        "campaigns",
        ["status", "type"],
        unique=False,
    )
    op.create_index(
        "ix_campaigns_niches_gin",
        "campaigns",
        ["niches"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_campaigns_niches_gin", table_name="campaigns")
    op.drop_index("ix_campaigns_status_type", table_name="campaigns")
    op.drop_index("ix_campaigns_brand_id_status", table_name="campaigns")
    op.drop_table("campaigns")
    postgresql.ENUM(name="campaign_status_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="campaign_type_enum").drop(op.get_bind(), checkfirst=True)
