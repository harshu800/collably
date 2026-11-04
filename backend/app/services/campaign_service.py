"""Campaign service — single writer for campaign lifecycle + edit guards.

Material fields are immutable once any application exists; non-material
fields stay editable until the campaign is archived. ``number_of_creators``
is a special case — it is non-material but may only move upward.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CampaignLocked
from app.models.application import CampaignApplication
from app.models.brand_profile import BrandProfile
from app.models.campaign import Campaign, CampaignStatus, CampaignType
from app.models.user import User

# Fields that CANNOT be changed once an application exists for the campaign.
MATERIAL_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "type",
        "budget_paise",
        "deliverable_spec",
        "revision_limit",
        "usage_rights",
        "disclosure_required",
        "submission_deadline",
        "eligibility_filters",
    }
)

# Fields that stay editable until the campaign is archived.
NON_MATERIAL_FIELDS: frozenset[str] = frozenset(
    {
        "description",
        "niches",
        "platforms",
        "languages",
        "locations",
        "number_of_creators",
    }
)


async def _load_brand_profile_for_user(
    session: AsyncSession,
    user: User,
) -> BrandProfile:
    stmt = select(BrandProfile).where(BrandProfile.user_id == user.id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = BrandProfile(user_id=user.id)
        session.add(row)
        await session.flush()
    return row


async def create(
    session: AsyncSession,
    *,
    brand_user: User,
    data: dict[str, Any],
) -> Campaign:
    brand = await _load_brand_profile_for_user(session, brand_user)
    status_value = data.pop("status", "open")
    campaign = Campaign(
        brand_id=brand.id,
        title=data["title"],
        description=data.get("description"),
        type=CampaignType(data["type"]),
        niches=list(data.get("niches") or []),
        platforms=list(data.get("platforms") or []),
        languages=list(data.get("languages") or []),
        locations=list(data.get("locations") or []),
        budget_paise=int(data["budget_paise"]),
        currency="INR",
        number_of_creators=int(data.get("number_of_creators") or 1),
        deliverable_spec=list(data.get("deliverable_spec") or []),
        submission_deadline=data.get("submission_deadline"),
        revision_limit=int(data.get("revision_limit") or 0),
        usage_rights=data.get("usage_rights"),
        disclosure_required=bool(data.get("disclosure_required", True)),
        eligibility_filters=dict(data.get("eligibility_filters") or {}),
        status=CampaignStatus(status_value),
    )
    session.add(campaign)
    await session.flush()
    return campaign


async def get_by_id(
    session: AsyncSession,
    campaign_id: uuid.UUID,
) -> Campaign | None:
    return await session.get(Campaign, campaign_id)


async def _applications_exist(
    session: AsyncSession,
    campaign_id: uuid.UUID,
) -> bool:
    stmt = select(func.count()).select_from(CampaignApplication).where(
        CampaignApplication.campaign_id == campaign_id,
    )
    count = (await session.execute(stmt)).scalar_one()
    return int(count) > 0


def _normalise_type(value: Any) -> CampaignType:
    if isinstance(value, CampaignType):
        return value
    return CampaignType(str(value))


async def update(
    session: AsyncSession,
    *,
    campaign: Campaign,
    patch: dict[str, Any],
) -> Campaign:
    """Apply a patch, enforcing material vs non-material rules."""

    # Reload the campaign row under FOR UPDATE so a concurrent accept-flow
    # cannot slip an application in between our count and our write.
    locked = (
        await session.execute(
            select(Campaign).where(Campaign.id == campaign.id).with_for_update()
        )
    ).scalar_one()

    has_applications = await _applications_exist(session, locked.id)

    # Enforce ``number_of_creators`` upward-only — regardless of applications.
    if "number_of_creators" in patch:
        new_value = int(patch["number_of_creators"])
        if new_value < locked.number_of_creators:
            raise CampaignLocked(
                "number_of_creators can only move upward.",
                offending_fields=["number_of_creators"],
            )

    # Enforce material-field immutability once an application exists.
    if has_applications:
        offending: list[str] = []
        for key, new_value in patch.items():
            if key not in MATERIAL_FIELDS:
                continue
            current = getattr(locked, key)
            if isinstance(current, CampaignType):
                try:
                    new_cmp = _normalise_type(new_value)
                except Exception:
                    new_cmp = new_value  # type: ignore[assignment]
                if new_cmp != current:
                    offending.append(key)
                continue
            if new_value != current:
                offending.append(key)
        if offending:
            raise CampaignLocked(
                "Material fields cannot be changed after an application exists.",
                offending_fields=offending,
            )

    # Apply the patch — only touching known fields on the model.
    for key, value in patch.items():
        if key == "type":
            setattr(locked, key, _normalise_type(value))
        elif hasattr(locked, key):
            setattr(locked, key, value)

    await session.flush()
    # ``updated_at`` has ``onupdate=func.now()`` server-side; SQLAlchemy marks
    # the attribute as expired after the UPDATE so the next read would trigger
    # an implicit lazy-load. Refresh now so Pydantic can serialise safely
    # without re-entering IO from a sync context.
    await session.refresh(locked)
    return locked


async def close(session: AsyncSession, *, campaign: Campaign) -> Campaign:
    campaign.status = CampaignStatus.closed
    await session.flush()
    await session.refresh(campaign)
    return campaign


async def archive(session: AsyncSession, *, campaign: Campaign) -> Campaign:
    campaign.status = CampaignStatus.archived
    campaign.archived_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(campaign)
    return campaign
