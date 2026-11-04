"""Dev-only mock payment endpoints.

Only reachable when ``settings.enable_mock_payment_endpoints`` is True — the
router is always mounted so that reloading the app for a flag flip is not
required, but each handler short-circuits to 404 when the flag is off.
Internally computes X-Mock-Signature over the generated flat body and
dispatches to the same :func:`payment_service.handle_webhook_event` the real
provider webhook path would hit, so the production code path is exercised by
tests and by local dev.
"""


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.payment import Payment
from app.models.payout import Payout
from app.providers.payment.mock import (
    SIGNATURE_HEADER,
    MockSandboxProvider,
    compute_signature,
)
from app.services import payment_service

router = APIRouter(tags=["mock-payments"], include_in_schema=False)


def _ensure_enabled() -> None:
    if not get_settings().enable_mock_payment_endpoints:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found."
        )


@router.post("/payments/mock/confirm/{order_id}")
async def confirm_mock_funding(
    order_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ensure_enabled()
    pay = (
        await db.execute(
            select(Payment).where(Payment.provider_order_id == order_id)
        )
    ).scalar_one_or_none()
    if pay is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found.",
        )
    body = MockSandboxProvider.build_funding_event_body(
        order_id=order_id,
        amount_paise=pay.amount_paise,
        currency=pay.currency,
        status="succeeded",
        event_type="funding.succeeded",
    )
    signature = compute_signature(body)
    result = await payment_service.handle_webhook_event(
        db,
        provider_name="mock",
        raw_body=body,
        headers={SIGNATURE_HEADER: signature},
    )
    await db.commit()
    return result


@router.post("/payments/mock/confirm-payout/{payout_id}")
async def confirm_mock_payout(
    payout_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ensure_enabled()
    payout = (
        await db.execute(
            select(Payout).where(Payout.provider_payout_id == payout_id)
        )
    ).scalar_one_or_none()
    if payout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payout not found.",
        )
    body = MockSandboxProvider.build_payout_event_body(
        payout_id=payout_id,
        amount_paise=payout.amount_paise,
        currency=payout.currency,
        status="paid",
        event_type="payout.paid",
    )
    signature = compute_signature(body)
    result = await payment_service.handle_webhook_event(
        db,
        provider_name="mock",
        raw_body=body,
        headers={SIGNATURE_HEADER: signature},
    )
    await db.commit()
    return result
