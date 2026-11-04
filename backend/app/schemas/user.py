"""Pydantic schemas for /users/me + role selection."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MeOut(BaseModel):
    """Shape returned by GET /api/v1/users/me."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Literal["creator", "brand", "admin"] | None
    clerk_user_id: str
    is_active: bool


class RoleSelectionIn(BaseModel):
    """Body of POST /api/v1/users/me/role — admin is not self-selectable."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: Literal["creator", "brand"]
