"""Webhook routes — raw body read + delegated to payment_service."""


from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import payment_service

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/payments/{provider}")
async def receive_payment_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # IMPORTANT: read the raw body BEFORE JSON parsing so the signature is
    # computed over the exact bytes.
    body = await request.body()
    headers = dict(request.headers)
    result = await payment_service.handle_webhook_event(
        db,
        provider_name=provider,
        raw_body=body,
        headers=headers,
    )
    await db.commit()
    return result
