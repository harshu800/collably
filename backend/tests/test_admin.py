"""Admin + dispute resolution tests (FEAT-004).

Covers:
* Non-admin users receive 403 on every ``/admin/*`` route.
* Admin can list the various collections.
* Dispute resolution for the three resolution types:
  - ``release_to_creator`` triggers initiate_payout; payout transitions to paid
    via the mock confirm endpoint; collab moves to completed.
  - ``refund_to_brand`` creates a Refund row and transitions the collab to
    cancelled.
  - ``split`` records split_bps + transitions to completed with no new money
    movement (bookkeeping only per design §17 / v2r2-4).
* Audit rows are written for every admin action.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.dispute import DisputeStatus
from app.models.payment import Payment
from app.models.payout import Payout
from app.models.refund import Refund
from app.models.webhook_event import PaymentWebhookEvent
from app.providers.payment.base import PaymentProviderError, RefundCreated
from app.providers.payment.mock import SIGNATURE_HEADER, MockSandboxProvider, compute_signature
from app.services import payment_service
from tests.helpers import (
    apply_and_accept,
    fund_and_confirm,
    make_campaign,
    onboard_brand,
    onboard_creator,
    set_upi_payout_method,
    sign_both_parties,
)

ADMIN_ROUTES: list[tuple[str, str, dict | None]] = [
    ("GET", "/api/v1/admin/users", None),
    ("GET", "/api/v1/admin/campaigns", None),
    ("GET", "/api/v1/admin/collaborations", None),
    ("GET", "/api/v1/admin/reports", None),
    ("GET", "/api/v1/admin/disputes", None),
    ("GET", "/api/v1/admin/payment-events", None),
    ("GET", "/api/v1/admin/audit-logs", None),
    ("POST", f"/api/v1/admin/users/{uuid.uuid4()}/deactivate", None),
    ("POST", f"/api/v1/admin/campaigns/{uuid.uuid4()}/archive", None),
    (
        "POST",
        f"/api/v1/admin/reports/{uuid.uuid4()}/review",
        {"status": "reviewed"},
    ),
    (
        "POST",
        f"/api/v1/admin/disputes/{uuid.uuid4()}/resolve",
        {"resolution": "refund_to_brand"},
    ),
]


@pytest.mark.asyncio
async def test_non_admin_forbidden_on_every_admin_route(
    client, brand_user, creator_user
):
    for method, path, body in ADMIN_ROUTES:
        for user in (brand_user, creator_user):
            if method == "GET":
                r = await client.get(path, headers=user["auth_header"])
            else:
                r = await client.post(
                    path, headers=user["auth_header"], json=body or {}
                )
            assert r.status_code == 403, (
                f"{method} {path} for {user['role']}: got {r.status_code}, {r.text}"
            )


@pytest.mark.asyncio
async def test_admin_can_list_users_campaigns_collaborations(
    client, admin_user, brand_user
):
    await onboard_brand(client, brand_user)
    await make_campaign(client, brand_user)
    r = await client.get("/api/v1/admin/users", headers=admin_user["auth_header"])
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    r = await client.get(
        "/api/v1/admin/campaigns", headers=admin_user["auth_header"]
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1
    r = await client.get(
        "/api/v1/admin/collaborations", headers=admin_user["auth_header"]
    )
    assert r.status_code == 200


async def _open_funded_dispute(client, brand_user, creator_user):
    """Build a funded collaboration and open a dispute on it. Returns (collab_id, dispute_id)."""

    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    await set_upi_payout_method(client, creator_user)
    campaign = await make_campaign(client, brand_user, spec_items=1)
    pair = await apply_and_accept(
        client,
        brand=brand_user,
        creator=creator_user,
        campaign_id=campaign["id"],
    )
    collab_id = pair["collaboration_id"]
    await sign_both_parties(
        client, collaboration_id=collab_id, brand=brand_user, creator=creator_user
    )
    await fund_and_confirm(client, collaboration_id=collab_id, brand=brand_user)
    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/disputes",
        json={"reason": "Testing resolution path"},
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 201, r.text
    return collab_id, r.json()["id"]


async def _mock_confirm_payout(client, payout_id: str) -> None:
    """Hit the dev-only mock confirm-payout endpoint."""

    # We know the dev endpoint but it only takes the id — the handler
    # constructs the signed body itself.
    r = await client.post(f"/api/v1/payments/mock/confirm-payout/{payout_id}")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_dispute_release_runs_payout(
    client, db, admin_user, brand_user, creator_user
):
    collab_id, dispute_id = await _open_funded_dispute(
        client, brand_user, creator_user
    )
    r = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        headers=admin_user["auth_header"],
        json={"resolution": "release_to_creator"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resolution"] == "release_to_creator"

    # A Payout row should now exist for this collab.
    payout_row = (
        await db.execute(select(Payout).where(Payout.collaboration_id == collab_id))
    ).scalar_one()
    assert payout_row.status.value == "pending"

    assert payout_row.provider_payout_id is not None
    await _mock_confirm_payout(client, payout_row.provider_payout_id)

    # Reload the collaboration via API as creator; status should be completed.
    r = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=creator_user["auth_header"]
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert r.json()["payout_status"] == "paid"

    # Audit log contains dispute.resolved + payout.paid.
    actions = (
        await db.execute(select(AuditLog.action))
    ).scalars().all()
    assert "dispute.resolved" in actions
    assert "payout.paid" in actions


@pytest.mark.asyncio
async def test_dispute_refund_creates_refund_and_cancels(
    client, db, admin_user, brand_user, creator_user
):
    collab_id, dispute_id = await _open_funded_dispute(
        client, brand_user, creator_user
    )
    r = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        headers=admin_user["auth_header"],
        json={"resolution": "refund_to_brand"},
    )
    assert r.status_code == 200, r.text

    r = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=brand_user["auth_header"]
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"

    refund_count = int(
        (
            await db.execute(select(func.count()).select_from(Refund))
        ).scalar_one()
    )
    assert refund_count >= 1

    # No Payout for this collab.
    payouts = (
        await db.execute(
            select(func.count())
            .select_from(Payout)
            .where(Payout.collaboration_id == collab_id)
        )
    ).scalar_one()
    assert payouts == 0


@pytest.mark.asyncio
async def test_live_provider_dispute_refund_retries_with_stable_idempotency_key(
    client, db, admin_user, brand_user, creator_user, monkeypatch
):
    from types import SimpleNamespace

    from app.services import dispute_service

    collab_id, dispute_id = await _open_funded_dispute(
        client, brand_user, creator_user
    )
    payment = (
        await db.execute(
            select(Payment).where(Payment.collaboration_id == collab_id)
        )
    ).scalar_one()
    payment.provider = "razorpay"
    payment.razorpay_payment_id = "pay_test_123"
    await db.flush()

    calls = []

    class FakeProvider:
        name = "razorpay"

        def refund(self, *, provider_payment_id, amount_paise, idempotency_key):
            calls.append((provider_payment_id, amount_paise, idempotency_key))
            if len(calls) == 1:
                raise PaymentProviderError("temporary network failure")
            return RefundCreated(
                provider_refund_id="rfnd_test_123",
                amount_paise=amount_paise,
                currency="INR",
                status="pending",
            )

    monkeypatch.setattr(
        dispute_service,
        "get_settings",
        lambda: SimpleNamespace(payment_provider="razorpay"),
    )
    monkeypatch.setattr(
        dispute_service, "get_payment_provider", lambda _settings: FakeProvider()
    )

    payload = {"resolution": "refund_to_brand"}
    response = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        headers=admin_user["auth_header"],
        json=payload,
    )

    assert response.status_code == 502
    requested_refund = (
        await db.execute(select(Refund).where(Refund.payment_id == payment.id))
    ).scalar_one()
    assert requested_refund.status == "requested"
    stable_refund_id = requested_refund.id
    collab_response = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=brand_user["auth_header"]
    )
    assert collab_response.json()["status"] == "disputed"

    response = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        headers=admin_user["auth_header"],
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert requested_refund.id == stable_refund_id
    requested_refund.provider_refund_id = None
    assert requested_refund.status == "pending"

    refund_event = PaymentWebhookEvent(
        provider="razorpay",
        provider_event_id="evt_refund_processed_test",
        event_type="refund.processed",
        payload={
            "refund_id": "rfnd_test_123",
            "local_refund_id": str(stable_refund_id),
            "payment_id": "pay_test_123",
            "amount_paise": payment.amount_paise,
            "currency": "INR",
            "status": "processed",
        },
        signature="verified-in-test",
        verified=True,
    )
    db.add(refund_event)
    await db.flush()
    await payment_service._apply_event(db, event=refund_event)
    await db.refresh(payment)
    assert requested_refund.provider_refund_id == "rfnd_test_123"
    assert requested_refund.status == "processed"
    assert payment.status.value == "refunded"

    collab_response = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=brand_user["auth_header"]
    )
    assert collab_response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_failed_refund_webhook_reopens_dispute_for_safe_retry(
    client, db, admin_user, brand_user, creator_user, monkeypatch
):
    from types import SimpleNamespace

    from app.models.dispute import Dispute
    from app.services import dispute_service

    collab_id, dispute_id = await _open_funded_dispute(
        client, brand_user, creator_user
    )
    payment = (
        await db.execute(
            select(Payment).where(Payment.collaboration_id == collab_id)
        )
    ).scalar_one()
    payment.provider = "razorpay"
    payment.razorpay_payment_id = "pay_test_failed_refund"
    await db.flush()

    keys = []

    class FakeProvider:
        name = "razorpay"

        def refund(self, *, provider_payment_id, amount_paise, idempotency_key):
            keys.append(idempotency_key)
            return RefundCreated(
                provider_refund_id=f"rfnd_retry_{len(keys)}",
                amount_paise=amount_paise,
                currency="INR",
                status="pending",
            )

    monkeypatch.setattr(
        dispute_service,
        "get_settings",
        lambda: SimpleNamespace(payment_provider="razorpay"),
    )
    monkeypatch.setattr(
        dispute_service, "get_payment_provider", lambda _settings: FakeProvider()
    )

    payload = {"resolution": "refund_to_brand"}
    response = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        headers=admin_user["auth_header"],
        json=payload,
    )
    assert response.status_code == 200, response.text

    refund = (
        await db.execute(select(Refund).where(Refund.payment_id == payment.id))
    ).scalar_one()
    failed_event = PaymentWebhookEvent(
        provider="razorpay",
        provider_event_id="evt_refund_failed_test",
        event_type="refund.failed",
        payload={
            "refund_id": "rfnd_retry_1",
            "payment_id": "pay_test_failed_refund",
            "amount_paise": payment.amount_paise,
            "currency": "INR",
            "status": "failed",
        },
        signature="verified-in-test",
        verified=True,
    )
    db.add(failed_event)
    await db.flush()
    await payment_service._apply_event(db, event=failed_event)

    dispute = await db.get(Dispute, uuid.UUID(dispute_id))
    assert refund.status == "failed"
    assert dispute.status == DisputeStatus.open
    collab_response = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=brand_user["auth_header"]
    )
    assert collab_response.json()["status"] == "disputed"

    response = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        headers=admin_user["auth_header"],
        json=payload,
    )
    assert response.status_code == 200, response.text
    assert len(keys) == 2
    assert keys[0] != keys[1]


@pytest.mark.asyncio
async def test_dispute_split_is_bookkeeping_only(
    client, db, admin_user, brand_user, creator_user
):
    collab_id, dispute_id = await _open_funded_dispute(
        client, brand_user, creator_user
    )
    r = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        headers=admin_user["auth_header"],
        json={"resolution": "split", "split_bps": 5000},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["resolution"] == "split"
    assert body["split_bps"] == 5000

    r = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=brand_user["auth_header"]
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"

    # No Payout row and no Refund row.
    payouts = int(
        (
            await db.execute(
                select(func.count())
                .select_from(Payout)
                .where(Payout.collaboration_id == collab_id)
            )
        ).scalar_one()
    )
    assert payouts == 0, "split must not create a Payout"
    refunds = int(
        (
            await db.execute(select(func.count()).select_from(Refund))
        ).scalar_one()
    )
    assert refunds == 0, "split must not create a Refund"

    # Audit written with the split details.
    diffs = (
        await db.execute(
            select(AuditLog.diff).where(AuditLog.action == "dispute.resolved")
        )
    ).scalars().all()
    assert any(
        d.get("resolution") == "split" and d.get("split_bps") == 5000
        for d in diffs
    )


@pytest.mark.asyncio
async def test_admin_deactivate_user_writes_audit(
    client, db, admin_user, brand_user
):
    target_id = (
        await client.get("/api/v1/users/me", headers=brand_user["auth_header"])
    ).json()["id"]
    r = await client.post(
        f"/api/v1/admin/users/{target_id}/deactivate",
        headers=admin_user["auth_header"],
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    actions = (
        await db.execute(select(AuditLog.action))
    ).scalars().all()
    assert "admin.user_deactivated" in actions


@pytest.mark.asyncio
async def test_resolve_split_requires_split_bps(
    client, admin_user, brand_user, creator_user
):
    _, dispute_id = await _open_funded_dispute(client, brand_user, creator_user)
    r = await client.post(
        f"/api/v1/admin/disputes/{dispute_id}/resolve",
        headers=admin_user["auth_header"],
        json={"resolution": "split"},
    )
    # 422 — the body omitted split_bps so our service raises SplitBpsRequired.
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_mock_signature_round_trip():
    """Sanity check — the mock provider used by _mock_confirm_payout signs
    its own body, so no HMAC drift between tests and the dev endpoints."""

    body = MockSandboxProvider.build_payout_event_body(
        payout_id="mock_payout_abc",
        amount_paise=1000,
    )
    sig = compute_signature(body)
    # Round-trip through verify.
    provider = MockSandboxProvider()
    event = provider.verify_webhook(
        body=body, headers={SIGNATURE_HEADER: sig}
    )
    assert json.loads(body.decode("utf-8"))["payout_id"] == "mock_payout_abc"
    assert event.event_type == "payout.paid"
