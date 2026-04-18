"""Pytest fixtures for the async stack (aiosqlite in-memory or PostgreSQL).

Database selection:
  - Default: SQLite in-memory (no external dependency)
  - If DATABASE_URL_TEST env var set: Use PostgreSQL (for concurrent tests)

To run with PostgreSQL:
  1. Start test DB: docker compose --profile test up db-test
  2. Set env: export DATABASE_URL_TEST=postgresql+asyncpg://postgres:postgres@localhost:5433/test_database
  3. Run tests: pytest tests/integration/records/test_concurrency.py -v
"""

import datetime
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
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings
from app.database import Base, get_db
from app.main import app
from tests.shared.payloads import RECORD_API


# ---------------------------------------------------------------------------
# Database engine selection (SQLite fallback, PostgreSQL for concurrent tests)
# ---------------------------------------------------------------------------
_TEST_DB_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "sqlite+aiosqlite:///:memory:",  # Default: in-memory SQLite
)

# For PostgreSQL, set pool size to match concurrent test load
_engine_kwargs = {}
if "postgresql" in _TEST_DB_URL:
    # Use NullPool in tests to ensure connections are not pooled across
    # event loop boundaries. Pooling can create connections attached to a
    # different asyncio event loop, causing "Future attached to a different
    # loop" RuntimeError when pytest_asyncio switches loops between tests.
    _engine_kwargs["poolclass"] = NullPool

_engine = None
_AsyncSessionLocal = None


def _ensure_sessionmaker() -> None:
    """Lazily create the async engine and sessionmaker.

    Must be called from the test event loop (i.e., inside fixtures). Creating
    the engine at import time can bind asyncpg internals to a different
    asyncio event loop which causes "Future attached to a different loop"
    errors during testing. Creating lazily inside fixtures avoids that.
    """
    global _engine, _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _engine = create_async_engine(_TEST_DB_URL, echo=False, **_engine_kwargs)
        _AsyncSessionLocal = async_sessionmaker(
            bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False
        )


_RECORD_TIMESTAMP = datetime.datetime.fromisoformat("2024-01-01T00:00:00")

# Export flag for use in test markers
IS_POSTGRES = "postgresql" in _TEST_DB_URL
IS_SQLITE = "sqlite" in _TEST_DB_URL


