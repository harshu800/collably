"""Async SQLAlchemy engine + sessionmaker and the ``get_db`` dependency.

The engine is created lazily on first access so tests can set
``DATABASE_URL`` in their environment before the app is imported and still
get a session pointed at ``marketplace_test``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            future=True,
        )
        _sessionmaker = async_sessionmaker(
            bind=_engine,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


# Backwards-compatible module attribute. Importing this still works; it is
# resolved on first use (the ``get_db`` dependency goes through
# ``get_sessionmaker`` so test setups that swap the engine do not get stale
# bindings).
class _SessionLocalProxy:
    def __call__(self, *args: object, **kwargs: object) -> AsyncSession:
        return get_sessionmaker()(*args, **kwargs)


AsyncSessionLocal = _SessionLocalProxy()


def reset_engine() -> None:
    """Dispose the current engine so the next call rebuilds it. Test helper."""

    global _engine, _sessionmaker
    _engine = None
    _sessionmaker = None


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields a session and commits on normal exit."""

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
