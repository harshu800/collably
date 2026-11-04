"""Pydantic schemas for /me/payout-method routes.

The input schema accepts either a UPI VPA or a bank branch; validation
mirrors design §9. Responses never include decrypted secrets — only the
non-sensitive projection.
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

UPI_VPA_REGEX = re.compile(r"^[a-zA-Z0-9._-]{2,100}@[a-zA-Z][a-zA-Z0-9.-]{1,100}$")
IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
ACCOUNT_NUMBER_REGEX = re.compile(r"^[0-9]{6,20}$")


class _ForbidExtras(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PayoutMethodIn(_ForbidExtras):
    method: Literal["upi", "bank"]
    label: str | None = Field(default=None, max_length=100)
    holder_name: str = Field(min_length=2, max_length=100)
    # UPI
    upi_vpa: str | None = Field(default=None, max_length=200)
    # Bank
    account_number: str | None = Field(default=None, max_length=20)
    ifsc: str | None = Field(default=None, max_length=11)

    @model_validator(mode="after")
    def _check_method_fields(self) -> PayoutMethodIn:
        if self.method == "upi":
            if not self.upi_vpa:
                raise ValueError("upi_vpa is required when method='upi'.")
            if not UPI_VPA_REGEX.match(self.upi_vpa):
                raise ValueError("upi_vpa format is invalid.")
            if self.account_number or self.ifsc:
                raise ValueError(
                    "account_number/ifsc must be empty when method='upi'."
                )
        else:
            if not self.account_number:
                raise ValueError("account_number is required when method='bank'.")
            if not ACCOUNT_NUMBER_REGEX.match(self.account_number):
                raise ValueError("account_number must be 6–20 digits.")
            if not self.ifsc:
                raise ValueError("ifsc is required when method='bank'.")
            if not IFSC_REGEX.match(self.ifsc):
                raise ValueError("ifsc format is invalid.")
            if self.upi_vpa:
                raise ValueError(
                    "upi_vpa must be empty when method='bank'."
                )
        return self


class PayoutMethodOut(BaseModel):
    id: uuid.UUID
    method: Literal["upi", "bank"]
    label: str | None = None
    holder_name: str
    account_number_last4: str | None = None
    upi_vpa_masked: str | None = None
    verified: bool
