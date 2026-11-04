"""Application service — the single writer for application state transitions.

Core complexity lives in :func:`accept`: the campaign row is locked with
``SELECT ... FOR UPDATE`` while we count prior accepted applications so the
``number_of_creators`` cap holds under concurrent acceptances (design §8.2).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SlotLimitReached
from app.models.application import ApplicationStatus, CampaignApplication
from app.models.brand_profile import BrandProfile
from app.models.campaign import Campaign, CampaignStatus, CampaignType
from app.models.creator_profile import CreatorProfile
from app.models.user import User
from app.services import audit_service, collaboration_service, notification_service

NON_TERMINAL_STATES: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.invited,
        ApplicationStatus.submitted,
        ApplicationStatus.shortlisted,
    }
)


async def _brand_owner_user(
    session: AsyncSession, campaign: Campaign
) -> User | None:
    bp = await session.get(BrandProfile, campaign.brand_id)
    if bp is None:
        return None
    return await session.get(User, bp.user_id)


async def _creator_user(
    session: AsyncSession, creator_id: uuid.UUID
) -> User | None:
    cp = await session.get(CreatorProfile, creator_id)
    if cp is None:
        return None
    return await session.get(User, cp.user_id)


async def _notify_and_audit_transition(
    session: AsyncSession,
    *,
    application: CampaignApplication,
    actor_user: User | None,
    action: str,
    recipient: User | None,
) -> None:
    payload = {
        "application_id": str(application.id),
        "campaign_id": str(application.campaign_id),
        "status": application.status.value,
    }
    await notification_service.write_for_user(
        session, user=recipient, type_=action, payload=payload
    )
    await audit_service.write(
        session,
        actor_user_id=actor_user.id if actor_user else None,
        action=action,
        target_type="application",
        target_id=application.id,
        diff=payload,
    )


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


async def get_creator_profile(
    session: AsyncSession,
    *,
    user: User,
) -> CreatorProfile | None:
    stmt = select(CreatorProfile).where(CreatorProfile.user_id == user.id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_application(
    session: AsyncSession,
    application_id: uuid.UUID,
) -> CampaignApplication | None:
    return await session.get(CampaignApplication, application_id)


# ---------------------------------------------------------------------------
# Capability match
# ---------------------------------------------------------------------------


def creator_matches_campaign_type(
    creator: CreatorProfile,
    campaign: Campaign,
) -> bool:
    """Return ``True`` if the creator's capability flags match the campaign type."""

    if campaign.type == CampaignType.ugc:
        return creator.does_ugc
    if campaign.type == CampaignType.influencer:
        return creator.does_influencer
    if campaign.type == CampaignType.hybrid:
        return creator.does_ugc and creator.does_influencer
    return False  # pragma: no cover - defensive


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


async def submit(
    session: AsyncSession,
    *,
    creator_user: User,
    campaign: Campaign,
    data: dict[str, Any],
) -> CampaignApplication:
    """Creator submits a new application to a campaign (status=submitted).

    Raises:
        HTTPException 409 if the campaign is not open.
        HTTPException 403 if the creator's capability flags do not match the
            campaign type.
        HTTPException 409 if the (campaign, creator) pair already has an
            application (DB unique index enforces).
    """

    if campaign.status != CampaignStatus.open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign is not open to applications.",
        )

    creator = await get_creator_profile(session, user=creator_user)
    if creator is None or not creator.is_onboarded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Complete your creator profile before applying.",
        )

    if not creator_matches_campaign_type(creator, campaign):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your creator capabilities do not match this campaign type.",
        )

    application = CampaignApplication(
        campaign_id=campaign.id,
        creator_id=creator.id,
        proposed_price_paise=data.get("proposed_price_paise"),
        currency="INR",
        pitch=data.get("pitch"),
        portfolio_links=list(data.get("portfolio_links") or []),
        status=ApplicationStatus.submitted,
        invited_by_brand=False,
    )
    session.add(application)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this campaign.",
        ) from exc
    await session.refresh(application)

    brand_user = await _brand_owner_user(session, campaign)
    payload = {
        "application_id": str(application.id),
        "campaign_id": str(campaign.id),
        "creator_id": str(creator.id),
    }
    await notification_service.write_for_user(
        session, user=brand_user, type_="application.submitted", payload=payload
    )
    await audit_service.write(
        session,
        actor_user_id=creator_user.id,
        action="application.submitted",
        target_type="application",
        target_id=application.id,
        diff=payload,
    )
    return application


