"""Profile tests — onboarding happy path, GSTIN validation, public strip."""

from __future__ import annotations

import httpx
import pytest

VALID_GSTIN = "27AAPFU0939F1ZV"


@pytest.mark.asyncio
async def test_creator_onboarding_flips_is_onboarded(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    """A creator who fills in the required fields becomes is_onboarded=True."""

    headers = creator_user["auth_header"]

    # Initially the GET auto-creates an empty profile; is_onboarded must be False.
    r0 = await client.get("/api/v1/me/profile", headers=headers)
    assert r0.status_code == 200, r0.text
    assert r0.json()["role"] == "creator"
    assert r0.json()["creator"]["is_onboarded"] is False

    patch_body = {
        "display_name": "Priya S",
        "bio": "UGC creator in beauty + skincare.",
        "city": "Mumbai",
        "state": "Maharashtra",
        "does_ugc": True,
        "niches": ["beauty", "skincare"],
        "content_types": ["unboxing", "demo"],
        "starting_rate_paise": 500_000,
    }
    r1 = await client.patch("/api/v1/me/profile", json=patch_body, headers=headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["creator"]["is_onboarded"] is True

    r2 = await client.post(
        "/api/v1/me/profile/complete-onboarding",
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["is_onboarded"] is True
    assert r2.json()["missing_fields"] == []


@pytest.mark.asyncio
async def test_creator_without_capability_flag_misses_onboarding(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    headers = creator_user["auth_header"]
    r = await client.patch(
        "/api/v1/me/profile",
        json={
            "display_name": "No-capability Creator",
            "bio": "n/a",
            "city": "Delhi",
            "state": "Delhi",
        },
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["creator"]["is_onboarded"] is False
    r2 = await client.post(
        "/api/v1/me/profile/complete-onboarding", headers=headers
    )
    assert r2.status_code == 200
    assert "does_ugc_or_does_influencer" in r2.json()["missing_fields"]


@pytest.mark.asyncio
async def test_brand_gstin_valid_and_invalid(
    client: httpx.AsyncClient,
    brand_user: dict,
) -> None:
    headers = brand_user["auth_header"]

    # Garbage GSTIN → 422.
    bad = await client.patch(
        "/api/v1/me/profile",
        json={"gstin": "notagstinvalue"},  # 15 chars but wrong format
        headers=headers,
    )
    assert bad.status_code == 422, bad.text

    # Valid GSTIN survives round-trip (and uppercases).
    ok = await client.patch(
        "/api/v1/me/profile",
        json={
            "company_name": "Example D2C Pvt Ltd",
            "industry": "beauty",
            "contact_name": "Rhea",
            "contact_email": "rhea@example.com",
            "gstin": VALID_GSTIN.lower(),
        },
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["brand"]["gstin"] == VALID_GSTIN
    assert ok.json()["brand"]["is_onboarded"] is True


@pytest.mark.asyncio
async def test_public_creator_detail_strips_contact_email(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    headers = creator_user["auth_header"]
    patch_body = {
        "display_name": "Public Creator",
        "bio": "hi",
        "city": "Bengaluru",
        "state": "Karnataka",
        "does_ugc": True,
    }
    r = await client.patch("/api/v1/me/profile", json=patch_body, headers=headers)
    assert r.status_code == 200
    creator_id = r.json()["creator"]["id"]

    # Public endpoint — no auth; must not leak contact_email or any email at all.
    pub = await client.get(f"/api/v1/creators/{creator_id}")
    assert pub.status_code == 200, pub.text
    body = pub.json()
    assert "contact_email" not in body
    assert "email" not in body
    assert "user_id" not in body
    # Shape stays discoverable.
    assert body["display_name"] == "Public Creator"


@pytest.mark.asyncio
async def test_get_brand_requires_self_or_admin(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    # Owner can see their own brand profile.
    me = await client.get("/api/v1/me/profile", headers=brand_user["auth_header"])
    assert me.status_code == 200
    brand_id = me.json()["brand"]["id"]

    # Another user (a creator) sees 404.
    foreign = await client.get(
        f"/api/v1/brands/{brand_id}", headers=creator_user["auth_header"]
    )
    assert foreign.status_code == 404

    # Owner succeeds.
    mine = await client.get(
        f"/api/v1/brands/{brand_id}", headers=brand_user["auth_header"]
    )
    assert mine.status_code == 200
