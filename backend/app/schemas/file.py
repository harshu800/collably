"""Pydantic schemas for the file routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_type: str
    size_bytes: int
    original_filename: str
    visibility: Literal["public", "private"]
    created_at: datetime


class SignedUrlOut(BaseModel):
    url: str
    expires_in: int
