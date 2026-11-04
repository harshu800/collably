"""Notification service — single writer for :class:`Notification` rows.

Every call also dispatches the matching email via the configured
:class:`EmailProvider`. The console provider used in dev logs at INFO so
tests can observe without a mail server.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_outbox import EmailOutbox
from app.models.notification import Notification
from app.models.user import User


def _subject_for(type_: str, payload: dict[str, Any]) -> str:
    """Short, honest subject line. Avoids hype or false promises."""

    friendly = {
        "application.submitted": "A creator applied to your campaign",
        "application.invited": "You have been invited to a campaign",
        "application.accepted": "Your application was accepted",
        "application.rejected": "Update on your application",
        "application.withdrawn": "A creator withdrew their application",
        "application.shortlisted": "You were shortlisted",
        "agreement.signed": "Agreement signed",
        "agreement.new_version": "A new agreement version was proposed",
        "funding.initiated": "Funding initiated",
        "funding.confirmed": "Funding confirmed",
        "funding.failed": "Funding failed",
        "payout.initiated": "Payout initiated",
        "payout.paid": "Payout confirmed",
        "payout.failed": "Payout failed",
        "payout.pending_method": "Set up a payout method to receive funds",
        "deliverable.submitted": "A deliverable was submitted",
        "deliverable.approved": "Your deliverable was approved",
        "deliverable.revision_requested": "A revision was requested",
        "dispute.opened": "A dispute was opened",
        "dispute.resolved": "A dispute was resolved",
        "admin.account_deactivated": "Your account was restricted",
        "admin.campaign_archived": "A campaign was archived by an admin",
    }
    base = friendly.get(type_, type_.replace(".", " ").title())
    collab = payload.get("collaboration_id")
    if collab:
        return f"{base} (collab {str(collab)[:8]})"
    return base


def _render_body(type_: str) -> str:
    return (
        "You have a new update in Collably.\n\n"
        "Sign in to the app to review the details.\n\n"
        f"Notification: {type_}"
    )


async def write(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    type_: str,
    payload: dict[str, Any] | None = None,
    email: str | None = None,
) -> Notification:
    """Insert a notification and enqueue its email in the same transaction."""

    data = dict(payload or {})
    row = Notification(user_id=user_id, type=type_, payload=data)
    session.add(row)
    await session.flush()

    if email:
        session.add(EmailOutbox(notification_id=row.id))
        await session.flush()
    return row


async def write_for_user(
    session: AsyncSession,
    *,
    user: User | None,
    type_: str,
    payload: dict[str, Any] | None = None,
) -> Notification | None:
    """Convenience: skip if ``user`` is None (lookup miss)."""

    if user is None:
        return None
    return await write(
        session,
        user_id=user.id,
        type_=type_,
        payload=payload,
        email=user.email,
    )
