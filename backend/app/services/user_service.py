"""User service — role assignment lives here (single writer)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateTransition
from app.models.user import User, UserRole

ALLOWED_SELF_ROLES: frozenset[str] = frozenset({"creator", "brand"})


async def set_role_once(
    session: AsyncSession,
    *,
    user: User,
    role: str,
) -> User:
    """Set ``user.role`` exactly once.

    Raises :class:`ValueError` if ``role`` is outside the self-selectable
    set and :class:`InvalidStateTransition` if the user already has a role
    assigned. The service does not commit — the router is the transaction
    boundary.
    """

    if role not in ALLOWED_SELF_ROLES:
        raise ValueError(
            f"Role {role!r} may not be self-assigned; "
            "allowed roles are 'creator' or 'brand'."
        )
    if user.role is not None:
        raise InvalidStateTransition(
            "User already has a role assigned."
        )
    user.role = UserRole(role)
    await session.flush()
    return user
