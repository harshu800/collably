"""Structured JSON logging with a per-request correlation id.

A middleware stamps every request with a UUID4 request id (or honors an
inbound ``X-Request-ID`` header). The id is attached to a context var so log
records emitted during that request include it. One access log line is emitted
per request on completion.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def _add_request_id(_logger, _method, event_dict):  # noqa: ANN001
    rid = request_id_var.get()
    if rid:
        event_dict["request_id"] = rid
    uid = user_id_var.get()
    if uid:
        event_dict["user_id"] = uid
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog + stdlib logging to emit JSON lines."""

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Baseline stdlib config so library logs flow through our handler.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name) if name else structlog.get_logger()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request id to each request and log one access line."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._log = get_logger("http")

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        inbound = request.headers.get("x-request-id")
        rid = inbound or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["x-request-id"] = rid
            return response
        finally:
            latency_ms = int((time.perf_counter() - start) * 1000)
            self._log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                latency_ms=latency_ms,
            )
            request_id_var.reset(token)
