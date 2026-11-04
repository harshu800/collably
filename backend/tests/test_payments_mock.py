"""Mock-funding happy path + bad-signature + duplicate-event idempotency."""

from __future__ import annotations

import httpx
import pytest

from tests.helpers import (
    apply_and_accept,
    make_campaign,
    onboard_brand,
    onboard_creator,
    set_upi_payout_method,
    sign_both_parties,
)


@pytest.mark.asyncio
async def test_create_order_marks_initiated(
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

    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "initiated"
    assert body["provider"] == "mock"
    assert body["provider_order_id"].startswith("mock_order_")

    g = await client.get(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert g.json()["funding_status"] == "funding_initiated"
    assert g.json()["collaboration_status"] == "funding_initiated"


@pytest.mark.asyncio
async def test_mock_confirm_good_signature_moves_to_funded(
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

    c = await client.post(f"/api/v1/payments/mock/confirm/{order_id}")
    assert c.status_code == 200
    assert c.json()["status"] == "ok"

    g = await client.get(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert g.json()["funding_status"] == "funding_confirmed"
    assert g.json()["collaboration_status"] == "funded"


@pytest.mark.asyncio
async def test_bad_signature_returns_401_state_unchanged(
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
    # Send a direct webhook with wrong signature.
    import json

    body = json.dumps(
        {
            "event_id": "mock_evt_bad",
            "event_type": "funding.succeeded",
            "order_id": order_id,
            "amount_paise": 100_000,
            "currency": "INR",
            "status": "succeeded",
            "occurred_at": "2026-10-28T00:00:00Z",
        }
    ).encode()
    r = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={"X-Mock-Signature": "deadbeef"},
    )
    assert r.status_code == 401
    g = await client.get(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert g.json()["funding_status"] == "funding_initiated"


@pytest.mark.asyncio
async def test_duplicate_event_is_idempotent(
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

    # Craft a fixed event id so the second replay matches the first.
    import json

    from app.providers.payment.mock import SIGNATURE_HEADER, compute_signature

    body = json.dumps(
        {
            "event_id": "mock_evt_fixed_123",
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
    assert r1.status_code == 200
    assert r1.json()["status"] == "ok"
    r2 = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: sig},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"
