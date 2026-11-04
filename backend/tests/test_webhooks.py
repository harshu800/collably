"""Direct webhook POST tests — signatures + idempotency."""

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
async def test_bad_signature_no_mutation(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
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
    f = await client.post(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    order_id = f.json()["provider_order_id"]

    body = json.dumps(
        {
            "event_id": "mock_evt_x",
            "event_type": "funding.succeeded",
            "order_id": order_id,
            "amount_paise": 100_000,
            "currency": "INR",
            "status": "succeeded",
            "occurred_at": "2026-10-28T00:00:00Z",
        },
        separators=(",", ":"),
    ).encode()
    r = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: "zzz"},
    )
    assert r.status_code == 401

    g = await client.get(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert g.json()["funding_status"] == "funding_initiated"


@pytest.mark.asyncio
async def test_duplicate_replay_returns_duplicate(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
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
    f = await client.post(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    order_id = f.json()["provider_order_id"]

    body = json.dumps(
        {
            "event_id": "mock_evt_replay",
            "event_type": "funding.succeeded",
            "order_id": order_id,
            "amount_paise": 100_000,
            "currency": "INR",
            "status": "succeeded",
            "occurred_at": "2026-10-28T00:00:00Z",
        },
        separators=(",", ":"),
    ).encode()
    sig = compute_signature(body)
    r1 = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: sig},
    )
    assert r1.json()["status"] == "ok"
    r2 = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: sig},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("amount_paise", "currency"),
    [(1, "INR"), (100_000, "USD")],
)
async def test_funding_webhook_mismatch_does_not_settle_payment(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
    amount_paise: int,
    currency: str,
) -> None:
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
    funding = await client.post(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    order_id = funding.json()["provider_order_id"]

    body = json.dumps(
        {
            "event_id": f"mock_evt_mismatch_{amount_paise}_{currency}",
            "event_type": "funding.succeeded",
            "order_id": order_id,
            "amount_paise": amount_paise,
            "currency": currency,
            "status": "succeeded",
            "occurred_at": "2026-10-28T00:00:00Z",
        },
        separators=(",", ":"),
    ).encode()
    response = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: compute_signature(body)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    status_response = await client.get(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert status_response.json()["funding_status"] == "funding_initiated"


@pytest.mark.asyncio
async def test_unrecognized_funding_event_does_not_settle_payment(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
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
    funding = await client.post(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    body = json.dumps(
        {
            "event_id": "mock_evt_unrecognized",
            "event_type": "funding.processing",
            "order_id": funding.json()["provider_order_id"],
            "amount_paise": 100_000,
            "currency": "INR",
            "status": "processing",
            "occurred_at": "2026-10-28T00:00:00Z",
        },
        separators=(",", ":"),
    ).encode()
    response = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: compute_signature(body)},
    )

    assert response.status_code == 200
    status_response = await client.get(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert status_response.json()["funding_status"] == "funding_initiated"


@pytest.mark.asyncio
async def test_webhook_route_provider_must_match_configured_provider(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/webhooks/payments/razorpay",
        content=b"{}",
        headers={},
    )

    assert response.status_code == 401
