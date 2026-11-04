"""CreatorPayoutMethod schema + IDOR + non-sensitive projection tests."""

from __future__ import annotations

import httpx
import pytest

from tests.helpers import onboard_creator, register


@pytest.mark.asyncio
async def test_put_upi_minimum_fields(
    client: httpx.AsyncClient, creator_user: dict
) -> None:
    await onboard_creator(client, creator_user)
    r = await client.put(
        "/api/v1/me/payout-method",
        json={"method": "upi", "holder_name": "C H", "upi_vpa": "user@okbank"},
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["method"] == "upi"
    assert body["holder_name"] == "C H"
    assert body["upi_vpa_masked"] is not None
    assert "okbank" in body["upi_vpa_masked"]
    assert body["account_number_last4"] is None
    assert body["verified"] is False


@pytest.mark.asyncio
async def test_put_bank_minimum_fields(
    client: httpx.AsyncClient, creator_user: dict
) -> None:
    await onboard_creator(client, creator_user)
    r = await client.put(
        "/api/v1/me/payout-method",
        json={
            "method": "bank",
            "holder_name": "C Holder",
            "account_number": "1234567890",
            "ifsc": "HDFC0001234",
        },
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["method"] == "bank"
    assert body["account_number_last4"] == "7890"
    assert body["upi_vpa_masked"] is None


@pytest.mark.asyncio
async def test_invalid_upi_vpa_rejects(
    client: httpx.AsyncClient, creator_user: dict
) -> None:
    await onboard_creator(client, creator_user)
    r = await client.put(
        "/api/v1/me/payout-method",
        json={"method": "upi", "holder_name": "X", "upi_vpa": "not-a-vpa"},
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_invalid_ifsc_rejects(
    client: httpx.AsyncClient, creator_user: dict
) -> None:
    await onboard_creator(client, creator_user)
    r = await client.put(
        "/api/v1/me/payout-method",
        json={
            "method": "bank",
            "holder_name": "X",
            "account_number": "1234567890",
            "ifsc": "bad",
        },
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_missing_returns_404(
    client: httpx.AsyncClient, creator_user: dict
) -> None:
    await onboard_creator(client, creator_user)
    r = await client.get(
        "/api/v1/me/payout-method", headers=creator_user["auth_header"]
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_response_never_contains_sensitive_fields(
    client: httpx.AsyncClient, creator_user: dict
) -> None:
    await onboard_creator(client, creator_user)
    r = await client.put(
        "/api/v1/me/payout-method",
        json={
            "method": "bank",
            "holder_name": "X",
            "account_number": "1234567890",
            "ifsc": "HDFC0001234",
        },
        headers=creator_user["auth_header"],
    )
    body = r.json()
    for key in ("account_number", "ifsc", "upi_vpa"):
        assert key not in body


@pytest.mark.asyncio
async def test_cannot_read_another_creators_method_idor(
    client: httpx.AsyncClient, creator_user: dict
) -> None:
    # Creator A sets a method.
    await onboard_creator(client, creator_user)
    r = await client.put(
        "/api/v1/me/payout-method",
        json={"method": "upi", "holder_name": "AA", "upi_vpa": "aa@okbank"},
        headers=creator_user["auth_header"],
    )
    assert r.status_code == 200
    # Creator B reads /me/payout-method — only their own.
    other = await register(client, "creator")
    await onboard_creator(client, other)
    r2 = await client.get(
        "/api/v1/me/payout-method", headers=other["auth_header"]
    )
    assert r2.status_code == 404
