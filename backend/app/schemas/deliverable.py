"""Pydantic schemas for deliverable routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class _ForbidExtras(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DeliverableCreateIn(_ForbidExtras):
    spec_index: int = Field(ge=0, le=100, default=0)
    kind: Literal["file", "link"]
    file_id: uuid.UUID | None = None
    external_url: HttpUrl | None = None
    caption: str | None = Field(default=None, max_length=2000)


class DeliverableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    collaboration_id: uuid.UUID
    spec_index: int
    kind: Literal["file", "link"]
    file_id: uuid.UUID | None
    external_url: str | None
    caption: str | None
    status: Literal["submitted", "revision_requested", "approved", "disputed"]
    revision_count: int
    created_at: datetime
    updated_at: datetime


class RevisionRequestIn(_ForbidExtras):
    note: str = Field(min_length=1, max_length=2000)


class DisputeOpenIn(_ForbidExtras):
    reason: str = Field(min_length=1, max_length=2000)
