"""Signed-file-token signing and AES-GCM payout field crypto.

Everything in this module is a pure function. Password hashing + Clerk auth
JWT handling live elsewhere — this file only owns the two bits of local
cryptography the backend still needs:

* HS256 signed file tokens for short-lived download URLs.
* AES-256-GCM field encryption for payout methods.
"""

from __future__ import annotations

import base64
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

# -----------------------------------------------------------------------
# Signed file-download tokens (short-lived HS256 JWT, independent of Clerk)
# -----------------------------------------------------------------------

FILE_TOKEN_ALGORITHM = "HS256"
FILE_TOKEN_LEEWAY_SECONDS = 30


def _now_utc() -> datetime:
    return datetime.now(UTC)


def create_file_token(
    *,
    file_id: str,
    user_id: str,
    ttl_seconds: int = 300,
) -> str:
    settings = get_settings()
    now = _now_utc()
    claims: dict[str, Any] = {
        "sub": user_id,
        "type": "file",
        "file_id": file_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(
        claims,
        settings.file_token_secret,
        algorithm=FILE_TOKEN_ALGORITHM,
    )


def decode_file_token(token: str) -> dict[str, Any]:
    """Decode a signed file-download token.

    Raises :class:`jwt.InvalidTokenError` (or subclass) on any failure
    including expiry past the 30s leeway and type-claim mismatch.
    """

    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.file_token_secret,
        algorithms=[FILE_TOKEN_ALGORITHM],
        leeway=FILE_TOKEN_LEEWAY_SECONDS,
    )
    if payload.get("type") != "file":
        raise jwt.InvalidTokenError(
            f"Expected token type 'file', got {payload.get('type')!r}"
        )
    return payload


# -----------------------------------------------------------------------
# AES-256-GCM field encryption for payout methods
# -----------------------------------------------------------------------


def _load_enc_key() -> bytes:
    settings = get_settings()
    raw = base64.b64decode(settings.payout_field_enc_key, validate=False)
    if len(raw) != 32:
        # Caller may still use this in dev with the placeholder key — pad or
        # truncate to 32 bytes so the primitives don't crash locally. The
        # production startup check prevents this path from being hit live.
        raw = (raw + b"\x00" * 32)[:32]
    return raw


def field_encrypt(plaintext: str, *, aad: bytes | None = None) -> bytes:
    """Return ``nonce || ciphertext`` as a single bytes blob."""

    key = _load_enc_key()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), aad)
    return nonce + ct


def field_decrypt(blob: bytes, *, aad: bytes | None = None) -> str:
    key = _load_enc_key()
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:]
    return aes.decrypt(nonce, ct, aad).decode("utf-8")
