"""CreatorPayoutMethod service — soft-active lifecycle (design §4.1).

A partial unique index enforces at most one active row per creator; this
service inserts a new active row and marks any prior active row
``is_active=false`` in the same transaction.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import field_encrypt
from app.models.payout_method import CreatorPayoutMethod, PayoutMethodKind


async def get_active(
    session: AsyncSession,
    *,
    creator_id: uuid.UUID,
) -> CreatorPayoutMethod | None:
    stmt = select(CreatorPayoutMethod).where(
        CreatorPayoutMethod.creator_id == creator_id,
        CreatorPayoutMethod.is_active.is_(True),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    creator_id: uuid.UUID,
    payload: dict[str, Any],
) -> CreatorPayoutMethod:
    """Insert a new active row; deactivate the prior active row in the same tx."""

    # Deactivate any current active row FIRST so the partial unique index
    # does not reject the subsequent insert.
    await session.execute(
        update(CreatorPayoutMethod)
        .where(
            CreatorPayoutMethod.creator_id == creator_id,
            CreatorPayoutMethod.is_active.is_(True),
        )
        .values(is_active=False)
    )
    await session.flush()

    method = PayoutMethodKind(payload["method"])
    holder_name = payload["holder_name"]
    label = payload.get("label")

    row = CreatorPayoutMethod(
        creator_id=creator_id,
        method=method,
        label=label,
        holder_name=holder_name,
        verified=False,
        is_active=True,
    )
    if method == PayoutMethodKind.upi:
        vpa = payload["upi_vpa"]
        row.upi_vpa_ciphertext = field_encrypt(vpa)
    else:
        account_number = payload["account_number"]
        ifsc = payload["ifsc"]
        row.account_number_ciphertext = field_encrypt(account_number)
        row.account_number_last4 = account_number[-4:]
        row.ifsc_ciphertext = field_encrypt(ifsc)
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def deactivate(
    session: AsyncSession,
    *,
    creator_id: uuid.UUID,
) -> None:
    """Soft-delete: set is_active=false on the current active row (if any)."""

    await session.execute(
        update(CreatorPayoutMethod)
        .where(
            CreatorPayoutMethod.creator_id == creator_id,
            CreatorPayoutMethod.is_active.is_(True),
        )
        .values(is_active=False)
    )
    await session.flush()


def _mask_upi_from_ciphertext(ciphertext: bytes | None) -> str | None:
    """Masked VPA for display. Decrypts, masks, discards the plaintext."""

    if ciphertext is None:
        return None
    from app.core.security import field_decrypt

    vpa = field_decrypt(ciphertext)
    if "@" not in vpa:
        return "***"
    local, host = vpa.split("@", 1)
    prefix = local[:3] if len(local) > 3 else local[:1]
    return f"{prefix}***@{host}"


def non_sensitive_projection(row: CreatorPayoutMethod) -> dict[str, Any]:
    """Return the API-safe projection of a payout method row."""

    return {
        "id": row.id,
        "method": row.method.value,
        "label": row.label,
        "holder_name": row.holder_name,
        "account_number_last4": row.account_number_last4,
        "upi_vpa_masked": (
            _mask_upi_from_ciphertext(row.upi_vpa_ciphertext)
            if row.method == PayoutMethodKind.upi
            else None
        ),
        "verified": row.verified,
    }
