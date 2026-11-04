"""Agreement routes — sign (either party)."""


import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.agreement import AgreementVersion
from app.models.user import User
from app.schemas.agreement import AgreementOut
from app.services import agreement_service

router = APIRouter(tags=["agreements"])


@router.post("/agreements/{agreement_id}/sign", response_model=AgreementOut)
async def sign_agreement(
    agreement_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgreementOut:
    row = await db.get(AgreementVersion, agreement_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found."
        )
    signed = await agreement_service.sign(db, agreement_id=agreement_id, user=user)
    await db.commit()
    return AgreementOut.model_validate(signed)
