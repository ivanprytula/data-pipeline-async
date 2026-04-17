"""Pytest fixtures for the async stack (aiosqlite in-memory)."""

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch


# Set testing environment BEFORE any app imports
# This ensures the app loads with testing configuration.
os.environ["ENVIRONMENT"] = "testing"
os.environ.setdefault("DOCS_USERNAME", "")
os.environ.setdefault("DOCS_PASSWORD", "")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.database import Base, get_db
from app.main import app
from tests.shared.payloads import RECORD_API


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


# ---------------------------------------------------------------------------
# Settings Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def test_settings() -> Settings:
    """Override app settings for testing.

    Useful for tests that need to verify different configurations
    (e.g., docs auth enabled/disabled, different log levels).
    """
    return Settings(
        environment="testing",
        app_version="1.0.0-test",
        docs_username=None,  # Docs public in tests by default
        docs_password=None,
        api_v1_bearer_token=None,
        jwt_secret="test-secret-key-32-chars-minimum!!",
        db_echo=False,
    )


@pytest.fixture()
def settings_with_docs_auth() -> Settings:
    """Settings with documentation authentication enabled."""
    return Settings(
        environment="testing",
        docs_username="admin",
        docs_password="secret123",
        db_echo=False,
    )


@pytest.fixture()
def settings_with_api_token() -> Settings:
    """Settings with API v1 bearer token enabled."""
    return Settings(
        environment="testing",
        api_v1_bearer_token="test-bearer-token-123",
        db_echo=False,
    )


# ---------------------------------------------------------------------------
# Record Fixtures (pre-populated records for testing)
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def created_record(client: AsyncClient) -> dict:
    """Create and return a single valid record."""
    response = await client.post("/api/v1/records", json=RECORD_API)
    return response.json()


@pytest_asyncio.fixture()
async def created_records(client: AsyncClient) -> list[dict]:
    """Create and return multiple records."""
    records = []
    for i in range(3):
        payload = {
            **RECORD_API,
            "source": f"source-{i}",
            "tags": ["test", f"record-{i}"],
        }
        response = await client.post("/api/v1/records", json=payload)
        records.append(response.json())
    return records


@pytest_asyncio.fixture()
async def record_payload() -> dict:
    """Valid record payload for testing."""
    return RECORD_API.copy()


# ---------------------------------------------------------------------------
# Mock/Override Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture()
async def mock_db_failure() -> AsyncGenerator[AsyncMock]:
    """Mock database that raises RuntimeError on execute().

    Use with app.dependency_overrides[get_db] to simulate DB failure.
    """
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = RuntimeError("Database connection lost")
    yield mock_session


@pytest.fixture()
def app_with_docs_auth(settings_with_docs_auth: Settings):
    """FastAPI app with docs authentication enabled."""
    with patch("app.main.settings", settings_with_docs_auth):
        yield app


@pytest.fixture()
def app_with_api_token(settings_with_api_token: Settings):
    """FastAPI app with API token authentication enabled."""
    with patch("app.main.settings", settings_with_api_token):
        yield app
