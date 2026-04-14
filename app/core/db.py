"""
Async SQLAlchemy engine + session factory.
Provides get_db() dependency and Base declarative base.

Engine is created lazily (on first call to get_engine()) so that importing
this module — e.g. from Alembic's env.py — does NOT require asyncpg to be
installed or DB_URL to be set.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# Module-level singletons, populated lazily on first use
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return (creating if necessary) the shared async engine."""
    global _engine
    if _engine is None:
        from app.core.config import settings  # deferred import avoids circular deps
        _engine = create_async_engine(
            settings.DB_URL,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,   # health-check connections before use
            echo=settings.is_dev, # log SQL only in dev
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (creating if necessary) the shared session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# Convenience alias used by services that need a session outside of a request
# (e.g. bot intent handlers). Import this, not the factory directly.
AsyncSessionLocal = get_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a single async DB session per request.
    Rolls back on exception, always closes the session.
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
