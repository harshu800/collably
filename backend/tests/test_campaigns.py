"""Campaign tests — create, filter, pagination, material-edit lock."""

from __future__ import annotations

import httpx
import pytest


async def _onboard_brand(client: httpx.AsyncClient, brand_user: dict) -> None:
    r = await client.patch(
        "/api/v1/me/profile",
        json={
            "company_name": "Example D2C",
            "industry": "beauty",
            "contact_name": "Brand Owner",
            "contact_email": "owner@example.com",
        },
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 200, r.text


async def _onboard_creator(
    client: httpx.AsyncClient,
    creator_user: dict,
    *,
    does_ugc: bool = True,
    does_influencer: bool = False,
    niches: list[str] | None = None,
) -> dict:
    r = await client.patch(
        "/api/v1/me/profile",
        json={
            "display_name": "C",
            "bio": "b",
            "city": "Mumbai",
            "state": "MH",
            "does_ugc": does_ugc,
            "does_influencer": does_influencer,
            "niches": niches or ["beauty"],
        },
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 200, r.text
    return r.json()["creator"]


def _campaign_body(**overrides) -> dict:
    body = {
        "title": "Beauty UGC Winter",
        "description": "Unboxing + demo videos.",
        "type": "ugc",
        "niches": ["beauty", "skincare"],
        "platforms": ["instagram"],
        "languages": ["en"],
        "locations": ["Mumbai"],
        "budget_paise": 500_000,
        "number_of_creators": 2,
        "deliverable_spec": [
            {"kind": "file", "description": "Unboxing video", "quantity": 1},
        ],
        "revision_limit": 2,
        "usage_rights": "Perpetual, paid media.",
        "disclosure_required": True,
    }
    body.update(overrides)
    return body


@pytest.mark.asyncio
async def test_brand_creates_campaign(
    client: httpx.AsyncClient,
    brand_user: dict,
) -> None:
    await _onboard_brand(client, brand_user)
    r = await client.post(
        "/api/v1/campaigns",
        json=_campaign_body(),
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "open"
    assert r.json()["type"] == "ugc"
    assert r.json()["budget_paise"] == 500_000


@pytest.mark.asyncio
async def test_creator_cannot_create_campaign(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    r = await client.post(
        "/api/v1/campaigns",
        json=_campaign_body(),
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_public_list_filters_by_type_and_niche(
    client: httpx.AsyncClient,
    brand_user: dict,
) -> None:
    await _onboard_brand(client, brand_user)
    await client.post(
        "/api/v1/campaigns",
        json=_campaign_body(title="UGC Beauty", type="ugc", niches=["beauty"]),
        headers=brand_user["auth_header"],
    )
    await client.post(
        "/api/v1/campaigns",
        json=_campaign_body(
            title="Influencer Finance",
            type="influencer",
            niches=["finance"],
        ),
        headers=brand_user["auth_header"],
    )

    only_ugc = await client.get("/api/v1/campaigns", params={"type": "ugc"})
    assert only_ugc.status_code == 200
    titles = [c["title"] for c in only_ugc.json()["items"]]
    assert "UGC Beauty" in titles
    assert "Influencer Finance" not in titles

    only_beauty = await client.get("/api/v1/campaigns", params={"niche": "beauty"})
    assert only_beauty.status_code == 200
    assert all("beauty" in c["niches"] for c in only_beauty.json()["items"])


@pytest.mark.asyncio
async def test_pagination_bounds_rejected_422(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/campaigns", params={"page_size": 500})
    assert r.status_code == 422

    r2 = await client.get("/api/v1/campaigns", params={"page": 0})
    assert r2.status_code == 422


@pytest.mark.asyncio
async def test_material_edit_after_application_is_locked(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await _onboard_brand(client, brand_user)
    await _onboard_creator(client, creator_user, does_ugc=True)
    created = await client.post(
        "/api/v1/campaigns",
        json=_campaign_body(number_of_creators=2),
        headers=brand_user["auth_header"],
    )
    assert created.status_code == 201, created.text
    campaign_id = created.json()["id"]

    # Submit an application so the campaign is now "locked" on material fields.
    app = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={"pitch": "Me me me"},
        headers=creator_user["auth_header"],
    )
    assert app.status_code == 201, app.text

    # Non-material change still works.
    ok = await client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={"description": "updated copy"},
        headers=brand_user["auth_header"],
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["description"] == "updated copy"

    # Material change refused with 409 campaign_locked + offending fields list.
    locked = await client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={"title": "New Title", "budget_paise": 999},
        headers=brand_user["auth_header"],
    )
    assert locked.status_code == 409, locked.text
    body = locked.json()
    assert body["error_code"] == "campaign_locked"
    assert set(body["details"]["offending_fields"]) == {"title", "budget_paise"}

    # number_of_creators upward OK; downward refused.
    up = await client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={"number_of_creators": 5},
        headers=brand_user["auth_header"],
    )
    assert up.status_code == 200, up.text
    down = await client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={"number_of_creators": 1},
        headers=brand_user["auth_header"],
    )
    assert down.status_code == 409
    assert down.json()["error_code"] == "campaign_locked"
    assert "number_of_creators" in down.json()["details"]["offending_fields"]


@pytest.mark.asyncio
async def test_number_of_creators_downward_without_applications_is_still_blocked(
    client: httpx.AsyncClient,
    brand_user: dict,
) -> None:
    """`number_of_creators` is upward-only regardless of applications."""

    await _onboard_brand(client, brand_user)
    created = await client.post(
        "/api/v1/campaigns",
        json=_campaign_body(number_of_creators=5),
        headers=brand_user["auth_header"],
    )
    campaign_id = created.json()["id"]
    r = await client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={"number_of_creators": 2},
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 409, r.text
    assert r.json()["error_code"] == "campaign_locked"
