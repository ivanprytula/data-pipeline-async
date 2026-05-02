# PostgreSQL Connection Pooling Strategy

## Overview

This document explains the connection pooling strategy across data-pipeline-async services and when to use `QueuePool` vs `NullPool`.

## Quick Reference

| Service | Role | Pooling | Reason |
|---------|------|---------|--------|
| **ingestor** | CRUD (primary writer) | `QueuePool` (pool_size=10, max_overflow=20) | Multi-operation transactions, connection reuse efficiency |
| **query_api** | Read-only analytics | `NullPool` | Stateless HTTP queries, horizontal scaling, zero overhead |
| **dashboard** | UI backend | N/A (calls services via httpx) | No direct DB connection; calls ingestor + ai_gateway via HTTP |
| **ai_gateway** | Vector search | N/A (Qdrant only) | No PostgreSQL dependency |
| **processor** | Kafka consumer | N/A (event stream only) | No PostgreSQL dependency |

## Connection Pooling Models

### QueuePool (Default for CRUD Services)

**What it is:**
- SQLAlchemy default pool class for synchronous and async engines
- Maintains a persistent pool of N base connections
- Temporarily creates additional connections (up to `max_overflow`) during spikes
- Reuses connections across multiple operations within a request

**When to use:**
- Long-lived CRUD sessions spanning multiple database operations
- Transaction management (BEGIN, INSERT, COMMIT/ROLLBACK)
- Stateful services that benefit from connection reuse
- Services that require connection pooling lifecycle (warmup, health checks)

**Configuration (ingestor example):**
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,           # Base pool size (permanent connections)
    max_overflow=20,        # Additional temp connections during spikes
    pool_timeout=30,        # Seconds to wait for a connection
    pool_recycle=3600,      # Recycle connections older than 1 hour
    pool_pre_ping=True,     # Verify connection alive before use
    echo=False,
)
```

**Sizing guidance:**
- `pool_size`: 5-20, depends on concurrency. Start at 10.
- `max_overflow`: 1.5-3x pool_size. Allows spikes without failing.
- `pool_timeout`: 15-60s. How long to wait for available connection.
- `pool_recycle`: 3600s (1h). Prevents database-side timeout (PostgreSQL default ~30min idle disconnect).

### NullPool (Read-Only Stateless Services)

**What it is:**
- No pooling: creates a fresh connection per operation, discards immediately
- Zero pool management overhead
- Ideal for stateless, horizontally-scaled services

**When to use:**
- Read-only HTTP endpoints with independent queries (no spanning operations)
- Stateless services deployed as N replicas
- Serverless/FaaS patterns (scales to zero)
- Services that don't benefit from connection reuse

**Why query_api uses NullPool:**

1. **Read-Only Workload** — Each HTTP request executes independent `SELECT` queries. No transaction spans multiple operations or request boundaries. Connection reuse provides zero performance benefit.

2. **Stateless Horizontal Scaling** — Query API is deployed as stateless HTTP service (N replicas). Each replica can connect/disconnect freely without coordination. QueuePool with `pool_size=10` would waste memory on 10 connections × N replicas.

3. **Zero Overhead** — NullPool creates a connection per query, discards immediately. No background pool management, no pool warmup, minimal memory. Ideal for 100+ replicas or serverless patterns.

4. **Horizontal Autoscaling** — Database connection limit is predictable: one connection per active query. Can safely scale query_api to 100 replicas without exhausting PostgreSQL max connections (default 100).
   - With QueuePool (pool_size=10): 10 replicas × 10 connections = 100 connections → **at capacity**
   - With NullPool: 100 replicas × 1 connection per query = **scales freely**

**Configuration (query_api example):**
```python
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # No pooling
    # DO NOT use: pool_size, max_overflow, pool_timeout, pool_recycle, pool_pre_ping
    # These are QueuePool parameters and raise errors with NullPool
)
```

## PostgreSQL Connection Limits

PostgreSQL default: `max_connections = 100`

**Example capacity planning:**
- **Ingestor with QueuePool**: 10 permanent + 20 spike = 30 connections used
- **Query API with NullPool**: 1 connection per active query (spikes absorbed by HTTP backlog, not connections)
- **Total available**: 100 - 30 (ingestor) = 70 connections for query_api queries

## Adding a New Service

**If your service is CRUD / Stateful:**
1. Use `QueuePool` (default, don't specify `poolclass`)
2. Configure in `database.py`:
   ```python
   engine = create_async_engine(
       DATABASE_URL,
       pool_size=10,
       max_overflow=20,
       pool_recycle=3600,
       pool_pre_ping=True,
   )
   ```
3. Size based on expected concurrency

**If your service is Read-Only / Stateless:**
1. Use `NullPool` explicitly:
   ```python
   from sqlalchemy.pool import NullPool
   engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
   ```
2. Omit all pooling parameters

**If your service doesn't use PostgreSQL:**
1. No engine configuration needed
2. Example: ai_gateway (Qdrant only), processor (Kafka only), dashboard (HTTP calls only)

## Monitoring Pool Usage

For ingestor (QueuePool), monitor:
```sql
-- Active connections by database
SELECT datname, count(*) as connections FROM pg_stat_activity GROUP BY datname;

-- Idle in transaction (potential problem)
SELECT * FROM pg_stat_activity WHERE state = 'idle in transaction' AND query_start < now() - interval '5 minutes';

-- Check pool exhaustion symptoms
SELECT datname, max_conn, num_conn, used FROM pg_stat_database;
```

## References

- SQLAlchemy 2.0 [Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- PostgreSQL [Connection Limits](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- Alembic [Configuration](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
