"""add public brand profile fields

Revision ID: 0013_brand_public_profile_fields
Revises: 0012_email_outbox
Create Date: 2026-11-06 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_brand_public_profile_fields"
down_revision: str | None = "0012_email_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "brand_profiles",
        sa.Column("city", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "brand_profiles",
        sa.Column("state", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "brand_profiles",
        sa.Column(
            "social_handles",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("brand_profiles", "social_handles")
    op.drop_column("brand_profiles", "state")
    op.drop_column("brand_profiles", "city")
