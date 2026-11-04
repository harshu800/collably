"""Campaign CRUD + state-transition routes."""


import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.brand_profile import BrandProfile
from app.models.campaign import Campaign, CampaignStatus, CampaignType
from app.models.user import User, UserRole
from app.schemas.campaign import (
    CampaignCreateIn,
    CampaignListOut,
    CampaignOut,
    CampaignPatchIn,
)
from app.services import campaign_service

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _to_out(campaign: Campaign) -> CampaignOut:
    return CampaignOut.model_validate(campaign)


async def _load_owned_campaign(
    db: AsyncSession,
    *,
    campaign_id: uuid.UUID,
    user: User,
) -> Campaign:
    campaign = await campaign_service.get_by_id(db, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found.",
        )
    if user.role == UserRole.admin:
        return campaign
    # Owner check â€” campaign.brand_id is the BrandProfile.id; cross-reference
    # against the current user's BrandProfile.
    brand = (
        await db.execute(select(BrandProfile).where(BrandProfile.user_id == user.id))
    ).scalar_one_or_none()
    if brand is None or brand.id != campaign.brand_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found.",
        )
    return campaign


@router.post(
    "",
    response_model=CampaignOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    body: CampaignCreateIn,
    user: User = Depends(require_role(UserRole.brand)),
    db: AsyncSession = Depends(get_db),
) -> CampaignOut:
    data: dict[str, Any] = body.model_dump()
    # Convert nested Pydantic models in deliverable_spec into plain dicts for JSONB.
    data["deliverable_spec"] = [
        item if isinstance(item, dict) else item.model_dump()  # type: ignore[union-attr]
        for item in data.get("deliverable_spec") or []
    ]
    campaign = await campaign_service.create(db, brand_user=user, data=data)
    await db.commit()
    return _to_out(campaign)


@router.get("", response_model=CampaignListOut)
async def list_campaigns(
    niche: Annotated[str | None, Query(max_length=50)] = None,
    type: Annotated[  # noqa: A002  - matches path convention
        Literal["ugc", "influencer", "hybrid"] | None,
        Query(),
    ] = None,
    language: Annotated[str | None, Query(max_length=50)] = None,
    location: Annotated[str | None, Query(max_length=120)] = None,
    budget_min: Annotated[int | None, Query(ge=0, le=10**10)] = None,
    budget_max: Annotated[int | None, Query(ge=0, le=10**10)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    db: AsyncSession = Depends(get_db),
) -> CampaignListOut:
    conditions = [Campaign.status == CampaignStatus.open]
    if niche:
        conditions.append(Campaign.niches.any(niche))
    if type:
        conditions.append(Campaign.type == CampaignType(type))
    if language:
        conditions.append(Campaign.languages.any(language))
    if location:
        conditions.append(Campaign.locations.any(location))
    if budget_min is not None:
        conditions.append(Campaign.budget_paise >= budget_min)
    if budget_max is not None:
        conditions.append(Campaign.budget_paise <= budget_max)

    where_clause = and_(*conditions)

    total = int(
        (
            await db.execute(
                select(func.count()).select_from(Campaign).where(where_clause)
            )
        ).scalar_one()
    )

    rows = (
        await db.execute(
            select(Campaign)
            .where(where_clause)
            .order_by(Campaign.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return CampaignListOut(
        items=[_to_out(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CampaignOut:
    campaign = await campaign_service.get_by_id(db, campaign_id)
    if campaign is None or campaign.status == CampaignStatus.archived:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found.",
        )
    return _to_out(campaign)


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def patch_campaign(
    campaign_id: uuid.UUID,
    body: CampaignPatchIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignOut:
    campaign = await _load_owned_campaign(db, campaign_id=campaign_id, user=user)
    patch = body.model_dump(exclude_unset=True)
    if "deliverable_spec" in patch and patch["deliverable_spec"] is not None:
        patch["deliverable_spec"] = [
            item if isinstance(item, dict) else item.model_dump()  # type: ignore[union-attr]
            for item in patch["deliverable_spec"]
        ]
    updated = await campaign_service.update(db, campaign=campaign, patch=patch)
    await db.commit()
    return _to_out(updated)


@router.post("/{campaign_id}/close", response_model=CampaignOut)
async def close_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignOut:
    campaign = await _load_owned_campaign(db, campaign_id=campaign_id, user=user)
    campaign = await campaign_service.close(db, campaign=campaign)
    await db.commit()
    return _to_out(campaign)


@router.post("/{campaign_id}/archive", response_model=CampaignOut)
async def archive_campaign(
    campaign_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CampaignOut:
    campaign = await _load_owned_campaign(db, campaign_id=campaign_id, user=user)
    campaign = await campaign_service.archive(db, campaign=campaign)
    await db.commit()
    return _to_out(campaign)
