"""deliverables + deliverable_revisions

Revision ID: 0007_deliverables
Revises: 0006_collaborations_agreements
Create Date: 2026-10-28 10:05:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_deliverables"
down_revision = "0006_collabs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    deliverable_kind = postgresql.ENUM(
        "file", "link", name="deliverable_kind_enum"
    )
    deliverable_kind.create(op.get_bind(), checkfirst=True)

    deliverable_status = postgresql.ENUM(
        "submitted",
        "revision_requested",
        "approved",
        "disputed",
        name="deliverable_status_enum",
    )
    deliverable_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "deliverables",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collaboration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spec_index", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "file", "link", name="deliverable_kind_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "submitted",
                "revision_requested",
                "approved",
                "disputed",
                name="deliverable_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'submitted'"),
        ),
        sa.Column(
            "revision_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
        sa.PrimaryKeyConstraint("id", name="pk_deliverables"),
        sa.ForeignKeyConstraint(
            ["collaboration_id"],
            ["collaborations.id"],
            name="fk_deliverables_collaboration_id_collaborations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            name="fk_deliverables_file_id_files",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_deliverables_collaboration_id_status",
        "deliverables",
        ["collaboration_id", "status"],
        unique=False,
    )

    op.create_table(
        "deliverable_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("deliverable_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_deliverable_revisions"),
        sa.ForeignKeyConstraint(
            ["deliverable_id"],
            ["deliverables.id"],
            name="fk_deliverable_revisions_deliverable_id_deliverables",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name="fk_deliverable_revisions_requested_by_user_id_users",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("deliverable_revisions")
    op.drop_index(
        "ix_deliverables_collaboration_id_status", table_name="deliverables"
    )
    op.drop_table("deliverables")
    postgresql.ENUM(name="deliverable_status_enum").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="deliverable_kind_enum").drop(
        op.get_bind(), checkfirst=True
    )
