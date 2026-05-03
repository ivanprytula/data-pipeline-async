"""Pytest fixtures for webhook service integration tests.

Uses aiosqlite in-memory SQLite for database isolation — no PostgreSQL required.
Kafka publishing is mocked to avoid requiring a live broker.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.webhook.core.database import get_db
from services.webhook.main import app
from services.webhook.models import Base


_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session", autouse=True)
def apply_migrations() -> None:
    """Override root apply_migrations: webhook tests use in-memory SQLite — no-op."""


@pytest_asyncio.fixture
async def db_engine():
    """Create an in-memory SQLite engine for tests."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession]:
    """Provide a clean AsyncSession for each test."""
    session_factory = async_sessionmaker(
        db_engine, expire_on_commit=False, autoflush=False
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """HTTP test client with dependency-injected test database session.

    Kafka publishing is mocked to return offset 42 — avoids requiring a
    live broker in tests.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with (
        patch(
            "services.webhook.routers.webhooks.publish_webhook_event",
            new=AsyncMock(return_value=42),
        ),
        patch(
            "services.webhook.routers.health._check_postgres",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.webhook.routers.health._check_kafka",
            new=AsyncMock(return_value=True),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_source(db_session: AsyncSession):
    """Insert a test webhook source into the DB before each test.

    Returns the WebhookSource ORM instance.
    """
    from services.webhook.crud import create_webhook_source

    return await create_webhook_source(
        session=db_session,
        name="test-source",
        description="Integration test source",
        signing_key_secret_name=None,
        signing_algorithm="hmac-sha256",
        rate_limit_per_minute=100,
    )


SAMPLE_PAYLOAD: dict[str, Any] = {
    "event": "payment.completed",
    "amount": 9999,
    "currency": "USD",
}
