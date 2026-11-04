"""Collaboration model + enums.

Design §4.1 / §8.3. ``funded`` and ``in_progress`` are deliberately distinct —
the funding webhook writes ``funded``; the first deliverable submission flips
``funded → in_progress``.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CollaborationStatus(str, enum.Enum):
    pending_agreement = "pending_agreement"
    agreement_signed = "agreement_signed"
    funding_initiated = "funding_initiated"
    funded = "funded"
    in_progress = "in_progress"
    in_review = "in_review"
    approved = "approved"
    completed = "completed"
    disputed = "disputed"
    cancelled = "cancelled"


class FundingStatus(str, enum.Enum):
    not_funded = "not_funded"
    funding_initiated = "funding_initiated"
    funding_confirmed = "funding_confirmed"
    funding_failed = "funding_failed"


class CollaborationPayoutStatus(str, enum.Enum):
    """Payout status column on Collaboration (includes 'none')."""

    none = "none"
    pending = "pending"
    processing = "processing"
    paid = "paid"
    failed = "failed"


class Collaboration(Base, TimestampMixin):
    __tablename__ = "collaborations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creator_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[CollaborationStatus] = mapped_column(
        SAEnum(
            CollaborationStatus,
            name="collaboration_status_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=CollaborationStatus.pending_agreement,
    )
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    funding_status: Mapped[FundingStatus] = mapped_column(
        SAEnum(
            FundingStatus,
            name="funding_status_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=FundingStatus.not_funded,
    )
    payout_status: Mapped[CollaborationPayoutStatus] = mapped_column(
        SAEnum(
            CollaborationPayoutStatus,
            name="payout_status_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=CollaborationPayoutStatus.none,
    )

    __table_args__ = (
        Index("ix_collaborations_brand_id_status", "brand_id", "status"),
        Index("ix_collaborations_creator_id_status", "creator_id", "status"),
        CheckConstraint("currency = 'INR'", name="currency_inr_only"),
        CheckConstraint("price_paise >= 0", name="price_paise_non_negative"),
    )
