"""CampaignApplication + ``application_status_enum``."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ApplicationStatus(str, enum.Enum):
    invited = "invited"
    submitted = "submitted"
    shortlisted = "shortlisted"
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"


class CampaignApplication(Base, TimestampMixin):
    __tablename__ = "campaign_applications"

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
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creator_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposed_price_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    pitch: Mapped[str | None] = mapped_column(Text, nullable=True)
    portfolio_links: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        SAEnum(
            ApplicationStatus,
            name="application_status_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=ApplicationStatus.submitted,
    )
    invited_by_brand: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "creator_id",
            name="uq_campaign_applications_campaign_id_creator_id",
        ),
        Index(
            "ix_campaign_applications_campaign_id_status",
            "campaign_id",
            "status",
        ),
        CheckConstraint("currency = 'INR'", name="currency_inr_only"),
        CheckConstraint(
            "proposed_price_paise IS NULL OR proposed_price_paise >= 0",
            name="proposed_price_paise_non_negative",
        ),
    )
