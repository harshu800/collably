"""Pydantic schemas for the campaign routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MONEY_MAX_PAISE = 10**10  # ₹10 crore cap (design §9)


class _ForbidExtras(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DeliverableSpecItem(_ForbidExtras):
    kind: Literal["file", "link"]
    description: str = Field(min_length=1, max_length=500)
    quantity: int = Field(default=1, ge=1, le=50)


class CampaignCreateIn(_ForbidExtras):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    type: Literal["ugc", "influencer", "hybrid"]
    niches: list[str] = Field(default_factory=list, max_length=20)
    platforms: list[str] = Field(default_factory=list, max_length=20)
    languages: list[str] = Field(default_factory=list, max_length=20)
    locations: list[str] = Field(default_factory=list, max_length=20)
    budget_paise: Annotated[int, Field(ge=0, le=MONEY_MAX_PAISE)]
    number_of_creators: Annotated[int, Field(ge=1, le=100)] = 1
    deliverable_spec: list[DeliverableSpecItem] = Field(default_factory=list, max_length=20)
    submission_deadline: datetime | None = None
    revision_limit: Annotated[int, Field(ge=0, le=10)] = 0
    usage_rights: str | None = Field(default=None, max_length=5000)
    disclosure_required: bool = True
    eligibility_filters: dict[str, Any] = Field(default_factory=dict)
    status: Literal["draft", "open"] = "open"


class CampaignPatchIn(_ForbidExtras):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    type: Literal["ugc", "influencer", "hybrid"] | None = None
    niches: list[str] | None = Field(default=None, max_length=20)
    platforms: list[str] | None = Field(default=None, max_length=20)
    languages: list[str] | None = Field(default=None, max_length=20)
    locations: list[str] | None = Field(default=None, max_length=20)
    budget_paise: Annotated[int, Field(ge=0, le=MONEY_MAX_PAISE)] | None = None
    number_of_creators: Annotated[int, Field(ge=1, le=100)] | None = None
    deliverable_spec: list[DeliverableSpecItem] | None = Field(default=None, max_length=20)
    submission_deadline: datetime | None = None
    revision_limit: Annotated[int, Field(ge=0, le=10)] | None = None
    usage_rights: str | None = Field(default=None, max_length=5000)
    disclosure_required: bool | None = None
    eligibility_filters: dict[str, Any] | None = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_id: uuid.UUID
    title: str
    description: str | None
    type: Literal["ugc", "influencer", "hybrid"]
    niches: list[str]
    platforms: list[str]
    languages: list[str]
    locations: list[str]
    budget_paise: int
    currency: str
    number_of_creators: int
    deliverable_spec: list[dict[str, Any]]
    submission_deadline: datetime | None
    revision_limit: int
    usage_rights: str | None
    disclosure_required: bool
    eligibility_filters: dict[str, Any]
    status: Literal["draft", "open", "closed", "archived"]
    created_at: datetime
    updated_at: datetime


class CampaignListOut(BaseModel):
    items: list[CampaignOut]
    page: int
    page_size: int
    total: int
