"""Clerk webhook route — upserts local User rows on user.created/updated/deleted."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import WebhookVerificationError

from app.core.clerk import verify_clerk_webhook
from app.db.session import get_db
from app.models.user import User
from app.services import audit_service

router = APIRouter(prefix="/clerk", tags=["clerk"])


def _primary_email(data: dict[str, Any]) -> str | None:
    emails = data.get("email_addresses") or []
    if isinstance(emails, list) and emails:
        first = emails[0]
        if isinstance(first, dict):
            value = first.get("email_address") or first.get("email")
            if isinstance(value, str) and value:
                return value.lower()
    for key in ("email_address", "email", "primary_email"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value.lower()
    return None


async def _upsert_from_clerk(
    db: AsyncSession, *, clerk_user_id: str, email: str | None
) -> User:
    stmt = select(User).where(User.clerk_user_id == clerk_user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is not None:
        if email and user.email.lower() != email:
            user.email = email
        if not user.is_active:
            user.is_active = True
        await db.flush()
        return user
    user = User(
        clerk_user_id=clerk_user_id,
        email=(email or f"{clerk_user_id}@placeholder.clerk"),
        role=None,
        is_active=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:  # pragma: no cover - defensive
            raise
    return user


@router.post("/webhook")
async def receive_clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # IMPORTANT: read the raw body before any JSON parsing so svix can
    # verify the signature over the exact bytes.
    raw_body = await request.body()
    headers = dict(request.headers)
    try:
        event = verify_clerk_webhook(raw_body, headers)
    except WebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Clerk webhook signature.",
        ) from exc

    event_type = str(event.get("type") or "")
    data = event.get("data") or {}
    if not isinstance(data, dict):
        data = {}

    if event_type in {"user.created", "user.updated"}:
        clerk_user_id = str(data.get("id") or "")
        if not clerk_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clerk webhook payload missing data.id.",
            )
        await _upsert_from_clerk(
            db, clerk_user_id=clerk_user_id, email=_primary_email(data)
        )
        await db.commit()
        return {"status": "ok", "type": event_type}

    if event_type == "user.deleted":
        clerk_user_id = str(data.get("id") or "")
        if not clerk_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clerk webhook payload missing data.id.",
            )
        stmt = select(User).where(User.clerk_user_id == clerk_user_id)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is not None:
            user.is_active = False
            await audit_service.write(
                db,
                actor_user_id=None,
                action="user.deleted_via_clerk",
                target_type="user",
                target_id=user.id,
                diff={"clerk_user_id": clerk_user_id},
            )
        await db.commit()
        return {"status": "ok", "type": event_type}

    # Ignore every other event type (session.*, email.*, etc.).
    return {"status": "ignored", "type": event_type}
