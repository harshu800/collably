"""MockSandboxProvider — deterministic in-process payment provider for dev + tests.

Webhook payload shape is FLAT per design §7.1 so the reconciliation-on-read
JSONB containment query (``payload @> {"order_id": "..."}``) works. The real
Razorpay adapter must flatten nested provider payloads into this same shape
before persisting to :class:`PaymentWebhookEvent`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.payment.base import (
    BeneficiaryRef,
    InvalidWebhookSignature,
    OrderCreated,
    OrderStatus,
    PayoutCreated,
    PayoutStatus,
    RefundCreated,
    VerifiedEvent,
)

_log = get_logger("payments.mock")

SIGNATURE_HEADER = "X-Mock-Signature"


def _mock_secret() -> bytes:
    return get_settings().mock_payment_webhook_secret.encode("utf-8")


def compute_signature(body: bytes) -> str:
    """Compute the HMAC-SHA256 hex digest the mock provider expects."""

    return hmac.new(_mock_secret(), body, hashlib.sha256).hexdigest()


def _mask_upi(vpa: str) -> str:
    if "@" not in vpa:
        return "***"
    local, host = vpa.split("@", 1)
    if len(local) <= 3:
        return f"{local[:1]}***@{host}"
    return f"{local[:3]}***@{host}"


class MockSandboxProvider:
    """In-process mock provider — generates deterministic ids, signs its own events."""

    name = "mock"

    def is_implemented(self) -> bool:
        return True

    # -- Orders --------------------------------------------------------

    def create_order(
        self,
        *,
        collaboration_id: uuid.UUID,
        amount_paise: int,
        currency: str,
        metadata: Mapping[str, Any],
    ) -> OrderCreated:
        order_id = "mock_order_" + uuid.uuid4().hex
        return OrderCreated(
            provider_order_id=order_id,
            amount_paise=amount_paise,
            currency=currency,
            raw_response={
                "collaboration_id": str(collaboration_id),
                "metadata": dict(metadata),
            },
        )

    def fetch_status(self, *, provider_order_id: str) -> OrderStatus:
        return OrderStatus(
            provider_order_id=provider_order_id,
            status="created",
            raw_response={},
        )

    # -- Webhooks ------------------------------------------------------

    def verify_webhook(
        self, *, body: bytes, headers: Mapping[str, str]
    ) -> VerifiedEvent:
        # Header lookup is case-insensitive in HTTP; normalise.
        normalised = {k.lower(): v for k, v in headers.items()}
        signature = normalised.get(SIGNATURE_HEADER.lower(), "")
        expected = compute_signature(body)
        if not hmac.compare_digest(signature, expected):
            raise InvalidWebhookSignature("mock signature mismatch")
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise InvalidWebhookSignature("mock payload not valid JSON") from exc
        event_id = str(payload.get("event_id") or "")
        event_type = str(payload.get("event_type") or "")
        if not event_id or not event_type:
            raise InvalidWebhookSignature("mock payload missing event_id/event_type")
        return VerifiedEvent(
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            signature=signature,
        )

    # -- Payouts -------------------------------------------------------

    def create_payout(
        self,
        *,
        collaboration_id: uuid.UUID,
        amount_paise: int,
        currency: str,
        beneficiary: BeneficiaryRef,
    ) -> PayoutCreated:
        # Log ONLY non-sensitive fields. Never log the decrypted VPA or
        # account number (design §12).
        if beneficiary.method == "upi" and beneficiary.upi_vpa:
            display = _mask_upi(beneficiary.upi_vpa)
        elif beneficiary.method == "bank" and beneficiary.bank:
            last4 = beneficiary.bank.account_number[-4:]
            display = f"****{last4}"
        else:
            display = "***"
        _log.info(
            "[MOCK PAYMENT] create_payout",
            method=beneficiary.method,
            holder_name=beneficiary.holder_name,
            display=display,
            amount_paise=amount_paise,
            currency=currency,
            collaboration_id=str(collaboration_id),
        )
        payout_id = "mock_payout_" + uuid.uuid4().hex
        return PayoutCreated(
            provider_payout_id=payout_id,
            amount_paise=amount_paise,
            currency=currency,
            raw_response={},
        )

    def fetch_payout_status(
        self, *, provider_payout_id: str
    ) -> PayoutStatus:
        return PayoutStatus(
            provider_payout_id=provider_payout_id,
            status="pending",
            raw_response={},
        )

    # -- Refunds -------------------------------------------------------

    def refund(
        self,
        *,
        provider_payment_id: str,
        amount_paise: int,
        idempotency_key: str,
    ) -> RefundCreated:
        refund_id = "mock_refund_" + idempotency_key
        return RefundCreated(
            provider_refund_id=refund_id,
            amount_paise=amount_paise,
            currency="INR",
            raw_response={"provider_payment_id": provider_payment_id},
            status="processed",
        )

    # -- Internal helpers used by the dev-only mock endpoints ----------

    @staticmethod
    def build_funding_event_body(
        *,
        order_id: str,
        amount_paise: int,
        currency: str = "INR",
        status: str = "succeeded",
        event_type: str = "funding.succeeded",
        event_id: str | None = None,
        occurred_at: str | None = None,
    ) -> bytes:
        payload: dict[str, Any] = {
            "event_id": event_id or ("mock_evt_" + uuid.uuid4().hex),
            "event_type": event_type,
            "order_id": order_id,
            "amount_paise": amount_paise,
            "currency": currency,
            "status": status,
            "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def build_payout_event_body(
        *,
        payout_id: str,
        amount_paise: int,
        currency: str = "INR",
        status: str = "paid",
        event_type: str = "payout.paid",
        event_id: str | None = None,
        occurred_at: str | None = None,
    ) -> bytes:
        payload: dict[str, Any] = {
            "event_id": event_id or ("mock_evt_" + uuid.uuid4().hex),
            "event_type": event_type,
            "payout_id": payout_id,
            "amount_paise": amount_paise,
            "currency": currency,
            "status": status,
            "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")
