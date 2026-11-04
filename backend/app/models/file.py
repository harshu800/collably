"""File model + the ``file_visibility_enum`` Postgres enum.

Private files are only served through the signed-token endpoint; direct
``uploads/`` serving is explicitly disabled (design §7.2).
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class FileVisibility(str, enum.Enum):
    public = "public"
    private = "private"


class File(Base, TimestampMixin):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    visibility: Mapped[FileVisibility] = mapped_column(
        SAEnum(
            FileVisibility,
            name="file_visibility_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
        default=FileVisibility.private,
    )
