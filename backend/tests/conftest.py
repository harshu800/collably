"""Shared pytest fixtures.

Setup contract:

* A dedicated Postgres database ``marketplace_test`` is created once per test
  session using an admin connection and ``alembic upgrade head`` is run against
  it. The database is not dropped at session end — repeat runs reuse it so
  migrations only execute when a new revision is introduced.
* Each test opens a nested transaction (``SAVEPOINT``) that is rolled back on
  teardown so tests do not see each other's writes.
* The FastAPI app's ``get_db`` dependency is overridden to return the
  per-test session.
* ``TESTING_BYPASS_CLERK=true`` makes :func:`app.core.clerk.verify_clerk_jwt`
  accept locally-minted HS256 tokens signed with ``TESTING_CLERK_LOCAL_SECRET``
  so we never touch the real Clerk service in tests.
"""

from __future__ import annotations

import asyncio
import base64
import os
import secrets
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Environment overrides — must happen before any ``from app...`` imports so
# ``Settings`` picks up the test URL.
# ---------------------------------------------------------------------------

_TEST_DB_NAME = "marketplace_test"
_PG_USER = os.getenv("POSTGRES_USER", "marketplace")
_PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "marketplace")
_PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
_PG_PORT = os.getenv("POSTGRES_PORT", "5432")

os.environ.setdefault("ENV", "test")
os.environ["DATABASE_URL"] = (
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB_NAME}"
)
os.environ["DATABASE_URL_SYNC"] = (
    f"postgresql+psycopg2://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB_NAME}"
)

# --- Clerk test bypass -------------------------------------------------------
TESTING_CLERK_LOCAL_SECRET = secrets.token_hex(32)
os.environ["TESTING_BYPASS_CLERK"] = "true"
os.environ["TESTING_CLERK_LOCAL_SECRET"] = TESTING_CLERK_LOCAL_SECRET
os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_REPLACE_ME")
os.environ.setdefault("CLERK_PUBLISHABLE_KEY", "pk_test_REPLACE_ME")
os.environ.setdefault("CLERK_WEBHOOK_SECRET", "your_clerk_webhook_secret")
os.environ.setdefault(
    "CLERK_JWKS_URL", "https://example.com/.well-known/jwks.json"
)
os.environ.setdefault(
    "CLERK_ISSUER", "https://example.clerk.accounts.dev"
)

# Deterministic, non-placeholder secrets so prod-check logic can run cleanly
# in tests that explicitly flip ENV=prod.
os.environ["FILE_TOKEN_SECRET"] = "test-file-token-secret-" + ("a" * 32)
os.environ["PAYOUT_FIELD_ENC_KEY"] = base64.b64encode(b"0" * 32).decode()
os.environ["MOCK_PAYMENT_WEBHOOK_SECRET"] = "test-mock-webhook-secret"
os.environ.setdefault("ENABLE_MOCK_PAYMENT_ENDPOINTS", "true")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

# Now safe to import the app.
import httpx  # noqa: E402
import sqlalchemy as sa  # noqa: E402

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

# Rate limits exist to protect production; disable globally in tests so
# we can fire many requests from the same loopback IP without 429s.
limiter.enabled = False


# ---------------------------------------------------------------------------
# Clerk bypass token minting helper
# ---------------------------------------------------------------------------


def make_clerk_token(
    *,
    clerk_user_id: str,
    email: str | None = None,
    ttl_seconds: int = 3600,
) -> str:
    """Mint a bypass-mode Clerk JWT for use in tests.

    The signing path mirrors :func:`app.core.clerk.verify_clerk_jwt`'s
    testing branch: HS256 over ``TESTING_CLERK_LOCAL_SECRET`` with a
    ``type='clerk_test'`` claim.
    """

    now = datetime.now(UTC)
    payload = {
        "sub": clerk_user_id,
        "email": email,
        "email_verified": True,
        "type": "clerk_test",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        "iss": "test",
    }
    return jwt.encode(
        {k: v for k, v in payload.items() if v is not None},
        TESTING_CLERK_LOCAL_SECRET,
        algorithm="HS256",
    )


# ---------------------------------------------------------------------------
# Event loop fixture — one loop for the whole session.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database bootstrap — create the test DB and run migrations once per session.
# ---------------------------------------------------------------------------


