"""Dispute service — open + admin resolve.

Resolution semantics (design §17 / v2r2-4):
- ``release_to_creator``: run the same payout code path as approval; the
  collaboration ends in ``completed`` once the mock payout webhook lands.
- ``refund_to_brand``: create a :class:`Refund` row against the Payment and
  flip the collaboration to ``cancelled``.
- ``split``: bookkeeping only — record ``split_bps``, flip the collaboration
  to ``completed``, write audit. No new money moves.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    DomainError,
    InvalidStateTransition,
)
from app.core.errors import (
    PaymentProviderError as DomainPaymentProviderError,
)
from app.core.logging import get_logger
from app.models.brand_profile import BrandProfile
from app.models.collaboration import (
    Collaboration,
    CollaborationPayoutStatus,
    CollaborationStatus,
)
from app.models.creator_profile import CreatorProfile
from app.models.dispute import Dispute, DisputeResolution, DisputeStatus
from app.models.payment import Payment, PaymentKind, PaymentStatus
from app.models.refund import Refund
from app.models.user import User, UserRole
from app.providers.payment import (
    PaymentProviderError as ProviderPaymentError,
)
from app.providers.payment import (
    get_payment_provider,
)
from app.services import (
    audit_service,
    collaboration_service,
    notification_service,
    payment_service,
)

_log = get_logger("dispute_service")


class DisputeNotFound(DomainError):
    status_code = 404
    error_code = "dispute_not_found"
    message = "Dispute not found."


class DisputeAlreadyResolved(DomainError):
    status_code = 409
    error_code = "dispute_already_resolved"
    message = "Dispute has already been resolved."


class SplitBpsRequired(DomainError):
    status_code = 422
    error_code = "split_bps_required"
    message = "split_bps is required when resolution='split' and must be 0..10000."


# ---------------------------------------------------------------------------
# Helpers to resolve the two counterparty users for notifications
# ---------------------------------------------------------------------------


async def _brand_user(session: AsyncSession, collab: Collaboration) -> User | None:
    bp = await session.get(BrandProfile, collab.brand_id)
    if bp is None:
        return None
    return await session.get(User, bp.user_id)


async def _creator_user(
    session: AsyncSession, collab: Collaboration
) -> User | None:
    cp = await session.get(CreatorProfile, collab.creator_id)
    if cp is None:
        return None
    return await session.get(User, cp.user_id)


# ---------------------------------------------------------------------------
# Open
# ---------------------------------------------------------------------------


async def open(
    session: AsyncSession,
    *,
    collaboration: Collaboration,
    user: User,
    reason: str,
) -> Dispute:
    """A party opens a dispute. Flips the collab to ``disputed`` + notifies."""

    locked = await collaboration_service.lock_collaboration(
        session, collaboration.id
    )
    assert locked is not None

    if locked.status in {
        CollaborationStatus.completed,
        CollaborationStatus.cancelled,
    }:
        raise InvalidStateTransition(
            f"Cannot dispute a {locked.status.value} collaboration.",
            source=locked.status.value,
            target=CollaborationStatus.disputed.value,
        )

    # Only participants may open a dispute.
    if user.role not in {UserRole.brand, UserRole.creator, UserRole.admin}:
        raise InvalidStateTransition("Only a participant may open a dispute.")

    dispute = Dispute(
        collaboration_id=locked.id,
        opened_by_user_id=user.id,
        reason=reason,
        status=DisputeStatus.open,
    )
    session.add(dispute)
    locked.status = CollaborationStatus.disputed
    await session.flush()
    await session.refresh(dispute)

    brand_user = await _brand_user(session, locked)
    creator_user = await _creator_user(session, locked)
    payload = {
        "collaboration_id": str(locked.id),
        "dispute_id": str(dispute.id),
        "opened_by": str(user.id),
        "reason": reason,
    }
    # Notify the counterparty + opener. (Admins see it via /admin/disputes.)
    for recipient in (brand_user, creator_user):
        await notification_service.write_for_user(
            session,
            user=recipient,
            type_="dispute.opened",
            payload=payload,
        )

    await audit_service.write(
        session,
        actor_user_id=user.id,
        action="dispute.opened",
        target_type="dispute",
        target_id=dispute.id,
        diff=payload,
    )
    return dispute


# ---------------------------------------------------------------------------
# Resolve (admin-only)
# ---------------------------------------------------------------------------


async def resolve(
    session: AsyncSession,
    *,
    dispute_id: uuid.UUID,
    admin_user: User,
    resolution: str,
    split_bps: int | None = None,
) -> Dispute:
    if admin_user.role != UserRole.admin:
        raise InvalidStateTransition("Only an admin can resolve a dispute.")

    dispute = (
        await session.execute(
            select(Dispute)
            .where(Dispute.id == dispute_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if dispute is None:
        raise DisputeNotFound()
    if dispute.status != DisputeStatus.open:
        raise DisputeAlreadyResolved()

    try:
        resolution_enum = DisputeResolution(resolution)
    except ValueError as exc:
        raise InvalidStateTransition(
            f"Unknown resolution {resolution!r}."
        ) from exc

    if resolution_enum == DisputeResolution.split:
        if split_bps is None or not (0 <= split_bps <= 10_000):
            raise SplitBpsRequired()
    else:
        split_bps = None

    collab = await collaboration_service.lock_collaboration(
        session, dispute.collaboration_id
    )
    assert collab is not None

    now = datetime.now(UTC)

    resulting_status: str
    if resolution_enum == DisputeResolution.release_to_creator:
        dispute.resolution = resolution_enum
        dispute.split_bps = split_bps
        dispute.resolved_by_admin_id = admin_user.id
        dispute.resolved_at = now
        dispute.status = DisputeStatus.resolved
        # Treat the collaboration as approved so the payout path can run.
        collab.status = CollaborationStatus.approved
        await session.flush()
        try:
            await payment_service.initiate_payout(session, collaboration=collab)
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "dispute_release_payout_failed",
                dispute_id=str(dispute.id),
                error=repr(exc),
            )
        await session.refresh(collab)
        resulting_status = collab.status.value
    elif resolution_enum == DisputeResolution.refund_to_brand:
        payment = (
            await session.execute(
                select(Payment)
                .where(Payment.collaboration_id == collab.id)
                .where(Payment.kind == PaymentKind.funding)
                .order_by(Payment.created_at.desc())
            )
        ).scalars().first()
        if payment is None or payment.status != PaymentStatus.succeeded:
            raise InvalidStateTransition(
                "A successful funding payment is required before issuing a refund."
            )

        settings = get_settings()
        if settings.payment_provider == "mock":
            refund = Refund(
                payment_id=payment.id,
                amount_paise=payment.amount_paise,
                currency=payment.currency,
                status="processed",
            )
            session.add(refund)
            payment.status = PaymentStatus.refunded
        else:
            if (
                payment.provider != settings.payment_provider
                or not payment.razorpay_payment_id
            ):
                raise InvalidStateTransition(
                    "The successful payment is missing its configured provider "
                    "payment reference."
                )

            refund = (
                await session.execute(
                    select(Refund)
                    .where(Refund.payment_id == payment.id)
                    .order_by(Refund.created_at.desc())
                    .with_for_update()
                )
            ).scalars().first()
            if refund is None or refund.status == "failed":
                refund = Refund(
                    payment_id=payment.id,
                    amount_paise=payment.amount_paise,
                    currency=payment.currency,
                    status="requested",
                )
                session.add(refund)
                await session.flush()
                # Persist the stable refund ID before the network call. Razorpay
                # uses it as the idempotency key if this request must be retried.
                await session.commit()
            elif refund.status == "processed":
                payment.status = PaymentStatus.refunded
            elif refund.status not in {"requested", "pending", "created"}:
                raise InvalidStateTransition(
                    f"Refund cannot be retried from status {refund.status!r}."
                )

            if refund.status != "processed":
                provider = get_payment_provider(settings)
                try:
                    created = provider.refund(
                        provider_payment_id=payment.razorpay_payment_id,
                        amount_paise=payment.amount_paise,
                        idempotency_key=str(refund.id),
                    )
                except ProviderPaymentError as exc:
                    raise DomainPaymentProviderError() from exc

                refund = (
                    await session.execute(
                        select(Refund)
                        .where(Refund.id == refund.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                ).scalar_one()
                await session.refresh(payment)
                if refund.status == "failed":
                    raise DomainPaymentProviderError(
                        "The payment provider could not process the refund."
                    )
                if refund.status != "processed" and (
                    not created.provider_refund_id
                    or created.amount_paise != payment.amount_paise
                    or created.currency.upper() != payment.currency
                    or created.status not in {"pending", "processed", "failed"}
                    or (
                        refund.provider_refund_id is not None
                        and refund.provider_refund_id != created.provider_refund_id
                    )
                ):
                    raise DomainPaymentProviderError(
                        "The payment provider returned an invalid refund response."
                    )
                if refund.status != "processed":
                    refund.provider_refund_id = created.provider_refund_id
                    refund.status = created.status
                if refund.status == "processed":
                    payment.status = PaymentStatus.refunded
                elif refund.status == "failed":
                    await session.flush()
                    await session.commit()
                    raise DomainPaymentProviderError(
                        "The payment provider could not process the refund."
                    )

            dispute = (
                await session.execute(
                    select(Dispute)
                    .where(Dispute.id == dispute.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalar_one()
            if dispute.status != DisputeStatus.open:
                if (
                    dispute.status == DisputeStatus.resolved
                    and dispute.resolution == DisputeResolution.refund_to_brand
                ):
                    return dispute
                raise DisputeAlreadyResolved()

        dispute.resolution = resolution_enum
        dispute.split_bps = None
        dispute.resolved_by_admin_id = admin_user.id
        dispute.resolved_at = now
        dispute.status = DisputeStatus.resolved
        collab.status = CollaborationStatus.cancelled
        collab.payout_status = CollaborationPayoutStatus.none
        await session.flush()
        resulting_status = collab.status.value
    else:  # split — bookkeeping only
        dispute.resolution = resolution_enum
        dispute.split_bps = split_bps
        dispute.resolved_by_admin_id = admin_user.id
        dispute.resolved_at = now
        dispute.status = DisputeStatus.resolved
        collab.status = CollaborationStatus.completed
        await session.flush()
        resulting_status = collab.status.value

    await session.flush()
    await session.refresh(dispute)

    brand_user = await _brand_user(session, collab)
    creator_user = await _creator_user(session, collab)
    payload = {
        "collaboration_id": str(collab.id),
        "dispute_id": str(dispute.id),
        "resolution": resolution_enum.value,
        "split_bps": split_bps,
        "collaboration_status": resulting_status,
    }
    for recipient in (brand_user, creator_user):
        await notification_service.write_for_user(
            session,
            user=recipient,
            type_="dispute.resolved",
            payload=payload,
        )

    await audit_service.write(
        session,
        actor_user_id=admin_user.id,
        action="dispute.resolved",
        target_type="dispute",
        target_id=dispute.id,
        diff=payload,
    )
    return dispute
