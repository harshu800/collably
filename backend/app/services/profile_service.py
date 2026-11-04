"""Profile service — the single writer for creator + brand profile state.

Also owns the "mark onboarded if the required fields are now set" check so
the frontend has a single source of truth for the onboarding gate.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand_profile import BrandProfile
from app.models.creator_profile import CreatorProfile
from app.models.user import User, UserRole

# Minimum fields a creator must fill in before :attr:`is_onboarded` can flip.
CREATOR_REQUIRED_FIELDS: tuple[str, ...] = (
    "display_name",
    "bio",
    "city",
)
BRAND_REQUIRED_FIELDS: tuple[str, ...] = (
    "company_name",
    "industry",
    "contact_name",
    "contact_email",
)


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


async def get_or_create_creator_profile(
    session: AsyncSession,
    *,
    user: User,
) -> CreatorProfile:
    stmt = select(CreatorProfile).where(CreatorProfile.user_id == user.id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is not None:
        return row
    row = CreatorProfile(user_id=user.id)
    session.add(row)
    await session.flush()
    return row


async def get_or_create_brand_profile(
    session: AsyncSession,
    *,
    user: User,
) -> BrandProfile:
    stmt = select(BrandProfile).where(BrandProfile.user_id == user.id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is not None:
        return row
    row = BrandProfile(user_id=user.id)
    session.add(row)
    await session.flush()
    return row


async def get_creator_profile_by_id(
    session: AsyncSession,
    *,
    creator_id: uuid.UUID,
) -> CreatorProfile | None:
    return await session.get(CreatorProfile, creator_id)


async def get_brand_profile_by_id(
    session: AsyncSession,
    *,
    brand_id: uuid.UUID,
) -> BrandProfile | None:
    return await session.get(BrandProfile, brand_id)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def _apply_patch(instance: Any, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if hasattr(instance, key):
            setattr(instance, key, value)


async def update_creator_profile(
    session: AsyncSession,
    *,
    user: User,
    patch: dict[str, Any],
) -> CreatorProfile:
    profile = await get_or_create_creator_profile(session, user=user)
    _apply_patch(profile, patch)
    _maybe_mark_creator_onboarded(profile)
    await session.flush()
    await session.refresh(profile)
    return profile


async def update_brand_profile(
    session: AsyncSession,
    *,
    user: User,
    patch: dict[str, Any],
) -> BrandProfile:
    profile = await get_or_create_brand_profile(session, user=user)
    _apply_patch(profile, patch)
    _maybe_mark_brand_onboarded(profile)
    await session.flush()
    await session.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Onboarding completeness
# ---------------------------------------------------------------------------


def _missing_creator_fields(profile: CreatorProfile) -> list[str]:
    missing: list[str] = []
    for field in CREATOR_REQUIRED_FIELDS:
        value = getattr(profile, field, None)
        if not value:
            missing.append(field)
    # Must choose at least one of the capability flags.
    if not (profile.does_ugc or profile.does_influencer):
        missing.append("does_ugc_or_does_influencer")
    return missing


def _missing_brand_fields(profile: BrandProfile) -> list[str]:
    missing: list[str] = []
    for field in BRAND_REQUIRED_FIELDS:
        value = getattr(profile, field, None)
        if not value:
            missing.append(field)
    return missing


def _maybe_mark_creator_onboarded(profile: CreatorProfile) -> None:
    if not _missing_creator_fields(profile):
        profile.is_onboarded = True


def _maybe_mark_brand_onboarded(profile: BrandProfile) -> None:
    if not _missing_brand_fields(profile):
        profile.is_onboarded = True


async def complete_onboarding(
    session: AsyncSession,
    *,
    user: User,
) -> tuple[bool, list[str]]:
    """Return ``(is_onboarded, missing_fields)`` for the caller's profile."""

    if user.role == UserRole.creator:
        profile = await get_or_create_creator_profile(session, user=user)
        missing = _missing_creator_fields(profile)
        if not missing:
            profile.is_onboarded = True
        await session.flush()
        return profile.is_onboarded, missing
    if user.role == UserRole.brand:
        profile = await get_or_create_brand_profile(session, user=user)
        missing = _missing_brand_fields(profile)
        if not missing:
            profile.is_onboarded = True
        await session.flush()
        return profile.is_onboarded, missing
    # Admin has no profile — always "onboarded" for the UI.
    return True, []
