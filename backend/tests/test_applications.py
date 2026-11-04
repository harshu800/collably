"""Application tests — duplicates, capability match, transitions, slot cap race."""

from __future__ import annotations

import asyncio
import secrets

import httpx
import pytest

# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


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
) -> dict:
    r = await client.patch(
        "/api/v1/me/profile",
        json={
            "display_name": "Creator",
            "bio": "bio",
            "city": "Mumbai",
            "state": "MH",
            "does_ugc": does_ugc,
            "does_influencer": does_influencer,
            "niches": ["beauty"],
        },
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 200, r.text
    return r.json()["creator"]


async def _register(client: httpx.AsyncClient, role: str) -> dict:
    from tests.helpers import register

    return await register(client, role)


async def _make_campaign(
    client: httpx.AsyncClient,
    brand_user: dict,
    *,
    campaign_type: str = "ugc",
    number_of_creators: int = 1,
) -> str:
    body = {
        "title": "Test Campaign",
        "type": campaign_type,
        "budget_paise": 100_000,
        "number_of_creators": number_of_creators,
        "deliverable_spec": [
            {"kind": "file", "description": "video", "quantity": 1}
        ],
        "revision_limit": 1,
        "usage_rights": "paid media",
    }
    r = await client.post(
        "/api/v1/campaigns", json=body, headers=brand_user["auth_header"]
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_application_is_409(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await _onboard_brand(client, brand_user)
    await _onboard_creator(client, creator_user)
    campaign_id = await _make_campaign(client, brand_user)

    first = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={"pitch": "first"},
        headers=creator_user["auth_header"],
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={"pitch": "again"},
        headers=creator_user["auth_header"],
    )
    assert second.status_code == 409, second.text


@pytest.mark.asyncio
async def test_capability_mismatch_is_403(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await _onboard_brand(client, brand_user)
    # UGC-only creator applies to an influencer campaign.
    await _onboard_creator(client, creator_user, does_ugc=True, does_influencer=False)
    campaign_id = await _make_campaign(client, brand_user, campaign_type="influencer")
    r = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={"pitch": "hi"},
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_withdraw_from_each_non_terminal_state(
    client: httpx.AsyncClient,
    brand_user: dict,
) -> None:
    """submitted / shortlisted / invited → withdrawn."""

    await _onboard_brand(client, brand_user)
    campaign_id = await _make_campaign(client, brand_user)

    # submitted → withdrawn.
    c1 = await _register(client, "creator")
    await _onboard_creator(client, c1)
    s = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={},
        headers=c1["auth_header"],
    )
    app_id = s.json()["id"]
    w = await client.post(
        f"/api/v1/applications/{app_id}/withdraw", headers=c1["auth_header"]
    )
    assert w.status_code == 200 and w.json()["status"] == "withdrawn"

    # shortlisted → withdrawn.
    c2 = await _register(client, "creator")
    await _onboard_creator(client, c2)
    s2 = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={},
        headers=c2["auth_header"],
    )
    app2 = s2.json()["id"]
    sh = await client.post(
        f"/api/v1/applications/{app2}/shortlist",
        headers=brand_user["auth_header"],
    )
    assert sh.status_code == 200 and sh.json()["status"] == "shortlisted"
    w2 = await client.post(
        f"/api/v1/applications/{app2}/withdraw", headers=c2["auth_header"]
    )
    assert w2.status_code == 200 and w2.json()["status"] == "withdrawn"

    # invited → withdrawn.
    c3 = await _register(client, "creator")
    c3_profile = await _onboard_creator(client, c3)
    inv = await client.post(
        f"/api/v1/campaigns/{campaign_id}/invitations",
        json={"creator_id": c3_profile["id"]},
        headers=brand_user["auth_header"],
    )
    assert inv.status_code == 201 and inv.json()["status"] == "invited"
    w3 = await client.post(
        f"/api/v1/applications/{inv.json()['id']}/withdraw",
        headers=c3["auth_header"],
    )
    assert w3.status_code == 200 and w3.json()["status"] == "withdrawn"


@pytest.mark.asyncio
async def test_direct_submitted_to_accepted(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    """FR-4.3: a brand may accept a submitted application without shortlisting first."""

    await _onboard_brand(client, brand_user)
    await _onboard_creator(client, creator_user)
    campaign_id = await _make_campaign(client, brand_user)
    s = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={},
        headers=creator_user["auth_header"],
    )
    app_id = s.json()["id"]
    a = await client.post(
        f"/api/v1/applications/{app_id}/accept",
        headers=brand_user["auth_header"],
    )
    assert a.status_code == 200, a.text
    assert a.json()["application"]["status"] == "accepted"
    # FEAT-003 wires the real Collaboration insert.
    assert a.json()["collaboration_id"] is not None


@pytest.mark.asyncio
async def test_shortlisted_then_accepted(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await _onboard_brand(client, brand_user)
    await _onboard_creator(client, creator_user)
    campaign_id = await _make_campaign(client, brand_user)
    s = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={},
        headers=creator_user["auth_header"],
    )
    app_id = s.json()["id"]
    sh = await client.post(
        f"/api/v1/applications/{app_id}/shortlist",
        headers=brand_user["auth_header"],
    )
    assert sh.status_code == 200 and sh.json()["status"] == "shortlisted"
    a = await client.post(
        f"/api/v1/applications/{app_id}/accept",
        headers=brand_user["auth_header"],
    )
    assert a.status_code == 200
    assert a.json()["application"]["status"] == "accepted"


@pytest.mark.asyncio
async def test_invited_then_accepted(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await _onboard_brand(client, brand_user)
    creator = await _onboard_creator(client, creator_user)
    campaign_id = await _make_campaign(client, brand_user)
    inv = await client.post(
        f"/api/v1/campaigns/{campaign_id}/invitations",
        json={"creator_id": creator["id"]},
        headers=brand_user["auth_header"],
    )
    assert inv.status_code == 201 and inv.json()["status"] == "invited"
    a = await client.post(
        f"/api/v1/applications/{inv.json()['id']}/accept",
        headers=brand_user["auth_header"],
    )
    assert a.status_code == 200
    assert a.json()["application"]["status"] == "accepted"


@pytest.mark.asyncio
async def test_slot_limit_race() -> None:
    """Two concurrent `application_service.accept()` calls on a 1-slot campaign:
    exactly one succeeds, the other receives :class:`SlotLimitReached`.

    The default test fixture wraps every request in a single Postgres
    SAVEPOINT on a single connection, so it cannot model two independent
    transactions racing on the Campaign row's ``FOR UPDATE`` lock. This test
    therefore commits its setup to the real test database via its own
    AsyncSession, runs the race through two more AsyncSessions, and cleans
    up on teardown so the next test still starts from a clean baseline.
    """

    import uuid as _uuid

    from app.core.errors import SlotLimitReached
    from app.db.session import get_sessionmaker
    from app.models.application import (
        ApplicationStatus as _AS,
    )
    from app.models.application import (
        CampaignApplication as _App,
    )
    from app.models.brand_profile import BrandProfile as _BP
    from app.models.campaign import (
        Campaign as _C,
    )
    from app.models.campaign import (
        CampaignStatus as _CS,
    )
    from app.models.campaign import (
        CampaignType as _CT,
    )
    from app.models.creator_profile import CreatorProfile as _CP
    from app.models.user import User as _U
    from app.models.user import UserRole as _UR
    from app.services import application_service as _app_svc

    maker = get_sessionmaker()

    created_user_ids: list[_uuid.UUID] = []
    created_brand_profile_id: _uuid.UUID | None = None
    created_creator_profile_ids: list[_uuid.UUID] = []
    created_campaign_id: _uuid.UUID | None = None
    created_application_ids: list[_uuid.UUID] = []

    # --- Setup (committed) ------------------------------------------------
    async with maker() as setup:
        brand = _U(
            email=f"brand-race-{secrets.token_hex(4)}@example.com",
            clerk_user_id=f"user_{_uuid.uuid4().hex[:16]}",
            role=_UR.brand,
        )
        c1 = _U(
            email=f"c1-race-{secrets.token_hex(4)}@example.com",
            clerk_user_id=f"user_{_uuid.uuid4().hex[:16]}",
            role=_UR.creator,
        )
        c2 = _U(
            email=f"c2-race-{secrets.token_hex(4)}@example.com",
            clerk_user_id=f"user_{_uuid.uuid4().hex[:16]}",
            role=_UR.creator,
        )
        setup.add_all([brand, c1, c2])
        await setup.flush()
        created_user_ids.extend([brand.id, c1.id, c2.id])

        bp = _BP(
            user_id=brand.id,
            company_name="RaceCo",
            industry="beauty",
            contact_name="x",
            contact_email="x@example.com",
            is_onboarded=True,
        )
        cp1 = _CP(
            user_id=c1.id,
            display_name="r1",
            bio="b",
            city="Mumbai",
            state="MH",
            does_ugc=True,
            niches=["beauty"],
            is_onboarded=True,
        )
        cp2 = _CP(
            user_id=c2.id,
            display_name="r2",
            bio="b",
            city="Mumbai",
            state="MH",
            does_ugc=True,
            niches=["beauty"],
            is_onboarded=True,
        )
        setup.add_all([bp, cp1, cp2])
        await setup.flush()
        created_brand_profile_id = bp.id
        created_creator_profile_ids.extend([cp1.id, cp2.id])

        camp = _C(
            brand_id=bp.id,
            title="Race Campaign",
            type=_CT.ugc,
            budget_paise=100,
            number_of_creators=1,
            deliverable_spec=[{"kind": "file", "description": "v", "quantity": 1}],
            revision_limit=0,
            disclosure_required=True,
            status=_CS.open,
        )
        setup.add(camp)
        await setup.flush()
        created_campaign_id = camp.id

        app1 = _App(campaign_id=camp.id, creator_id=cp1.id, status=_AS.submitted)
        app2 = _App(campaign_id=camp.id, creator_id=cp2.id, status=_AS.submitted)
        setup.add_all([app1, app2])
        await setup.flush()
        created_application_ids.extend([app1.id, app2.id])
        await setup.commit()

    # --- The race itself --------------------------------------------------
    async def _try_accept(app_id: _uuid.UUID) -> tuple[str, Exception | None]:
        async with maker() as sess:
            try:
                async with sess.begin():
                    app = await sess.get(_App, app_id)
                    assert app is not None
                    await _app_svc.accept(sess, application=app)
                return ("ok", None)
            except SlotLimitReached as exc:
                return ("slot_limit_reached", exc)
            except Exception as exc:  # noqa: BLE001
                return ("error", exc)

    try:
        results = await asyncio.gather(
            _try_accept(created_application_ids[0]),
            _try_accept(created_application_ids[1]),
        )
        outcomes = [r[0] for r in results]
        assert sorted(outcomes) == ["ok", "slot_limit_reached"], (outcomes, results)
    finally:
        # --- Cleanup ------------------------------------------------------
        async with maker() as cleanup:
            async with cleanup.begin():
                from sqlalchemy import delete

                await cleanup.execute(
                    delete(_App).where(_App.id.in_(created_application_ids))
                )
                if created_campaign_id is not None:
                    await cleanup.execute(
                        delete(_C).where(_C.id == created_campaign_id)
                    )
                if created_creator_profile_ids:
                    await cleanup.execute(
                        delete(_CP).where(_CP.id.in_(created_creator_profile_ids))
                    )
                if created_brand_profile_id is not None:
                    await cleanup.execute(
                        delete(_BP).where(_BP.id == created_brand_profile_id)
                    )
                if created_user_ids:
                    await cleanup.execute(
                        delete(_U).where(_U.id.in_(created_user_ids))
                    )


@pytest.mark.asyncio
async def test_hybrid_campaign_requires_both_capabilities(
    client: httpx.AsyncClient,
    brand_user: dict,
    creator_user: dict,
) -> None:
    await _onboard_brand(client, brand_user)
    # Only UGC flag, not influencer.
    await _onboard_creator(client, creator_user, does_ugc=True, does_influencer=False)
    campaign_id = await _make_campaign(client, brand_user, campaign_type="hybrid")
    r = await client.post(
        f"/api/v1/campaigns/{campaign_id}/applications",
        json={},
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 403
