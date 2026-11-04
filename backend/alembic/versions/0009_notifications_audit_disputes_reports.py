"""notifications + audit_logs + disputes + reports

Revision ID: 0009_notif_audit_disputes
Revises: 0008_payments
Create Date: 2026-10-28 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_notif_audit_disputes"
down_revision = "0008_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dispute_status = postgresql.ENUM(
        "open",
        "resolved",
        "rejected",
        name="dispute_status_enum",
    )
    dispute_status.create(op.get_bind(), checkfirst=True)

    dispute_resolution = postgresql.ENUM(
        "release_to_creator",
        "refund_to_brand",
        "split",
        name="dispute_resolution_enum",
    )
    dispute_resolution.create(op.get_bind(), checkfirst=True)

    report_target_type = postgresql.ENUM(
        "user",
        "campaign",
        name="report_target_type_enum",
    )
    report_target_type.create(op.get_bind(), checkfirst=True)

    report_status = postgresql.ENUM(
        "open",
        "reviewed",
        "dismissed",
        name="report_status_enum",
    )
    report_status.create(op.get_bind(), checkfirst=True)

    # --- notifications --------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_notifications_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_notifications_user_id_read_at",
        "notifications",
        ["user_id", "read_at"],
    )

    # --- audit_logs -----------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "diff",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_audit_logs_target_type_target_id",
        "audit_logs",
        ["target_type", "target_id"],
    )
    op.create_index(
        "ix_audit_logs_actor_user_id",
        "audit_logs",
        ["actor_user_id"],
    )

    # --- disputes -------------------------------------------------------
    op.create_table(
        "disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "collaboration_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "opened_by_user_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open",
                "resolved",
                "rejected",
                name="dispute_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "resolution",
            postgresql.ENUM(
                "release_to_creator",
                "refund_to_brand",
                "split",
                name="dispute_resolution_enum",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("split_bps", sa.Integer(), nullable=True),
        sa.Column(
            "resolved_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "resolved_at", sa.DateTime(timezone=True), nullable=True
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
        sa.PrimaryKeyConstraint("id", name="pk_disputes"),
        sa.ForeignKeyConstraint(
            ["collaboration_id"],
            ["collaborations.id"],
            name="fk_disputes_collaboration_id_collaborations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["opened_by_user_id"],
            ["users.id"],
            name="fk_disputes_opened_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_admin_id"],
            ["users.id"],
            name="fk_disputes_resolved_by_admin_id_users",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "split_bps IS NULL OR (split_bps >= 0 AND split_bps <= 10000)",
            name="ck_disputes_split_bps_in_range",
        ),
    )
    op.create_index(
        "ix_disputes_collaboration_id_status",
        "disputes",
        ["collaboration_id", "status"],
    )

    # --- reports --------------------------------------------------------
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "reporter_user_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "target_type",
            postgresql.ENUM(
                "user",
                "campaign",
                name="report_target_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open",
                "reviewed",
                "dismissed",
                name="report_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'open'"),
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
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"],
            ["users.id"],
            name="fk_reports_reporter_user_id_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index(
        "ix_reports_target_type_target_id",
        "reports",
        ["target_type", "target_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reports_target_type_target_id", table_name="reports")
    op.drop_index("ix_reports_status", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_disputes_collaboration_id_status", table_name="disputes")
    op.drop_table("disputes")

    op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index(
        "ix_audit_logs_target_type_target_id", table_name="audit_logs"
    )
    op.drop_table("audit_logs")

    op.drop_index(
        "ix_notifications_user_id_read_at", table_name="notifications"
    )
    op.drop_table("notifications")

    postgresql.ENUM(name="report_status_enum").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="report_target_type_enum").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="dispute_resolution_enum").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="dispute_status_enum").drop(
        op.get_bind(), checkfirst=True
    )
