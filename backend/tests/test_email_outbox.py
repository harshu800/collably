from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.email_outbox import EmailOutbox
from app.models.user import User
from app.services import email_outbox_service, notification_service
from tests.helpers import onboard_creator


@pytest.mark.asyncio
async def test_notification_and_email_are_enqueued_in_same_transaction(
    client, creator_user: dict, db
) -> None:
    await onboard_creator(client, creator_user)
    user = (
        await db.execute(
            select(User).where(User.email == creator_user["email"])
        )
    ).scalar_one()

    row = await notification_service.write(
        db,
        user_id=user.id,
        type_="application.accepted",
        payload={"campaign_id": "campaign-1"},
        email=user.email,
    )

    outbox = (
        await db.execute(
            select(EmailOutbox).where(EmailOutbox.notification_id == row.id)
        )
    ).scalar_one()
    assert outbox.status == "queued"
    assert outbox.attempts == 0


@pytest.mark.asyncio
async def test_worker_marks_successful_email_sent(
    client, creator_user: dict, db, monkeypatch
) -> None:
    await onboard_creator(client, creator_user)
    user = (
        await db.execute(
            select(User).where(User.email == creator_user["email"])
        )
    ).scalar_one()
    notification = await notification_service.write(
        db,
        user_id=user.id,
        type_="application.accepted",
        payload={"campaign_id": "campaign-1"},
        email=user.email,
    )
    await db.flush()
    outbox = (
        await db.execute(
            select(EmailOutbox).where(
                EmailOutbox.notification_id == notification.id
            )
        )
    ).scalar_one()

    sent: list[dict[str, str]] = []

    class FakeProvider:
        def send(self, **message) -> None:
            sent.append(message)

    monkeypatch.setattr(email_outbox_service, "get_settings", lambda: object())
    monkeypatch.setattr(
        email_outbox_service, "get_email_provider", lambda _settings: FakeProvider()
    )

    claimed_ids = await email_outbox_service.claim_batch(db)
    assert claimed_ids == [outbox.id]
    await db.commit()
    assert await email_outbox_service.deliver_claimed(db, outbox.id)

    await db.refresh(outbox)
    assert outbox.status == "sent"
    assert outbox.sent_at is not None
    assert sent == [
        {
            "to": user.email,
            "subject": "Your application was accepted",
            "body_text": (
                "You have a new update in Collably.\n\n"
                "Sign in to the app to review the details.\n\n"
                "Notification: application.accepted"
            ),
        }
    ]


@pytest.mark.asyncio
async def test_worker_retries_transient_delivery_failure(
    client, creator_user: dict, db, monkeypatch
) -> None:
    await onboard_creator(client, creator_user)
    user = (
        await db.execute(
            select(User).where(User.email == creator_user["email"])
        )
    ).scalar_one()
    notification = await notification_service.write(
        db,
        user_id=user.id,
        type_="application.accepted",
        payload={},
        email=user.email,
    )
    await db.flush()
    outbox = (
        await db.execute(
            select(EmailOutbox).where(
                EmailOutbox.notification_id == notification.id
            )
        )
    ).scalar_one()

    class FailingProvider:
        def send(self, **_message) -> None:
            raise ConnectionError("provider unavailable")

    monkeypatch.setattr(email_outbox_service, "get_settings", lambda: object())
    monkeypatch.setattr(
        email_outbox_service,
        "get_email_provider",
        lambda _settings: FailingProvider(),
    )

    await email_outbox_service.claim_batch(db)
    await db.commit()
    assert not await email_outbox_service.deliver_claimed(db, outbox.id)

    await db.refresh(outbox)
    assert outbox.status == "queued"
    assert outbox.attempts == 1
    assert outbox.last_error_type == "ConnectionError"
    assert outbox.available_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_worker_dead_letters_after_max_attempts(
    client, creator_user: dict, db, monkeypatch
) -> None:
    await onboard_creator(client, creator_user)
    user = (
        await db.execute(
            select(User).where(User.email == creator_user["email"])
        )
    ).scalar_one()
    notification = await notification_service.write(
        db,
        user_id=user.id,
        type_="application.accepted",
        payload={},
        email=user.email,
    )
    await db.flush()
    outbox = (
        await db.execute(
            select(EmailOutbox).where(
                EmailOutbox.notification_id == notification.id
            )
        )
    ).scalar_one()

    class FailingProvider:
        def send(self, **_message) -> None:
            raise TimeoutError("provider timed out")

    monkeypatch.setattr(email_outbox_service, "get_settings", lambda: object())
    monkeypatch.setattr(
        email_outbox_service,
        "get_email_provider",
        lambda _settings: FailingProvider(),
    )

    await email_outbox_service.claim_batch(db)
    await db.commit()
    assert not await email_outbox_service.deliver_claimed(
        db, outbox.id, max_attempts=1
    )

    await db.refresh(outbox)
    assert outbox.status == "failed"
    assert outbox.last_error_type == "TimeoutError"


@pytest.mark.asyncio
async def test_claim_recovers_expired_worker_lease(
    client, creator_user: dict, db
) -> None:
    await onboard_creator(client, creator_user)
    user = (
        await db.execute(
            select(User).where(User.email == creator_user["email"])
        )
    ).scalar_one()
    notification = await notification_service.write(
        db,
        user_id=user.id,
        type_="application.accepted",
        payload={},
        email=user.email,
    )
    await db.flush()
    outbox = (
        await db.execute(
            select(EmailOutbox).where(
                EmailOutbox.notification_id == notification.id
            )
        )
    ).scalar_one()
    outbox.status = "processing"
    outbox.attempts = 1
    outbox.locked_at = datetime.now(UTC) - timedelta(minutes=20)
    await db.flush()

    claimed_ids = await email_outbox_service.claim_batch(db)
    await db.refresh(outbox)

    assert claimed_ids == [outbox.id]
    assert outbox.attempts == 2
    assert outbox.status == "processing"
