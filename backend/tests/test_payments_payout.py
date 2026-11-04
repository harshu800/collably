"""Payout initiation flows + retry endpoint + non-creator 404."""

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
    register,
    set_upi_payout_method,
    sign_both_parties,
)

PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def _upload_png(client: httpx.AsyncClient, creator: dict) -> str:
    files = {"file": ("x.png", io.BytesIO(PNG), "image/png")}
    r = await client.post(
        "/api/v1/files", files=files, headers=creator["auth_header"]
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _run_to_approved(
    client: httpx.AsyncClient,
    brand: dict,
    creator: dict,
    *,
    set_method: bool,
) -> dict:
    await onboard_brand(client, brand)
    await onboard_creator(client, creator)
    if set_method:
        await set_upi_payout_method(client, creator)
    campaign = await make_campaign(client, brand)
    accepted = await apply_and_accept(
        client, brand=brand, creator=creator, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    await sign_both_parties(
        client, collaboration_id=collab_id, brand=brand, creator=creator
    )
    await fund_and_confirm(client, collaboration_id=collab_id, brand=brand)
    file_id = await _upload_png(client, creator)
    s = await client.post(
        f"/api/v1/collaborations/{collab_id}/deliverables",
        json={"spec_index": 0, "kind": "file", "file_id": file_id},
        headers=creator["auth_header"],
    )
    assert s.status_code == 201
    deliverable_id = s.json()["id"]
    a = await client.post(
        f"/api/v1/deliverables/{deliverable_id}/approve",
        headers=brand["auth_header"],
    )
    assert a.status_code == 200
    return {"collab_id": collab_id, "approve_response": a.json()}


@pytest.mark.asyncio
async def test_approval_without_method_marks_pending_method(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    out = await _run_to_approved(client, brand_user, creator_user, set_method=False)
    assert out["approve_response"]["collaboration_status"] == "approved"
    assert out["approve_response"]["payout"]["status"] == "pending_method"
    # No Payout row yet — GET returns 404.
    r = await client.get(
        f"/api/v1/collaborations/{out['collab_id']}/payouts",
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_set_method_then_retry_creates_payout(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    out = await _run_to_approved(client, brand_user, creator_user, set_method=False)
    collab_id = out["collab_id"]

    await set_upi_payout_method(client, creator_user)

    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/payouts",
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["beneficiary_snapshot"]["method"] == "upi"
    assert "upi_vpa_masked" in body["beneficiary_snapshot"]


@pytest.mark.asyncio
async def test_live_provider_blocks_unverified_payout_method(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    from app.services import payment_service

    out = await _run_to_approved(client, brand_user, creator_user, set_method=False)
    collab_id = out["collab_id"]
    await set_upi_payout_method(client, creator_user)

    class ProviderMustNotBeCalled:
        name = "razorpay"

        def create_payout(self, **_kwargs):
            pytest.fail("unverified payout method must not reach payment provider")

    monkeypatch.setattr(
        payment_service,
        "get_settings",
        lambda: SimpleNamespace(payment_provider="razorpay"),
    )
    monkeypatch.setattr(
        payment_service,
        "get_payment_provider",
        lambda _settings: ProviderMustNotBeCalled(),
    )

    response = await client.post(
        f"/api/v1/collaborations/{collab_id}/payouts",
        headers=creator_user["auth_header"],
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "payout_method_not_verified"


@pytest.mark.asyncio
async def test_approval_with_method_creates_payout_inline(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    out = await _run_to_approved(client, brand_user, creator_user, set_method=True)
    assert out["approve_response"]["payout"]["status"] == "pending"
    r = await client.get(
        f"/api/v1/collaborations/{out['collab_id']}/payouts",
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_retry_before_approval_is_409(
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
    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/payouts",
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 409
    assert r.json()["error_code"] == "work_not_approved"


@pytest.mark.asyncio
async def test_retry_by_non_creator_is_404(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    out = await _run_to_approved(client, brand_user, creator_user, set_method=False)
    collab_id = out["collab_id"]
    # Brand attempts to call the creator-only retry endpoint → 404.
    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/payouts",
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_mock_confirm_payout_marks_paid_and_completes(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    out = await _run_to_approved(client, brand_user, creator_user, set_method=True)
    collab_id = out["collab_id"]
    pr = await client.get(
        f"/api/v1/collaborations/{collab_id}/payouts",
        headers=brand_user["auth_header"],
    )
    payout_id = pr.json()["provider_payout_id"]
    assert payout_id is not None
    c = await client.post(f"/api/v1/payments/mock/confirm-payout/{payout_id}")
    assert c.status_code == 200
    pr2 = await client.get(
        f"/api/v1/collaborations/{collab_id}/payouts",
        headers=brand_user["auth_header"],
    )
    assert pr2.json()["status"] == "paid"
    collab = await client.get(
        f"/api/v1/collaborations/{collab_id}",
        headers=brand_user["auth_header"],
    )
    assert collab.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_second_payout_rejects_as_already_exists(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    out = await _run_to_approved(client, brand_user, creator_user, set_method=True)
    collab_id = out["collab_id"]
    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/payouts",
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 409
    assert r.json()["error_code"] == "payout_already_exists"


@pytest.mark.asyncio
async def test_outsider_cannot_retry(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    out = await _run_to_approved(client, brand_user, creator_user, set_method=False)
    collab_id = out["collab_id"]
    outsider = await register(client, "creator")
    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/payouts",
        headers=outsider["auth_header"],
    )
    assert r.status_code == 404
