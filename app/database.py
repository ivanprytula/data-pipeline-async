"""Async database engine, session factory, and dependency injection.

Why `expire_on_commit=False` — after `await session.commit()`
SQA would expire every attribute. In an async context we cannot lazily reload them
(no sync DB round-trips allowed), so `expire_on_commit=False` keeps the values in-memory
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,  # Permanent connections in pool
    max_overflow=settings.db_max_overflow,  # Temporary connections during spikes
    pool_timeout=settings.db_pool_timeout,  # Wait time for connection
    pool_recycle=settings.db_pool_recycle,  # Prevent stale connections
    pool_pre_ping=True,  # Verify connection before use
    echo=settings.db_echo,  # SQL logging for debugging
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,  # Manual control over flushing
    expire_on_commit=False,  # Keep data accessible after commit, avoids lazy-load error
    autocommit=False,  # Require explicit commits
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: yields a fresh async DB session for each request.

    How it solves AsyncSession concurrency:
    - Each request gets its own session instance (no sharing between requests)
    - SQLAlchemy warns "AsyncSession is not safe for use in concurrent tasks"
      but this means: don't share a single session across multiple concurrent tasks
    - FastAPI's dependency injection ensures each request has isolated session
    - Request 1 → AsyncSession A, Request 2 → AsyncSession B, etc.
    - Even though multiple requests are concurrent (async), they don't share sessions

    Session lifecycle:
    - Context manager: yields session on enter, auto-closes on exit (cleanup guaranteed)
    - Sessions created fresh per request (stateless pattern)
    - Implicit by on_exit: session rolls back if exc before yield, commits if explicit
    """
    async with AsyncSessionLocal() as session:
        # Safety check: ensure session was created with expire_on_commit=False.
        # Async SQLAlchemy requires this in async code to avoid lazy-loading
        # that would perform sync DB calls after the event loop context has moved on.
        if getattr(session, "expire_on_commit", True):
            raise RuntimeError(
                "AsyncSessionLocal must be configured with expire_on_commit=False"
            )
        yield session
