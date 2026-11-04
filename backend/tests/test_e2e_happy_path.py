"""Scripted end-to-end happy path (design §14, AC §6, FEAT-005 step 3).

Drives the full 15-step marketplace flow via HTTP against the running FastAPI
app with the in-process mock payment provider. One scripted test — fails
loudly if any transition deviates from the design state machine.
"""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.collaboration import (
    CollaborationPayoutStatus,
    CollaborationStatus,
    FundingStatus,
)
from app.models.notification import Notification
from app.providers.payment.mock import SIGNATURE_HEADER, compute_signature

# A minimal real PNG that passes libmagic.
_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

# UPI VPA used by the creator. The e2e MUST never see this plaintext appear
# in captured log output (design §12 secrets-in-logs guarantee).
CREATOR_VPA = "e2e-creator@okbank"
CREATOR_HOLDER = "E2E Creator"


@pytest.mark.asyncio
async def test_e2e_happy_path_full_15_steps(
    client: httpx.AsyncClient, db, capfd: pytest.CaptureFixture[str]
) -> None:
    # ------------------------------------------------------------------
    # Step 1 — Provision brand user through Clerk bypass + role selection.
    # ------------------------------------------------------------------
    from tests.helpers import register

    brand_email = "e2e-brand@example.com"
    creator_email = "e2e-creator@example.com"

    brand = await register(client, "brand", email=brand_email)
    brand_auth = brand["auth_header"]

    # ------------------------------------------------------------------
    # Step 2 — Complete brand profile + onboarding.
    # ------------------------------------------------------------------
    r = await client.patch(
        "/api/v1/me/profile",
        json={
            "company_name": "E2E Beauty Co.",
            "industry": "beauty",
            "contact_name": "Brand Owner",
            "contact_email": "owner@example.com",
        },
        headers=brand_auth,
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/me/profile/complete-onboarding", headers=brand_auth
    )
    assert r.status_code == 200
    assert r.json()["is_onboarded"] is True, r.json()

    # ------------------------------------------------------------------
    # Step 3 — Create UGC campaign.
    # ------------------------------------------------------------------
    r = await client.post(
        "/api/v1/campaigns",
        json={
            "title": "E2E Festive UGC",
            "type": "ugc",
            "budget_paise": 100_000,
            "revision_limit": 2,
            "number_of_creators": 1,
            "deliverable_spec": [
                {"kind": "file", "description": "one short-form video", "quantity": 1}
            ],
            "submission_deadline": "2099-12-31T00:00:00Z",
            "usage_rights": "paid media, 90 days",
            "disclosure_required": False,
        },
        headers=brand_auth,
    )
    assert r.status_code == 201, r.text
    campaign_id = r.json()["id"]

    # ------------------------------------------------------------------
    # Step 4 — Provision creator user through Clerk bypass + role selection.
    # ------------------------------------------------------------------
    creator = await register(client, "creator", email=creator_email)
    creator_auth = creator["auth_header"]

    # ------------------------------------------------------------------
    # Step 5 — Complete creator profile + onboarding (does_ugc=True).
    # ------------------------------------------------------------------
    r = await client.patch(
        "/api/v1/me/profile",
        json={
            "display_name": "E2E Creator",
            "bio": "e2e bio",
            "city": "Mumbai",
            "state": "MH",
            "does_ugc": True,
            "does_influencer": False,
            "niches": ["beauty"],
        },
        headers=creator_auth,
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/me/profile/complete-onboarding", headers=creator_auth
    )
    assert r.status_code == 200
    assert r.json()["is_onboarded"] is True

    # ------------------------------------------------------------------
    # Step 6 — Creator sets UPI payout method via PUT /me/payout-method.
    # ------------------------------------------------------------------
    r = await client.put(
        "/api/v1/me/payout-method",
        json={
            "method": "upi",
            "holder_name": CREATOR_HOLDER,
            "upi_vpa": CREATOR_VPA,
        },
        headers=creator_auth,
    )
    assert r.status_code == 200, r.text
    pm = r.json()
    assert pm["method"] == "upi"
    # Projection must only contain the masked VPA.
    assert pm["upi_vpa_masked"] and "***" in pm["upi_vpa_masked"]
    assert "upi_vpa" not in pm

    # ------------------------------------------------------------------
    # Step 7 — Creator applies to the campaign.
    # ------------------------------------------------------------------
    r = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={},
        headers=creator_auth,
    )
    assert r.status_code == 201, r.text
    application_id = r.json()["id"]
    assert r.json()["status"] == "submitted"

    # ------------------------------------------------------------------
    # Step 8 — Brand directly accepts (no shortlist step; validates
    # HIGH-2 — submitted → accepted). Collaboration lands in
    # pending_agreement.
    # ------------------------------------------------------------------
    r = await client.post(
        f"/api/v1/applications/{application_id}/accept", headers=brand_auth
    )
    assert r.status_code == 200, r.text
    collaboration_id = r.json()["collaboration_id"]
    assert collaboration_id is not None

    r = await client.get(
        f"/api/v1/collaborations/{collaboration_id}", headers=brand_auth
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending_agreement"

    # ------------------------------------------------------------------
    # Step 9 — Both parties sign the current agreement. The second
    # signature flips the collaboration to `agreement_signed` in a single
    # transaction.
    # ------------------------------------------------------------------
    r = await client.get(
        f"/api/v1/collaborations/{collaboration_id}/agreement",
        headers=brand_auth,
    )
    assert r.status_code == 200
    agreement_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/agreements/{agreement_id}/sign", headers=brand_auth
    )
    assert r.status_code == 200
    # First signature keeps collab in pending_agreement.
    collab = await client.get(
        f"/api/v1/collaborations/{collaboration_id}", headers=brand_auth
    )
    assert collab.json()["status"] == "pending_agreement"

    r = await client.post(
        f"/api/v1/agreements/{agreement_id}/sign", headers=creator_auth
    )
    assert r.status_code == 200
    collab = await client.get(
        f"/api/v1/collaborations/{collaboration_id}", headers=brand_auth
    )
    assert collab.json()["status"] == "agreement_signed"

    # ------------------------------------------------------------------
    # Step 10 — Brand initiates funding → funding_initiated, capture the
    # provider order id.
    # ------------------------------------------------------------------
    r = await client.post(
        f"/api/v1/collaborations/{collaboration_id}/funding", headers=brand_auth
    )
    assert r.status_code == 200, r.text
    order_id = r.json()["provider_order_id"]
    assert order_id.startswith("mock_order_")

    # ------------------------------------------------------------------
    # Step 11 — Replay the funding event straight to the webhook endpoint
    # with the correct X-Mock-Signature so that we control the event_id
    # (needed for the step-15 duplicate replay).
    # ------------------------------------------------------------------
    event_id = "e2e_mock_evt_funding_01"
    body = json.dumps(
        {
            "event_id": event_id,
            "event_type": "funding.succeeded",
            "order_id": order_id,
            "amount_paise": 100_000,
            "currency": "INR",
            "status": "succeeded",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    sig = compute_signature(body)
    r = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: sig},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = await client.get(
        f"/api/v1/collaborations/{collaboration_id}/funding", headers=brand_auth
    )
    assert r.status_code == 200
    assert r.json()["funding_status"] == "funding_confirmed"
    assert r.json()["collaboration_status"] == "funded"

    # ------------------------------------------------------------------
    # Step 12 — Creator uploads a tiny PNG as the single-spec deliverable.
    # First submission transitions funded → in_progress and because the
    # single spec item is now covered → in_review.
    # ------------------------------------------------------------------
    r = await client.post(
        "/api/v1/files",
        files={"file": ("hero.png", io.BytesIO(_PNG), "image/png")},
        headers=creator_auth,
    )
    assert r.status_code == 201, r.text
    file_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/collaborations/{collaboration_id}/deliverables",
        json={"spec_index": 0, "kind": "file", "file_id": file_id},
        headers=creator_auth,
    )
    assert r.status_code == 201, r.text
    deliverable_id = r.json()["id"]

    collab = await client.get(
        f"/api/v1/collaborations/{collaboration_id}", headers=brand_auth
    )
    assert collab.json()["status"] == "in_review"

    # ------------------------------------------------------------------
    # Step 13 — Brand approves the deliverable → collab = approved and a
    # Payout row lands in `pending` with beneficiary_snapshot.method='upi'
    # and a masked VPA.
    # ------------------------------------------------------------------
    r = await client.post(
        f"/api/v1/deliverables/{deliverable_id}/approve", headers=brand_auth
    )
    assert r.status_code == 200, r.text
    body_j = r.json()
    assert body_j["collaboration_status"] == "approved"
    assert body_j["payout"]["status"] == "pending"

    r = await client.get(
        f"/api/v1/collaborations/{collaboration_id}/payouts", headers=brand_auth
    )
    assert r.status_code == 200
    payout = r.json()
    assert payout["status"] == "pending"
    assert payout["beneficiary_snapshot"]["method"] == "upi"
    masked = payout["beneficiary_snapshot"].get("upi_vpa_masked")
    assert masked and "***" in masked, masked
    # Plaintext VPA MUST NOT appear anywhere in the snapshot.
    snapshot_text = json.dumps(payout["beneficiary_snapshot"])
    assert CREATOR_VPA not in snapshot_text

    provider_payout_id = payout["provider_payout_id"]
    assert provider_payout_id and provider_payout_id.startswith("mock_payout_")

    # ------------------------------------------------------------------
    # Step 14 — Hit POST /payments/mock/confirm-payout/{payout_id} —
    # Payout flips to paid, Collaboration → completed.
    # ------------------------------------------------------------------
    r = await client.post(
        f"/api/v1/payments/mock/confirm-payout/{provider_payout_id}"
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"

    r = await client.get(
        f"/api/v1/collaborations/{collaboration_id}", headers=brand_auth
    )
    assert r.json()["status"] == "completed"

    r = await client.get(
        f"/api/v1/collaborations/{collaboration_id}/payouts", headers=brand_auth
    )
    assert r.json()["status"] == "paid"

    # ------------------------------------------------------------------
    # Step 15 — Replay the funding webhook with the same event_id →
    # response 200 with status='duplicate' and state unchanged.
    # ------------------------------------------------------------------
    r = await client.post(
        "/api/v1/webhooks/payments/mock",
        content=body,
        headers={SIGNATURE_HEADER: sig},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "duplicate"

    r = await client.get(
        f"/api/v1/collaborations/{collaboration_id}", headers=brand_auth
    )
    collab_final = r.json()
    assert collab_final["status"] == "completed"
    assert collab_final["funding_status"] == "funding_confirmed"
    assert collab_final["payout_status"] == "paid"

    # ------------------------------------------------------------------
    # Final asserts against the DB.
    # ------------------------------------------------------------------
    from uuid import UUID as _UUID

    collab_uuid = _UUID(collaboration_id)

    # Audit entries land across several target_types (application,
    # agreement, deliverable, collaboration). The floor below is loose on
    # purpose — the point is that each state transition emitted at least
    # one audit row.
    audit_count = (
        await db.execute(select(func.count(AuditLog.id)))
    ).scalar_one()
    # Expected: application.accepted, agreement.signed (x2),
    # funding.initiated, funding.confirmed, deliverable.submitted,
    # deliverable.approved, payout.initiated, payout.paid  →  ≥ 7.
    assert audit_count >= 7, f"audit log too thin: {audit_count}"

    # Notifications must have landed for both parties on the expected events.
    notif_types = (
        await db.execute(
            select(Notification.type)
            .where(Notification.payload["collaboration_id"].astext == collaboration_id)
        )
    ).scalars().all()
    assert any(t == "funding.confirmed" for t in notif_types), notif_types
    assert any(t == "payout.paid" for t in notif_types), notif_types

    # Status enums at the DB layer match the API view (defence against a
    # phantom reconciliation path).
    from app.models.collaboration import Collaboration

    collab_row = await db.get(Collaboration, collab_uuid)
    assert collab_row is not None
    assert collab_row.status == CollaborationStatus.completed
    assert collab_row.funding_status == FundingStatus.funding_confirmed
    assert collab_row.payout_status == CollaborationPayoutStatus.paid

    # ------------------------------------------------------------------
    # Secrets-in-logs guarantee — scrape captured stdout + stderr and
    # confirm no decrypted VPA / holder-plus-VPA fragment leaked.
    # ------------------------------------------------------------------
    captured = capfd.readouterr()
    combined = captured.out + captured.err
    assert CREATOR_VPA not in combined, (
        "Decrypted UPI VPA leaked into logs: " + CREATOR_VPA
    )
