"""Deliverable routes — submit, list, approve, request-revision, dispute."""


import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.collaborations import _load_collaboration_as_participant
from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.brand_profile import BrandProfile
from app.models.collaboration import Collaboration
from app.models.deliverable import Deliverable
from app.models.user import User, UserRole
from app.schemas.deliverable import (
    DeliverableCreateIn,
    DeliverableOut,
    DisputeOpenIn,
    RevisionRequestIn,
)
from app.services import deliverable_service

router = APIRouter(tags=["deliverables"])


async def _load_deliverable_as_participant(
    db: AsyncSession,
    *,
    deliverable_id: uuid.UUID,
    user: User,
) -> tuple[Deliverable, Collaboration]:
    deliverable = await db.get(Deliverable, deliverable_id)
    if deliverable is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable not found."
        )
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=deliverable.collaboration_id, user=user
    )
    return deliverable, collab


@router.post(
    "/collaborations/{collaboration_id}/deliverables",
    response_model=DeliverableOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_deliverable(
    collaboration_id: uuid.UUID,
    body: DeliverableCreateIn,
    user: User = Depends(require_role(UserRole.creator)),
    db: AsyncSession = Depends(get_db),
) -> DeliverableOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    payload = body.model_dump()
    if payload.get("external_url") is not None:
        payload["external_url"] = str(payload["external_url"])
    deliverable = await deliverable_service.submit(
        db, collaboration=collab, user=user, payload=payload
    )
    await db.commit()
    return DeliverableOut.model_validate(deliverable)


@router.get(
    "/collaborations/{collaboration_id}/deliverables",
    response_model=list[DeliverableOut],
)
async def list_deliverables(
    collaboration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DeliverableOut]:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    rows = (
        await db.execute(
            select(Deliverable)
            .where(Deliverable.collaboration_id == collab.id)
            .order_by(Deliverable.created_at.asc())
        )
    ).scalars().all()
    return [DeliverableOut.model_validate(r) for r in rows]


def _assert_brand_party(user: User, db_check_result) -> None:
    if user.role == UserRole.admin:
        return
    if user.role != UserRole.brand:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the brand can perform this action.",
        )
    _ = db_check_result


async def _assert_brand_owner(db: AsyncSession, *, user: User, collab: Collaboration) -> None:
    if user.role == UserRole.admin:
        return
    if user.role != UserRole.brand:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the brand can perform this action.",
        )
    bp = (
        await db.execute(
            select(BrandProfile).where(BrandProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if bp is None or bp.id != collab.brand_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deliverable not found."
        )


@router.post("/deliverables/{deliverable_id}/approve")
async def approve_deliverable(
    deliverable_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deliverable, collab = await _load_deliverable_as_participant(
        db, deliverable_id=deliverable_id, user=user
    )
    await _assert_brand_owner(db, user=user, collab=collab)
    result = await deliverable_service.approve(db, deliverable=deliverable, user=user)
    await db.commit()
    return {
        "deliverable": DeliverableOut.model_validate(result["deliverable"]).model_dump(
            mode="json"
        ),
        "collaboration_status": result["collaboration"].status.value,
        "payout": result["payout"],
    }


@router.post(
    "/deliverables/{deliverable_id}/request-revision", response_model=DeliverableOut
)
async def request_revision(
    deliverable_id: uuid.UUID,
    body: RevisionRequestIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeliverableOut:
    deliverable, collab = await _load_deliverable_as_participant(
        db, deliverable_id=deliverable_id, user=user
    )
    await _assert_brand_owner(db, user=user, collab=collab)
    deliverable = await deliverable_service.request_revision(
        db, deliverable=deliverable, user=user, note=body.note
    )
    await db.commit()
    return DeliverableOut.model_validate(deliverable)


@router.post("/deliverables/{deliverable_id}/dispute")
async def open_dispute(
    deliverable_id: uuid.UUID,
    body: DisputeOpenIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deliverable, _ = await _load_deliverable_as_participant(
        db, deliverable_id=deliverable_id, user=user
    )
    dispute = await deliverable_service.open_dispute(
        db, deliverable=deliverable, user=user, reason=body.reason
    )
    await db.commit()
    return {"status": "ok", "dispute_id": str(dispute.id)}
