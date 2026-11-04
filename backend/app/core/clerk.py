"""Clerk integration — JWT verification + webhook signature verification.

Two primitives live here:

* :func:`verify_clerk_jwt` — validates a Bearer token Clerk minted for a
  session. In normal operation it fetches Clerk's JWKS (RS256) and verifies
  the signature + ``iss`` claim + expiry (with a 30s leeway). When
  ``TESTING_BYPASS_CLERK`` is set, it instead verifies a locally-minted
  HS256 token signed with ``TESTING_CLERK_LOCAL_SECRET`` so our pytest suite
  can run without the real Clerk service.

* :func:`verify_clerk_webhook` — wraps ``svix.Webhook`` for inbound Clerk
  webhook deliveries, with a parallel bypass path triggered by the
  ``X-Testing-Clerk-Bypass`` header.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx
import jwt
from svix.webhooks import Webhook, WebhookVerificationError

from app.core.config import get_settings

CLERK_JWT_ALGORITHM = "RS256"
CLERK_JWT_LEEWAY_SECONDS = 30
JWKS_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class ClerkClaims:
    """Normalized subset of a Clerk-issued JWT we care about."""

    sub: str
    email: str | None
    raw: dict[str, Any]


# ---------------------------------------------------------------------------
# JWKS client (1h cache, refetch on missing kid)
# ---------------------------------------------------------------------------


class ClerkJWKSClient:
    """Tiny JWKS client with a one-hour cache keyed by ``kid``.

    On a cache miss (or a seen token referencing an unknown ``kid``) the
    client re-fetches the JWKS once before giving up.
    """

    def __init__(self, jwks_url: str) -> None:
        self._jwks_url = jwks_url
        self._lock = Lock()
        self._fetched_at: float = 0.0
        self._keys: dict[str, Any] = {}

    def _needs_refresh(self, kid: str) -> bool:
        if kid in self._keys and time.monotonic() - self._fetched_at < JWKS_CACHE_TTL_SECONDS:
            return False
        return True

    def _fetch(self) -> None:
        with httpx.Client(timeout=10.0) as http:
            resp = http.get(self._jwks_url)
            resp.raise_for_status()
            data = resp.json()
        keys = data.get("keys") or []
        parsed: dict[str, Any] = {}
        for jwk_dict in keys:
            kid = jwk_dict.get("kid")
            if not kid:
                continue
            try:
                parsed[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(
                    json.dumps(jwk_dict)
                )
            except Exception:
                # Skip malformed entries rather than failing the whole fetch.
                continue
        self._keys = parsed
        self._fetched_at = time.monotonic()

    def get_signing_key(self, kid: str) -> Any:
        with self._lock:
            if self._needs_refresh(kid):
                self._fetch()
            if kid not in self._keys:
                # Try once more in case the cache was simply stale.
                self._fetch()
            if kid not in self._keys:
                raise jwt.InvalidTokenError(f"Unknown Clerk JWK kid: {kid}")
            return self._keys[kid]


_jwks_client: ClerkJWKSClient | None = None
_jwks_client_lock = Lock()


def _get_jwks_client() -> ClerkJWKSClient:
    global _jwks_client
    with _jwks_client_lock:
        settings = get_settings()
        if _jwks_client is None or _jwks_client._jwks_url != settings.clerk_jwks_url:
            _jwks_client = ClerkJWKSClient(settings.clerk_jwks_url)
        return _jwks_client


def reset_jwks_client_cache() -> None:
    """Test helper — drops the module-level JWKS client."""

    global _jwks_client
    with _jwks_client_lock:
        _jwks_client = None


# ---------------------------------------------------------------------------
# JWT verification
# ---------------------------------------------------------------------------


def _normalize_email(payload: dict[str, Any]) -> str | None:
    for key in ("email", "primary_email", "email_address"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value.lower()
    return None


def verify_clerk_jwt(token: str) -> ClerkClaims:
    """Verify a Clerk-issued bearer JWT and return the normalized claims.

    Raises :class:`jwt.InvalidTokenError` (or subclass) on any failure.
    """

    settings = get_settings()

    if settings.testing_bypass_clerk:
        if not settings.testing_clerk_local_secret:
            raise jwt.InvalidTokenError(
                "TESTING_BYPASS_CLERK is on but TESTING_CLERK_LOCAL_SECRET is empty"
            )
        payload = jwt.decode(
            token,
            settings.testing_clerk_local_secret,
            algorithms=["HS256"],
            leeway=CLERK_JWT_LEEWAY_SECONDS,
            options={"verify_aud": False, "verify_iss": False},
        )
        if payload.get("type") != "clerk_test":
            raise jwt.InvalidTokenError(
                "Testing Clerk token missing type='clerk_test'"
            )
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise jwt.InvalidTokenError("Testing Clerk token missing 'sub'")
        return ClerkClaims(sub=sub, email=_normalize_email(payload), raw=payload)

    # Real Clerk path.
    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise jwt.InvalidTokenError("Malformed JWT header") from exc
    kid = header.get("kid")
    if not kid:
        raise jwt.InvalidTokenError("JWT header missing 'kid'")

    signing_key = _get_jwks_client().get_signing_key(kid)
    payload = jwt.decode(
        token,
        signing_key,
        algorithms=[CLERK_JWT_ALGORITHM],
        issuer=settings.clerk_issuer or None,
        leeway=CLERK_JWT_LEEWAY_SECONDS,
        options={"verify_aud": False},
    )
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise jwt.InvalidTokenError("Clerk token missing 'sub'")
    return ClerkClaims(sub=sub, email=_normalize_email(payload), raw=payload)


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------


TESTING_WEBHOOK_BYPASS_HEADER = "x-testing-clerk-bypass"


def verify_clerk_webhook(
    body: bytes,
    headers: Mapping[str, str],
) -> dict[str, Any]:
    """Verify a Clerk webhook delivery via svix.

    Returns the parsed JSON payload. Raises
    :class:`svix.webhooks.WebhookVerificationError` on failure (or
    :class:`ValueError` for a malformed test-bypass invocation) — callers map
    those to HTTP 401.
    """

    settings = get_settings()
    normalised = {k.lower(): v for k, v in headers.items()}

    # Test bypass path — only engaged when the explicit header is present AND
    # TESTING_BYPASS_CLERK is enabled server-side.
    bypass_header = normalised.get(TESTING_WEBHOOK_BYPASS_HEADER)
    if bypass_header is not None:
        if not settings.testing_bypass_clerk:
            raise WebhookVerificationError(
                "Testing-Clerk-Bypass header rejected: bypass disabled"
            )
        if not settings.testing_clerk_local_secret or bypass_header != settings.testing_clerk_local_secret:
            raise WebhookVerificationError(
                "Testing-Clerk-Bypass header did not match local secret"
            )
        try:
            return json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise WebhookVerificationError("Bypass body not JSON") from exc

    # Real svix path.
    wh = Webhook(settings.clerk_webhook_secret)
    # svix.Webhook.verify accepts a mapping-like object for headers.
    payload = wh.verify(body, dict(headers))
    if isinstance(payload, bytes | str):
        payload = json.loads(payload if isinstance(payload, str) else payload.decode("utf-8"))
    return payload
