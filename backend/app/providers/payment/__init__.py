"""Payment provider factory. Reads ``settings.payment_provider``.

The startup production check parameterises its "is this provider a stub?"
guard on :meth:`PaymentProvider.is_implemented`, so a future real Razorpay
adapter self-removes the guard once it flips the sentinel to ``True``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.providers.payment.base import (
    BankBeneficiary,
    BeneficiaryRef,
    InvalidWebhookSignature,
    OrderCreated,
    OrderStatus,
    PaymentProvider,
    PaymentProviderError,
    PayoutCreated,
    PayoutStatus,
    RefundCreated,
    VerifiedEvent,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.core.config import Settings


def get_payment_provider(settings: Settings) -> PaymentProvider:
    name = settings.payment_provider
    if name == "razorpay":
        from app.providers.payment.razorpay import RazorpayProvider

        return RazorpayProvider()
    from app.providers.payment.mock import MockSandboxProvider

    return MockSandboxProvider()


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
    "get_payment_provider",
]
