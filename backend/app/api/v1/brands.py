"""Brand profile read â€” self or admin only."""


import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.brand_profile import BrandProfile
from app.models.user import User, UserRole
from app.schemas.profile import BrandProfileSelfOut, BrandPublicOut

router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("/{brand_id}", response_model=BrandProfileSelfOut)
async def get_brand(
    brand_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BrandProfileSelfOut:
    row = await db.get(BrandProfile, brand_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found.",
        )
    is_owner = row.user_id == user.id
    is_admin = user.role == UserRole.admin
    if not (is_owner or is_admin):
        # 404 (not 403) hides existence of resources the viewer may not touch.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found.",
        )
    return BrandProfileSelfOut.model_validate(row)


@router.get("/{brand_id}/public", response_model=BrandPublicOut)
async def get_public_brand(
    brand_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BrandPublicOut:
    row = await db.get(BrandProfile, brand_id)
    if row is None or not row.is_onboarded:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found.",
        )
    return BrandPublicOut.model_validate(row)
