"""slowapi Limiter configured to honor X-Forwarded-For when TRUST_PROXY=true."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings


def _client_ip(request: Request) -> str:
    """Return the client IP, honoring the first X-Forwarded-For hop in proxied mode."""

    if get_settings().trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip, headers_enabled=True)
