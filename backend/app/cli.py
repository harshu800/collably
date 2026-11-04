"""Admin + seed CLI.

Entry points are exposed as subcommands of ``python -m app.cli``.

- ``grant_admin <identifier>`` — promotes an existing user to the ``admin``
  role, matching ``identifier`` against either ``email`` or ``clerk_user_id``.
  Prints the resolved user and exits 0; idempotent when the target is
  already an admin.
- ``seed_demo`` — DEV-ONLY: idempotently inserts a deterministic brand user,
  a deterministic creator user (with ``does_ugc=true``) and one open UGC
  campaign owned by the brand. Users are keyed by Clerk-id placeholders;
  the operator is reminded to create matching Clerk accounts and set each
  one's ``external_id`` to the placeholder clerk id.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.brand_profile import BrandProfile
from app.models.campaign import Campaign, CampaignStatus, CampaignType
from app.models.creator_profile import CreatorProfile
from app.models.user import User, UserRole

# -- seed_demo constants (deterministic so re-running is idempotent) ----------

DEMO_BRAND_EMAIL = "demo-brand@test.local"
DEMO_CREATOR_EMAIL = "demo-creator@test.local"
DEMO_BRAND_CLERK_ID = "demo_brand_clerk_id"
DEMO_CREATOR_CLERK_ID = "demo_creator_clerk_id"
DEMO_CAMPAIGN_TITLE = "Demo UGC — festive drop"


# ---------------------------------------------------------------------------
# grant_admin
# ---------------------------------------------------------------------------


async def _cmd_grant_admin(identifier: str) -> int:
    """Promote the matching user to admin. Match by email or clerk_user_id."""

    needle = identifier.strip()
    if not needle:
        print("Identifier may not be empty.", file=sys.stderr)
        return 2

    async with AsyncSessionLocal() as session:
        normalized = needle.lower()
        stmt = select(User).where(
            (User.email == normalized) | (User.clerk_user_id == needle)
        )
        user = (await session.execute(stmt)).scalar_one_or_none()
        if user is None:
            print(
                f"No user matched email or clerk_user_id {identifier!r}.",
                file=sys.stderr,
            )
            return 2

        if user.role == UserRole.admin:
            print(
                "Already admin: "
                f"id={user.id} clerk_user_id={user.clerk_user_id} email={user.email}"
            )
            return 0

        user.role = UserRole.admin
        await session.commit()
        print(
            "Promoted to admin: "
            f"id={user.id} clerk_user_id={user.clerk_user_id} email={user.email}"
        )
        return 0


# ---------------------------------------------------------------------------
# seed_demo
# ---------------------------------------------------------------------------


async def _get_or_create_user_by_clerk_id(
    session: AsyncSession,
    *,
    clerk_user_id: str,
    email: str,
    role: UserRole,
) -> tuple[User, bool]:
    """Return ``(user, created)``. Keyed by ``clerk_user_id`` for idempotency."""

    existing = (
        await session.execute(
            select(User).where(User.clerk_user_id == clerk_user_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.role != role:
            existing.role = role
        return existing, False
    user = User(
        clerk_user_id=clerk_user_id,
        email=email,
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    return user, True


async def _ensure_brand_profile(
    session: AsyncSession, *, user: User
) -> BrandProfile:
    row = (
        await session.execute(
            select(BrandProfile).where(BrandProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = BrandProfile(user_id=user.id)
        session.add(row)
        await session.flush()
    row.company_name = row.company_name or "Demo D2C Brand"
    row.industry = row.industry or "beauty"
    row.contact_name = row.contact_name or "Demo Owner"
    row.contact_email = row.contact_email or "owner@demo.test"
    row.is_onboarded = True
    await session.flush()
    return row


async def _ensure_creator_profile(
    session: AsyncSession, *, user: User
) -> CreatorProfile:
    row = (
        await session.execute(
            select(CreatorProfile).where(CreatorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        row = CreatorProfile(user_id=user.id)
        session.add(row)
        await session.flush()
    row.display_name = row.display_name or "Demo Creator"
    row.bio = row.bio or "Demo creator bio — beauty, lifestyle."
    row.city = row.city or "Mumbai"
    row.state = row.state or "MH"
    row.does_ugc = True
    row.niches = row.niches or ["beauty"]
    row.is_onboarded = True
    await session.flush()
    return row


async def _ensure_demo_campaign(
    session: AsyncSession, *, brand_profile: BrandProfile
) -> Campaign:
    existing = (
        await session.execute(
            select(Campaign).where(
                Campaign.brand_id == brand_profile.id,
                Campaign.title == DEMO_CAMPAIGN_TITLE,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    campaign = Campaign(
        brand_id=brand_profile.id,
        title=DEMO_CAMPAIGN_TITLE,
        description="Short-form video for a festive skincare launch.",
        type=CampaignType.ugc,
        niches=["beauty"],
        platforms=["instagram"],
        languages=["en"],
        locations=["Mumbai"],
        budget_paise=100_000,
        currency="INR",
        number_of_creators=1,
        deliverable_spec=[
            {
                "kind": "file",
                "description": "one 30s short-form video",
                "quantity": 1,
            }
        ],
        revision_limit=2,
        usage_rights="paid media, 90 days",
        disclosure_required=False,
        status=CampaignStatus.open,
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def _cmd_seed_demo() -> int:
    async with AsyncSessionLocal() as session:
        brand_user, brand_created = await _get_or_create_user_by_clerk_id(
            session,
            clerk_user_id=DEMO_BRAND_CLERK_ID,
            email=DEMO_BRAND_EMAIL,
            role=UserRole.brand,
        )
        creator_user, creator_created = await _get_or_create_user_by_clerk_id(
            session,
            clerk_user_id=DEMO_CREATOR_CLERK_ID,
            email=DEMO_CREATOR_EMAIL,
            role=UserRole.creator,
        )
        brand_profile = await _ensure_brand_profile(session, user=brand_user)
        await _ensure_creator_profile(session, user=creator_user)
        campaign = await _ensure_demo_campaign(
            session, brand_profile=brand_profile
        )
        await session.commit()

    print("=" * 60)
    print("DEV-ONLY: demo seed complete.")
    print("These rows are placeholders only — Clerk owns credentials now.")
    print(
        "To log in as these users you MUST create matching Clerk accounts "
        "and set each account's `external_id` to the placeholder clerk id below."
    )
    print("=" * 60)
    print(f"Brand:   {DEMO_BRAND_EMAIL}  clerk_user_id={DEMO_BRAND_CLERK_ID}  (new={brand_created})")
    print(f"Creator: {DEMO_CREATOR_EMAIL}  clerk_user_id={DEMO_CREATOR_CLERK_ID}  (new={creator_created})")
    print(f"Open campaign: {campaign.title}  id={campaign.id}")
    return 0


async def _cmd_email_worker(
    *,
    poll_interval_seconds: float,
    batch_size: int,
) -> int:
    settings = get_settings()
    settings.validate_production()

    from app.services.email_outbox_service import run_worker

    await run_worker(
        poll_interval_seconds=poll_interval_seconds,
        batch_size=batch_size,
    )
    return 0


# ---------------------------------------------------------------------------
# Argparse plumbing
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Administrative commands for the marketplace backend.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_admin = sub.add_parser(
        "grant_admin",
        help=(
            "Promote an existing user to admin, matched by email or clerk_user_id."
        ),
    )
    p_admin.add_argument(
        "identifier",
        help="Email address or Clerk user id to promote.",
    )

    sub.add_parser(
        "seed_demo",
        help=(
            "DEV-ONLY: insert a deterministic brand, creator, and open "
            "campaign. Idempotent."
        ),
    )
    p_email_worker = sub.add_parser(
        "email_worker",
        help="Send queued notification emails and retry transient failures.",
    )
    p_email_worker.add_argument(
        "--poll-interval",
        type=float,
        default=5,
        help="Seconds to wait when no queued emails are ready (default: 5).",
    )
    p_email_worker.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Maximum emails claimed per poll (default: 20).",
    )

    args = parser.parse_args(argv)

    if args.command == "grant_admin":
        return asyncio.run(_cmd_grant_admin(args.identifier))

    if args.command == "seed_demo":
        return asyncio.run(_cmd_seed_demo())

    if args.command == "email_worker":
        return asyncio.run(
            _cmd_email_worker(
                poll_interval_seconds=args.poll_interval,
                batch_size=args.batch_size,
            )
        )

    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
