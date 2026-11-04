"""Agreement service — signing + versioning.

:func:`sign` is idempotent on re-sign (if the signer's column is already
stamped, no mutation happens). When BOTH ``brand_signed_at`` and
``creator_signed_at`` become non-null AND the collaboration is still
``pending_agreement``, the collaboration flips to ``agreement_signed`` within
the same transaction (design §8.3 / finding 17).

:func:`create_new_version` enforces the "exactly one current agreement"
invariant via the DB partial unique index ``ux_agreement_current``; the
service stamps ``superseded_at`` on the current row before inserting the
new one in the same transaction.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateTransition
from app.models.agreement import AgreementVersion
from app.models.brand_profile import BrandProfile
from app.models.collaboration import Collaboration, CollaborationStatus
from app.models.creator_profile import CreatorProfile
from app.models.user import User, UserRole
from app.services import audit_service, collaboration_service, notification_service


async def _lock_current(
    session: AsyncSession, agreement_id: uuid.UUID
) -> AgreementVersion | None:
    stmt = (
        select(AgreementVersion)
        .where(AgreementVersion.id == agreement_id)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def sign(
    session: AsyncSession,
    *,
    agreement_id: uuid.UUID,
    user: User,
) -> AgreementVersion:
    """Record a signature. Idempotent on re-sign. See design §8.3."""

    agreement = await _lock_current(session, agreement_id)
    if agreement is None:
        raise InvalidStateTransition("Agreement not found.")
    if agreement.superseded_at is not None:
        raise InvalidStateTransition(
            "Cannot sign a superseded agreement version.",
        )

    collaboration = await session.get(Collaboration, agreement.collaboration_id)
    assert collaboration is not None

    now = datetime.now(UTC)
    signer_side: str | None = None  # "brand" | "creator" | None (idempotent)

    if user.role == UserRole.brand:
        brand = (
            await session.execute(
                select(BrandProfile).where(BrandProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if brand is None or brand.id != collaboration.brand_id:
            raise InvalidStateTransition(
                "Only the collaboration's brand may sign on the brand side."
            )
        if agreement.brand_signed_at is None:
            agreement.brand_signed_at = now
            signer_side = "brand"
    elif user.role == UserRole.creator:
        creator = (
            await session.execute(
                select(CreatorProfile).where(CreatorProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if creator is None or creator.id != collaboration.creator_id:
            raise InvalidStateTransition(
                "Only the collaboration's creator may sign on the creator side."
            )
        if agreement.creator_signed_at is None:
            agreement.creator_signed_at = now
            signer_side = "creator"
    else:
        # Admin or others cannot sign on behalf of a party.
        raise InvalidStateTransition(
            "Only the brand or creator parties may sign an agreement."
        )

    await session.flush()

    # Flip collaboration status iff both sides have signed and we're still in
    # pending_agreement.
    fully_signed_now = (
        agreement.brand_signed_at is not None
        and agreement.creator_signed_at is not None
    )
    if (
        fully_signed_now
        and collaboration.status == CollaborationStatus.pending_agreement
    ):
        await collaboration_service.mark_agreement_signed(session, collaboration)

    # Audit + notify only when something actually changed.
    if signer_side is not None:
        counterparty_user = await _counterparty_user(
            session, collaboration, signer_side
        )
        payload = {
            "agreement_id": str(agreement.id),
            "collaboration_id": str(collaboration.id),
            "signer_side": signer_side,
            "fully_signed": fully_signed_now,
        }
        await notification_service.write_for_user(
            session,
            user=counterparty_user,
            type_="agreement.signed",
            payload=payload,
        )
        await audit_service.write(
            session,
            actor_user_id=user.id,
            action="agreement.signed",
            target_type="agreement",
            target_id=agreement.id,
            diff=payload,
        )

    await session.refresh(agreement)
    return agreement


async def _counterparty_user(
    session: AsyncSession,
    collaboration: Collaboration,
    signer_side: str,
) -> User | None:
    if signer_side == "brand":
        cp = await session.get(CreatorProfile, collaboration.creator_id)
        return await session.get(User, cp.user_id) if cp else None
    bp = await session.get(BrandProfile, collaboration.brand_id)
    return await session.get(User, bp.user_id) if bp else None


async def create_new_version(
    session: AsyncSession,
    *,
    collaboration_id: uuid.UUID,
    patch: dict[str, Any],
    actor_user: User | None = None,
) -> AgreementVersion:
    """Supersede the current agreement and insert v2 (or higher).

    The DB partial unique index ``ux_agreement_current`` guarantees that two
    current rows cannot coexist; this function stamps ``superseded_at`` on
    the current row in the same transaction so the insert succeeds.
    """

    stmt = (
        select(AgreementVersion)
        .where(
            AgreementVersion.collaboration_id == collaboration_id,
            AgreementVersion.superseded_at.is_(None),
        )
        .with_for_update()
    )
    current = (await session.execute(stmt)).scalar_one_or_none()
    if current is None:
        raise InvalidStateTransition(
            "No current agreement to supersede for this collaboration."
        )

    now = datetime.now(UTC)
    current.superseded_at = now

    new_fields: dict[str, Any] = {
        "scope": current.scope,
        "deliverable_spec": list(current.deliverable_spec or []),
        "price_paise": current.price_paise,
        "currency": current.currency,
        "deadline": current.deadline,
        "revision_limit": current.revision_limit,
        "usage_rights": current.usage_rights,
        "disclosure_required": current.disclosure_required,
    }
    for key, value in patch.items():
        if key in new_fields:
            new_fields[key] = value

    next_version = AgreementVersion(
        collaboration_id=collaboration_id,
        version_number=current.version_number + 1,
        brand_signed_at=None,
        creator_signed_at=None,
        superseded_at=None,
        **new_fields,
    )
    session.add(next_version)
    await session.flush()
    await session.refresh(next_version)

    collaboration = await session.get(Collaboration, collaboration_id)
    if collaboration is not None:
        # Notify both parties — a new version requires fresh signatures.
        brand_user = None
        creator_user = None
        bp = await session.get(BrandProfile, collaboration.brand_id)
        if bp is not None:
            brand_user = await session.get(User, bp.user_id)
        cp = await session.get(CreatorProfile, collaboration.creator_id)
        if cp is not None:
            creator_user = await session.get(User, cp.user_id)
        payload = {
            "collaboration_id": str(collaboration.id),
            "agreement_id": str(next_version.id),
            "version_number": next_version.version_number,
        }
        for recipient in (brand_user, creator_user):
            await notification_service.write_for_user(
                session,
                user=recipient,
                type_="agreement.new_version",
                payload=payload,
            )
    await audit_service.write(
        session,
        actor_user_id=actor_user.id if actor_user else None,
        action="agreement.new_version",
        target_type="agreement",
        target_id=next_version.id,
        diff={
            "collaboration_id": str(collaboration_id),
            "version_number": next_version.version_number,
        },
    )
    return next_version
