"""Collaboration listing + per-id read tests."""

from __future__ import annotations

import httpx
import pytest

from tests.helpers import (
    apply_and_accept,
    make_campaign,
    onboard_brand,
    onboard_creator,
    register,
)


@pytest.mark.asyncio
async def test_accept_creates_pending_agreement_collaboration(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    accepted = await apply_and_accept(
        client,
        brand=brand_user,
        creator=creator_user,
        campaign_id=campaign["id"],
        price_paise=50_000,
    )
    r = await client.get(
        f"/api/v1/collaborations/{accepted['collaboration_id']}",
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending_agreement"
    assert body["funding_status"] == "not_funded"
    assert body["payout_status"] == "none"
    assert body["price_paise"] == 50_000


@pytest.mark.asyncio
async def test_list_role_scoped(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )

    other_brand = await register(client, "brand")
    await onboard_brand(client, other_brand)
    other_creator = await register(client, "creator")
    await onboard_creator(client, other_creator)
    camp2 = await make_campaign(client, other_brand)
    await apply_and_accept(
        client, brand=other_brand, creator=other_creator, campaign_id=camp2["id"]
    )

    brand_list = await client.get(
        "/api/v1/collaborations", headers=brand_user["auth_header"]
    )
    assert brand_list.status_code == 200
    brand_ids = {c["id"] for c in brand_list.json()}
    other_list = await client.get(
        "/api/v1/collaborations", headers=other_brand["auth_header"]
    )
    other_ids = {c["id"] for c in other_list.json()}
    assert brand_ids.isdisjoint(other_ids)

    creator_list = await client.get(
        "/api/v1/collaborations", headers=creator_user["auth_header"]
    )
    assert creator_list.status_code == 200
    assert len(creator_list.json()) >= 1


@pytest.mark.asyncio
async def test_non_participant_gets_404(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    outsider = await register(client, "creator")
    await onboard_creator(client, outsider)
    r = await client.get(
        f"/api/v1/collaborations/{accepted['collaboration_id']}",
        headers=outsider["auth_header"],
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_sees_any_collaboration(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
    admin_user: dict,
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    r = await client.get(
        f"/api/v1/collaborations/{accepted['collaboration_id']}",
        headers=admin_user["auth_header"],
    )
    assert r.status_code == 200
