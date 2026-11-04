"""baseline — enable citext extension

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-18 14:23:50.000000

The baseline migration's only operation is enabling the ``citext`` extension
so later migrations can use case-insensitive text columns (e.g. for emails).
"""

from __future__ import annotations

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")


def downgrade() -> None:
    # Dropping citext is intentionally a no-op: once columns reference the
    # extension, dropping it would cascade and remove data.
    pass
