"""Pydantic schemas for collaboration routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CollaborationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    application_id: uuid.UUID
    brand_id: uuid.UUID
    creator_id: uuid.UUID
    status: Literal[
        "pending_agreement",
        "agreement_signed",
        "funding_initiated",
        "funded",
        "in_progress",
        "in_review",
        "approved",
        "completed",
        "disputed",
        "cancelled",
    ]
    price_paise: int
    currency: str
    funding_status: Literal[
        "not_funded", "funding_initiated", "funding_confirmed", "funding_failed"
    ]
    payout_status: Literal["none", "pending", "processing", "paid", "failed"]
    created_at: datetime
    updated_at: datetime
