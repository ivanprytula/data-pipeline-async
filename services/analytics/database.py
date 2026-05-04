"""Database engine, session factory, and get_db dependency for analytics.

Uses NullPool (no connection pooling) — see inline comment for rationale.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


DATABASE_URL: str = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required for analytics. "
        "Set it via environment variable or a secrets manager."
    )

# POOLING STRATEGY: NullPool (No Connection Pooling)
# ─────────────────────────────────────────────────
# Why NullPool for analytics instead of the default QueuePool?
#
# 1. READ-ONLY WORKLOAD — each HTTP request runs independent SELECT queries.
#    Connection reuse via pooling provides zero benefit here.
#
# 2. STATELESS HORIZONTAL SCALING — multiple replicas can connect/disconnect
#    freely.  QueuePool wastes memory (pool_size per replica).
#
# 3. PREDICTABLE CONNECTION LIMITS — connection count is fixed per request,
#    safe to autoscale without pool exhaustion.
#
# Ingestor uses QueuePool (see ingestor/database.py) because it has stateful
# CRUD sessions spanning multiple operations and transaction boundaries.
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency: yield a fresh async database session per request."""
    async with AsyncSessionLocal() as session:
        yield session
