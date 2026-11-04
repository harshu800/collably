"""FastAPI app factory: structured logging + request id + settings validation + routes."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestIdMiddleware, configure_logging, get_logger
from app.core.rate_limit import limiter


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ANN001
    # Startup
    settings = get_settings()
    configure_logging("INFO" if not settings.debug else "DEBUG")
    log = get_logger("startup")
    log.info(
        "boot",
        env=settings.env,
        debug=settings.debug,
        payment_provider=settings.payment_provider,
    )
    # Fail fast on prod misconfiguration.
    settings.validate_production()
    yield
    # Shutdown (nothing yet — the async engine disposes on process exit).


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="India Marketplace API",
        version="0.1.0",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    # Structured JSON logs with per-request correlation id.
    app.add_middleware(RequestIdMiddleware)

    # CORS allowlist.
    origins = settings.cors_origin_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["x-request-id"],
        )

    # Rate limiting (slowapi).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Typed domain errors → JSON responses with stable error_code strings.
    register_exception_handlers(app)

    # Routes.
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root(request: Request) -> dict[str, str]:
        return {"status": "ok", "service": "india-marketplace-api"}

    return app


app = create_app()
