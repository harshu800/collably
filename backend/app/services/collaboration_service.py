"""Collaboration service — single writer for collaboration state transitions.

:func:`create_from_application` is called from
:func:`app.services.application_service.accept` inside the same transaction
and is the ONLY path that inserts a Collaboration (plus its initial
AgreementVersion row).

Every ``mark_*`` helper performs its transition under a ``FOR UPDATE`` lock
and raises :class:`InvalidStateTransition` on an illegal source state.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateTransition, WorkNotUnlocked
from app.models.agreement import AgreementVersion
from app.models.application import CampaignApplication
from app.models.campaign import Campaign
from app.models.collaboration import (
    Collaboration,
    CollaborationStatus,
    FundingStatus,
)

# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


async def create_from_application(
    session: AsyncSession,
    application: CampaignApplication,
) -> uuid.UUID:
    """Insert a Collaboration + its initial AgreementVersion (version_number=1).

    Called from :func:`application_service.accept` once an application has
    just been flipped to ``accepted`` under the campaign's ``FOR UPDATE``
    lock. Returns the new collaboration id.
    """

    campaign = await session.get(Campaign, application.campaign_id)
    assert campaign is not None, "application.campaign_id must reference an existing campaign"

    price_paise = (
        application.proposed_price_paise
        if application.proposed_price_paise is not None
        else campaign.budget_paise
    )

    collaboration = Collaboration(
        campaign_id=campaign.id,
        application_id=application.id,
        brand_id=campaign.brand_id,
        creator_id=application.creator_id,
        status=CollaborationStatus.pending_agreement,
        price_paise=price_paise,
        currency="INR",
        funding_status=FundingStatus.not_funded,
    )
    session.add(collaboration)
    await session.flush()

    # Initial agreement is version 1. Fields are copied from the campaign per
    # design §5.
    agreement = AgreementVersion(
        collaboration_id=collaboration.id,
        version_number=1,
        scope=campaign.description,
        deliverable_spec=list(campaign.deliverable_spec or []),
        price_paise=price_paise,
        currency="INR",
        deadline=campaign.submission_deadline,
        revision_limit=campaign.revision_limit,
        usage_rights=campaign.usage_rights,
        disclosure_required=campaign.disclosure_required,
    )
    session.add(agreement)
    await session.flush()

    return collaboration.id


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


async def get_current_agreement(
    session: AsyncSession,
    collaboration_id: uuid.UUID,
) -> AgreementVersion | None:
    stmt = select(AgreementVersion).where(
        AgreementVersion.collaboration_id == collaboration_id,
        AgreementVersion.superseded_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def lock_collaboration(
    session: AsyncSession,
    collaboration_id: uuid.UUID,
) -> Collaboration | None:
    stmt = (
        select(Collaboration)
        .where(Collaboration.id == collaboration_id)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Shared gate: current agreement must be fully signed
# ---------------------------------------------------------------------------


async def require_current_agreement_fully_signed(
    session: AsyncSession,
    collaboration: Collaboration,
) -> AgreementVersion:
    """Load the current agreement; raise WorkNotUnlocked(reason='agreement') if
    either party's signature is missing.

    v2r2-1: a single shared helper so every write-side service checks the same
    way, including after a supersession where the new current agreement is
    unsigned.
    """

    agreement = await get_current_agreement(session, collaboration.id)
    if (
        agreement is None
        or agreement.brand_signed_at is None
        or agreement.creator_signed_at is None
    ):
        raise WorkNotUnlocked(
            "Current agreement is not fully signed.",
            reason="agreement",
        )
    return agreement


# ---------------------------------------------------------------------------
# Named transitions
# ---------------------------------------------------------------------------


def _ensure_source(
    collaboration: Collaboration,
    allowed: Iterable[CollaborationStatus],
    target: CollaborationStatus,
) -> None:
    if collaboration.status not in set(allowed):
        raise InvalidStateTransition(
            f"Cannot move collaboration from {collaboration.status.value} "
            f"to {target.value}.",
            source=collaboration.status.value,
            target=target.value,
        )


async def _transition(
    session: AsyncSession,
    collaboration: Collaboration,
    *,
    allowed: Iterable[CollaborationStatus],
    target: CollaborationStatus,
) -> Collaboration:
    locked = await lock_collaboration(session, collaboration.id)
    assert locked is not None
    _ensure_source(locked, allowed, target)
    locked.status = target
    await session.flush()
    await session.refresh(locked)
    return locked


async def mark_agreement_signed(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    return await _transition(
        session,
        collaboration,
        allowed={CollaborationStatus.pending_agreement},
        target=CollaborationStatus.agreement_signed,
    )


async def mark_funding_initiated(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    return await _transition(
        session,
        collaboration,
        allowed={CollaborationStatus.agreement_signed},
        target=CollaborationStatus.funding_initiated,
    )


async def mark_funded(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    return await _transition(
        session,
        collaboration,
        allowed={CollaborationStatus.funding_initiated},
        target=CollaborationStatus.funded,
    )


async def mark_in_progress(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    return await _transition(
        session,
        collaboration,
        allowed={CollaborationStatus.funded},
        target=CollaborationStatus.in_progress,
    )


async def mark_in_review(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    return await _transition(
        session,
        collaboration,
        allowed={
            CollaborationStatus.funded,
            CollaborationStatus.in_progress,
            CollaborationStatus.in_review,
        },
        target=CollaborationStatus.in_review,
    )


async def mark_approved(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    return await _transition(
        session,
        collaboration,
        allowed={
            CollaborationStatus.in_review,
            CollaborationStatus.in_progress,
            CollaborationStatus.funded,
        },
        target=CollaborationStatus.approved,
    )


async def mark_completed(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    return await _transition(
        session,
        collaboration,
        allowed={CollaborationStatus.approved},
        target=CollaborationStatus.completed,
    )


async def mark_disputed(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    locked = await lock_collaboration(session, collaboration.id)
    assert locked is not None
    if locked.status in {CollaborationStatus.completed, CollaborationStatus.cancelled}:
        raise InvalidStateTransition(
            f"Cannot dispute a {locked.status.value} collaboration.",
            source=locked.status.value,
            target=CollaborationStatus.disputed.value,
        )
    locked.status = CollaborationStatus.disputed
    await session.flush()
    await session.refresh(locked)
    return locked


async def mark_cancelled(
    session: AsyncSession, collaboration: Collaboration
) -> Collaboration:
    locked = await lock_collaboration(session, collaboration.id)
    assert locked is not None
    if locked.status in {CollaborationStatus.completed, CollaborationStatus.cancelled}:
        raise InvalidStateTransition(
            f"Cannot cancel a {locked.status.value} collaboration.",
            source=locked.status.value,
            target=CollaborationStatus.cancelled.value,
        )
    locked.status = CollaborationStatus.cancelled
    await session.flush()
    await session.refresh(locked)
    return locked