def _ensure_test_database_exists() -> None:
    """Create ``marketplace_test`` via an admin connection to ``postgres`` if missing."""

    admin_url = (
        f"postgresql+psycopg2://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/postgres"
    )
    admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            sa.text("SELECT 1 FROM pg_database WHERE datname = :n"),
            {"n": _TEST_DB_NAME},
        ).scalar()
        if not exists:
            conn.execute(sa.text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
    admin_engine.dispose()


def _wipe_users_pre_clerk_migration() -> None:
    """Pre-clear the test ``users`` table so migration 0010 can run.

    The 0010_clerk_auth upgrade aborts if any non-demo user row exists —
    that safety net is for production. The test DB is persistent across
    sessions, so stray rows from prior runs would otherwise block the
    migration. We clear only when the schema is still at the pre-Clerk
    shape (users.password_hash present) + alembic hasn't yet advanced past
    0009.
    """

    admin_url = os.environ["DATABASE_URL_SYNC"]
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            has_users = conn.execute(
                sa.text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'users'"
                )
            ).scalar()
            if not has_users:
                return
            has_password_hash = conn.execute(
                sa.text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'users' AND column_name = 'password_hash'"
                )
            ).scalar()
            if not has_password_hash:
                return
            conn.execute(sa.text("TRUNCATE TABLE users CASCADE"))
    finally:
        engine.dispose()


def _run_migrations() -> None:
    _wipe_users_pre_clerk_migration()
    cfg = Config()
    # Resolve path relative to this file so pytest can run from any cwd.
    import pathlib

    backend_root = pathlib.Path(__file__).resolve().parents[1]
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL_SYNC"])
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def _setup_database() -> Iterator[None]:
    _ensure_test_database_exists()
    _run_migrations()
    yield


# ---------------------------------------------------------------------------
# Per-test session fixture — nested transaction rolled back on teardown.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db(_setup_database) -> AsyncIterator[Any]:
    engine = db_session.get_engine()
    async with engine.connect() as connection:
        trans = await connection.begin()
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        maker = async_sessionmaker(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint",
        )
        async with maker() as session:
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()


@pytest_asyncio.fixture
async def client(db) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client with the ``get_db`` dependency wired to the test session."""

    async def _override_get_db():
        yield db

    fastapi_app.dependency_overrides[db_session.get_db] = _override_get_db

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        try:
            yield c
        finally:
            fastapi_app.dependency_overrides.pop(db_session.get_db, None)


# ---------------------------------------------------------------------------
# User fixtures — all built on top of the Clerk bypass path
# ---------------------------------------------------------------------------


async def _register_user(
    client: httpx.AsyncClient,
    role: str,
    *,
    email: str | None = None,
    clerk_user_id: str | None = None,
) -> dict[str, Any]:
    """Mint a bypass Clerk token, auto-provision via /users/me, pick a role."""

    clerk_user_id = clerk_user_id or f"user_{secrets.token_hex(8)}"
    email = email or f"{role}-{secrets.token_hex(4)}@example.com"
    token = make_clerk_token(clerk_user_id=clerk_user_id, email=email)
    auth = {"Authorization": f"Bearer {token}"}

    # First GET /users/me auto-provisions the row.
    me = await client.get("/api/v1/users/me", headers=auth)
    assert me.status_code == 200, me.text

    # Then select the role once.
    r = await client.post(
        "/api/v1/users/me/role", json={"role": role}, headers=auth
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return {
        "email": body["email"],
        "clerk_user_id": body["clerk_user_id"],
        "role": body["role"],
        "access_token": token,
        "auth_header": auth,
    }


@pytest_asyncio.fixture
async def brand_user(client: httpx.AsyncClient):
    return await _register_user(client, "brand")


@pytest_asyncio.fixture
async def creator_user(client: httpx.AsyncClient):
    return await _register_user(client, "creator")


@pytest_asyncio.fixture
async def second_creator_user(client: httpx.AsyncClient):
    return await _register_user(client, "creator")


@pytest_asyncio.fixture
async def admin_user(db, client: httpx.AsyncClient):
    """Admin user inserted directly through the DB (admin is not self-selectable)."""

    clerk_user_id = f"user_admin_{secrets.token_hex(8)}"
    email = f"admin-{secrets.token_hex(4)}@example.com"
    user = User(
        clerk_user_id=clerk_user_id,
        email=email,
        role=UserRole.admin,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    token = make_clerk_token(clerk_user_id=clerk_user_id, email=email)
    return {
        "id": str(user.id),
        "email": email,
        "clerk_user_id": clerk_user_id,
        "role": "admin",
        "access_token": token,
        "auth_header": {"Authorization": f"Bearer {token}"},
    }


__all__ = [
    "TESTING_CLERK_LOCAL_SECRET",
    "admin_user",
    "brand_user",
    "client",
    "creator_user",
    "db",
    "event_loop",
    "make_clerk_token",
]

# Silence "unused" lint on the UUID import — it's used by downstream helpers.
_ = uuid
