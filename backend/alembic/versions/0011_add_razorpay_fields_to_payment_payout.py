"""add_razorpay_fields_to_payment_payout

Revision ID: 0011_add_razorpay_fields
Revises: 0010_clerk_auth
Create Date: 2026-11-02 12:24:04.774905

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011_add_razorpay_fields'
down_revision: Union[str, None] = '0010_clerk_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Razorpay fields to payments table
    op.add_column(
        "payments",
        sa.Column("razorpay_payment_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("razorpay_refund_id", sa.String(length=128), nullable=True),
    )

    # Add Razorpay fields to payouts table
    op.add_column(
        "payouts",
        sa.Column("razorpay_fund_account_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "payouts",
        sa.Column("razorpay_contact_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    # Drop Razorpay fields from payouts table
    op.drop_column("payouts", "razorpay_contact_id")
    op.drop_column("payouts", "razorpay_fund_account_id")

    # Drop Razorpay fields from payments table
    op.drop_column("payments", "razorpay_refund_id")
    op.drop_column("payments", "razorpay_payment_id")
