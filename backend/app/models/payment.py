"""Payment model — a funding payment order against a Collaboration."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PaymentKind(str, enum.Enum):
    funding = "funding"


class PaymentStatus(str, enum.Enum):
    created = "created"
    initiated = "initiated"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    collaboration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collaborations.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[PaymentKind] = mapped_column(
        SAEnum(
            PaymentKind,
            name="payment_kind_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=PaymentKind.funding,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(
            PaymentStatus,
            name="payment_status_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=PaymentStatus.created,
    )
    raw_response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    razorpay_refund_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_order_id",
            name="uq_payments_provider_provider_order_id",
        ),
        CheckConstraint("currency = 'INR'", name="currency_inr_only"),
        CheckConstraint("amount_paise >= 0", name="amount_paise_non_negative"),
    )
