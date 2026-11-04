"""Webhook-before-order reconciliation on read (design §8.4)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.providers.payment.mock import SIGNATURE_HEADER, compute_signature
from tests.helpers import (
    apply_and_accept,
    make_campaign,
    onboard_brand,
    onboard_creator,
    set_upi_payout_method,
    sign_both_parties,
)


@pytest.mark.asyncio
async def test_webhook_before_payment_reconciles_on_read(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict, db
) -> None:
    """Scenario:

    1. Collaboration ready to fund (both signatures).
    2. Deliver a verified webhook for a provider_order_id BEFORE the Payment
       row exists — the event lands with processed_at=null.
    3. Create the Payment row via the normal funding flow using the same
       order_id (we patch the provider for determinism).
    4. GET /collaborations/{id}/funding runs the reconciliation path, applies
       the pending event, and the collaboration flips to funded.
    """

    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    await set_upi_payout_method(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    await sign_both_parties(
        client, collaboration_id=collab_id, brand=brand_user, creator=creator_user
    )

    # Patch the mock provider's create_order to return a deterministic id.
    pre_order_id = "mock_order_recon_123"
    body = json.dumps(
        {
            "event_id": "mock_evt_recon",
            "event_type": "funding.succeeded",
            "order_id": pre_order_id,
            "amount_paise": 100_000,
            "currency": "INR",
            "status": "succeeded",
            "occurred_at": "2026-10-28T00:00:00Z",
        },
        separators=(",", ":"),
    ).encode()
    sig = compute_signature(body)
    r = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: sig},
    )
    # The event is persisted but could not be applied yet — _DeferEventApplication
    # left processed_at NULL. The webhook endpoint still returns 200 "ok"
    # because the (idempotent) INSERT succeeded.
    assert r.status_code == 200

    # Now create the Payment row with the SAME provider_order_id via a
    # service-layer patch (monkey-patch the mock provider's create_order so
    # the subsequent funding call persists our well-known order_id).
    from unittest.mock import patch

    from app.providers.payment.base import OrderCreated

    def _deterministic_create_order(self, **kwargs):  # noqa: ANN001
        return OrderCreated(
            provider_order_id=pre_order_id,
            amount_paise=kwargs["amount_paise"],
            currency=kwargs["currency"],
            raw_response={},
        )

    with patch(
        "app.providers.payment.mock.MockSandboxProvider.create_order",
        _deterministic_create_order,
    ):
        f = await client.post(
            f"/api/v1/collaborations/{collab_id}/funding",
            headers=brand_user["auth_header"],
        )
    assert f.status_code == 200

    # The initial status is funding_initiated. GET triggers reconciliation.
    g = await client.get(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert g.json()["funding_status"] == "funding_confirmed"
    assert g.json()["collaboration_status"] == "funded"

    # The deferred event now has processed_at set — read via the ``db``
    # fixture which shares the test SAVEPOINT with every HTTP write above.
    from sqlalchemy import select

    from app.models.webhook_event import PaymentWebhookEvent

    ev = (
        await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider_event_id == "mock_evt_recon"
            )
        )
    ).scalar_one()
    assert ev.processed_at is not None
