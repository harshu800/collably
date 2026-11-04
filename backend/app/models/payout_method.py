"""CreatorPayoutMethod — a creator's active payout destination (UPI or bank).

Design §4.1 soft-active lifecycle: a partial unique index
``ux_payout_method_active ON creator_payout_method (creator_id) WHERE is_active=true``
guarantees at most one active row per creator; historical rows referenced by
past :class:`Payout` records are preserved as ``is_active=false``.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, LargeBinary, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PayoutMethodKind(str, enum.Enum):
    upi = "upi"
    bank = "bank"


class CreatorPayoutMethod(Base, TimestampMixin):
    __tablename__ = "creator_payout_method"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creator_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    method: Mapped[PayoutMethodKind] = mapped_column(
        SAEnum(
            PayoutMethodKind,
            name="payout_method_enum",
            values_callable=lambda e: [m.value for m in e],
            native_enum=True,
        ),
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    holder_name: Mapped[str] = mapped_column(String(100), nullable=False)
    upi_vpa_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    account_number_ciphertext: Mapped[bytes | None] = mapped_column(
        LargeBinary, nullable=True
    )
    account_number_last4: Mapped[str | None] = mapped_column(Text, nullable=True)
    ifsc_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "("
            "method = 'upi' AND upi_vpa_ciphertext IS NOT NULL "
            "AND account_number_ciphertext IS NULL"
            ") OR ("
            "method = 'bank' AND account_number_ciphertext IS NOT NULL "
            "AND ifsc_ciphertext IS NOT NULL "
            "AND account_number_last4 IS NOT NULL"
            ")",
            name="payout_method_fields_consistent",
        ),
    )
