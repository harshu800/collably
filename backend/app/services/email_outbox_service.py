"""Claim and deliver notification emails from the durable outbox."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.models.email_outbox import EmailOutbox
from app.models.notification import Notification
from app.models.user import User
from app.providers.email import get_email_provider
from app.services.notification_service import _render_body, _subject_for

_log = get_logger("email_outbox")
_LOCK_LEASE: Final = timedelta(minutes=10)
_MAX_RETRY_DELAY_SECONDS: Final = 6 * 60 * 60
_MAX_BATCH_SIZE: Final = 50


def retry_delay_seconds(attempt: int) -> int:
    """Exponential retry delay, capped at six hours."""

    return min(60 * (2 ** max(0, attempt - 1)), _MAX_RETRY_DELAY_SECONDS)


async def claim_batch(
    session: AsyncSession,
    *,
    batch_size: int = 20,
    now: datetime | None = None,
) -> list[uuid.UUID]:
    """Atomically claim due and abandoned outbox rows for one worker."""

    if not 1 <= batch_size <= _MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {_MAX_BATCH_SIZE}")
    current_time = now or datetime.now(UTC)
    stale_before = current_time - _LOCK_LEASE
    stmt = (
        select(EmailOutbox)
        .where(
            or_(
                and_(
                    EmailOutbox.status == "queued",
                    EmailOutbox.available_at <= current_time,
                ),
                and_(
                    EmailOutbox.status == "processing",
                    EmailOutbox.locked_at < stale_before,
                ),
            )
        )
        .order_by(EmailOutbox.created_at, EmailOutbox.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = (await session.execute(stmt)).scalars().all()
    for row in rows:
        row.status = "processing"
        row.attempts += 1
        row.locked_at = current_time
    await session.flush()
    return [row.id for row in rows]


async def deliver_claimed(
    session: AsyncSession,
    outbox_id: uuid.UUID,
    *,
    max_attempts: int = 10,
) -> bool:
    """Send one claimed message and persist success or retry state."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    result = await session.execute(
        select(EmailOutbox, Notification, User.email)
        .join(Notification, Notification.id == EmailOutbox.notification_id)
        .join(User, User.id == Notification.user_id)
        .where(
            EmailOutbox.id == outbox_id,
            EmailOutbox.status == "processing",
        )
    )
    item = result.one_or_none()
    if item is None:
        return False

    outbox, notification, recipient = item
    try:
        provider = get_email_provider(get_settings())
        await asyncio.to_thread(
            provider.send,
            to=recipient,
            subject=_subject_for(notification.type, notification.payload),
            body_text=_render_body(notification.type),
        )
    except Exception as exc:  # noqa: BLE001
        outbox.last_error_type = type(exc).__name__[:100]
        outbox.locked_at = None
        if outbox.attempts >= max_attempts:
            outbox.status = "failed"
        else:
            outbox.status = "queued"
            outbox.available_at = datetime.now(UTC) + timedelta(
                seconds=retry_delay_seconds(outbox.attempts)
            )
        await session.commit()
        _log.warning(
            "email_delivery_failed",
            outbox_id=str(outbox.id),
            notification_type=notification.type,
            attempt=outbox.attempts,
            status=outbox.status,
            error_type=outbox.last_error_type,
        )
        return False

    outbox.status = "sent"
    outbox.sent_at = datetime.now(UTC)
    outbox.locked_at = None
    outbox.last_error_type = None
    await session.commit()
    _log.info(
        "email_delivery_succeeded",
        outbox_id=str(outbox.id),
        notification_type=notification.type,
    )
    return True


async def run_worker(
    *,
    poll_interval_seconds: float = 5,
    batch_size: int = 20,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Poll and deliver queued emails until the process is stopped."""

    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be greater than zero")
    if not 1 <= batch_size <= _MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {_MAX_BATCH_SIZE}")

    factory = session_factory or get_sessionmaker()
    _log.info(
        "email_worker_started",
        poll_interval_seconds=poll_interval_seconds,
        batch_size=batch_size,
    )
    while True:
        async with factory() as session:
            claimed_ids = await claim_batch(session, batch_size=batch_size)
            await session.commit()

        for outbox_id in claimed_ids:
            async with factory() as session:
                await deliver_claimed(session, outbox_id)

        if not claimed_ids:
            await asyncio.sleep(poll_interval_seconds)
