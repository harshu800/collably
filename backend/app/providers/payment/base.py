"""PaymentProvider contract + dataclasses (design §7.1).

The provider seam is intentionally narrow — it does not know anything about
Collaboration status or the service layer. The service layer composes these
primitive operations into the business flows.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class OrderCreated:
    provider_order_id: str
    amount_paise: int
    currency: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderStatus:
    provider_order_id: str
    status: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerifiedEvent:
    event_id: str
    event_type: str
    payload: dict[str, Any]
    signature: str


@dataclass(frozen=True)
class PayoutCreated:
    provider_payout_id: str
    amount_paise: int
    currency: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PayoutStatus:
    provider_payout_id: str
    status: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RefundCreated:
    provider_refund_id: str
    amount_paise: int
    currency: str
    raw_response: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"


@dataclass(frozen=True)
class BankBeneficiary:
    account_number: str
    ifsc: str


@dataclass(frozen=True)
class BeneficiaryRef:
    # NOTE: ``creator_user_id`` is populated from ``CreatorProfile.user_id``
    # (not ``CreatorProfile.id``) — addresses v2r2-2 NIT.
    creator_user_id: uuid.UUID
    method: Literal["upi", "bank"]
    holder_name: str
    upi_vpa: str | None = None
    bank: BankBeneficiary | None = None


class InvalidWebhookSignature(Exception):
    """Raised by :meth:`PaymentProvider.verify_webhook` on signature mismatch."""


class PaymentProviderError(Exception):
    """Base class for provider-side failures surfaced to the service layer."""


@runtime_checkable
class PaymentProvider(Protocol):
    name: str

    def is_implemented(self) -> bool: ...

    def create_order(
        self,
        *,
        collaboration_id: uuid.UUID,
        amount_paise: int,
        currency: str,
        metadata: Mapping[str, Any],
    ) -> OrderCreated: ...

    def fetch_status(self, *, provider_order_id: str) -> OrderStatus: ...

    def verify_webhook(
        self, *, body: bytes, headers: Mapping[str, str]
    ) -> VerifiedEvent: ...

    def refund(
        self,
        *,
        provider_payment_id: str,
        amount_paise: int,
        idempotency_key: str,
    ) -> RefundCreated: ...

    def create_payout(
        self,
        *,
        collaboration_id: uuid.UUID,
        amount_paise: int,
        currency: str,
        beneficiary: BeneficiaryRef,
    ) -> PayoutCreated: ...

    def fetch_payout_status(self, *, provider_payout_id: str) -> PayoutStatus: ...


__all__ = [
    "BankBeneficiary",
    "BeneficiaryRef",
    "InvalidWebhookSignature",
    "OrderCreated",
    "OrderStatus",
    "PaymentProvider",
    "PaymentProviderError",
    "PayoutCreated",
    "PayoutStatus",
    "RefundCreated",
    "VerifiedEvent",
]
