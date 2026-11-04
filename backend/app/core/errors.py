"""Typed application exceptions and their HTTP response mappings.

Every state transition that can fail raises one of these from the service
layer; the FastAPI exception handlers in :mod:`app.main` translate them into
JSON responses with a stable ``error_code`` string per design §9/§10.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base class for typed domain errors.

    Subclasses set :attr:`status_code` and :attr:`error_code`. Routers do not
    catch these — the global handler in :func:`register_exception_handlers`
    renders them.
    """

    status_code: int = 400
    error_code: str = "domain_error"
    message: str = "Domain error"

    def __init__(self, message: str | None = None, **details) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)


# -- Auth / registration --------------------------------------------------
class EmailTaken(DomainError):
    status_code = 409
    error_code = "email_taken"
    message = "An account with that email already exists."


class InvalidCredentials(DomainError):
    status_code = 401
    error_code = "invalid_credentials"
    message = "Invalid email or password."


class InvalidRefresh(DomainError):
    status_code = 401
    error_code = "invalid_refresh"
    message = "Refresh token is invalid or has been revoked."


# -- Collaboration / deliverable gates ------------------------------------
class WorkNotUnlocked(DomainError):
    status_code = 409
    error_code = "work_not_unlocked"
    message = "Collaboration is not ready for this action."


class SlotLimitReached(DomainError):
    status_code = 409
    error_code = "slot_limit_reached"
    message = "The campaign has already filled every creator slot."


class CampaignLocked(DomainError):
    status_code = 409
    error_code = "campaign_locked"
    message = "Material campaign fields cannot be changed after an application exists."


class RevisionLimitReached(DomainError):
    status_code = 409
    error_code = "revision_limit_reached"
    message = "Revision limit for this deliverable has been reached."


class InvalidStateTransition(DomainError):
    status_code = 409
    error_code = "invalid_state_transition"
    message = "Illegal state transition."


class PaymentProviderError(DomainError):
    status_code = 502
    error_code = "payment_provider_error"
    message = "Payment provider error."


# -- Payout --------------------------------------------------------------
class PayoutMethodRequired(DomainError):
    status_code = 409
    error_code = "payout_method_required"
    message = "The creator has not set an active payout method."


class PayoutMethodNotVerified(DomainError):
    status_code = 409
    error_code = "payout_method_not_verified"
    message = "The creator's payout method must pass provider verification before payout."


class PayoutAlreadyExists(DomainError):
    status_code = 409
    error_code = "payout_already_exists"
    message = "A payout has already been created for this collaboration."


class WorkNotApproved(DomainError):
    status_code = 409
    error_code = "work_not_approved"
    message = "Collaboration must be approved before a payout can be initiated."


# -- Webhooks -----------------------------------------------------------
class InvalidWebhookSignature(DomainError):
    status_code = 401
    error_code = "invalid_webhook_signature"
    message = "Webhook signature verification failed."


class DuplicateWebhookEvent(DomainError):
    """Raised internally to signal idempotent duplicate; handler returns 200."""

    status_code = 200
    error_code = "duplicate"
    message = "Webhook event already processed."


# -----------------------------------------------------------------------


async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    payload: dict = {"error_code": exc.error_code, "message": exc.message}
    if exc.details:
        payload["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=payload)


def register_exception_handlers(app) -> None:  # noqa: ANN001
    """Wire the typed error -> JSON response mapping onto a FastAPI app."""

    app.add_exception_handler(DomainError, _domain_error_handler)
