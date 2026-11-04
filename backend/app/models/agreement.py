"""AgreementVersion model.

Design §4.1 / §8.3. Partial unique index ``ux_agreement_current`` on
``(collaboration_id) WHERE superseded_at IS NULL`` is created by Alembic
migration 0006 — SQLAlchemy's declarative Index does not emit a
``WHERE`` clause portably across backends, so the index is authored directly
in the migration.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AgreementVersion(Base, TimestampMixin):
    __tablename__ = "agreement_version"

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
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    deliverable_spec: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revision_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_rights: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclosure_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    brand_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    creator_signed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "collaboration_id",
            "version_number",
            name="uq_agreement_version_collaboration_id_version_number",
        ),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("revision_limit >= 0", name="revision_limit_non_negative"),
        CheckConstraint("price_paise >= 0", name="price_paise_non_negative"),
        CheckConstraint("currency = 'INR'", name="currency_inr_only"),
    )
