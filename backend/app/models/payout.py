"""Payout model — one row per collaboration payout."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PayoutStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    paid = "paid"
    failed = "failed"


class Payout(Base, TimestampMixin):
    __tablename__ = "payouts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    collaboration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collaborations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    payout_method_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creator_payout_method.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_payout_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[PayoutStatus] = mapped_column(
        SAEnum(
            PayoutStatus,
            name="payout_status_enum_tbl",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=PayoutStatus.pending,
    )
    beneficiary_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    razorpay_fund_account_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    razorpay_contact_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    __table_args__ = (
        CheckConstraint("currency = 'INR'", name="currency_inr_only"),
        CheckConstraint("amount_paise >= 0", name="amount_paise_non_negative"),
    )
