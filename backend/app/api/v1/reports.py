"""User-facing /reports route — a report submits a Report row for admin review."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.report import Report, ReportStatus, ReportTargetType
from app.models.user import User
from app.schemas.admin import ReportCreateIn, ReportOut
from app.services import audit_service

router = APIRouter(tags=["reports"])


@router.post(
    "/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_report(
    body: ReportCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    row = Report(
        reporter_user_id=user.id,
        target_type=ReportTargetType(body.target_type),
        target_id=body.target_id,
        reason=body.reason,
        status=ReportStatus.open,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await audit_service.write(
        db,
        actor_user_id=user.id,
        action="report.submitted",
        target_type="report",
        target_id=row.id,
        diff={
            "target_type": body.target_type,
            "target_id": str(body.target_id),
        },
    )
    await db.commit()
    return ReportOut.model_validate(row)
