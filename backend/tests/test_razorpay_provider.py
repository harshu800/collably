from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from app.providers.payment import razorpay as razorpay_provider
from app.providers.payment.base import InvalidWebhookSignature


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> razorpay_provider.RazorpayProvider:
    monkeypatch.setattr(
        razorpay_provider,
        "get_settings",
        lambda: SimpleNamespace(
            razorpay_key_id="key",
            razorpay_key_secret="secret",
            razorpay_webhook_secret="webhook-secret",
            razorpayx_account_number="123456789012",
        ),
    )
    return razorpay_provider.RazorpayProvider()


def _signature(body: bytes) -> str:
    return hmac.new(
        b"webhook-secret", body, hashlib.sha256
    ).hexdigest()


def test_webhook_keeps_provider_event_id_for_idempotency(
    provider: razorpay_provider.RazorpayProvider,
) -> None:
    body = json.dumps({"event": "payment.captured"}).encode()

    event = provider.verify_webhook(
        body=body,
        headers={
            "X-Razorpay-Signature": _signature(body),
            "X-Razorpay-Event-Id": "evt_unique_123",
        },
    )

    assert event.event_id == "evt_unique_123"


def test_funding_event_extracts_payment_id(
    provider: razorpay_provider.RazorpayProvider,
) -> None:
    body = json.dumps(
        {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_123",
                        "order_id": "order_123",
                        "amount": 50000,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            },
        }
    ).encode()

    event = provider.verify_webhook(
        body=body,
        headers={
            "X-Razorpay-Signature": _signature(body),
            "X-Razorpay-Event-Id": "evt_unique_123",
        },
    )

    assert event.payload["payment_id"] == "pay_123"
    assert event.payload["order_id"] == "order_123"
    assert event.payload["amount_paise"] == 50000


def test_webhook_requires_provider_event_id(
    provider: razorpay_provider.RazorpayProvider,
) -> None:
    body = json.dumps({"event": "payment.captured"}).encode()

    with pytest.raises(InvalidWebhookSignature, match="event ID"):
        provider.verify_webhook(
            body=body,
            headers={"X-Razorpay-Signature": _signature(body)},
        )


def test_webhook_rejects_non_object_payload(
    provider: razorpay_provider.RazorpayProvider,
) -> None:
    body = json.dumps(["not", "an", "event"]).encode()

    with pytest.raises(InvalidWebhookSignature, match="JSON object"):
        provider.verify_webhook(
            body=body,
            headers={
                "X-Razorpay-Signature": _signature(body),
                "X-Razorpay-Event-Id": "evt_unique_123",
            },
        )


def test_webhook_rejects_bad_signature(
    provider: razorpay_provider.RazorpayProvider,
) -> None:
    body = json.dumps({"event": "payment.captured"}).encode()

    with pytest.raises(InvalidWebhookSignature, match="signature mismatch"):
        provider.verify_webhook(
            body=body,
            headers={
                "X-Razorpay-Signature": "invalid",
                "X-Razorpay-Event-Id": "evt_unique_123",
            },
        )


def test_refund_uses_provider_idempotency_header(
    provider: razorpay_provider.RazorpayProvider,
) -> None:
    calls = []

    def create_refund(payment_id, payload, **options):
        calls.append((payment_id, payload, options))
        return {
            "id": "rfnd_123",
            "amount": 50000,
            "currency": "INR",
            "status": "pending",
        }

    provider._client.payment.refund = create_refund
    result = provider.refund(
        provider_payment_id="pay_123",
        amount_paise=50000,
        idempotency_key="refund-key-123456",
    )

    assert calls == [
        (
            "pay_123",
            {
                "amount": 50000,
                "notes": {"collably_refund_id": "refund-key-123456"},
            },
            {"headers": {"X-Refund-Idempotency": "refund-key-123456"}},
        )
    ]
    assert result.provider_refund_id == "rfnd_123"
    assert result.status == "pending"


def test_refund_webhook_extracts_payment_and_refund_references(
    provider: razorpay_provider.RazorpayProvider,
) -> None:
    body = json.dumps(
        {
            "event": "refund.processed",
            "payload": {
                "refund": {
                    "entity": {
                        "id": "rfnd_123",
                        "payment_id": "pay_123",
                        "amount": 50000,
                        "currency": "INR",
                        "status": "processed",
                        "notes": {"collably_refund_id": "refund-key-123456"},
                    }
                }
            },
        }
    ).encode()

    event = provider.verify_webhook(
        body=body,
        headers={
            "X-Razorpay-Signature": _signature(body),
            "X-Razorpay-Event-Id": "evt_refund_123",
        },
    )

    assert event.event_type == "refund.processed"
    assert event.payload["refund_id"] == "rfnd_123"
    assert event.payload["local_refund_id"] == "refund-key-123456"
    assert event.payload["payment_id"] == "pay_123"
    assert event.payload["amount_paise"] == 50000
    assert event.payload["currency"] == "INR"
    assert event.payload["status"] == "processed"
