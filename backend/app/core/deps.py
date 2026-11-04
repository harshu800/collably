"""Dependency injection helpers: current user, role gates."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk import verify_clerk_jwt
from app.core.logging import user_id_var
from app.db.session import get_db
from app.models.user import User, UserRole

_bearer_scheme = HTTPBearer(auto_error=False)


async def _lookup_or_provision_user(
    db: AsyncSession,
    *,
    clerk_user_id: str,
    email: str | None,
) -> User:
    """Return the local ``User`` for a Clerk sub, inserting a shell row on first sight.

    Freshly-provisioned users carry ``role=None`` so the caller must still go
    through :func:`require_role` / the role-selection endpoint before writing.
    """

    stmt = select(User).where(User.clerk_user_id == clerk_user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user

    fallback_email = (email or f"{clerk_user_id}@placeholder.clerk").lower()
    user = User(
        email=fallback_email,
        clerk_user_id=clerk_user_id,
        role=None,
        is_active=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # Another request raced us; roll back and re-select by clerk_user_id.
        await db.rollback()
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:  # pragma: no cover - theoretically unreachable
            raise
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from an ``Authorization: Bearer`` Clerk JWT.

    401s on any failure (missing header, invalid signature, expired, user
    deactivated).
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = verify_clerk_jwt(credentials.credentials)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await _lookup_or_provision_user(
        db, clerk_user_id=claims.sub, email=claims.email
    )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not found or deactivated.",
        )

    # Attach the user id to the structured-log context var for this request.
    user_id_var.set(str(user.id))
    return user


def require_role(*roles: UserRole | str) -> Callable[..., Awaitable[User]]:
    """Dependency factory enforcing that ``current_user.role`` is in ``roles``.

    A user whose Clerk account exists but who has not yet selected a role
    receives 403 "Complete onboarding before continuing." — downstream routes
    can rely on ``user.role`` being non-null.
    """

    allowed: set[str] = set()
    for r in roles:
        allowed.add(r.value if isinstance(r, UserRole) else str(r))

    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Complete onboarding before continuing.",
            )
        if user.role.value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return user

    return _dep
