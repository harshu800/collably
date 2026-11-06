"""Pydantic schemas for creator + brand profile routes."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

# GSTIN format per design §9. 15 characters: 2 digits + 5 letters + 4 digits +
# 1 letter + 1 letter-or-digit (not 0) + 'Z' + 1 letter-or-digit.
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

MONEY_MAX_PAISE = 10**10  # ₹10 crore cap (design §9)


class _ForbidExtras(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Shared nested shapes
# ---------------------------------------------------------------------------


class PortfolioLink(_ForbidExtras):
    label: str = Field(min_length=1, max_length=100)
    url: HttpUrl


class SocialHandle(_ForbidExtras):
    platform: str = Field(min_length=1, max_length=50)
    handle: str = Field(min_length=1, max_length=2048)
    follower_count: int | None = Field(default=None, ge=0, le=10_000_000_000)
    # Follower counts are self-reported; we persist a sentinel so the frontend
    # can show an "unverified" badge next to the number.
    unverified: Literal[True] = True

    @field_validator("handle")
    @classmethod
    def _validate_profile_url(cls, value: str) -> str:
        if "://" not in value:
            return value
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Social profile URLs must use HTTP or HTTPS.")
        return value


class BillingAddress(_ForbidExtras):
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(default="IN", min_length=2, max_length=2)


# ---------------------------------------------------------------------------
# Creator profile
# ---------------------------------------------------------------------------


class CreatorProfilePatch(_ForbidExtras):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_file_id: uuid.UUID | None = None
    bio: str | None = Field(default=None, max_length=2000)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    languages: list[str] | None = Field(default=None, max_length=20)
    niches: list[str] | None = Field(default=None, max_length=20)
    does_ugc: bool | None = None
    does_influencer: bool | None = None
    content_types: list[str] | None = Field(default=None, max_length=20)
    starting_rate_paise: Annotated[int, Field(ge=0, le=MONEY_MAX_PAISE)] | None = None
    portfolio_links: list[PortfolioLink] | None = Field(default=None, max_length=20)
    social_handles: list[SocialHandle] | None = Field(default=None, max_length=20)


class CreatorProfileSelfOut(BaseModel):
    """Full creator profile shape, returned to the owner on ``GET /me/profile``."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str | None
    avatar_file_id: uuid.UUID | None
    bio: str | None
    city: str | None
    state: str | None
    languages: list[str]
    niches: list[str]
    does_ugc: bool
    does_influencer: bool
    content_types: list[str]
    starting_rate_paise: int | None
    currency: str
    portfolio_links: list[dict[str, Any]]
    social_handles: list[dict[str, Any]]
    is_onboarded: bool


class CreatorPublicOut(BaseModel):
    """Public creator view — strips every field that could expose contact info."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str | None
    avatar_file_id: uuid.UUID | None
    bio: str | None
    city: str | None
    state: str | None
    languages: list[str]
    niches: list[str]
    does_ugc: bool
    does_influencer: bool
    content_types: list[str]
    starting_rate_paise: int | None
    currency: str
    portfolio_links: list[dict[str, Any]]
    # Social handles are included but the follower_count field is caller-reported;
    # see note on :class:`SocialHandle` above.
    social_handles: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Brand profile
# ---------------------------------------------------------------------------


class BrandProfilePatch(_ForbidExtras):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    website: HttpUrl | None = None
    logo_file_id: uuid.UUID | None = None
    industry: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: EmailStr | None = None
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    billing_address: BillingAddress | None = None
    description: str | None = Field(default=None, max_length=2000)
    social_handles: list[SocialHandle] | None = Field(default=None, max_length=20)

    @field_validator("gstin")
    @classmethod
    def _validate_gstin(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v_upper = v.upper()
        if not GSTIN_REGEX.match(v_upper):
            raise ValueError("GSTIN must match the 15-character Indian GSTIN pattern.")
        return v_upper


class BrandProfileSelfOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    company_name: str | None
    website: str | None
    logo_file_id: uuid.UUID | None
    industry: str | None
    city: str | None
    state: str | None
    contact_name: str | None
    contact_email: str | None
    gstin: str | None
    billing_address: dict[str, Any]
    description: str | None
    social_handles: list[dict[str, Any]]
    is_onboarded: bool


class BrandPublicOut(BaseModel):
    """Public brand details without billing or direct contact information."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_name: str | None
    website: str | None
    logo_file_id: uuid.UUID | None
    industry: str | None
    city: str | None
    state: str | None
    description: str | None
    social_handles: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Role-aware ``/me/profile`` envelope
# ---------------------------------------------------------------------------


class MeProfileOut(BaseModel):
    role: Literal["creator", "brand", "admin"] | None
    creator: CreatorProfileSelfOut | None = None
    brand: BrandProfileSelfOut | None = None


class OnboardingResult(BaseModel):
    is_onboarded: bool
    missing_fields: list[str]