async def invite(
    session: AsyncSession,
    *,
    campaign: Campaign,
    creator: CreatorProfile,
    pitch: str | None = None,
    actor_user: User | None = None,
) -> CampaignApplication:
    """Brand creates an application in ``invited`` state for a specific creator."""

    if campaign.status != CampaignStatus.open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign is not open to invitations.",
        )

    application = CampaignApplication(
        campaign_id=campaign.id,
        creator_id=creator.id,
        currency="INR",
        pitch=pitch,
        status=ApplicationStatus.invited,
        invited_by_brand=True,
    )
    session.add(application)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An application for this creator already exists.",
        ) from exc
    await session.refresh(application)

    recipient = await _creator_user(session, creator.id)
    await _notify_and_audit_transition(
        session,
        application=application,
        actor_user=actor_user,
        action="application.invited",
        recipient=recipient,
    )
    return application


async def withdraw(
    session: AsyncSession,
    *,
    application: CampaignApplication,
    actor_user: User | None = None,
) -> CampaignApplication:
    """Creator withdraws from a non-terminal state."""

    if application.status not in NON_TERMINAL_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application cannot be withdrawn from its current state.",
        )
    application.status = ApplicationStatus.withdrawn
    await session.flush()
    await session.refresh(application)

    campaign = await session.get(Campaign, application.campaign_id)
    recipient = await _brand_owner_user(session, campaign) if campaign else None
    await _notify_and_audit_transition(
        session,
        application=application,
        actor_user=actor_user,
        action="application.withdrawn",
        recipient=recipient,
    )
    return application


async def shortlist(
    session: AsyncSession,
    *,
    application: CampaignApplication,
    actor_user: User | None = None,
) -> CampaignApplication:
    if application.status != ApplicationStatus.submitted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only submitted applications can be shortlisted.",
        )
    application.status = ApplicationStatus.shortlisted
    await session.flush()
    await session.refresh(application)

    recipient = await _creator_user(session, application.creator_id)
    await _notify_and_audit_transition(
        session,
        application=application,
        actor_user=actor_user,
        action="application.shortlisted",
        recipient=recipient,
    )
    return application


async def reject(
    session: AsyncSession,
    *,
    application: CampaignApplication,
    actor_user: User | None = None,
) -> CampaignApplication:
    if application.status not in NON_TERMINAL_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application is already terminal.",
        )
    application.status = ApplicationStatus.rejected
    await session.flush()
    await session.refresh(application)

    recipient = await _creator_user(session, application.creator_id)
    await _notify_and_audit_transition(
        session,
        application=application,
        actor_user=actor_user,
        action="application.rejected",
        recipient=recipient,
    )
    return application


async def accept(
    session: AsyncSession,
    *,
    application: CampaignApplication,
    actor_user: User | None = None,
) -> tuple[CampaignApplication, uuid.UUID | None]:
    """Flip the application to ``accepted`` under a per-campaign write lock.

    Steps (design §8.2):
      1. ``SELECT ... FOR UPDATE`` the Campaign row so concurrent accepts
         serialise behind the same lock.
      2. Count rows with ``status='accepted'`` for this campaign.
      3. Refuse with :class:`SlotLimitReached` if the cap is already met.
      4. Flip the application to ``accepted``.
      5. Call :func:`collaboration_service.create_from_application` to create
         the (FEAT-003) Collaboration row — stubbed in FEAT-002 to ``None``.
    """

    if application.status not in {
        ApplicationStatus.submitted,
        ApplicationStatus.shortlisted,
        ApplicationStatus.invited,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application cannot be accepted from its current state.",
        )

    # Lock the campaign row for the duration of the transaction.
    locked_campaign = (
        await session.execute(
            select(Campaign)
            .where(Campaign.id == application.campaign_id)
            .with_for_update()
        )
    ).scalar_one()

    accepted_count_stmt = (
        select(func.count())
        .select_from(CampaignApplication)
        .where(
            CampaignApplication.campaign_id == locked_campaign.id,
            CampaignApplication.status == ApplicationStatus.accepted,
        )
    )
    accepted_count = int((await session.execute(accepted_count_stmt)).scalar_one())
    if accepted_count >= locked_campaign.number_of_creators:
        raise SlotLimitReached()

    application.status = ApplicationStatus.accepted
    await session.flush()
    await session.refresh(application)

    collaboration_id = await collaboration_service.create_from_application(
        session,
        application,
    )

    recipient = await _creator_user(session, application.creator_id)
    payload = {
        "application_id": str(application.id),
        "campaign_id": str(application.campaign_id),
        "collaboration_id": str(collaboration_id) if collaboration_id else None,
        "status": application.status.value,
    }
    await notification_service.write_for_user(
        session, user=recipient, type_="application.accepted", payload=payload
    )
    await audit_service.write(
        session,
        actor_user_id=actor_user.id if actor_user else None,
        action="application.accepted",
        target_type="application",
        target_id=application.id,
        diff=payload,
    )
    return application, collaboration_id
