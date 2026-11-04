"""BrandProfile — the brand-side counterpart to CreatorProfile."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BrandProfile(Base, TimestampMixin):
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    website: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # GSTIN is validated via regex at the application layer (design §9); no DB check.
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    billing_address: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_onboarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Free-form notes field (optional, matches public-dashboard pattern).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
