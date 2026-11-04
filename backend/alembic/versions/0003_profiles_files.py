"""profiles + files

Revision ID: 0003_profiles_files
Revises: 0002_users
Create Date: 2026-10-18 14:23:52.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_profiles_files"
down_revision = "0002_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    file_visibility = postgresql.ENUM(
        "public",
        "private",
        name="file_visibility_enum",
    )
    file_visibility.create(op.get_bind(), checkfirst=True)

    # --- files ----------------------------------------------------------
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column(
            "visibility",
            postgresql.ENUM(
                "public",
                "private",
                name="file_visibility_enum",
                create_type=False,
            ),
            nullable=False,
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
        sa.PrimaryKeyConstraint("id", name="pk_files"),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name="fk_files_owner_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_files_owner_user_id", "files", ["owner_user_id"], unique=False)

    # --- creator_profiles ----------------------------------------------
    op.create_table(
        "creator_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("avatar_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column(
            "languages",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "niches",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "does_ugc",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "does_influencer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "content_types",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("starting_rate_paise", sa.BigInteger(), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column(
            "portfolio_links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "social_handles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_onboarded",
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
        sa.PrimaryKeyConstraint("id", name="pk_creator_profiles"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_creator_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["avatar_file_id"],
            ["files.id"],
            name="fk_creator_profiles_avatar_file_id_files",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("user_id", name="uq_creator_profiles_user_id"),
        sa.CheckConstraint("currency = 'INR'", name="ck_creator_profiles_currency_inr_only"),
    )
    op.create_index(
        "ix_creator_profiles_niches_gin",
        "creator_profiles",
        ["niches"],
        unique=False,
        postgresql_using="gin",
    )

    # --- brand_profiles ------------------------------------------------
    op.create_table(
        "brand_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("website", sa.String(length=2048), nullable=True),
        sa.Column("logo_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("industry", sa.String(length=120), nullable=True),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column(
            "billing_address",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_onboarded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_brand_profiles"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_brand_profiles_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["logo_file_id"],
            ["files.id"],
            name="fk_brand_profiles_logo_file_id_files",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("user_id", name="uq_brand_profiles_user_id"),
    )


def downgrade() -> None:
    op.drop_table("brand_profiles")
    op.drop_index("ix_creator_profiles_niches_gin", table_name="creator_profiles")
    op.drop_table("creator_profiles")
    op.drop_index("ix_files_owner_user_id", table_name="files")
    op.drop_table("files")
    postgresql.ENUM(name="file_visibility_enum").drop(op.get_bind(), checkfirst=True)
