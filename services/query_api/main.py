"""Query API — Read-only analytics service.

Phase 5 CQRS read side: decoupled from ingestor, optimized for analytics queries.

Features:
- Materialized views for fast pre-aggregated data
- Window functions for ranking and percentile calculations
- CTEs for multi-step transformations
- Eventual consistency (reads may lag slightly behind ingestor writes)
"""

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from services.query_api import dependencies
from services.query_api.routers import analytics


logger = logging.getLogger(__name__)

# Database configuration (read-only, same PostgreSQL as ingestor)
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required for query_api. "
        "Set it via environment variables or a secrets manager."
    )

# Create async engine with read-only semantics
#
# POOLING STRATEGY: NullPool (No Connection Pooling)
# ─────────────────────────────────────────────────
# Why NullPool for query_api instead of default QueuePool?
#
# 1. READ-ONLY WORKLOAD
#    Each HTTP request executes independent SELECT queries.
#    No transaction spans multiple operations or request boundaries.
#    Connection reuse via pooling provides zero benefit.
#
# 2. STATELESS HORIZONTAL SCALING
#    Query API is deployed as stateless HTTP service (N replicas).
#    Each replica can connect/disconnect freely without coordination.
#    No shared connection pool state between replicas.
#    QueuePool would waste memory on pool_size per replica.
#
# 3. ZERO OVERHEAD
#    NullPool creates a fresh connection per query, discards immediately.
#    No background pool management, no pool warmup, minimal memory.
#    Ideal for serverless/FaaS deployment patterns (scales to zero).
#
# 4. HORIZONTAL AUTOSCALING
#    Database connection limit is predictable: fixed per request.
#    Can safely scale to 100 replicas without pool explosion.
#    QueuePool with pool_size=10 would exhaust connections at 10 replicas.
#
# INGESTOR (CRUD service) USES QueuePool:
# ─────────────────────────────────────
# Ingestor has persistent CRUD sessions spanning multiple operations:
#   - Multi-row inserts with error handling
#   - Transaction management (rollback on failure)
#   - Connection reuse across request lifecycle
#   - Stateful workers processing pipeline tasks
# QueuePool with pool_size=10, max_overflow=20 optimizes this pattern.
#
# Reference: See ingestor/database.py for production QueuePool config.
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # No connection pooling for stateless read-only service
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Dependency: Get database session for read-only queries."""
    async with AsyncSessionLocal() as session:
        yield session


# Configure the dependencies module with the actual get_db implementation
dependencies.get_db = get_db  # ty:ignore[invalid-assignment]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle.

    Startup: Verify database connection.
    Shutdown: Close engine and dispose pools.
    """
    logger.info("Query API starting up...")
    try:
        # Verify database connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

    yield

    logger.info("Query API shutting down...")
    await engine.dispose()


app = FastAPI(
    title="Query API — Analytics Read Side",
    description="CQRS read-optimized service for Phase 5. Read-only access to PostgreSQL.",
    version="0.1.0",
    lifespan=lifespan,
)


# Include analytics routes
app.include_router(analytics.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "query_api"}


@app.get("/readyz", tags=["readiness"])
async def readiness() -> dict:
    """Readiness probe: Verify database connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as e:
        return {"ready": False, "reason": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
