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
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.sql_echo,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # avoids lazy-load errors after commit
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: yields an async DB session, always closes on exit."""
    async with AsyncSessionLocal() as session:
        yield session
