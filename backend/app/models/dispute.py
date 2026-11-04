"""Dispute model — opened by a party, resolved by an admin (design §4.1 / §17).

``split`` resolution is bookkeeping only in v1 per design §17 and v2r2-4:
``split_bps`` is recorded, the collaboration flips to ``completed``, and no
new money moves. ``release_to_creator`` triggers the normal payout path;
``refund_to_brand`` creates a Refund row and flips the collab to
``cancelled``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DisputeStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    rejected = "rejected"


class DisputeResolution(str, enum.Enum):
    release_to_creator = "release_to_creator"
    refund_to_brand = "refund_to_brand"
    split = "split"


class Dispute(Base, TimestampMixin):
    __tablename__ = "disputes"

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
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DisputeStatus] = mapped_column(
        SAEnum(
            DisputeStatus,
            name="dispute_status_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=DisputeStatus.open,
    )
    resolution: Mapped[DisputeResolution | None] = mapped_column(
        SAEnum(
            DisputeResolution,
            name="dispute_resolution_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=True,
    )
    split_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "split_bps IS NULL OR (split_bps >= 0 AND split_bps <= 10000)",
            name="split_bps_in_range",
        ),
        Index("ix_disputes_collaboration_id_status", "collaboration_id", "status"),
    )
