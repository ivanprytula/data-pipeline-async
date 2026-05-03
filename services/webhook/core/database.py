"""Webhook service database configuration.

Separate engine/session from the ingestor — each service owns its
connection pool independently, even though they share the same
PostgreSQL instance (single-DB monorepo pattern).
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.webhook.models import Base


_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline",
)

engine = create_async_engine(_DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
)


async def get_db():
    """FastAPI dependency — yields an AsyncSession per request."""
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables() -> None:
    """Create tables on startup (dev/test only; prod uses Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
