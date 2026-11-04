"""add durable email outbox

Revision ID: 0012_email_outbox
Revises: 0011_add_razorpay_fields
Create Date: 2026-11-03 22:58:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0012_email_outbox"
down_revision: str | None = "0011_add_razorpay_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="queued",
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_type", sa.String(length=100), nullable=True),
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
            "status IN ('queued', 'processing', 'sent', 'failed')",
            name="ck_email_outbox_email_outbox_status_valid",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_email_outbox_email_outbox_attempts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name="fk_email_outbox_notification_id_notifications",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_email_outbox"),
        sa.UniqueConstraint(
            "notification_id",
            name="uq_email_outbox_notification_id",
        ),
    )
    op.create_index(
        "ix_email_outbox_status_available_at",
        "email_outbox",
        ["status", "available_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_outbox_status_available_at",
        table_name="email_outbox",
    )
    op.drop_table("email_outbox")
