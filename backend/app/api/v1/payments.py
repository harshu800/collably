"""Payment + payout routes."""


import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.collaborations import _load_collaboration_as_participant
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.creator_profile import CreatorProfile
from app.models.payment import Payment, PaymentKind
from app.models.payout import Payout
from app.models.user import User, UserRole
from app.schemas.payment import FundingStatusOut, PaymentOut, PayoutOut
from app.services import payment_service

router = APIRouter(tags=["payments"])


@router.post(
    "/collaborations/{collaboration_id}/funding", response_model=PaymentOut
)
async def initiate_funding(
    collaboration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    if user.role not in {UserRole.brand, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the brand can initiate funding.",
        )
    payment = await payment_service.initiate_funding(
        db, collaboration=collab, actor_user=user
    )
    await db.commit()
    return PaymentOut.model_validate(payment)


@router.get(
    "/collaborations/{collaboration_id}/funding", response_model=FundingStatusOut
)
async def get_funding_status(
    collaboration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FundingStatusOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    funding_status = await payment_service.get_funding_status(
        db, collaboration_id=collab.id
    )
    await db.commit()
    # Reload for the latest collaboration status after reconciliation.
    await db.refresh(collab)
    return FundingStatusOut(
        collaboration_id=collab.id,
        funding_status=funding_status.value,  # type: ignore[arg-type]
        collaboration_status=collab.status.value,
    )


@router.post(
    "/collaborations/{collaboration_id}/payouts",
    response_model=PayoutOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_payout(
    collaboration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PayoutOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    # Creator-only retry: a non-creator sees 404 regardless of participation
    # (design §6).
    if user.role != UserRole.creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collaboration not found."
        )
    cp = (
        await db.execute(
            select(CreatorProfile).where(CreatorProfile.user_id == user.id)
        )
    ).scalar_one_or_none()
    if cp is None or cp.id != collab.creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Collaboration not found."
        )
    payout = await payment_service.initiate_payout(db, collaboration=collab)
    await db.commit()
    return PayoutOut.model_validate(payout)


@router.get(
    "/collaborations/{collaboration_id}/payouts", response_model=PayoutOut
)
async def get_payout(
    collaboration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PayoutOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    payout = (
        await db.execute(
            select(Payout).where(Payout.collaboration_id == collab.id)
        )
    ).scalar_one_or_none()
    if payout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No payout for this collaboration."
        )
    return PayoutOut.model_validate(payout)


@router.get(
    "/collaborations/{collaboration_id}/payment", response_model=PaymentOut
)
async def get_payment(
    collaboration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentOut:
    collab = await _load_collaboration_as_participant(
        db, collaboration_id=collaboration_id, user=user
    )
    pay = (
        await db.execute(
            select(Payment).where(
                Payment.collaboration_id == collab.id,
                Payment.kind == PaymentKind.funding,
            )
        )
    ).scalar_one_or_none()
    if pay is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No payment for this collaboration.",
        )
    return PaymentOut.model_validate(pay)
