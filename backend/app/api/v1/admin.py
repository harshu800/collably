"""Admin routes — require_role('admin'). Read-only lists + a few mutators.

Every mutating admin action also writes an :class:`AuditLog` row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_role
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.campaign import Campaign, CampaignStatus
from app.models.collaboration import Collaboration
from app.models.dispute import Dispute
from app.models.report import Report, ReportStatus
from app.models.user import User, UserRole
from app.models.webhook_event import PaymentWebhookEvent
from app.schemas.admin import (
    AdminUserOut,
    AuditLogOut,
    DisputeOut,
    DisputeResolveIn,
    ReportOut,
    ReportReviewIn,
    WebhookEventOut,
)
from app.schemas.campaign import CampaignOut
from app.schemas.collaboration import CollaborationOut
from app.services import audit_service, dispute_service

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    _admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserOut]:
    rows = (
        await db.execute(
            select(User)
            .order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return [AdminUserOut.model_validate(r) for r in rows]


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut)
async def deactivate_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> AdminUserOut:
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )
    if target.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admins cannot deactivate their own account.",
        )
    target.is_active = False
    await db.flush()
    await audit_service.write(
        db,
        actor_user_id=admin.id,
        action="admin.user_deactivated",
        target_type="user",
        target_id=target.id,
        diff={"email": target.email, "role": target.role.value},
    )
    await db.commit()
    await db.refresh(target)
    return AdminUserOut.model_validate(target)


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------


@router.get("/campaigns", response_model=list[CampaignOut])
async def list_campaigns(
    _admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[CampaignOut]:
    rows = (
        await db.execute(
            select(Campaign).order_by(Campaign.created_at.desc()).limit(200)
        )
    ).scalars().all()
    return [CampaignOut.model_validate(r) for r in rows]


@router.post("/campaigns/{campaign_id}/archive", response_model=CampaignOut)
async def archive_campaign(
    campaign_id: uuid.UUID,
    admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> CampaignOut:
    row = await db.get(Campaign, campaign_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found."
        )
    row.status = CampaignStatus.archived
    row.archived_at = datetime.now(UTC)
    await db.flush()
    await audit_service.write(
        db,
        actor_user_id=admin.id,
        action="admin.campaign_archived",
        target_type="campaign",
        target_id=row.id,
        diff={"title": row.title},
    )
    await db.commit()
    await db.refresh(row)
    return CampaignOut.model_validate(row)


# ---------------------------------------------------------------------------
# Collaborations
# ---------------------------------------------------------------------------


@router.get("/collaborations", response_model=list[CollaborationOut])
async def list_collaborations(
    _admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[CollaborationOut]:
    rows = (
        await db.execute(
            select(Collaboration)
            .order_by(Collaboration.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    return [CollaborationOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@router.get("/reports", response_model=list[ReportOut])
async def list_reports(
    _admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[ReportOut]:
    rows = (
        await db.execute(
            select(Report).order_by(Report.created_at.desc()).limit(200)
        )
    ).scalars().all()
    return [ReportOut.model_validate(r) for r in rows]


@router.post("/reports/{report_id}/review", response_model=ReportOut)
async def review_report(
    report_id: uuid.UUID,
    body: ReportReviewIn,
    admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    row = await db.get(Report, report_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found."
        )
    row.status = ReportStatus(body.status)
    await db.flush()
    await audit_service.write(
        db,
        actor_user_id=admin.id,
        action="admin.report_reviewed",
        target_type="report",
        target_id=row.id,
        diff={"status": row.status.value},
    )
    await db.commit()
    await db.refresh(row)
    return ReportOut.model_validate(row)


# ---------------------------------------------------------------------------
# Disputes
# ---------------------------------------------------------------------------


@router.get("/disputes", response_model=list[DisputeOut])
async def list_disputes(
    _admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[DisputeOut]:
    rows = (
        await db.execute(
            select(Dispute).order_by(Dispute.created_at.desc()).limit(200)
        )
    ).scalars().all()
    return [DisputeOut.model_validate(r) for r in rows]


@router.post("/disputes/{dispute_id}/resolve", response_model=DisputeOut)
async def resolve_dispute(
    dispute_id: uuid.UUID,
    body: DisputeResolveIn,
    admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> DisputeOut:
    dispute = await dispute_service.resolve(
        db,
        dispute_id=dispute_id,
        admin_user=admin,
        resolution=body.resolution,
        split_bps=body.split_bps,
    )
    await db.commit()
    return DisputeOut.model_validate(dispute)


# ---------------------------------------------------------------------------
# Payment webhook events (read-only)
# ---------------------------------------------------------------------------


@router.get("/payment-events", response_model=list[WebhookEventOut])
async def list_payment_events(
    _admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookEventOut]:
    rows = (
        await db.execute(
            select(PaymentWebhookEvent)
            .order_by(PaymentWebhookEvent.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    return [WebhookEventOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Audit log (read-only)
# ---------------------------------------------------------------------------


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def list_audit_logs(
    _admin: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLogOut]:
    rows = (
        await db.execute(
            select(AuditLog)
            .order_by(AuditLog.occurred_at.desc())
            .limit(200)
        )
    ).scalars().all()
    return [AuditLogOut.model_validate(r) for r in rows]
