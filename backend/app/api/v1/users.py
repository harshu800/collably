"""/users/me + /me/profile routes."""

from __future__ import annotations

import re
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import InvalidStateTransition
from app.db.session import get_db
from app.models.file import File, FileVisibility
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

PROFILE_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
PORTFOLIO_TYPES = PROFILE_IMAGE_TYPES | frozenset(
    {"video/mp4", "video/quicktime", "application/pdf"}
)
PUBLIC_FILE_ID = re.compile(r"^[0-9a-fA-F-]{36}$")


async def _validate_profile_file(
    db: AsyncSession,
    *,
    user: User,
    file_id: uuid.UUID,
    allowed_types: frozenset[str],
) -> None:
    file_row = await db.get(File, file_id)
    if (
        file_row is None
        or file_row.owner_user_id != user.id
        or file_row.visibility != FileVisibility.public
        or file_row.content_type not in allowed_types
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Profile files must be uploaded by you and match the requested file type.",
        )


async def _validate_creator_file_references(
    db: AsyncSession,
    *,
    user: User,
    patch: dict,
) -> None:
    avatar_id = patch.get("avatar_file_id")
    if avatar_id is not None:
        await _validate_profile_file(
            db, user=user, file_id=uuid.UUID(avatar_id), allowed_types=PROFILE_IMAGE_TYPES
        )

    links = patch.get("portfolio_links")
    if links is None:
        return
    for link in links:
        path_parts = urlsplit(link["url"]).path.rstrip("/").split("/")
        if len(path_parts) < 3 or path_parts[-3:-1] != ["files", "public"]:
            continue
        raw_file_id = path_parts[-1]
        if not PUBLIC_FILE_ID.fullmatch(raw_file_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Portfolio file URL is invalid.",
            )
        try:
            portfolio_file_id = uuid.UUID(raw_file_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Portfolio file URL is invalid.",
            ) from exc
        await _validate_profile_file(
            db,
            user=user,
            file_id=portfolio_file_id,
            allowed_types=PORTFOLIO_TYPES,
        )


async def _validate_brand_file_references(
    db: AsyncSession,
    *,
    user: User,
    patch: dict,
) -> None:
    logo_id = patch.get("logo_file_id")
    if logo_id is not None:
        await _validate_profile_file(
            db, user=user, file_id=uuid.UUID(logo_id), allowed_types=PROFILE_IMAGE_TYPES
        )


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
        patch = body.model_dump(exclude_unset=True, mode="json")
        await _validate_creator_file_references(db, user=user, patch=patch)
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
        patch = body.model_dump(exclude_unset=True, mode="json")
        # Pydantic HttpUrl -> str conversion so SQLAlchemy stores a plain string.
        if "website" in patch and patch["website"] is not None:
            patch["website"] = str(patch["website"])
        if "billing_address" in patch and patch["billing_address"] is not None:
            patch["billing_address"] = dict(patch["billing_address"])
        await _validate_brand_file_references(db, user=user, patch=patch)
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
