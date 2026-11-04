"""ENABLE_MOCK_PAYMENT_ENDPOINTS=false → mock endpoints return 404."""

from __future__ import annotations

import httpx
import pytest

from app.core.config import get_settings


@pytest.mark.asyncio
async def test_mock_endpoints_404_when_disabled(client: httpx.AsyncClient) -> None:
    settings = get_settings()
    original = settings.enable_mock_payment_endpoints
    settings.enable_mock_payment_endpoints = False
    try:
        r1 = await client.post("/api/v1/payments/mock/confirm/mock_order_x")
        assert r1.status_code == 404
        r2 = await client.post("/api/v1/payments/mock/confirm-payout/mock_payout_x")
        assert r2.status_code == 404
    finally:
        settings.enable_mock_payment_endpoints = original
