"""/users/me + /me/profile routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import InvalidStateTransition
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.profile import (
    BrandProfilePatch,
    BrandProfileSelfOut,
    CreatorProfilePatch,
    CreatorProfileSelfOut,
    MeProfileOut,
    OnboardingResult,
)
from app.schemas.user import MeOut, RoleSelectionIn
from app.services import profile_service, user_service

router = APIRouter(tags=["users"])


def _creator_self(profile) -> CreatorProfileSelfOut:  # noqa: ANN001
    return CreatorProfileSelfOut.model_validate(profile)


def _brand_self(profile) -> BrandProfileSelfOut:  # noqa: ANN001
    return BrandProfileSelfOut.model_validate(profile)


def _me_out(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        role=user.role.value if user.role else None,
        clerk_user_id=user.clerk_user_id,
        is_active=user.is_active,
    )


@router.get("/users/me", response_model=MeOut)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    # get_current_user may have provisioned a new row — commit so the next
    # request sees it.
    await db.commit()
    return _me_out(user)


@router.post("/users/me/role", response_model=MeOut)
async def set_me_role(
    body: RoleSelectionIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeOut:
    try:
        await user_service.set_role_once(db, user=user, role=body.role)
    except InvalidStateTransition as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role is already set and cannot be changed.",
        ) from exc
    await db.commit()
    return _me_out(user)


@router.get("/me/profile", response_model=MeProfileOut)
async def get_me_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeProfileOut:
    if user.role is None:
        await db.commit()
        return MeProfileOut(role=None)
    if user.role == UserRole.creator:
        profile = await profile_service.get_or_create_creator_profile(db, user=user)
        await db.commit()
        return MeProfileOut(role="creator", creator=_creator_self(profile))
    if user.role == UserRole.brand:
        profile = await profile_service.get_or_create_brand_profile(db, user=user)
        await db.commit()
        return MeProfileOut(role="brand", brand=_brand_self(profile))
    await db.commit()
    return MeProfileOut(role="admin")


@router.patch("/me/profile", response_model=MeProfileOut)
async def patch_me_profile(
    body: CreatorProfilePatch | BrandProfilePatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeProfileOut:
    if user.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Complete onboarding before continuing.",
        )
    if user.role == UserRole.creator:
        if not isinstance(body, CreatorProfilePatch):
            try:
                body = CreatorProfilePatch.model_validate(
                    body.model_dump(exclude_unset=True)
                )
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid creator profile patch.",
                ) from exc
        patch = body.model_dump(exclude_unset=True)
        profile = await profile_service.update_creator_profile(db, user=user, patch=patch)
        await db.commit()
        return MeProfileOut(role="creator", creator=_creator_self(profile))
    if user.role == UserRole.brand:
        if not isinstance(body, BrandProfilePatch):
            try:
                body = BrandProfilePatch.model_validate(
                    body.model_dump(exclude_unset=True)
                )
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid brand profile patch.",
                ) from exc
        patch = body.model_dump(exclude_unset=True)
        # Pydantic HttpUrl -> str conversion so SQLAlchemy stores a plain string.
        if "website" in patch and patch["website"] is not None:
            patch["website"] = str(patch["website"])
        if "billing_address" in patch and patch["billing_address"] is not None:
            patch["billing_address"] = (
                patch["billing_address"].model_dump()
                if hasattr(patch["billing_address"], "model_dump")
                else dict(patch["billing_address"])
            )
        profile = await profile_service.update_brand_profile(db, user=user, patch=patch)
        await db.commit()
        return MeProfileOut(role="brand", brand=_brand_self(profile))
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin accounts have no editable profile.",
    )


@router.post("/me/profile/complete-onboarding", response_model=OnboardingResult)
async def complete_onboarding(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingResult:
    if user.role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Complete onboarding before continuing.",
        )
    is_onboarded, missing = await profile_service.complete_onboarding(db, user=user)
    await db.commit()
    return OnboardingResult(is_onboarded=is_onboarded, missing_fields=missing)
