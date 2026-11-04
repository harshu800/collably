"""Deliverable service — submit, approve, request_revision, open_dispute.

All transitions take ``FOR UPDATE`` on the Collaboration and check the
current agreement's signatures and funding gate.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    InvalidStateTransition,
    PayoutMethodRequired,
    RevisionLimitReached,
    WorkNotUnlocked,
)
from app.core.logging import get_logger
from app.models.collaboration import (
    Collaboration,
    CollaborationStatus,
    FundingStatus,
)
from app.models.deliverable import (
    Deliverable,
    DeliverableKind,
    DeliverableStatus,
)
from app.models.revision import DeliverableRevision
from app.models.user import User
from app.services import (
    audit_service,
    collaboration_service,
    dispute_service,
    notification_service,
    payment_service,
)
from app.services._party_lookup import (
    brand_user_for_collab,
    creator_user_for_collab,
)
from app.services.collaboration_service import (
    require_current_agreement_fully_signed,
)

_log = get_logger("deliverable_service")

_SUBMIT_ALLOWED_STATUSES = {
    CollaborationStatus.funded,
    CollaborationStatus.in_progress,
    CollaborationStatus.in_review,
}


async def _spec_coverage(
    session: AsyncSession,
    *,
    collaboration_id: uuid.UUID,
    spec_items: int,
    acceptable_statuses: set[DeliverableStatus],
) -> bool:
    """Return True if every spec index 0..spec_items-1 has at least one
    Deliverable with status in ``acceptable_statuses``.
    """

    if spec_items == 0:
        return False
    rows = (
        await session.execute(
            select(Deliverable.spec_index).where(
                Deliverable.collaboration_id == collaboration_id,
                Deliverable.status.in_(acceptable_statuses),
            )
        )
    ).all()
    covered = {int(r[0]) for r in rows}
    return all(i in covered for i in range(spec_items))


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


async def submit(
    session: AsyncSession,
    *,
    collaboration: Collaboration,
    user: User,
    payload: dict[str, Any],
) -> Deliverable:
    """Creator submits a deliverable.

    Preconditions:
      - Collaboration status in {funded, in_progress, in_review}.
      - Collaboration funding_status == funding_confirmed (else WorkNotUnlocked funding).
      - Current agreement fully signed (else WorkNotUnlocked agreement).
    """

    locked = await collaboration_service.lock_collaboration(session, collaboration.id)
    assert locked is not None

    if locked.funding_status != FundingStatus.funding_confirmed:
        raise WorkNotUnlocked(
            "Funding has not been confirmed yet.",
            reason="funding",
        )
    if locked.status not in _SUBMIT_ALLOWED_STATUSES:
        raise WorkNotUnlocked(
            "Collaboration is not in a state that accepts deliverables.",
            reason="funding",
        )

    agreement = await require_current_agreement_fully_signed(session, locked)
    spec_items = len(agreement.deliverable_spec or [])

    spec_index = int(payload.get("spec_index", 0))
    if spec_index < 0 or (spec_items and spec_index >= spec_items):
        raise InvalidStateTransition(
            "spec_index is out of range for the current agreement."
        )

    kind = DeliverableKind(payload["kind"])
    file_id = payload.get("file_id")
    external_url = payload.get("external_url")
    if kind == DeliverableKind.file and file_id is None:
        raise InvalidStateTransition("A file-kind deliverable requires file_id.")
    if kind == DeliverableKind.link and not external_url:
        raise InvalidStateTransition(
            "A link-kind deliverable requires external_url."
        )

    deliverable = Deliverable(
        collaboration_id=locked.id,
        spec_index=spec_index,
        kind=kind,
        file_id=file_id,
        external_url=external_url,
        caption=payload.get("caption"),
        status=DeliverableStatus.submitted,
        revision_count=0,
    )
    session.add(deliverable)
    await session.flush()

    # If this is the first Deliverable for the collab and status==funded,
    # move to in_progress.
    if locked.status == CollaborationStatus.funded:
        locked.status = CollaborationStatus.in_progress
        await session.flush()

    # If every spec item now has a submitted|approved deliverable, flip to
    # in_review.
    covered = await _spec_coverage(
        session,
        collaboration_id=locked.id,
        spec_items=spec_items,
        acceptable_statuses={
            DeliverableStatus.submitted,
            DeliverableStatus.approved,
        },
    )
    if covered and locked.status != CollaborationStatus.in_review:
        locked.status = CollaborationStatus.in_review
        await session.flush()

    await session.refresh(deliverable)

    brand_user = await brand_user_for_collab(session, locked)
    payload = {
        "collaboration_id": str(locked.id),
        "deliverable_id": str(deliverable.id),
        "spec_index": deliverable.spec_index,
    }
    await notification_service.write_for_user(
        session, user=brand_user, type_="deliverable.submitted", payload=payload
    )
    await audit_service.write(
        session,
        actor_user_id=user.id,
        action="deliverable.submitted",
        target_type="deliverable",
        target_id=deliverable.id,
        diff=payload,
    )
    return deliverable


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------


async def approve(
    session: AsyncSession,
    *,
    deliverable: Deliverable,
    user: User,
) -> dict:
    """Brand approves a deliverable. Returns ``{deliverable, collaboration, payout?}``."""

    locked_collab = await collaboration_service.lock_collaboration(
        session, deliverable.collaboration_id
    )
    assert locked_collab is not None

    agreement = await require_current_agreement_fully_signed(session, locked_collab)
    spec_items = len(agreement.deliverable_spec or [])

    deliverable.status = DeliverableStatus.approved
    await session.flush()
    await session.refresh(deliverable)

    creator_user = await creator_user_for_collab(session, locked_collab)
    approve_payload = {
        "collaboration_id": str(locked_collab.id),
        "deliverable_id": str(deliverable.id),
        "spec_index": deliverable.spec_index,
    }
    await notification_service.write_for_user(
        session,
        user=creator_user,
        type_="deliverable.approved",
        payload=approve_payload,
    )
    await audit_service.write(
        session,
        actor_user_id=user.id,
        action="deliverable.approved",
        target_type="deliverable",
        target_id=deliverable.id,
        diff=approve_payload,
    )

    response: dict[str, Any] = {
        "deliverable": deliverable,
        "collaboration": locked_collab,
        "payout": None,
    }

    all_approved = await _spec_coverage(
        session,
        collaboration_id=locked_collab.id,
        spec_items=spec_items,
        acceptable_statuses={DeliverableStatus.approved},
    )
    if all_approved and locked_collab.status != CollaborationStatus.approved:
        locked_collab.status = CollaborationStatus.approved
        await session.flush()

        # Best-effort auto-payout.
        try:
            payout = await payment_service.initiate_payout(
                session, collaboration=locked_collab
            )
            response["payout"] = {"status": "pending", "id": str(payout.id)}
        except PayoutMethodRequired:
            response["payout"] = {"status": "pending_method"}
            # Nudge the creator to set a method.
            await notification_service.write_for_user(
                session,
                user=creator_user,
                type_="payout.pending_method",
                payload={"collaboration_id": str(locked_collab.id)},
            )
        except Exception as exc:  # noqa: BLE001
            # Non-fatal — approval never rolls back for a downstream payout
            # problem.
            _log.warning(
                "approve_payout_failed",
                collaboration_id=str(locked_collab.id),
                error=repr(exc),
            )
            response["payout"] = {"status": "pending_retry"}

    await session.refresh(locked_collab)
    await session.refresh(deliverable)
    return response


# ---------------------------------------------------------------------------
# Request revision
# ---------------------------------------------------------------------------


async def request_revision(
    session: AsyncSession,
    *,
    deliverable: Deliverable,
    user: User,
    note: str,
) -> Deliverable:
    """Brand requests a revision.

    In a single transaction:
      1. Current agreement must be fully signed (addresses v2r2-1).
      2. ``deliverable.revision_count + 1`` must be <= current agreement
         ``revision_limit`` else 409 revision_limit_reached.
      3. Increment ``revision_count``.
      4. Insert a :class:`DeliverableRevision` row.
      5. Flip ``deliverable.status='revision_requested'``.
    """

    locked_collab = await collaboration_service.lock_collaboration(
        session, deliverable.collaboration_id
    )
    assert locked_collab is not None

    agreement = await require_current_agreement_fully_signed(session, locked_collab)

    new_count = deliverable.revision_count + 1
    if new_count > agreement.revision_limit:
        raise RevisionLimitReached()

    deliverable.revision_count = new_count
    deliverable.status = DeliverableStatus.revision_requested
    session.add(
        DeliverableRevision(
            deliverable_id=deliverable.id,
            requested_by_user_id=user.id,
            note=note,
        )
    )
    await session.flush()
    await session.refresh(deliverable)

    creator_user = await creator_user_for_collab(session, locked_collab)
    payload = {
        "collaboration_id": str(locked_collab.id),
        "deliverable_id": str(deliverable.id),
        "revision_count": deliverable.revision_count,
        "note": note,
    }
    await notification_service.write_for_user(
        session,
        user=creator_user,
        type_="deliverable.revision_requested",
        payload=payload,
    )
    await audit_service.write(
        session,
        actor_user_id=user.id,
        action="deliverable.revision_requested",
        target_type="deliverable",
        target_id=deliverable.id,
        diff=payload,
    )
    return deliverable


# ---------------------------------------------------------------------------
# Open dispute (delegates to dispute_service)
# ---------------------------------------------------------------------------


async def open_dispute(
    session: AsyncSession,
    *,
    deliverable: Deliverable,
    user: User,
    reason: str,
):
    """Open a Dispute against the collaboration this deliverable belongs to."""

    collab = await collaboration_service.lock_collaboration(
        session, deliverable.collaboration_id
    )
    assert collab is not None
    return await dispute_service.open(
        session, collaboration=collab, user=user, reason=reason
    )
