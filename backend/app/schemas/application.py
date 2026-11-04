"""Pydantic schemas for the campaign-application routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

MONEY_MAX_PAISE = 10**10  # ₹10 crore cap (design §9)


class _ForbidExtras(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PortfolioLink(_ForbidExtras):
    label: str = Field(min_length=1, max_length=100)
    url: HttpUrl


class ApplicationCreateIn(_ForbidExtras):
    proposed_price_paise: Annotated[int, Field(ge=0, le=MONEY_MAX_PAISE)] | None = None
    pitch: str | None = Field(default=None, max_length=5000)
    portfolio_links: list[PortfolioLink] = Field(default_factory=list, max_length=10)


class ApplicationInviteIn(_ForbidExtras):
    creator_id: uuid.UUID
    pitch: str | None = Field(default=None, max_length=5000)


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    creator_id: uuid.UUID
    proposed_price_paise: int | None
    currency: str
    pitch: str | None
    portfolio_links: list[dict[str, Any]]
    status: Literal["invited", "submitted", "shortlisted", "accepted", "rejected", "withdrawn"]
    invited_by_brand: bool
    created_at: datetime
    updated_at: datetime


class AcceptanceResult(BaseModel):
    application: ApplicationOut
    # Collaboration creation is a stub in FEAT-002; FEAT-003 will populate this.
    collaboration_id: uuid.UUID | None = None