@pytest_asyncio.fixture()
async def db() -> AsyncGenerator[AsyncSession]:
    """Create schema, yield session, teardown schema — all async."""
    _ensure_sessionmaker()
    async with _engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)
    async with _AsyncSessionLocal() as session:  # type: ignore[call-arg]
        yield session
    async with _engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture()
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Async HTTPX client with DB dependency overridden.

    For PostgreSQL (and general robustness), provide a fresh `AsyncSession`
    for each HTTP request by using the module-level `_AsyncSessionLocal`.
    The `db` fixture is still depended-on to ensure schema creation.
    """

    # Ensure the module-level sessionmaker is created on the active test event loop
    _ensure_sessionmaker()

    async def _override() -> AsyncGenerator[AsyncSession]:
        # Defensive: ensure sessionmaker initialized (may be None if not created)
        _ensure_sessionmaker()
        assert _AsyncSessionLocal is not None, "_AsyncSessionLocal not initialized"
        SessionLocal = _AsyncSessionLocal  # type: ignore[assignment]

        # Provide a fresh session for each request to avoid sharing a single
        # session across concurrent requests (which causes asyncpg errors).
        async with SessionLocal() as session:  # type: ignore[call-arg]
            yield session

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def client_isolated(
    postgresql_async_session_isolated: AsyncSession,
) -> AsyncGenerator[AsyncClient]:
    """Async HTTPX client with isolated PostgreSQL session (no connection pooling).

    Use for concurrent tests to avoid asyncpg "another operation in progress" errors.
    Each HTTP request gets independent DB connection. Skips if PostgreSQL unavailable.
    """
    # Store the sessionmaker from the isolated session so we can create fresh sessions
    SessionLocal = postgresql_async_session_isolated._sessionmaker  # type: ignore

    async def _override() -> AsyncGenerator[AsyncSession]:
        # Create a FRESH session for each HTTP request (critical for concurrent tests!)
        async with SessionLocal() as session:
            yield session

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
async def sample_records_with_tags(db: AsyncSession) -> list:
    """Create sample records with varying tag counts for testing queries.

    Useful for N+1 demo and other query optimization tests.
    Creates records with 0, 2, 4, 6, 8 tags respectively.
    """
    from app.crud import create_record
    from app.schemas import RecordRequest

    records = []
    for i in range(5):
        request = RecordRequest(
            source=f"sample-{i}",
            timestamp=_RECORD_TIMESTAMP,
            data={"index": i},
            tags=[f"tag-{j}" for j in range(i * 2)],  # 0, 2, 4, 6, 8 tags
        )
        record = await create_record(db, request)
        records.append(record)
    return records


@pytest_asyncio.fixture()
async def record_payload() -> dict:
    """Valid record payload for testing."""
    return RECORD_API.copy()


# ---------------------------------------------------------------------------
# PostgreSQL Fixture (for EXPLAIN ANALYZE tests)
# ---------------------------------------------------------------------------
# Uses conditional connection to Docker PostgreSQL:
# 1. If Docker container at localhost:5433 is running: use it
# 2. Otherwise: skip tests gracefully
#
# To enable: docker compose --profile test up db-test


async def _check_postgres_available(
    host: str, port: int, user: str, password: str, db: str
) -> bool:
    """Check if PostgreSQL service is available.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        user: PostgreSQL user
        password: PostgreSQL password
        db: Database name

    Returns:
        True if connection successful, False otherwise
    """
    db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
    test_engine = create_async_engine(db_url, echo=False)
    try:
        async with test_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await test_engine.dispose()


@pytest_asyncio.fixture()
async def postgresql_async_session(request) -> AsyncGenerator[AsyncSession]:
    """Create PostgreSQL async session for EXPLAIN ANALYZE tests.

    Tries to connect to Docker PostgreSQL service at localhost:5433.
    If unavailable, skips tests gracefully.

    To enable: docker compose --profile test up db-test

    Yields:
        AsyncSession connected to PostgreSQL with schema created
    """
    # Configuration for Docker PostgreSQL service
    pg_config = {
        "host": "localhost",
        "port": 5433,
        "user": "postgres",
        "password": "postgres",
        "db": "test_database",
    }

    # Check if PostgreSQL is available
    available = await _check_postgres_available(
        pg_config["host"],
        pg_config["port"],
        pg_config["user"],
        pg_config["password"],
        pg_config["db"],
    )

    if not available:
        pytest.skip(
            f"PostgreSQL not available at {pg_config['host']}:{pg_config['port']}. "
            "Start with: docker compose --profile test up db-test"
        )
        return

    # Connect to Docker PostgreSQL
    db_url = f"postgresql+asyncpg://{pg_config['user']}:{pg_config['password']}@{pg_config['host']}:{pg_config['port']}/{pg_config['db']}"

    pg_engine = create_async_engine(db_url, echo=False)
    pg_sessionmaker = async_sessionmaker(
        bind=pg_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )

    # Create schema
    try:
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with pg_sessionmaker() as session:
            yield session
    finally:
        # Cleanup
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await pg_engine.dispose()


@pytest_asyncio.fixture()
async def postgresql_async_session_isolated() -> AsyncGenerator[AsyncSession]:
    """PostgreSQL-only fixture: Fresh engine + session per test (no connection pooling).

    Use for concurrent tests to avoid asyncpg "another operation in progress" errors.
    Skips if DATABASE_URL_TEST not set or points to SQLite.

    Each test gets isolated connection — no connection pooling/reuse within test.
    Solves: asyncpg cannot handle concurrent operations on same connection.
    """
    db_url = os.environ.get("DATABASE_URL_TEST")
    if not db_url or "sqlite" in db_url:
        pytest.skip(
            "DATABASE_URL_TEST not set or SQLite in use. "
            "Concurrent tests require PostgreSQL. "
            "Start with: docker compose --profile test up db-test"
        )

    # Create isolated engine — NO connection pooling (pool_size=1, max_overflow=0)
    # This ensures each test gets a fresh connection without reuse conflicts
    isolated_engine = create_async_engine(
        db_url,
        echo=False,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,  # Validate connections before use
    )

    # Create schema
    try:
        async with isolated_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session (expires_on_commit=False required for async)
        SessionLocal = async_sessionmaker(
            isolated_engine,
            expire_on_commit=False,
            autoflush=False,
        )

        async with SessionLocal() as session:
            # Store sessionmaker on the session for use by client_isolated
            session._sessionmaker = SessionLocal  # type: ignore
            yield session
    finally:
        # Cleanup
        async with isolated_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await isolated_engine.dispose()


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


# ---------------------------------------------------------------------------
# Pytest Hooks & Configuration
# ---------------------------------------------------------------------------
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "postgresonly: mark test to run only when PostgreSQL is available "
        "(skip on SQLite in-memory)",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip PostgreSQL-only tests when using SQLite.

    Tests marked with @pytest.mark.postgresonly will skip if DATABASE_URL_TEST
    is not set or points to SQLite.
    """
    if IS_SQLITE:
        skip_marker = pytest.mark.skip(
            reason="PostgreSQL not available. "
            "Run with: DATABASE_URL_TEST=postgresql+asyncpg://... pytest ..."
        )
        for item in items:
            if "postgresonly" in item.keywords:
                item.add_marker(skip_marker)
