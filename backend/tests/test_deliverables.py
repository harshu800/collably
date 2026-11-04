"""Deliverable submit/approve/revision gates + revision_count atomicity."""

from __future__ import annotations

import io

import httpx
import pytest

from tests.helpers import (
    apply_and_accept,
    fund_and_confirm,
    make_campaign,
    onboard_brand,
    onboard_creator,
    set_upi_payout_method,
    sign_both_parties,
)

# ---------------------------------------------------------------------------
# Fixtures / mini-helpers
# ---------------------------------------------------------------------------


_PNG_BYTES = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452"
    "0000000100000001"
    "08020000009077534D000000016352"
    "4742008D"
) + b"\x00" * 128


async def _upload_png(client: httpx.AsyncClient, creator: dict) -> str:
    # A minimal real-ish PNG for libmagic — generated test byte string
    # (reads as image/png via byte-signature table and libmagic).
    png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"file": ("x.png", io.BytesIO(png), "image/png")}
    r = await client.post(
        "/api/v1/files", files=files, headers=creator["auth_header"]
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _agreement_id(client: httpx.AsyncClient, collab_id: str, auth: dict) -> str:
    r = await client.get(
        f"/api/v1/collaborations/{collab_id}/agreement",
        headers=auth["auth_header"],
    )
    assert r.status_code == 200
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_before_funded_rejects_with_funding_reason(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    await sign_both_parties(
        client, collaboration_id=collab_id, brand=brand_user, creator=creator_user
    )

    file_id = await _upload_png(client, creator_user)
    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/deliverables",
        json={"spec_index": 0, "kind": "file", "file_id": file_id},
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 409
    assert r.json()["error_code"] == "work_not_unlocked"
    assert r.json()["details"]["reason"] == "funding"


@pytest.mark.asyncio
async def test_submit_after_v2_without_signatures_rejects_with_agreement_reason(
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
    await fund_and_confirm(client, collaboration_id=collab_id, brand=brand_user)

    # Supersede v1 — v2 has no signatures.
    sup = await client.post(
        f"/api/v1/collaborations/{collab_id}/agreements",
        json={"scope": "v2"},
        headers=brand_user["auth_header"],
    )
    assert sup.status_code == 201

    file_id = await _upload_png(client, creator_user)
    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/deliverables",
        json={"spec_index": 0, "kind": "file", "file_id": file_id},
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 409
    assert r.json()["details"]["reason"] == "agreement"


@pytest.mark.asyncio
async def test_full_submit_approve_flow(
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
    await fund_and_confirm(client, collaboration_id=collab_id, brand=brand_user)

    file_id = await _upload_png(client, creator_user)
    s = await client.post(
        f"/api/v1/collaborations/{collab_id}/deliverables",
        json={"spec_index": 0, "kind": "file", "file_id": file_id},
        headers=creator_user["auth_header"],
    )
    assert s.status_code == 201
    deliverable_id = s.json()["id"]

    # First submission → in_progress; sole spec item covered → in_review.
    collab = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=brand_user["auth_header"]
    )
    assert collab.json()["status"] == "in_review"

    a = await client.post(
        f"/api/v1/deliverables/{deliverable_id}/approve",
        headers=brand_user["auth_header"],
    )
    assert a.status_code == 200
    assert a.json()["collaboration_status"] == "approved"
    assert a.json()["payout"]["status"] == "pending"


@pytest.mark.asyncio
async def test_request_revision_atomic_increment_and_insert(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict, db
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    await set_upi_payout_method(client, creator_user)
    campaign = await make_campaign(client, brand_user, revision_limit=1)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    await sign_both_parties(
        client, collaboration_id=collab_id, brand=brand_user, creator=creator_user
    )
    await fund_and_confirm(client, collaboration_id=collab_id, brand=brand_user)

    file_id = await _upload_png(client, creator_user)
    s = await client.post(
        f"/api/v1/collaborations/{collab_id}/deliverables",
        json={"spec_index": 0, "kind": "file", "file_id": file_id},
        headers=creator_user["auth_header"],
    )
    deliverable_id = s.json()["id"]

    r = await client.post(
        f"/api/v1/deliverables/{deliverable_id}/request-revision",
        json={"note": "please redo"},
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "revision_requested"
    assert body["revision_count"] == 1

    # DB-level check — a DeliverableRevision row exists.
    from sqlalchemy import select

    from app.models.revision import DeliverableRevision

    rows = (
        await db.execute(
            select(DeliverableRevision).where(
                DeliverableRevision.deliverable_id == body["id"]
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].note == "please redo"


@pytest.mark.asyncio
async def test_request_revision_over_limit_rejects(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    await set_upi_payout_method(client, creator_user)
    campaign = await make_campaign(client, brand_user, revision_limit=1)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    await sign_both_parties(
        client, collaboration_id=collab_id, brand=brand_user, creator=creator_user
    )
    await fund_and_confirm(client, collaboration_id=collab_id, brand=brand_user)
    file_id = await _upload_png(client, creator_user)
    s = await client.post(
        f"/api/v1/collaborations/{collab_id}/deliverables",
        json={"spec_index": 0, "kind": "file", "file_id": file_id},
        headers=creator_user["auth_header"],
    )
    deliverable_id = s.json()["id"]

    r1 = await client.post(
        f"/api/v1/deliverables/{deliverable_id}/request-revision",
        json={"note": "one"},
        headers=brand_user["auth_header"],
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/v1/deliverables/{deliverable_id}/request-revision",
        json={"note": "two"},
        headers=brand_user["auth_header"],
    )
    assert r2.status_code == 409
    assert r2.json()["error_code"] == "revision_limit_reached"


@pytest.mark.asyncio
async def test_revision_count_preserved_across_supersession(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    """A deliverable at-cap under a lowered v2 limit cannot be revised again."""

    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    await set_upi_payout_method(client, creator_user)
    campaign = await make_campaign(client, brand_user, revision_limit=2)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    await sign_both_parties(
        client, collaboration_id=collab_id, brand=brand_user, creator=creator_user
    )
    await fund_and_confirm(client, collaboration_id=collab_id, brand=brand_user)
    file_id = await _upload_png(client, creator_user)
    s = await client.post(
        f"/api/v1/collaborations/{collab_id}/deliverables",
        json={"spec_index": 0, "kind": "file", "file_id": file_id},
        headers=creator_user["auth_header"],
    )
    deliverable_id = s.json()["id"]

    r1 = await client.post(
        f"/api/v1/deliverables/{deliverable_id}/request-revision",
        json={"note": "one"},
        headers=brand_user["auth_header"],
    )
    assert r1.status_code == 200
    assert r1.json()["revision_count"] == 1

    # Supersede with revision_limit=1 (which equals current count — at-cap).
    sup = await client.post(
        f"/api/v1/collaborations/{collab_id}/agreements",
        json={"revision_limit": 1},
        headers=brand_user["auth_header"],
    )
    assert sup.status_code == 201
    v2_id = sup.json()["id"]
    # Sign v2.
    await client.post(
        f"/api/v1/agreements/{v2_id}/sign", headers=brand_user["auth_header"]
    )
    await client.post(
        f"/api/v1/agreements/{v2_id}/sign", headers=creator_user["auth_header"]
    )

    # Any further revision request → over limit (1 + 1 > 1).
    r2 = await client.post(
        f"/api/v1/deliverables/{deliverable_id}/request-revision",
        json={"note": "nope"},
        headers=brand_user["auth_header"],
    )
    assert r2.status_code == 409
    assert r2.json()["error_code"] == "revision_limit_reached"
