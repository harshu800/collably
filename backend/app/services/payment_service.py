"""Payment service — funding, webhook application, payout initiation.

Writers:
- :func:`initiate_funding` is the single writer that stamps a Collaboration's
  ``funding_status='funding_initiated'`` AND inserts the Payment row.
- :func:`handle_webhook_event` (via :func:`_apply_funding_event`) is the SOLE
  writer that stamps ``funding_status='funding_confirmed'`` and the parent
  Collaboration's ``status='funded'``. It is also the SOLE writer that flips a
  Payout to ``paid`` and bumps the Collaboration to ``completed``.
- :func:`get_funding_status` is the reconciliation-on-read path (design §8.4).
- :func:`initiate_payout` is the only inserter of Payout rows and never logs
  the decrypted beneficiary.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import (
    InvalidWebhookSignature as DomainInvalidWebhookSignature,
)
from app.core.errors import (
    PayoutAlreadyExists,
    PayoutMethodNotVerified,
    PayoutMethodRequired,
    WorkNotApproved,
    WorkNotUnlocked,
)
from app.core.logging import get_logger
from app.core.security import field_decrypt
from app.models.collaboration import (
    Collaboration,
    CollaborationPayoutStatus,
    CollaborationStatus,
    FundingStatus,
)
from app.models.creator_profile import CreatorProfile
from app.models.dispute import Dispute, DisputeResolution, DisputeStatus
from app.models.payment import Payment, PaymentKind, PaymentStatus
from app.models.payout import Payout, PayoutStatus
from app.models.payout_method import CreatorPayoutMethod, PayoutMethodKind
from app.models.refund import Refund
from app.models.webhook_event import PaymentWebhookEvent
from app.providers.payment import (
    BankBeneficiary,
    BeneficiaryRef,
    InvalidWebhookSignature,
    get_payment_provider,
)
from app.services import (
    audit_service,
    collaboration_service,
    notification_service,
    payout_method_service,
)
from app.services._party_lookup import brand_user_for_collab, creator_user_for_collab

_log = get_logger("payment_service")


# ---------------------------------------------------------------------------
# Funding
# ---------------------------------------------------------------------------


async def initiate_funding(
    session: AsyncSession,
    *,
    collaboration: Collaboration,
    actor_user=None,
) -> Payment:
    """Create a provider order and record the Payment row.

    Raises :class:`WorkNotUnlocked(reason='agreement')` if the current
    agreement is not fully signed.
    """

    locked = await collaboration_service.lock_collaboration(session, collaboration.id)
    assert locked is not None
    await collaboration_service.require_current_agreement_fully_signed(session, locked)

    settings = get_settings()
    provider = get_payment_provider(settings)
    order = provider.create_order(
        collaboration_id=locked.id,
        amount_paise=locked.price_paise,
        currency=locked.currency,
        metadata={"collaboration_id": str(locked.id)},
    )

    payment = Payment(
        collaboration_id=locked.id,
        kind=PaymentKind.funding,
        provider=provider.name,
        provider_order_id=order.provider_order_id,
        amount_paise=order.amount_paise,
        currency=order.currency,
        status=PaymentStatus.initiated,
        raw_response=dict(order.raw_response or {}),
    )
    session.add(payment)
    # Flip the collaboration using the named transition (writer rule).
    await collaboration_service.mark_funding_initiated(session, locked)
    locked.funding_status = FundingStatus.funding_initiated
    await session.flush()
    await session.refresh(payment)

    creator_user = await creator_user_for_collab(session, locked)
    payload = {
        "collaboration_id": str(locked.id),
        "payment_id": str(payment.id),
        "amount_paise": payment.amount_paise,
    }
    await notification_service.write_for_user(
        session, user=creator_user, type_="funding.initiated", payload=payload
    )
    await audit_service.write(
        session,
        actor_user_id=actor_user.id if actor_user else None,
        action="funding.initiated",
        target_type="collaboration",
        target_id=locked.id,
        diff=payload,
    )
    return payment


# ---------------------------------------------------------------------------
# Webhook: verify + idempotent persist + apply
# ---------------------------------------------------------------------------


async def handle_webhook_event(
    session: AsyncSession,
    *,
    provider_name: str,
    raw_body: bytes,
    headers: Mapping[str, str],
) -> dict:
    """Verify the signature, persist with ON CONFLICT DO NOTHING, apply.

    Returns a dict ``{status: 'ok'|'duplicate'|'rejected'}``. Raises
    :class:`DomainInvalidWebhookSignature` (HTTP 401) on signature mismatch.
    """

    settings = get_settings()
    if provider_name != settings.payment_provider:
        raise DomainInvalidWebhookSignature(
            "payment provider does not match configuration"
        )
    provider = get_payment_provider(settings)

    try:
        event = provider.verify_webhook(body=raw_body, headers=headers)
    except InvalidWebhookSignature as exc:
        raise DomainInvalidWebhookSignature(str(exc)) from exc

    # Idempotent insert of the webhook event.
    stmt = (
        pg_insert(PaymentWebhookEvent)
        .values(
            provider=provider.name,
            provider_event_id=event.event_id,
            event_type=event.event_type,
            payload=event.payload,
            signature=event.signature,
            verified=True,
            processed_at=None,
        )
        .on_conflict_do_nothing(
            index_elements=["provider", "provider_event_id"],
        )
        .returning(PaymentWebhookEvent.id)
    )
    result = await session.execute(stmt)
    new_id = result.scalar()
    if new_id is None:
        # Duplicate event — the first delivery already got persisted.
        return {"status": "duplicate"}

    # Load the row we just inserted so we can mark processed_at.
    event_row = await session.get(PaymentWebhookEvent, new_id)
    assert event_row is not None

    try:
        await _apply_event(session, event=event_row)
    except _DeferEventApplication:
        # Webhook arrived before the matching Payment/Payout row. Leave
        # processed_at NULL so the reconciliation-on-read path (§8.4) picks
        # it up on the next status read.
        pass
    except _RejectEventApplication as exc:
        event_row.processed_at = datetime.now(UTC)
        await session.flush()
        _log.error(
            "payment_webhook_event_rejected",
            event_id=event_row.provider_event_id,
            provider=event_row.provider,
            reason=str(exc),
        )
        return {"status": "rejected"}
    return {"status": "ok"}


async def _apply_event(
    session: AsyncSession,
    *,
    event: PaymentWebhookEvent,
) -> None:
    """Apply a verified webhook event to the Payment/Payout + Collaboration."""

    payload = event.payload or {}
    event_type = event.event_type

    if event_type in {"funding.succeeded", "funding.failed"}:
        await _apply_funding_event(session, event=event)
    elif event_type in {"payout.paid", "payout.failed"}:
        await _apply_payout_event(session, event=event)
    elif event_type in {"refund.processed", "refund.failed"}:
        await _apply_refund_event(session, event=event)
    else:
        _log.warning("unknown_webhook_event_type", event_type=event_type)
        # Mark processed to avoid replay loops.
        event.processed_at = datetime.now(UTC)
        await session.flush()
        return

    event.processed_at = datetime.now(UTC)
    await session.flush()
    _ = payload  # silence lint for passthrough


async def _apply_funding_event(
    session: AsyncSession,
    *,
    event: PaymentWebhookEvent,
) -> None:
    order_id = (event.payload or {}).get("order_id")
    if not order_id:
        _log.warning("funding_event_missing_order_id", event_id=event.provider_event_id)
        return
    pay = (
        await session.execute(
            select(Payment).where(
                Payment.provider == event.provider,
                Payment.provider_order_id == order_id,
            )
        )
    ).scalar_one_or_none()
    if pay is None:
        # Payment row not yet created — reconciliation-on-read will retry.
        # Leave processed_at NULL by raising a signal the caller catches.
        raise _DeferEventApplication("payment row missing")

    _validate_settlement_amount(
        event=event,
        expected_amount=pay.amount_paise,
        expected_currency=pay.currency,
    )

    collab = await collaboration_service.lock_collaboration(
        session, pay.collaboration_id
    )
    assert collab is not None

    if event.event_type == "funding.failed":
        pay.status = PaymentStatus.failed
        collab.funding_status = FundingStatus.funding_failed
        await session.flush()
        return

    # Success path.
    payment_id = event.payload.get("payment_id")
    if payment_id is not None:
        if not isinstance(payment_id, str) or not payment_id:
            raise _RejectEventApplication("provider payment ID is invalid")
        pay.razorpay_payment_id = payment_id
    pay.status = PaymentStatus.succeeded
    collab.funding_status = FundingStatus.funding_confirmed
    if collab.status == CollaborationStatus.funding_initiated:
        collab.status = CollaborationStatus.funded
    await session.flush()

    brand_user = await brand_user_for_collab(session, collab)
    creator_user = await creator_user_for_collab(session, collab)
    payload = {
        "collaboration_id": str(collab.id),
        "payment_id": str(pay.id),
        "amount_paise": pay.amount_paise,
    }
    for recipient in (brand_user, creator_user):
        await notification_service.write_for_user(
            session, user=recipient, type_="funding.confirmed", payload=payload
        )
    await audit_service.write(
        session,
        actor_user_id=None,
        action="funding.confirmed",
        target_type="collaboration",
        target_id=collab.id,
        diff=payload,
    )


async def _apply_payout_event(
    session: AsyncSession,
    *,
    event: PaymentWebhookEvent,
) -> None:
    payout_id = (event.payload or {}).get("payout_id")
    if not payout_id:
        _log.warning("payout_event_missing_payout_id", event_id=event.provider_event_id)
        return
    payout = (
        await session.execute(
            select(Payout).where(
                Payout.provider == event.provider,
                Payout.provider_payout_id == payout_id,
            )
        )
    ).scalar_one_or_none()
    if payout is None:
        raise _DeferEventApplication("payout row missing")

    _validate_settlement_amount(
        event=event,
        expected_amount=payout.amount_paise,
        expected_currency=payout.currency,
    )

    collab = await collaboration_service.lock_collaboration(
        session, payout.collaboration_id
    )
    assert collab is not None

    if event.event_type == "payout.failed":
        payout.status = PayoutStatus.failed
        collab.payout_status = CollaborationPayoutStatus.failed
        await session.flush()
        return

    payout.status = PayoutStatus.paid
    collab.payout_status = CollaborationPayoutStatus.paid
    if collab.status == CollaborationStatus.approved:
        collab.status = CollaborationStatus.completed
    await session.flush()

    brand_user = await brand_user_for_collab(session, collab)
    creator_user = await creator_user_for_collab(session, collab)
    payload = {
        "collaboration_id": str(collab.id),
        "payout_id": str(payout.id),
        "amount_paise": payout.amount_paise,
    }
    for recipient in (brand_user, creator_user):
        await notification_service.write_for_user(
            session, user=recipient, type_="payout.paid", payload=payload
        )
    await audit_service.write(
        session,
        actor_user_id=None,
        action="payout.paid",
        target_type="collaboration",
        target_id=collab.id,
        diff=payload,
    )


async def _apply_refund_event(
    session: AsyncSession,
    *,
    event: PaymentWebhookEvent,
) -> None:
    payload = event.payload or {}
    refund_id = payload.get("refund_id")
    payment_id = payload.get("payment_id")
    if not refund_id or not payment_id:
        raise _RejectEventApplication("refund event is missing provider references")

    refund_query = (
        await session.execute(
            select(Refund)
            .join(Payment, Payment.id == Refund.payment_id)
            .where(
                Refund.provider_refund_id == refund_id,
                Payment.provider == event.provider,
            )
        )
    ).scalars()
    refund = refund_query.first()
    if refund is None and payload.get("local_refund_id"):
        try:
            local_refund_id = uuid.UUID(payload["local_refund_id"])
        except (ValueError, TypeError, AttributeError):
            local_refund_id = None
        if local_refund_id is not None:
            refund = (
                await session.execute(
                    select(Refund)
                    .join(Payment, Payment.id == Refund.payment_id)
                    .where(
                        Refund.id == local_refund_id,
                        Payment.provider == event.provider,
                    )
                )
            ).scalars().first()
    if refund is None:
        raise _RejectEventApplication("refund event does not match a local refund")

    payment = await session.get(Payment, refund.payment_id)
    assert payment is not None
    if payment.razorpay_payment_id != payment_id:
        raise _RejectEventApplication("refund event payment reference mismatch")
    if refund.provider_refund_id not in {None, refund_id}:
        raise _RejectEventApplication("refund event provider reference mismatch")
    refund.provider_refund_id = refund_id
    _validate_settlement_amount(
        event=event,
        expected_amount=refund.amount_paise,
        expected_currency=refund.currency,
    )

    if event.event_type == "refund.failed" and refund.status == "processed":
        return
    refund.status = (
        "processed" if event.event_type == "refund.processed" else "failed"
    )
    await session.flush()

    processed_amount = (
        await session.execute(
            select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                Refund.payment_id == payment.id,
                Refund.status == "processed",
            )
        )
    ).scalar_one()
    if processed_amount >= payment.amount_paise:
        payment.status = PaymentStatus.refunded
        dispute = (
            await session.execute(
                select(Dispute)
                .join(
                    Collaboration,
                    Collaboration.id == Dispute.collaboration_id,
                )
                .where(
                    Collaboration.id == payment.collaboration_id,
                    Dispute.resolution == DisputeResolution.refund_to_brand,
                    Dispute.status == DisputeStatus.open,
                )
                .with_for_update()
            )
        ).scalars().first()
        if dispute is not None:
            collab = await collaboration_service.lock_collaboration(
                session, payment.collaboration_id
            )
            assert collab is not None
            dispute.status = DisputeStatus.resolved
            collab.status = CollaborationStatus.cancelled
    elif event.event_type == "refund.failed":
        active_refunds = (
            await session.execute(
                select(func.count()).select_from(Refund).where(
                    Refund.payment_id == payment.id,
                    Refund.status.in_(("requested", "pending", "created")),
                )
            )
        ).scalar_one()
        if not active_refunds:
            dispute = (
                await session.execute(
                    select(Dispute)
                    .join(
                        Collaboration,
                        Collaboration.id == Dispute.collaboration_id,
                    )
                    .where(
                        Collaboration.id == payment.collaboration_id,
                        Dispute.resolution == DisputeResolution.refund_to_brand,
                        Dispute.status == DisputeStatus.resolved,
                    )
                    .with_for_update()
                )
            ).scalars().first()
            if dispute is not None:
                collab = await collaboration_service.lock_collaboration(
                    session, payment.collaboration_id
                )
                assert collab is not None
                dispute.status = DisputeStatus.open
                collab.status = CollaborationStatus.disputed
                _log.warning(
                    "provider_refund_failed",
                    dispute_id=str(dispute.id),
                    refund_id=str(refund.id),
                )


def _validate_settlement_amount(
    *,
    event: PaymentWebhookEvent,
    expected_amount: int,
    expected_currency: str,
) -> None:
    payload = event.payload or {}
    amount = payload.get("amount_paise")
    currency = payload.get("currency")
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise _RejectEventApplication("provider amount is missing or invalid")
    if amount != expected_amount:
        raise _RejectEventApplication("provider amount does not match local record")
    if not isinstance(currency, str) or currency.upper() != expected_currency:
        raise _RejectEventApplication("provider currency does not match local record")


class _DeferEventApplication(Exception):
    """Internal signal that an event cannot be applied yet (row missing)."""


class _RejectEventApplication(Exception):
    """Verified event was stored but did not satisfy settlement invariants."""


# ---------------------------------------------------------------------------
# Reconciliation-on-read (§8.4)
# ---------------------------------------------------------------------------


async def get_funding_status(
    session: AsyncSession,
    *,
    collaboration_id: uuid.UUID,
) -> FundingStatus:
    """Reconcile verified webhook events that arrived before the Payment row.

    Called from ``GET /collaborations/{id}/funding`` and anywhere else that
    needs the live funding status.
    """

    collab = await session.get(Collaboration, collaboration_id)
    if collab is None:
        raise LookupError("collaboration not found")

    if collab.funding_status != FundingStatus.funding_initiated:
        return collab.funding_status

    pay = (
        await session.execute(
            select(Payment).where(
                Payment.collaboration_id == collab.id,
                Payment.kind == PaymentKind.funding,
            )
        )
    ).scalar_one_or_none()
    if pay is None:
        return collab.funding_status

    # Load verified, unprocessed events whose payload references our order_id.
    events_stmt = select(PaymentWebhookEvent).where(
        PaymentWebhookEvent.verified.is_(True),
        PaymentWebhookEvent.processed_at.is_(None),
        PaymentWebhookEvent.payload.contains({"order_id": pay.provider_order_id}),
    )
    events = (await session.execute(events_stmt)).scalars().all()
    for ev in events:
        try:
            await _apply_event(session, event=ev)
        except _DeferEventApplication:
            # Still can't apply — try again next read.
            continue
        except _RejectEventApplication as exc:
            ev.processed_at = datetime.now(UTC)
            await session.flush()
            _log.error(
                "payment_webhook_event_rejected",
                event_id=ev.provider_event_id,
                provider=ev.provider,
                reason=str(exc),
            )
            continue
        except Exception as exc:  # noqa: BLE001
            _log.warning(
                "reconciliation_apply_failed",
                event_id=ev.provider_event_id,
                error=repr(exc),
            )
            continue

    # Reload the collaboration — its status may have changed.
    await session.refresh(collab)
    return collab.funding_status


# ---------------------------------------------------------------------------
# Payout
# ---------------------------------------------------------------------------


def _decrypt_beneficiary(
    row: CreatorPayoutMethod,
    *,
    creator_user_id: uuid.UUID,
) -> BeneficiaryRef:
    """Decrypt sensitive fields into an in-memory BeneficiaryRef.

    The returned object MUST NOT be logged. The caller passes it to the
    provider and lets it go out of scope immediately after.
    """

    if row.method == PayoutMethodKind.upi:
        assert row.upi_vpa_ciphertext is not None
        vpa = field_decrypt(row.upi_vpa_ciphertext)
        return BeneficiaryRef(
            creator_user_id=creator_user_id,
            method="upi",
            holder_name=row.holder_name,
            upi_vpa=vpa,
            bank=None,
        )
    assert row.account_number_ciphertext is not None
    assert row.ifsc_ciphertext is not None
    account_number = field_decrypt(row.account_number_ciphertext)
    ifsc = field_decrypt(row.ifsc_ciphertext)
    return BeneficiaryRef(
        creator_user_id=creator_user_id,
        method="bank",
        holder_name=row.holder_name,
        upi_vpa=None,
        bank=BankBeneficiary(account_number=account_number, ifsc=ifsc),
    )


async def initiate_payout(
    session: AsyncSession,
    *,
    collaboration: Collaboration,
) -> Payout:
    """Create a Payout row + call the provider. See design §8.5."""

    locked = await collaboration_service.lock_collaboration(session, collaboration.id)
    assert locked is not None

    if locked.status != CollaborationStatus.approved:
        raise WorkNotApproved()
    if locked.funding_status != FundingStatus.funding_confirmed:
        raise WorkNotUnlocked(
            "Funding must be confirmed before a payout can be initiated.",
            reason="funding",
        )

    existing = (
        await session.execute(
            select(Payout).where(Payout.collaboration_id == locked.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise PayoutAlreadyExists()

    active = await payout_method_service.get_active(
        session, creator_id=locked.creator_id
    )
    if active is None:
        raise PayoutMethodRequired()

    # Resolve CreatorProfile.user_id (required for BeneficiaryRef — v2r2-2).
    creator = await session.get(CreatorProfile, locked.creator_id)
    assert creator is not None

    settings = get_settings()
    provider = get_payment_provider(settings)
    if provider.name != "mock" and not active.verified:
        raise PayoutMethodNotVerified()

    beneficiary = _decrypt_beneficiary(active, creator_user_id=creator.user_id)
    try:
        created = provider.create_payout(
            collaboration_id=locked.id,
            amount_paise=locked.price_paise,
            currency=locked.currency,
            beneficiary=beneficiary,
        )
    finally:
        # Drop the plaintext reference immediately.
        del beneficiary

    snapshot = payout_method_service.non_sensitive_projection(active)
    snapshot = {k: v for k, v in snapshot.items() if k != "id"}

    payout = Payout(
        collaboration_id=locked.id,
        payout_method_id=active.id,
        provider=provider.name,
        provider_payout_id=created.provider_payout_id,
        amount_paise=created.amount_paise,
        currency=created.currency,
        status=PayoutStatus.pending,
        beneficiary_snapshot=snapshot,
    )
    session.add(payout)
    locked.payout_status = CollaborationPayoutStatus.pending
    await session.flush()
    await session.refresh(payout)

    creator_user = await creator_user_for_collab(session, locked)
    payload = {
        "collaboration_id": str(locked.id),
        "payout_id": str(payout.id),
        "amount_paise": payout.amount_paise,
    }
    await notification_service.write_for_user(
        session, user=creator_user, type_="payout.initiated", payload=payload
    )
    await audit_service.write(
        session,
        actor_user_id=None,
        action="payout.initiated",
        target_type="collaboration",
        target_id=locked.id,
        diff=payload,
    )
    return payout
