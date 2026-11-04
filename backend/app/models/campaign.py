"""Campaign model + ``campaign_type_enum`` + ``campaign_status_enum``."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CampaignType(str, enum.Enum):
    ugc = "ugc"
    influencer = "influencer"
    hybrid = "hybrid"


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    closed = "closed"
    archived = "archived"


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[CampaignType] = mapped_column(
        SAEnum(
            CampaignType,
            name="campaign_type_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
    )
    niches: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=list,
    )
    platforms: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=list,
    )
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        default=list,
    )
    locations: Mapped[list[str]] = mapped_column(
        ARRAY(String(120)),
        nullable=False,
        default=list,
    )
    budget_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    number_of_creators: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deliverable_spec: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    submission_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revision_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclosure_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    eligibility_filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[CampaignStatus] = mapped_column(
        SAEnum(
            CampaignStatus,
            name="campaign_status_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=CampaignStatus.draft,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("revision_limit >= 0", name="revision_limit_non_negative"),
        CheckConstraint("number_of_creators >= 1", name="number_of_creators_positive"),
        CheckConstraint("budget_paise >= 0", name="budget_paise_non_negative"),
        CheckConstraint("currency = 'INR'", name="currency_inr_only"),
        Index("ix_campaigns_brand_id_status", "brand_id", "status"),
        Index("ix_campaigns_status_type", "status", "type"),
        Index("ix_campaigns_niches_gin", "niches", postgresql_using="gin"),
    )
