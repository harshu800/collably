"""User model + the ``user_role_enum`` Postgres enum."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserRole(str, enum.Enum):
    creator = "creator"
    brand = "brand"
    admin = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        CITEXT(),
        nullable=False,
        index=True,
    )
    clerk_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    role: Mapped[UserRole | None] = mapped_column(
        SAEnum(
            UserRole,
            name="user_role_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        role_val = self.role.value if self.role else None
        return (
            f"<User id={self.id} email={self.email!r} "
            f"clerk_user_id={self.clerk_user_id!r} role={role_val}>"
        )
