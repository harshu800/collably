"""payments + payouts + refunds + payment_webhook_event + creator_payout_method

Revision ID: 0008_payments_payouts_payout_methods
Revises: 0007_deliverables
Create Date: 2026-10-28 10:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_payments"
down_revision = "0007_deliverables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    payment_kind = postgresql.ENUM("funding", name="payment_kind_enum")
    payment_kind.create(op.get_bind(), checkfirst=True)

    payment_status = postgresql.ENUM(
        "created",
        "initiated",
        "succeeded",
        "failed",
        "refunded",
        name="payment_status_enum",
    )
    payment_status.create(op.get_bind(), checkfirst=True)

    payout_status_tbl = postgresql.ENUM(
        "pending",
        "processing",
        "paid",
        "failed",
        name="payout_status_enum_tbl",
    )
    payout_status_tbl.create(op.get_bind(), checkfirst=True)

    payout_method_enum = postgresql.ENUM("upi", "bank", name="payout_method_enum")
    payout_method_enum.create(op.get_bind(), checkfirst=True)

    # --- creator_payout_method -------------------------------------------
    op.create_table(
        "creator_payout_method",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creator_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "method",
            postgresql.ENUM(
                "upi", "bank", name="payout_method_enum", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("holder_name", sa.String(length=100), nullable=False),
        sa.Column("upi_vpa_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("account_number_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("account_number_last4", sa.Text(), nullable=True),
        sa.Column("ifsc_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column(
            "verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.PrimaryKeyConstraint("id", name="pk_creator_payout_method"),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator_profiles.id"],
            name="fk_creator_payout_method_creator_id_creator_profiles",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "("
            "method = 'upi' AND upi_vpa_ciphertext IS NOT NULL "
            "AND account_number_ciphertext IS NULL"
            ") OR ("
            "method = 'bank' AND account_number_ciphertext IS NOT NULL "
            "AND ifsc_ciphertext IS NOT NULL "
            "AND account_number_last4 IS NOT NULL"
            ")",
            name="ck_creator_payout_method_payout_method_fields_consistent",
        ),
    )
    # Partial unique index — at most one active method per creator.
    op.execute(
        "CREATE UNIQUE INDEX ux_payout_method_active "
        "ON creator_payout_method (creator_id) "
        "WHERE is_active = true"
    )

    # --- payments -------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collaboration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "funding", name="payment_kind_enum", create_type=False
            ),
            nullable=False,
            server_default=sa.text("'funding'"),
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_order_id", sa.String(length=128), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "created",
                "initiated",
                "succeeded",
                "failed",
                "refunded",
                name="payment_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'created'"),
        ),
        sa.Column(
            "raw_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.ForeignKeyConstraint(
            ["collaboration_id"],
            ["collaborations.id"],
            name="fk_payments_collaboration_id_collaborations",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_order_id",
            name="uq_payments_provider_provider_order_id",
        ),
        sa.CheckConstraint(
            "currency = 'INR'",
            name="ck_payments_currency_inr_only",
        ),
        sa.CheckConstraint(
            "amount_paise >= 0",
            name="ck_payments_amount_paise_non_negative",
        ),
    )

    # --- payouts --------------------------------------------------------
    op.create_table(
        "payouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collaboration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payout_method_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_payout_id", sa.String(length=128), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "paid",
                "failed",
                name="payout_status_enum_tbl",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "beneficiary_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.PrimaryKeyConstraint("id", name="pk_payouts"),
        sa.ForeignKeyConstraint(
            ["collaboration_id"],
            ["collaborations.id"],
            name="fk_payouts_collaboration_id_collaborations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payout_method_id"],
            ["creator_payout_method.id"],
            name="fk_payouts_payout_method_id_creator_payout_method",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "collaboration_id",
            name="uq_payouts_collaboration_id",
        ),
        sa.CheckConstraint(
            "currency = 'INR'",
            name="ck_payouts_currency_inr_only",
        ),
        sa.CheckConstraint(
            "amount_paise >= 0",
            name="ck_payouts_amount_paise_non_negative",
        ),
    )

    # --- refunds --------------------------------------------------------
    op.create_table(
        "refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_refund_id", sa.String(length=128), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'INR'"),
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_refunds"),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name="fk_refunds_payment_id_payments",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "currency = 'INR'",
            name="ck_refunds_currency_inr_only",
        ),
        sa.CheckConstraint(
            "amount_paise >= 0",
            name="ck_refunds_amount_paise_non_negative",
        ),
    )

    # --- payment_webhook_event -----------------------------------------
    op.create_table(
        "payment_webhook_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column(
            "verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_payment_webhook_event"),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_payment_webhook_event_provider_provider_event_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("payment_webhook_event")
    op.drop_table("refunds")
    op.drop_table("payouts")
    op.drop_table("payments")
    op.execute("DROP INDEX IF EXISTS ux_payout_method_active")
    op.drop_table("creator_payout_method")
    postgresql.ENUM(name="payout_method_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="payout_status_enum_tbl").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="payment_status_enum").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="payment_kind_enum").drop(op.get_bind(), checkfirst=True)
