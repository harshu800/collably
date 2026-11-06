"""Profile tests — onboarding happy path, GSTIN validation, public strip."""

from __future__ import annotations

import httpx
import pytest

VALID_GSTIN = "27AAPFU0939F1ZV"
JPEG_HEADER = b"\xff\xd8\xff\xe0" + b"\x00" * 20
PDF_HEADER = b"%PDF-1.4\n" + b"\x00" * 20


def _jpeg_bytes(length: int = 1024) -> bytes:
    return JPEG_HEADER + b"\x00" * max(0, length - len(JPEG_HEADER))


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


@pytest.mark.asyncio
async def test_creator_profile_files_socials_and_portfolio_persist(
    client: httpx.AsyncClient,
    creator_user: dict,
    second_creator_user: dict,
) -> None:
    headers = creator_user["auth_header"]
    uploaded = await client.post(
        "/api/v1/files/profile-image",
        files={"file": ("creator.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    updated = await client.patch(
        "/api/v1/me/profile",
        json={
            "avatar_file_id": file_id,
            "portfolio_links": [
                {
                    "label": "Portfolio sample",
                    "url": f"https://api.example.com/api/v1/files/public/{file_id}",
                }
            ],
            "social_handles": [
                {
                    "platform": "Instagram",
                    "handle": "@creator",
                    "unverified": True,
                },
                {
                    "platform": "YouTube",
                    "handle": "https://youtube.com/@creator",
                    "unverified": True,
                },
            ],
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["creator"]["avatar_file_id"] == file_id

    reloaded = await client.get("/api/v1/me/profile", headers=headers)
    creator = reloaded.json()["creator"]
    assert creator["avatar_file_id"] == file_id
    assert creator["portfolio_links"][0]["label"] == "Portfolio sample"
    assert creator["social_handles"][1]["handle"] == "https://youtube.com/@creator"

    foreign_patch = await client.patch(
        "/api/v1/me/profile",
        json={"avatar_file_id": file_id},
        headers=second_creator_user["auth_header"],
    )
    assert foreign_patch.status_code == 422, foreign_patch.text


@pytest.mark.asyncio
async def test_creator_portfolio_upload_is_public_and_attached_to_profile(
    client: httpx.AsyncClient,
    creator_user: dict,
) -> None:
    headers = creator_user["auth_header"]
    uploaded = await client.post(
        "/api/v1/files/creator-portfolio",
        files={"file": ("sample.pdf", PDF_HEADER + b"portfolio", "application/pdf")},
        headers=headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    saved = await client.patch(
        "/api/v1/me/profile",
        json={
            "portfolio_links": [
                {
                    "label": "PDF portfolio",
                    "url": f"https://api.example.com/api/v1/files/public/{file_id}",
                }
            ]
        },
        headers=headers,
    )
    assert saved.status_code == 200, saved.text

    public_file = await client.get(f"/api/v1/files/public/{file_id}")
    assert public_file.status_code == 200
    assert public_file.content == PDF_HEADER + b"portfolio"
    reloaded = await client.get("/api/v1/me/profile", headers=headers)
    assert reloaded.json()["creator"]["portfolio_links"][0]["url"].endswith(file_id)


@pytest.mark.asyncio
async def test_brand_profile_public_fields_persist_without_private_data(
    client: httpx.AsyncClient,
    brand_user: dict,
) -> None:
    brand_headers = brand_user["auth_header"]
    uploaded = await client.post(
        "/api/v1/files/profile-image",
        files={"file": ("brand.jpg", _jpeg_bytes(), "image/jpeg")},
        headers=brand_headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    file_id = uploaded.json()["id"]

    updated = await client.patch(
        "/api/v1/me/profile",
        json={
            "company_name": "Good Goods",
            "industry": "Beauty",
            "contact_name": "Asha Rao",
            "contact_email": "asha@example.com",
            "logo_file_id": file_id,
            "city": "Mumbai",
            "state": "Maharashtra",
            "description": "Independent skincare brand",
            "website": "https://example.com",
            "social_handles": [
                {
                    "platform": "Instagram",
                    "handle": "@goodgoods",
                    "unverified": True,
                }
            ],
            "billing_address": {
                "line1": "Private billing address",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal_code": "400001",
                "country": "IN",
            },
        },
        headers=brand_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["brand"]["logo_file_id"] == file_id

    reloaded = await client.get("/api/v1/me/profile", headers=brand_headers)
    assert reloaded.json()["brand"]["city"] == "Mumbai"
    assert reloaded.json()["brand"]["social_handles"][0]["handle"] == "@goodgoods"

    brand_id = reloaded.json()["brand"]["id"]
    public = await client.get(f"/api/v1/brands/{brand_id}/public")
    assert public.status_code == 200, public.text
    public_profile = public.json()
    assert public_profile["logo_file_id"] == file_id
    assert public_profile["city"] == "Mumbai"
    assert "contact_email" not in public_profile
    assert "billing_address" not in public_profile
