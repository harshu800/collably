"""Clerk auth tests — webhook, auto-provision, role selection, require_role."""

from __future__ import annotations

import json
import secrets

import pytest
from sqlalchemy import select

from app.models.user import User, UserRole
from tests.conftest import TESTING_CLERK_LOCAL_SECRET, make_clerk_token

BYPASS_HEADER = "X-Testing-Clerk-Bypass"


def _webhook_body(event_type: str, data: dict) -> bytes:
    return json.dumps({"type": event_type, "data": data}).encode("utf-8")


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_signature_rejected(client):
    body = _webhook_body(
        "user.created", {"id": "user_x", "email_addresses": []}
    )
    r = await client.post(
        "/api/v1/clerk/webhook",
        content=body,
        headers={BYPASS_HEADER: "wrong-secret"},
    )
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_webhook_user_created_upserts_user(client, db):
    clerk_id = f"user_{secrets.token_hex(8)}"
    body = _webhook_body(
        "user.created",
        {
            "id": clerk_id,
            "email_addresses": [{"email_address": "Foo@Example.com"}],
        },
    )
    r = await client.post(
        "/api/v1/clerk/webhook",
        content=body,
        headers={BYPASS_HEADER: TESTING_CLERK_LOCAL_SECRET},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "ok", "type": "user.created"}

    row = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_id))
    ).scalar_one()
    assert row.email == "foo@example.com"
    assert row.role is None
    assert row.is_active is True


@pytest.mark.asyncio
async def test_webhook_user_created_idempotent(client, db):
    clerk_id = f"user_{secrets.token_hex(8)}"
    body = _webhook_body(
        "user.created",
        {
            "id": clerk_id,
            "email_addresses": [{"email_address": "a@example.com"}],
        },
    )
    for _ in range(2):
        r = await client.post(
            "/api/v1/clerk/webhook",
            content=body,
            headers={BYPASS_HEADER: TESTING_CLERK_LOCAL_SECRET},
        )
        assert r.status_code == 200, r.text

    rows = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_id))
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_webhook_user_updated_updates_email(client, db):
    clerk_id = f"user_{secrets.token_hex(8)}"
    created = _webhook_body(
        "user.created",
        {
            "id": clerk_id,
            "email_addresses": [{"email_address": "old@example.com"}],
        },
    )
    r = await client.post(
        "/api/v1/clerk/webhook",
        content=created,
        headers={BYPASS_HEADER: TESTING_CLERK_LOCAL_SECRET},
    )
    assert r.status_code == 200

    updated = _webhook_body(
        "user.updated",
        {
            "id": clerk_id,
            "email_addresses": [{"email_address": "new@example.com"}],
        },
    )
    r = await client.post(
        "/api/v1/clerk/webhook",
        content=updated,
        headers={BYPASS_HEADER: TESTING_CLERK_LOCAL_SECRET},
    )
    assert r.status_code == 200, r.text

    row = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_id))
    ).scalar_one()
    assert row.email == "new@example.com"


@pytest.mark.asyncio
async def test_webhook_user_deleted_deactivates(client, db):
    clerk_id = f"user_{secrets.token_hex(8)}"
    created = _webhook_body(
        "user.created",
        {
            "id": clerk_id,
            "email_addresses": [{"email_address": "dead@example.com"}],
        },
    )
    await client.post(
        "/api/v1/clerk/webhook",
        content=created,
        headers={BYPASS_HEADER: TESTING_CLERK_LOCAL_SECRET},
    )

    deleted = _webhook_body("user.deleted", {"id": clerk_id})
    r = await client.post(
        "/api/v1/clerk/webhook",
        content=deleted,
        headers={BYPASS_HEADER: TESTING_CLERK_LOCAL_SECRET},
    )
    assert r.status_code == 200
    row = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_id))
    ).scalar_one()
    assert row.is_active is False


# ---------------------------------------------------------------------------
# Bearer auto-provisioning + role selection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bearer_auto_provisions_on_first_request(client, db):
    clerk_id = f"user_{secrets.token_hex(8)}"
    email = f"first-{secrets.token_hex(4)}@example.com"
    token = make_clerk_token(clerk_user_id=clerk_id, email=email)

    r = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clerk_user_id"] == clerk_id
    assert body["email"] == email
    assert body["role"] is None

    row = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_id))
    ).scalar_one()
    assert row.role is None


@pytest.mark.asyncio
async def test_set_role_once_happy_path_creator(client):
    clerk_id = f"user_{secrets.token_hex(8)}"
    token = make_clerk_token(
        clerk_user_id=clerk_id, email=f"c-{secrets.token_hex(4)}@example.com"
    )
    auth = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/users/me", headers=auth)
    r = await client.post(
        "/api/v1/users/me/role", json={"role": "creator"}, headers=auth
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "creator"


@pytest.mark.asyncio
async def test_set_role_once_happy_path_brand(client):
    clerk_id = f"user_{secrets.token_hex(8)}"
    token = make_clerk_token(
        clerk_user_id=clerk_id, email=f"b-{secrets.token_hex(4)}@example.com"
    )
    auth = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/users/me", headers=auth)
    r = await client.post(
        "/api/v1/users/me/role", json={"role": "brand"}, headers=auth
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "brand"


@pytest.mark.asyncio
async def test_set_role_rejects_already_set(client):
    clerk_id = f"user_{secrets.token_hex(8)}"
    token = make_clerk_token(
        clerk_user_id=clerk_id, email=f"d-{secrets.token_hex(4)}@example.com"
    )
    auth = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/users/me", headers=auth)
    first = await client.post(
        "/api/v1/users/me/role", json={"role": "creator"}, headers=auth
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/v1/users/me/role", json={"role": "brand"}, headers=auth
    )
    assert second.status_code == 403, second.text


@pytest.mark.asyncio
async def test_set_role_rejects_admin_value(client):
    token = make_clerk_token(
        clerk_user_id=f"user_{secrets.token_hex(8)}",
        email=f"a-{secrets.token_hex(4)}@example.com",
    )
    auth = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/users/me", headers=auth)
    r = await client.post(
        "/api/v1/users/me/role", json={"role": "admin"}, headers=auth
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_set_role_rejects_invalid_value(client):
    token = make_clerk_token(
        clerk_user_id=f"user_{secrets.token_hex(8)}",
        email=f"i-{secrets.token_hex(4)}@example.com",
    )
    auth = {"Authorization": f"Bearer {token}"}
    await client.get("/api/v1/users/me", headers=auth)
    r = await client.post(
        "/api/v1/users/me/role", json={"role": "owner"}, headers=auth
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# Bearer failure paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_without_bearer_401(client):
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_me_bad_token_401(client):
    r = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_require_role_rejects_null_role_user(client, db):
    """A newly-provisioned Clerk user has role=None; brand/creator routes 403."""

    clerk_id = f"user_{secrets.token_hex(8)}"
    token = make_clerk_token(
        clerk_user_id=clerk_id,
        email=f"n-{secrets.token_hex(4)}@example.com",
    )
    auth = {"Authorization": f"Bearer {token}"}
    # Auto-provision.
    await client.get("/api/v1/users/me", headers=auth)
    # Any role-gated route — brand's PATCH /me/profile requires a role.
    r = await client.patch(
        "/api/v1/me/profile",
        json={"company_name": "X"},
        headers=auth,
    )
    assert r.status_code == 403

    row = (
        await db.execute(select(User).where(User.clerk_user_id == clerk_id))
    ).scalar_one()
    assert row.role is None
    # Sanity: role column is nullable, no stale persistence.
    assert isinstance(row.role, type(None)) or isinstance(row.role, UserRole)
