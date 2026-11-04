"""Health check endpoint."""


from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db.session import get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    """Readiness probe: checks database connectivity.

    Returns 200 if the database is reachable, 503 otherwise.
    Suitable for Kubernetes readiness probes or Docker Compose healthchecks.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=200,
            content={"status": "ready", "db": "connected"},
        )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "db": "unreachable"},
        )


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    """Liveness probe: always returns 200.

    Suitable for Kubernetes liveness probes to detect if the process is alive.
    """
    return {"status": "live"}
