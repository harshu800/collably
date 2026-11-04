"""IDOR coverage (FEAT-004).

Each test asserts that cross-tenant access returns ``404`` for private
resources (per design §4.2 — hide existence) rather than ``403``.
"""

from __future__ import annotations

import secrets

import pytest

from tests.helpers import (
    apply_and_accept,
    make_campaign,
    onboard_brand,
    onboard_creator,
    register,
    set_upi_payout_method,
)


@pytest.mark.asyncio
async def test_creator_cannot_view_another_creators_application(
    client, brand_user, creator_user
):
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    r = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/applications",
        headers=creator_user["auth_header"],
        json={},
    )
    assert r.status_code == 201
    app_id = r.json()["id"]

    other = await register(client, "creator")
    await onboard_creator(client, other)
    # Creator B tries to withdraw creator A's application → 404.
    r = await client.post(
        f"/api/v1/applications/{app_id}/withdraw",
        headers=other["auth_header"],
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_brand_cannot_edit_another_brands_campaign(
    client, brand_user
):
    await onboard_brand(client, brand_user)
    campaign = await make_campaign(client, brand_user)
    other_brand = await register(client, "brand")
    await onboard_brand(client, other_brand)
    r = await client.patch(
        f"/api/v1/campaigns/{campaign['id']}",
        headers=other_brand["auth_header"],
        json={"description": "evil"},
    )
    assert r.status_code == 404
    # And archive is also 404 for the non-owner.
    r = await client.post(
        f"/api/v1/campaigns/{campaign['id']}/archive",
        headers=other_brand["auth_header"],
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_creator_cannot_read_another_creators_payout_method(
    client, creator_user
):
    await onboard_creator(client, creator_user)
    await set_upi_payout_method(
        client, creator_user, vpa=f"first{secrets.token_hex(2)}@okbank"
    )
    other = await register(client, "creator")
    # The /me/payout-method endpoint is scoped by the current user, so the
    # other creator sees "no active method" (404) and never the first
    # creator's row.
    r = await client.get(
        "/api/v1/me/payout-method", headers=other["auth_header"]
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_brand_cannot_read_another_brands_collaboration(
    client, brand_user, creator_user
):
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    pair = await apply_and_accept(
        client,
        brand=brand_user,
        creator=creator_user,
        campaign_id=campaign["id"],
    )
    collab_id = pair["collaboration_id"]
    other_brand = await register(client, "brand")
    await onboard_brand(client, other_brand)
    r = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=other_brand["auth_header"]
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_creator_cannot_read_another_creators_collaboration(
    client, brand_user, creator_user
):
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    pair = await apply_and_accept(
        client,
        brand=brand_user,
        creator=creator_user,
        campaign_id=campaign["id"],
    )
    collab_id = pair["collaboration_id"]
    other = await register(client, "creator")
    await onboard_creator(client, other)
    r = await client.get(
        f"/api/v1/collaborations/{collab_id}",
        headers=other["auth_header"],
    )
    assert r.status_code == 404
