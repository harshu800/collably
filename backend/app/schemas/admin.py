"""Pydantic schemas for admin, notifications, disputes, reports routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _ForbidExtras(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    diff: dict[str, Any]
    occurred_at: datetime


# ---------------------------------------------------------------------------
# Disputes
# ---------------------------------------------------------------------------


class DisputeOpenIn(_ForbidExtras):
    reason: str = Field(min_length=1, max_length=2000)


class DisputeResolveIn(_ForbidExtras):
    resolution: Literal["release_to_creator", "refund_to_brand", "split"]
    split_bps: int | None = Field(default=None, ge=0, le=10000)


class DisputeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collaboration_id: uuid.UUID
    opened_by_user_id: uuid.UUID | None
    reason: str
    status: Literal["open", "resolved", "rejected"]
    resolution: Literal["release_to_creator", "refund_to_brand", "split"] | None
    split_bps: int | None
    resolved_by_admin_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


class ReportCreateIn(_ForbidExtras):
    target_type: Literal["user", "campaign"]
    target_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=2000)


class ReportReviewIn(_ForbidExtras):
    status: Literal["reviewed", "dismissed"]


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reporter_user_id: uuid.UUID | None
    target_type: Literal["user", "campaign"]
    target_id: uuid.UUID
    reason: str
    status: Literal["open", "reviewed", "dismissed"]
    created_at: datetime


# ---------------------------------------------------------------------------
# Admin listings
# ---------------------------------------------------------------------------


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Literal["creator", "brand", "admin"]
    is_active: bool
    created_at: datetime


class WebhookEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    provider_event_id: str
    event_type: str
    verified: bool
    processed_at: datetime | None
    created_at: datetime
