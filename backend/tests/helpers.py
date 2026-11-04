"""Shared test setup helpers."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from tests.conftest import _register_user


async def register(
    client: httpx.AsyncClient,
    role: str,
    *,
    email: str | None = None,
) -> dict:
    return await _register_user(client, role, email=email)


async def onboard_brand(client: httpx.AsyncClient, brand: dict) -> None:
    r = await client.patch(
        "/api/v1/me/profile",
        json={
            "company_name": "Example D2C",
            "industry": "beauty",
            "contact_name": "Owner",
            "contact_email": "owner@example.com",
        },
        headers=brand["auth_header"],
    )
    assert r.status_code == 200, r.text


async def onboard_creator(
    client: httpx.AsyncClient,
    creator: dict,
    *,
    does_ugc: bool = True,
    does_influencer: bool = False,
) -> dict:
    r = await client.patch(
        "/api/v1/me/profile",
        json={
            "display_name": "Creator",
            "bio": "bio",
            "city": "Mumbai",
            "state": "MH",
            "does_ugc": does_ugc,
            "does_influencer": does_influencer,
            "niches": ["beauty"],
        },
        headers=creator["auth_header"],
    )
    assert r.status_code == 200, r.text
    return r.json()["creator"]


async def make_campaign(
    client: httpx.AsyncClient,
    brand: dict,
    *,
    revision_limit: int = 1,
    spec_items: int = 1,
    number_of_creators: int = 1,
    budget_paise: int = 100_000,
) -> dict:
    body = {
        "title": "Test Campaign",
        "type": "ugc",
        "budget_paise": budget_paise,
        "number_of_creators": number_of_creators,
        "deliverable_spec": [
            {"kind": "file", "description": f"item-{i}", "quantity": 1}
            for i in range(spec_items)
        ],
        "revision_limit": revision_limit,
        "usage_rights": "paid media",
    }
    r = await client.post(
        "/api/v1/campaigns", json=body, headers=brand["auth_header"]
    )
    assert r.status_code == 201, r.text
    return r.json()


async def apply_and_accept(
    client: httpx.AsyncClient,
    *,
    brand: dict,
    creator: dict,
    campaign_id: str,
    price_paise: int | None = None,
) -> dict:
    payload: dict[str, Any] = {}
    if price_paise is not None:
        payload["proposed_price_paise"] = price_paise
    s = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json=payload,
        headers=creator["auth_header"],
    )
    assert s.status_code == 201, s.text
    app_id = s.json()["id"]
    a = await client.post(
        f"/api/v1/applications/{app_id}/accept",
        headers=brand["auth_header"],
    )
    assert a.status_code == 200, a.text
    collaboration_id = a.json()["collaboration_id"]
    assert collaboration_id is not None
    return {"application_id": app_id, "collaboration_id": collaboration_id}


async def sign_both_parties(
    client: httpx.AsyncClient,
    *,
    collaboration_id: str,
    brand: dict,
    creator: dict,
) -> dict:
    ar = await client.get(
        f"/api/v1/collaborations/{collaboration_id}/agreement",
        headers=brand["auth_header"],
    )
    assert ar.status_code == 200, ar.text
    agreement_id = ar.json()["id"]
    r1 = await client.post(
        f"/api/v1/agreements/{agreement_id}/sign",
        headers=brand["auth_header"],
    )
    assert r1.status_code == 200, r1.text
    r2 = await client.post(
        f"/api/v1/agreements/{agreement_id}/sign",
        headers=creator["auth_header"],
    )
    assert r2.status_code == 200, r2.text
    return r2.json()


async def set_upi_payout_method(
    client: httpx.AsyncClient, creator: dict, *, vpa: str = "user@okbank"
) -> dict:
    r = await client.put(
        "/api/v1/me/payout-method",
        json={
            "method": "upi",
            "holder_name": "Creator Holder",
            "upi_vpa": vpa,
        },
        headers=creator["auth_header"],
    )
    assert r.status_code == 200, r.text
    return r.json()


async def fund_and_confirm(
    client: httpx.AsyncClient,
    *,
    collaboration_id: str,
    brand: dict,
) -> dict:
    """Initiate funding then hit the mock-confirm endpoint."""

    f = await client.post(
        f"/api/v1/collaborations/{collaboration_id}/funding",
        headers=brand["auth_header"],
    )
    assert f.status_code == 200, f.text
    order_id = f.json()["provider_order_id"]
    c = await client.post(f"/api/v1/payments/mock/confirm/{order_id}")
    assert c.status_code == 200, c.text
    return f.json()


def _unused_uuid() -> str:
    return str(uuid.uuid4())
