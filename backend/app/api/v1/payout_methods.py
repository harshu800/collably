"""Creator payout method routes — /me/payout-method."""


from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.db.session import get_db
from app.models.creator_profile import CreatorProfile
from app.models.user import User, UserRole
from app.schemas.payout_method import PayoutMethodIn, PayoutMethodOut
from app.services import payout_method_service

router = APIRouter(tags=["payout-methods"])


async def _creator_profile(db: AsyncSession, user: User) -> CreatorProfile:
    cp = (
        await db.execute(
            select(CreatorProfile).where(CreatorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if cp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator profile not found.",
        )
    return cp


@router.get("/me/payout-method", response_model=PayoutMethodOut)
async def get_my_payout_method(
    user: User = Depends(require_role(UserRole.creator)),
    db: AsyncSession = Depends(get_db),
) -> PayoutMethodOut:
    cp = await _creator_profile(db, user)
    active = await payout_method_service.get_active(db, creator_id=cp.id)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active payout method.",
        )
    projection = payout_method_service.non_sensitive_projection(active)
    return PayoutMethodOut(**projection)


@router.put("/me/payout-method", response_model=PayoutMethodOut)
async def put_my_payout_method(
    body: PayoutMethodIn,
    user: User = Depends(require_role(UserRole.creator)),
    db: AsyncSession = Depends(get_db),
) -> PayoutMethodOut:
    cp = await _creator_profile(db, user)
    row = await payout_method_service.upsert(
        db, creator_id=cp.id, payload=body.model_dump()
    )
    await db.commit()
    projection = payout_method_service.non_sensitive_projection(row)
    return PayoutMethodOut(**projection)


@router.delete("/me/payout-method", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_payout_method(
    user: User = Depends(require_role(UserRole.creator)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    cp = await _creator_profile(db, user)
    await payout_method_service.deactivate(db, creator_id=cp.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
