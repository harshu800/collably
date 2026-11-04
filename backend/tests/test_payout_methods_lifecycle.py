"""CreatorPayoutMethod soft-active lifecycle tests."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.models.creator_profile import CreatorProfile
from app.models.payout_method import CreatorPayoutMethod
from tests.helpers import onboard_creator


@pytest.mark.asyncio
async def test_put_marks_prior_inactive_and_inserts_new_active(
    client: httpx.AsyncClient, creator_user: dict, db
) -> None:
    await onboard_creator(client, creator_user)
    await client.put(
        "/api/v1/me/payout-method",
        json={"method": "upi", "holder_name": "AA", "upi_vpa": "first@okbank"},
        headers=creator_user["auth_header"],
    )
    await client.put(
        "/api/v1/me/payout-method",
        json={"method": "upi", "holder_name": "AA", "upi_vpa": "second@okbank"},
        headers=creator_user["auth_header"],
    )
    cp = (
        await db.execute(
            select(CreatorProfile).where(
                CreatorProfile.user_id == __import__("uuid").UUID(
                    (await client.get(
                        "/api/v1/users/me",
                        headers=creator_user["auth_header"],
                    )).json()["id"]
                )
            )
        )
    ).scalar_one()
    rows = (
        await db.execute(
            select(CreatorPayoutMethod)
            .where(CreatorPayoutMethod.creator_id == cp.id)
            .order_by(CreatorPayoutMethod.created_at.asc())
        )
    ).scalars().all()
    assert len(rows) == 2
    assert rows[0].is_active is False
    assert rows[1].is_active is True


@pytest.mark.asyncio
async def test_delete_sets_inactive_is_idempotent(
    client: httpx.AsyncClient, creator_user: dict
) -> None:
    await onboard_creator(client, creator_user)
    r1 = await client.delete(
        "/api/v1/me/payout-method", headers=creator_user["auth_header"]
    )
    assert r1.status_code == 204
    # Still 204 even if nothing exists.
    r2 = await client.delete(
        "/api/v1/me/payout-method", headers=creator_user["auth_header"]
    )
    assert r2.status_code == 204

    await client.put(
        "/api/v1/me/payout-method",
        json={"method": "upi", "holder_name": "AA", "upi_vpa": "aa@okbank"},
        headers=creator_user["auth_header"],
    )
    r3 = await client.delete(
        "/api/v1/me/payout-method", headers=creator_user["auth_header"]
    )
    assert r3.status_code == 204
    g = await client.get(
        "/api/v1/me/payout-method", headers=creator_user["auth_header"]
    )
    assert g.status_code == 404


@pytest.mark.asyncio
async def test_db_rejects_two_active_rows(db) -> None:
    """Partial unique index ``ux_payout_method_active`` must raise at insert time."""

    import uuid as _uuid

    from sqlalchemy.exc import IntegrityError

    from app.models.payout_method import CreatorPayoutMethod, PayoutMethodKind
    from app.models.user import User, UserRole

    user = User(
        email=f"c-{_uuid.uuid4().hex[:8]}@e.com",
        clerk_user_id=f"user_{_uuid.uuid4().hex[:16]}",
        role=UserRole.creator,
    )
    db.add(user)
    await db.flush()
    cp = CreatorProfile(user_id=user.id, display_name="x", does_ugc=True)
    db.add(cp)
    await db.flush()
    db.add(
        CreatorPayoutMethod(
            creator_id=cp.id,
            method=PayoutMethodKind.upi,
            holder_name="A",
            upi_vpa_ciphertext=b"\x00" * 32,
            is_active=True,
        )
    )
    await db.flush()
    db.add(
        CreatorPayoutMethod(
            creator_id=cp.id,
            method=PayoutMethodKind.upi,
            holder_name="A",
            upi_vpa_ciphertext=b"\x00" * 32,
            is_active=True,
        )
    )
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()
