"""Public creator discovery endpoints."""


import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.creator_profile import CreatorProfile
from app.schemas.profile import CreatorPublicOut

router = APIRouter(prefix="/creators", tags=["creators"])


class CreatorListOut(BaseModel):
    items: list[CreatorPublicOut]
    page: int
    page_size: int
    total: int


@router.get("", response_model=CreatorListOut)
async def list_creators(
    niche: Annotated[str | None, Query(max_length=50)] = None,
    content_type: Annotated[str | None, Query(max_length=50)] = None,
    language: Annotated[str | None, Query(max_length=50)] = None,
    location: Annotated[str | None, Query(max_length=120)] = None,
    price_min: Annotated[int | None, Query(ge=0, le=10**10)] = None,
    price_max: Annotated[int | None, Query(ge=0, le=10**10)] = None,
    campaign_type_capability: Annotated[
        Literal["ugc", "influencer", "hybrid"] | None,
        Query(),
    ] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    db: AsyncSession = Depends(get_db),
) -> CreatorListOut:
    conditions = [CreatorProfile.is_onboarded.is_(True)]
    if niche:
        conditions.append(CreatorProfile.niches.any(niche))
    if content_type:
        conditions.append(CreatorProfile.content_types.any(content_type))
    if language:
        conditions.append(CreatorProfile.languages.any(language))
    if location:
        conditions.append(
            (CreatorProfile.city == location) | (CreatorProfile.state == location)
        )
    if price_min is not None:
        conditions.append(CreatorProfile.starting_rate_paise >= price_min)
    if price_max is not None:
        conditions.append(CreatorProfile.starting_rate_paise <= price_max)
    if campaign_type_capability == "ugc":
        conditions.append(CreatorProfile.does_ugc.is_(True))
    elif campaign_type_capability == "influencer":
        conditions.append(CreatorProfile.does_influencer.is_(True))
    elif campaign_type_capability == "hybrid":
        conditions.append(
            and_(
                CreatorProfile.does_ugc.is_(True),
                CreatorProfile.does_influencer.is_(True),
            )
        )

    where_clause = and_(*conditions) if conditions else None

    total_stmt = select(func.count()).select_from(CreatorProfile)
    if where_clause is not None:
        total_stmt = total_stmt.where(where_clause)
    total = int((await db.execute(total_stmt)).scalar_one())

    stmt = (
        select(CreatorProfile)
        .order_by(CreatorProfile.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    rows = (await db.execute(stmt)).scalars().all()

    return CreatorListOut(
        items=[CreatorPublicOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{creator_id}", response_model=CreatorPublicOut)
async def get_creator(
    creator_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CreatorPublicOut:
    row = await db.get(CreatorProfile, creator_id)
    if row is None or not row.is_onboarded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found.",
        )
    return CreatorPublicOut.model_validate(row)
