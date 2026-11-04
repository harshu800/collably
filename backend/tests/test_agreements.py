"""Agreement signing + supersession + partial-unique index tests."""

from __future__ import annotations

import httpx
import pytest

from tests.helpers import (
    apply_and_accept,
    make_campaign,
    onboard_brand,
    onboard_creator,
)


async def _get_agreement_id(client: httpx.AsyncClient, collab_id: str, auth: dict) -> str:
    r = await client.get(
        f"/api/v1/collaborations/{collab_id}/agreement",
        headers=auth["auth_header"],
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.mark.asyncio
async def test_first_signature_keeps_pending_agreement(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    agreement_id = await _get_agreement_id(client, collab_id, brand_user)

    r = await client.post(
        f"/api/v1/agreements/{agreement_id}/sign",
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 200
    assert r.json()["brand_signed_at"] is not None
    assert r.json()["creator_signed_at"] is None

    collab = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=brand_user["auth_header"]
    )
    assert collab.json()["status"] == "pending_agreement"


@pytest.mark.asyncio
async def test_both_signatures_flip_collab_to_agreement_signed(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    agreement_id = await _get_agreement_id(client, collab_id, brand_user)

    await client.post(
        f"/api/v1/agreements/{agreement_id}/sign",
        headers=brand_user["auth_header"],
    )
    r = await client.post(
        f"/api/v1/agreements/{agreement_id}/sign",
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 200
    assert r.json()["creator_signed_at"] is not None

    collab = await client.get(
        f"/api/v1/collaborations/{collab_id}", headers=brand_user["auth_header"]
    )
    assert collab.json()["status"] == "agreement_signed"


@pytest.mark.asyncio
async def test_double_sign_is_idempotent(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    agreement_id = await _get_agreement_id(client, collab_id, brand_user)

    r1 = await client.post(
        f"/api/v1/agreements/{agreement_id}/sign",
        headers=brand_user["auth_header"],
    )
    first_at = r1.json()["brand_signed_at"]

    r2 = await client.post(
        f"/api/v1/agreements/{agreement_id}/sign",
        headers=brand_user["auth_header"],
    )
    assert r2.status_code == 200
    # Idempotent — timestamp preserved.
    assert r2.json()["brand_signed_at"] == first_at
    assert r2.json()["creator_signed_at"] is None


@pytest.mark.asyncio
async def test_new_agreement_version_supersedes(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user, revision_limit=2)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    v1_id = await _get_agreement_id(client, collab_id, brand_user)

    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/agreements",
        json={"revision_limit": 1, "scope": "updated scope"},
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert v2["version_number"] == 2
    assert v2["revision_limit"] == 1
    assert v2["superseded_at"] is None

    # The current agreement is now v2.
    current = await client.get(
        f"/api/v1/collaborations/{collab_id}/agreement",
        headers=brand_user["auth_header"],
    )
    assert current.json()["id"] == v2["id"]
    assert current.json()["id"] != v1_id


@pytest.mark.asyncio
async def test_db_partial_unique_rejects_two_current_rows(db) -> None:
    """Attempting to insert a second (collaboration_id, superseded_at IS NULL)
    row at the DB layer must fail with the unique index violation.
    """

    import uuid as _uuid

    from sqlalchemy.exc import IntegrityError

    from app.models.agreement import AgreementVersion
    from app.models.application import ApplicationStatus, CampaignApplication
    from app.models.brand_profile import BrandProfile
    from app.models.campaign import Campaign, CampaignStatus, CampaignType
    from app.models.collaboration import (
        Collaboration,
        CollaborationStatus,
        FundingStatus,
    )
    from app.models.creator_profile import CreatorProfile
    from app.models.user import User, UserRole

    brand = User(
        email=f"b-{_uuid.uuid4().hex[:8]}@e.com",
        clerk_user_id=f"user_{_uuid.uuid4().hex[:16]}",
        role=UserRole.brand,
    )
    creator = User(
        email=f"c-{_uuid.uuid4().hex[:8]}@e.com",
        clerk_user_id=f"user_{_uuid.uuid4().hex[:16]}",
        role=UserRole.creator,
    )
    db.add_all([brand, creator])
    await db.flush()
    bp = BrandProfile(user_id=brand.id, company_name="x", is_onboarded=True)
    cp = CreatorProfile(user_id=creator.id, display_name="x", does_ugc=True, is_onboarded=True)
    db.add_all([bp, cp])
    await db.flush()
    camp = Campaign(
        brand_id=bp.id, title="t", type=CampaignType.ugc, budget_paise=100,
        number_of_creators=1, deliverable_spec=[{"kind": "file", "description": "a", "quantity": 1}],
        revision_limit=0, disclosure_required=True, status=CampaignStatus.open,
    )
    db.add(camp)
    await db.flush()
    app = CampaignApplication(campaign_id=camp.id, creator_id=cp.id, status=ApplicationStatus.submitted)
    db.add(app)
    await db.flush()
    collab = Collaboration(
        campaign_id=camp.id, application_id=app.id, brand_id=bp.id, creator_id=cp.id,
        status=CollaborationStatus.pending_agreement, price_paise=100,
        funding_status=FundingStatus.not_funded,
    )
    db.add(collab)
    await db.flush()
    # v1 already current (superseded_at IS NULL).
    db.add(AgreementVersion(
        collaboration_id=collab.id, version_number=1,
        deliverable_spec=[], price_paise=100, revision_limit=0,
        disclosure_required=True,
    ))
    await db.flush()
    # Attempt to insert a second current row.
    db.add(AgreementVersion(
        collaboration_id=collab.id, version_number=2,
        deliverable_spec=[], price_paise=100, revision_limit=0,
        disclosure_required=True,
    ))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_require_fully_signed_blocks_after_supersession(
    client: httpx.AsyncClient, brand_user: dict, creator_user: dict
) -> None:
    """After supersession, the new current row is unsigned — downstream
    writes gated on require_current_agreement_fully_signed must raise.
    """

    from tests.helpers import sign_both_parties

    await onboard_brand(client, brand_user)
    await onboard_creator(client, creator_user)
    campaign = await make_campaign(client, brand_user, revision_limit=2)
    accepted = await apply_and_accept(
        client, brand=brand_user, creator=creator_user, campaign_id=campaign["id"]
    )
    collab_id = accepted["collaboration_id"]
    await sign_both_parties(
        client,
        collaboration_id=collab_id,
        brand=brand_user,
        creator=creator_user,
    )

    # Supersede.
    r = await client.post(
        f"/api/v1/collaborations/{collab_id}/agreements",
        json={"scope": "updated"},
        headers=brand_user["auth_header"],
    )
    assert r.status_code == 201

    # Attempting to fund now — current (v2) is unsigned → 409 work_not_unlocked.
    f = await client.post(
        f"/api/v1/collaborations/{collab_id}/funding",
        headers=brand_user["auth_header"],
    )
    assert f.status_code == 409
    body = f.json()
    assert body["error_code"] == "work_not_unlocked"
    assert body["details"]["reason"] == "agreement"
