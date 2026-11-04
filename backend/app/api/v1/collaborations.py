"""Collaboration routes — role-scoped listing + per-id read + agreement subroutes.

Agreement write routes mounted under /collaborations/{id}/agreements live
alongside /agreements/{id}/sign in :mod:`app.api.v1.agreements`.
"""


import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.brand_profile import BrandProfile
from app.models.collaboration import Collaboration
from app.models.creator_profile import CreatorProfile
from app.models.user import User, UserRole
from app.schemas.admin import DisputeOpenIn, DisputeOut
from app.schemas.agreement import AgreementCreateIn, AgreementOut
from app.schemas.collaboration import CollaborationOut
from app.services import agreement_service, collaboration_service, dispute_service

router = APIRouter(tags=["collaborations"])


async def _load_collaboration_as_participant(
    db: AsyncSession,
    *,
    collaboration_id: uuid.UUID,
    user: User,
) -> Collaboration:
    """Return the collaboration if the user is a participant or admin, else 404."""

    collab = await db.get(Collaboration, collaboration_id)
    if collab is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collaboration not found."
        )
    if user.role == UserRole.admin:
        return collab
    if user.role == UserRole.brand:
        bp = (
            await db.execute(
                select(BrandProfile).where(BrandProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if bp is None or bp.id != collab.brand_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collaboration not found.",
            )
        return collab
    if user.role == UserRole.creator:
        cp = (
            await db.execute(
                select(CreatorProfile).where(CreatorProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if cp is None or cp.id != collab.creator_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collaboration not found.",
            )
        return collab
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Collaboration not found."
    )


@router.get("/collaborations", response_model=list[CollaborationOut])
async def list_collaborations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CollaborationOut]:
    conditions = []
    if user.role == UserRole.admin:
        pass  # no filter
    elif user.role == UserRole.brand:
        bp = (
            await db.execute(
                select(BrandProfile).where(BrandProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if bp is None:
            return []
        conditions.append(Collaboration.brand_id == bp.id)
    elif user.role == UserRole.creator:
        cp = (
            await db.execute(
                select(CreatorProfile).where(CreatorProfile.user_id == user.id)
            )
        ).scalar_one_or_none()
        if cp is None:
            return []
        conditions.append(Collaboration.creator_id == cp.id)
    else:
        return []
    stmt = select(Collaboration).order_by(Collaboration.created_at.desc())
    if conditions:
        stmt = stmt.where(or_(*conditions))
    rows = (await db.execute(stmt)).scalars().all()
    return [CollaborationOut.model_validate(r) for r in rows]


@router.get("/collaborations/{collaboration_id}", response_model=CollaborationOut)
async def get_collaboration(
    collaboration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CollaborationOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    return CollaborationOut.model_validate(collab)


@router.get(
    "/collaborations/{collaboration_id}/agreement",
    response_model=AgreementOut,
)
async def get_current_agreement(
    collaboration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgreementOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    agreement = await collaboration_service.get_current_agreement(db, collab.id)
    if agreement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current agreement for this collaboration.",
        )
    return AgreementOut.model_validate(agreement)


@router.post(
    "/collaborations/{collaboration_id}/agreements",
    response_model=AgreementOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_agreement_version(
    collaboration_id: uuid.UUID,
    body: AgreementCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgreementOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    # Only the brand (or admin) may create a new version.
    if user.role not in {UserRole.brand, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the brand can create a new agreement version.",
        )
    patch = body.model_dump(exclude_unset=True)
    new_version = await agreement_service.create_new_version(
        db, collaboration_id=collab.id, patch=patch, actor_user=user
    )
    await db.commit()
    return AgreementOut.model_validate(new_version)


@router.post(
    "/collaborations/{collaboration_id}/disputes",
    response_model=DisputeOut,
    status_code=status.HTTP_201_CREATED,
)
async def open_collaboration_dispute(
    collaboration_id: uuid.UUID,
    body: DisputeOpenIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DisputeOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    if user.role not in {UserRole.brand, UserRole.creator, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a participant may open a dispute.",
        )
    dispute = await dispute_service.open(
        db, collaboration=collab, user=user, reason=body.reason
    )
    await db.commit()
    return DisputeOut.model_validate(dispute)
