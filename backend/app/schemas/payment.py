"""Pydantic schemas for payment + payout routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collaboration_id: uuid.UUID
    kind: Literal["funding"]
    provider: str
    provider_order_id: str
    amount_paise: int
    currency: str
    status: Literal["created", "initiated", "succeeded", "failed", "refunded"]
    created_at: datetime
    updated_at: datetime


class FundingStatusOut(BaseModel):
    collaboration_id: uuid.UUID
    funding_status: Literal[
        "not_funded", "funding_initiated", "funding_confirmed", "funding_failed"
    ]
    collaboration_status: str


class PayoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collaboration_id: uuid.UUID
    provider: str
    provider_payout_id: str | None
    amount_paise: int
    currency: str
    status: Literal["pending", "processing", "paid", "failed"]
    beneficiary_snapshot: dict[str, Any]
    created_at: datetime
    updated_at: datetime
