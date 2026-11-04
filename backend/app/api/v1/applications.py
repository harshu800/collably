"""CampaignApplication routes â€” submit, invite, withdraw, shortlist, accept, reject."""


import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.application import CampaignApplication
from app.models.brand_profile import BrandProfile
from app.models.campaign import Campaign
from app.models.creator_profile import CreatorProfile
from app.models.user import User, UserRole
from app.schemas.application import (
    AcceptanceResult,
    ApplicationCreateIn,
    ApplicationInviteIn,
    ApplicationOut,
)
from app.services import application_service, campaign_service

router = APIRouter(tags=["applications"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_campaign_or_404(
    db: AsyncSession,
    campaign_id: uuid.UUID,
) -> Campaign:
    campaign = await campaign_service.get_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found.",
        )
    return campaign


async def _assert_brand_owns_campaign(
    db: AsyncSession,
    *,
    campaign: Campaign,
    user: User,
) -> None:
    if user.role == UserRole.admin:
        return
    brand = (
        await db.execute(select(BrandProfile).where(BrandProfile.user_id == user.id))
    ).scalar_one_or_none()
    if brand is None or brand.id != campaign.brand_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found.",
        )


async def _load_application_as_participant(
    db: AsyncSession,
    *,
    application_id: uuid.UUID,
    user: User,
    role: str,
) -> CampaignApplication:
    """Load an application + ownership-check against the current user.

    ``role`` controls which side of the application must match: ``'creator'``
    means the current user must own the ``CreatorProfile`` referenced on the
    application; ``'brand'`` means the current user must own the
    ``BrandProfile`` that owns the referenced ``Campaign``.
    """

    application = await application_service.get_application(db, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )
    if user.role == UserRole.admin:
        return application
    if role == "creator":
        creator = (
            await db.execute(
                select(CreatorProfile).where(CreatorProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if creator is None or creator.id != application.creator_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found.",
            )
    elif role == "brand":
        campaign = await campaign_service.get_by_id(db, application.campaign_id)
        if campaign is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found.",
            )
        await _assert_brand_owns_campaign(db, campaign=campaign, user=user)
    return application


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/campaigns/{campaign_id}/applications",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_application(
    campaign_id: uuid.UUID,
    body: ApplicationCreateIn,
    user: User = Depends(require_role(UserRole.creator)),
    db: AsyncSession = Depends(get_db),
) -> ApplicationOut:
    campaign = await _load_campaign_or_404(db, campaign_id)
    data = body.model_dump()
    # Pydantic URLs -> strings for JSONB storage.
    data["portfolio_links"] = [
        {
            "label": item["label"],
            "url": str(item["url"]),
        }
        for item in (data.get("portfolio_links") or [])
    ]
    application = await application_service.submit(
        db,
        creator_user=user,
        campaign=campaign,
        data=data,
    )
    await db.commit()
    return ApplicationOut.model_validate(application)


@router.get(
    "/campaigns/{campaign_id}/applications",
    response_model=list[ApplicationOut],
)
async def list_campaign_applications(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationOut]:
    campaign = await _load_campaign_or_404(db, campaign_id)
    await _assert_brand_owns_campaign(db, campaign=campaign, user=user)
    rows = (
        await db.execute(
            select(CampaignApplication)
            .where(CampaignApplication.campaign_id == campaign.id)
            .order_by(CampaignApplication.created_at.desc())
        )
    ).scalars().all()
    return [ApplicationOut.model_validate(r) for r in rows]


@router.get("/me/applications", response_model=list[ApplicationOut])
async def list_my_applications(
    user: User = Depends(require_role(UserRole.creator)),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationOut]:
    creator = (
        await db.execute(
            select(CreatorProfile).where(CreatorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if creator is None:
        return []
    rows = (
        await db.execute(
            select(CampaignApplication)
            .where(CampaignApplication.creator_id == creator.id)
            .order_by(CampaignApplication.created_at.desc())
        )
    ).scalars().all()
    return [ApplicationOut.model_validate(r) for r in rows]


@router.post("/applications/{application_id}/withdraw", response_model=ApplicationOut)
async def withdraw_application(
    application_id: uuid.UUID,
    user: User = Depends(require_role(UserRole.creator)),
    db: AsyncSession = Depends(get_db),
) -> ApplicationOut:
    application = await _load_application_as_participant(
        db, application_id=application_id, user=user, role="creator",
    )
    application = await application_service.withdraw(
        db, application=application, actor_user=user
    )
    await db.commit()
    return ApplicationOut.model_validate(application)


@router.post("/applications/{application_id}/shortlist", response_model=ApplicationOut)
async def shortlist_application(
    application_id: uuid.UUID,
    user: User = Depends(require_role(UserRole.brand, UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> ApplicationOut:
    application = await _load_application_as_participant(
        db, application_id=application_id, user=user, role="brand",
    )
    application = await application_service.shortlist(
        db, application=application, actor_user=user
    )
    await db.commit()
    return ApplicationOut.model_validate(application)


@router.post("/applications/{application_id}/accept", response_model=AcceptanceResult)
async def accept_application(
    application_id: uuid.UUID,
    user: User = Depends(require_role(UserRole.brand, UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> AcceptanceResult:
    application = await _load_application_as_participant(
        db, application_id=application_id, user=user, role="brand",
    )
    application, collaboration_id = await application_service.accept(
        db, application=application, actor_user=user,
    )
    await db.commit()
    return AcceptanceResult(
        application=ApplicationOut.model_validate(application),
        collaboration_id=collaboration_id,
    )


@router.post("/applications/{application_id}/reject", response_model=ApplicationOut)
async def reject_application(
    application_id: uuid.UUID,
    user: User = Depends(require_role(UserRole.brand, UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> ApplicationOut:
    application = await _load_application_as_participant(
        db, application_id=application_id, user=user, role="brand",
    )
    application = await application_service.reject(
        db, application=application, actor_user=user
    )
    await db.commit()
    return ApplicationOut.model_validate(application)


@router.post(
    "/campaigns/{campaign_id}/invitations",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
)
async def invite_creator(
    campaign_id: uuid.UUID,
    body: ApplicationInviteIn,
    user: User = Depends(require_role(UserRole.brand, UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> ApplicationOut:
    campaign = await _load_campaign_or_404(db, campaign_id)
    await _assert_brand_owns_campaign(db, campaign=campaign, user=user)
    creator = await db.get(CreatorProfile, body.creator_id)
    if creator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found.",
        )
    application = await application_service.invite(
        db, campaign=campaign, creator=creator, pitch=body.pitch, actor_user=user,
    )
    await db.commit()
    return ApplicationOut.model_validate(application)
