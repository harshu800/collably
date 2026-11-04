"""Pydantic schemas for agreement routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

MONEY_MAX_PAISE = 10**10


class _ForbidExtras(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgreementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collaboration_id: uuid.UUID
    version_number: int
    scope: str | None
    deliverable_spec: list[dict[str, Any]]
    price_paise: int
    currency: str
    deadline: datetime | None
    revision_limit: int
    usage_rights: str | None
    disclosure_required: bool
    brand_signed_at: datetime | None
    creator_signed_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgreementCreateIn(_ForbidExtras):
    scope: str | None = Field(default=None, max_length=5000)
    deliverable_spec: list[dict[str, Any]] | None = None
    price_paise: Annotated[int, Field(ge=0, le=MONEY_MAX_PAISE)] | None = None
    deadline: datetime | None = None
    revision_limit: Annotated[int, Field(ge=0, le=10)] | None = None
    usage_rights: str | None = Field(default=None, max_length=5000)
    disclosure_required: bool | None = None
