"""Pytest fixtures for the async stack (aiosqlite in-memory)."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app


# ---------------------------------------------------------------------------
# In-memory aiosqlite engine — no real PostgreSQL needed for unit tests
# ---------------------------------------------------------------------------
_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_engine = create_async_engine(_TEST_DB_URL, echo=False)
_AsyncSessionLocal = async_sessionmaker(
    bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False
)


@pytest_asyncio.fixture()
async def db() -> AsyncGenerator[AsyncSession]:
    """Create schema, yield session, teardown schema — all async."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with _AsyncSessionLocal() as session:
        yield session
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Async HTTPX client with DB dependency overridden."""

    async def _override() -> AsyncGenerator[AsyncSession]:
        yield db

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
