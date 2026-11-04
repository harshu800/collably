"""Razorpay provider — production payment adapter for Orders, Payments, and RazorpayX Payouts.

Webhook contract: Razorpay emits nested JSON (``{event, payload: {payment: {...}}}``).
This adapter flattens that into the shape documented in design §7.1
(``{event_id, event_type, order_id|payout_id, amount_paise, currency, status, occurred_at}``)
before persisting to :class:`PaymentWebhookEvent`, so the reconciliation-on-read JSONB
query works provider-agnostically.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import razorpay

from app.core.config import get_settings
from app.core.logging import get_logger
from app.providers.payment.base import (
    BeneficiaryRef,
    InvalidWebhookSignature,
    OrderCreated,
    OrderStatus,
    PaymentProviderError,
    PayoutCreated,
    PayoutStatus,
    RefundCreated,
    VerifiedEvent,
)

_log = get_logger("payments.razorpay")

SIGNATURE_HEADER = "X-Razorpay-Signature"
EVENT_ID_HEADER = "X-Razorpay-Event-Id"


def _mask_upi(vpa: str) -> str:
    """Mask UPI VPA for logging — same pattern as mock provider."""
    if "@" not in vpa:
        return "***"
    local, host = vpa.split("@", 1)
    if len(local) <= 3:
        return f"{local[:1]}***@{host}"
    return f"{local[:3]}***@{host}"


class RazorpayProvider:
    """Production Razorpay adapter for Orders API, Payments API, and RazorpayX Payouts."""

    name = "razorpay"

    def __init__(self) -> None:
        settings = get_settings()
        self._client = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )
        self._webhook_secret = settings.razorpay_webhook_secret
        self._razorpayx_account_number = settings.razorpayx_account_number

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
        """Create a Razorpay order using the Orders API."""
        try:
            response = self._client.order.create(
                {
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": str(collaboration_id),
                    "notes": dict(metadata),
                }
            )
            _log.info(
                "razorpay_order_created",
                order_id=response["id"],
                amount_paise=amount_paise,
                currency=currency,
            )
            return OrderCreated(
                provider_order_id=response["id"],
                amount_paise=response["amount"],
                currency=response["currency"],
                raw_response=response,
            )
        except Exception as exc:
            _log.error("razorpay_create_order_failed", error=repr(exc))
            raise PaymentProviderError(str(exc)) from exc

    def fetch_status(self, *, provider_order_id: str) -> OrderStatus:
        """Fetch the status of a Razorpay order."""
        try:
            response = self._client.order.fetch(provider_order_id)
            return OrderStatus(
                provider_order_id=provider_order_id,
                status=response["status"],
                raw_response=response,
            )
        except Exception as exc:
            _log.error(
                "razorpay_fetch_status_failed",
                order_id=provider_order_id,
                error=repr(exc),
            )
            raise PaymentProviderError(str(exc)) from exc

    # -- Webhooks ------------------------------------------------------

    def verify_webhook(
        self, *, body: bytes, headers: Mapping[str, str]
    ) -> VerifiedEvent:
        """Verify Razorpay webhook signature and flatten nested payload.

        Razorpay sends X-Razorpay-Signature header with HMAC-SHA256 hex digest.
        Webhook payloads are nested; we flatten them to match the mock provider's
        shape for JSONB containment queries.
        """
        # Case-insensitive header lookup
        normalised = {k.lower(): v for k, v in headers.items()}
        signature = normalised.get(SIGNATURE_HEADER.lower(), "")

        # Compute expected HMAC-SHA256
        expected = hmac.new(
            self._webhook_secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            raise InvalidWebhookSignature("razorpay signature mismatch")

        try:
            raw_payload = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise InvalidWebhookSignature("razorpay payload not valid JSON") from exc
        if not isinstance(raw_payload, dict):
            raise InvalidWebhookSignature("razorpay payload must be a JSON object")

        # Extract event info from Razorpay's nested structure
        event_name = raw_payload.get("event", "")
        if not event_name:
            raise InvalidWebhookSignature("razorpay payload missing 'event' field")

        event_id = normalised.get(EVENT_ID_HEADER.lower(), "").strip()
        if not event_id or len(event_id) > 128:
            raise InvalidWebhookSignature("razorpay event ID header missing or invalid")

        # Map Razorpay event names to our event_type
        event_type = self._map_event_type(event_name)

        # Flatten the nested payload based on event type
        flat_payload = self._flatten_payload(raw_payload, event_name)

        return VerifiedEvent(
            event_id=event_id,
            event_type=event_type,
            payload=flat_payload,
            signature=signature,
        )

    def _map_event_type(self, razorpay_event: str) -> str:
        """Map Razorpay event names to our internal event types."""
        mapping = {
            "payment.captured": "funding.succeeded",
            "payment.failed": "funding.failed",
            "order.paid": "funding.succeeded",
            "payout.processed": "payout.paid",
            "payout.reversed": "payout.failed",
            "payout.failed": "payout.failed",
            "refund.processed": "refund.processed",
            "refund.failed": "refund.failed",
        }
        return mapping.get(razorpay_event, razorpay_event)

    def _flatten_payload(
        self, raw_payload: dict[str, Any], event_name: str
    ) -> dict[str, Any]:
        """Flatten Razorpay's nested payload to match mock provider shape.

        Returns: {event_id, event_type, order_id|payout_id, amount_paise, currency, status, occurred_at}
        """
        occurred_at = datetime.now(UTC).isoformat()

        if event_name.startswith("refund."):
            refund_entity = (
                raw_payload.get("payload", {}).get("refund", {}).get("entity", {})
            )
            return {
                "refund_id": refund_entity.get("id", ""),
                "local_refund_id": (
                    refund_entity.get("notes", {}).get("collably_refund_id", "")
                    if isinstance(refund_entity.get("notes"), dict)
                    else ""
                ),
                "payment_id": refund_entity.get("payment_id", ""),
                "amount_paise": refund_entity.get("amount", 0),
                "currency": refund_entity.get("currency", "INR"),
                "status": refund_entity.get("status", ""),
                "occurred_at": occurred_at,
            }

        # Payment events (funding)
        if event_name.startswith("payment.") or event_name.startswith("order."):
            payment_entity = raw_payload.get("payload", {}).get("payment", {}).get("entity", {})
            if not payment_entity and event_name.startswith("order."):
                order_entity = raw_payload.get("payload", {}).get("order", {}).get("entity", {})
                return {
                    "order_id": order_entity.get("id", ""),
                    "amount_paise": order_entity.get("amount", 0),
                    "currency": order_entity.get("currency", "INR"),
                    "status": order_entity.get("status", ""),
                    "payment_id": "",
                    "occurred_at": occurred_at,
                }
            return {
                "order_id": payment_entity.get("order_id", ""),
                "amount_paise": payment_entity.get("amount", 0),
                "currency": payment_entity.get("currency", "INR"),
                "status": payment_entity.get("status", ""),
                "payment_id": payment_entity.get("id", ""),
                "occurred_at": occurred_at,
            }

        # Payout events
        if event_name.startswith("payout."):
            payout_entity = raw_payload.get("payload", {}).get("payout", {}).get("entity", {})
            return {
                "payout_id": payout_entity.get("id", ""),
                "amount_paise": payout_entity.get("amount", 0),
                "currency": payout_entity.get("currency", "INR"),
                "status": payout_entity.get("status", ""),
                "occurred_at": occurred_at,
            }

        # Unknown event type — return minimal structure
        _log.warning("unknown_razorpay_event_type", event=event_name)
        return {
            "status": "",
            "occurred_at": occurred_at,
        }

    # -- Refunds -------------------------------------------------------

    def refund(
        self,
        *,
        provider_payment_id: str,
        amount_paise: int,
        idempotency_key: str,
    ) -> RefundCreated:
        """Create an idempotent refund using the Razorpay Refunds API."""
        try:
            response = self._client.payment.refund(
                provider_payment_id,
                {
                    "amount": amount_paise,
                    "notes": {"collably_refund_id": idempotency_key},
                },
                headers={"X-Refund-Idempotency": idempotency_key},
            )
            _log.info(
                "razorpay_refund_created",
                refund_id=response["id"],
                payment_id=provider_payment_id,
                amount_paise=amount_paise,
            )
            return RefundCreated(
                provider_refund_id=response["id"],
                amount_paise=response["amount"],
                currency=response["currency"],
                raw_response=response,
                status=response["status"],
            )
        except Exception as exc:
            _log.error(
                "razorpay_refund_failed",
                payment_id=provider_payment_id,
                error=repr(exc),
            )
            raise PaymentProviderError(str(exc)) from exc

    # -- Payouts -------------------------------------------------------

    def create_payout(
        self,
        *,
        collaboration_id: uuid.UUID,
        amount_paise: int,
        currency: str,
        beneficiary: BeneficiaryRef,
    ) -> PayoutCreated:
        """Create a RazorpayX payout (Contact + Fund Account + Payout).

        Never log decrypted beneficiary fields (upi_vpa, account_number).
        """
        # Log only non-sensitive fields
        if beneficiary.method == "upi" and beneficiary.upi_vpa:
            display = _mask_upi(beneficiary.upi_vpa)
        elif beneficiary.method == "bank" and beneficiary.bank:
            last4 = beneficiary.bank.account_number[-4:]
            display = f"****{last4}"
        else:
            display = "***"

        _log.info(
            "razorpay_payout_initiating",
            method=beneficiary.method,
            holder_name=beneficiary.holder_name,
            display=display,
            amount_paise=amount_paise,
            currency=currency,
            collaboration_id=str(collaboration_id),
        )

        try:
            # Step 1: Create Contact
            contact_response = self._client.contact.create(
                {
                    "name": beneficiary.holder_name,
                    "type": "self",
                    "reference_id": str(beneficiary.creator_user_id),
                }
            )
            contact_id = contact_response["id"]

            # Step 2: Create Fund Account
            if beneficiary.method == "upi":
                assert beneficiary.upi_vpa is not None
                fa_payload = {
                    "contact_id": contact_id,
                    "account_type": "vpa",
                    "vpa": {"address": beneficiary.upi_vpa},
                }
            else:  # bank
                assert beneficiary.bank is not None
                fa_payload = {
                    "contact_id": contact_id,
                    "account_type": "bank_account",
                    "bank_account": {
                        "name": beneficiary.holder_name,
                        "ifsc": beneficiary.bank.ifsc,
                        "account_number": beneficiary.bank.account_number,
                    },
                }

            fund_account_response = self._client.fund_account.create(fa_payload)
            fund_account_id = fund_account_response["id"]

            # Step 3: Create Payout
            if (
                not self._razorpayx_account_number
                or self._razorpayx_account_number == "YOUR_RAZORPAYX_ACCOUNT_NUMBER"
            ):
                raise PaymentProviderError(
                    "RAZORPAYX_ACCOUNT_NUMBER is not configured."
                )
            payout_response = self._client.payout.create(
                {
                    "account_number": self._razorpayx_account_number,
                    "fund_account_id": fund_account_id,
                    "amount": amount_paise,
                    "currency": currency,
                    "mode": "IMPS" if beneficiary.method == "upi" else "NEFT",
                    "purpose": "payout",
                    "queue_if_low_balance": True,
                    "reference_id": str(collaboration_id),
                    "narration": f"Collab {collaboration_id}",
                }
            )

            _log.info(
                "razorpay_payout_created",
                payout_id=payout_response["id"],
                contact_id=contact_id,
                fund_account_id=fund_account_id,
            )

            return PayoutCreated(
                provider_payout_id=payout_response["id"],
                amount_paise=payout_response["amount"],
                currency=payout_response["currency"],
                raw_response={
                    "contact_id": contact_id,
                    "fund_account_id": fund_account_id,
                    **payout_response,
                },
            )
        except Exception as exc:
            _log.error("razorpay_payout_failed", error=repr(exc))
            raise PaymentProviderError(str(exc)) from exc

    def fetch_payout_status(
        self, *, provider_payout_id: str
    ) -> PayoutStatus:
        """Fetch the status of a RazorpayX payout."""
        try:
            response = self._client.payout.fetch(provider_payout_id)
            # Map Razorpay status to our enum
            razorpay_status = response["status"]
            mapped_status = self._map_payout_status(razorpay_status)

            return PayoutStatus(
                provider_payout_id=provider_payout_id,
                status=mapped_status,
                raw_response=response,
            )
        except Exception as exc:
            _log.error(
                "razorpay_fetch_payout_status_failed",
                payout_id=provider_payout_id,
                error=repr(exc),
            )
            raise PaymentProviderError(str(exc)) from exc

    def _map_payout_status(self, razorpay_status: str) -> str:
        """Map RazorpayX payout status to our internal status names."""
        mapping = {
            "processing": "pending",
            "processed": "paid",
            "reversed": "failed",
            "cancelled": "failed",
        }
        return mapping.get(razorpay_status, razorpay_status)
