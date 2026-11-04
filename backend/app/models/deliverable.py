"""Deliverable model + enums."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DeliverableKind(str, enum.Enum):
    file = "file"
    link = "link"


class DeliverableStatus(str, enum.Enum):
    submitted = "submitted"
    revision_requested = "revision_requested"
    approved = "approved"
    disputed = "disputed"


class Deliverable(Base, TimestampMixin):
    __tablename__ = "deliverables"

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
    spec_index: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[DeliverableKind] = mapped_column(
        SAEnum(
            DeliverableKind,
            name="deliverable_kind_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DeliverableStatus] = mapped_column(
        SAEnum(
            DeliverableStatus,
            name="deliverable_status_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=DeliverableStatus.submitted,
    )
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_deliverables_collaboration_id_status", "collaboration_id", "status"),
    )
