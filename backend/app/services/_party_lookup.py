"""Shared helpers for resolving the brand/creator :class:`User` of a collab.

Lives in its own module to avoid import cycles between the services that
emit notifications.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand_profile import BrandProfile
from app.models.collaboration import Collaboration
from app.models.creator_profile import CreatorProfile
from app.models.user import User


async def brand_user_for_collab(
    session: AsyncSession, collab: Collaboration
) -> User | None:
    bp = await session.get(BrandProfile, collab.brand_id)
    if bp is None:
        return None
    return await session.get(User, bp.user_id)


async def creator_user_for_collab(
    session: AsyncSession, collab: Collaboration
) -> User | None:
    cp = await session.get(CreatorProfile, collab.creator_id)
    if cp is None:
        return None
    return await session.get(User, cp.user_id)
