# Alembic + Python 3.14 + SQLAlchemy 2.0 Async

## Problem

On Python 3.14, `alembic upgrade head` failed with:

```shell
psycopg.OperationalError: connection failed: server closed the connection unexpectedly
AttributeError: 'Connection' object has no attribute 'dialect'
```

### Root Cause

1. **Async Engine Greenlet Bug**: SQLAlchemy's `async_engine_from_config()` uses greenlets internally for sync operations. Python 3.14's event loop rewrite broke greenlet interop in certain contexts.

2. **Raw DBAPI Connection Issue**: Passing a raw `psycopg.Connection` to Alembic's `context.configure()` failed because Alembic expects a SQLAlchemy `Connection` object with a `.dialect` attribute.

3. **Network Config**: PostgreSQL inside container needs `listen_addresses = '*'` to accept connections on Docker bridge interface (`172.16.0.0/12`). Without it, only localhost inside the container accepts connections, rejecting host CLI traffic arriving as non-loopback IPs.

## Solution

**Use SQLAlchemy's sync Engine with psycopg dialect** in `alembic/env.py`:

```python
from sqlalchemy import create_engine, pool
from alembic import context

_sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://")

def run_migrations_online() -> None:
    """Run migrations using a SQLAlchemy sync Engine (psycopg dialect).

    This provides a proper SQLAlchemy Connection with .dialect attribute.
    Runs at Alembic CLI top-level (not inside app's event loop).
    """
    connectable = create_engine(_sync_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()
```

**Why this works**:

- `create_engine()` with `postgresql+psycopg://` creates a **sync engine** (no greenlets)
- Runs at **Alembic CLI top-level** (not inside app's event loop)
- Returns a proper **SQLAlchemy `Connection`** (has `.dialect` attribute)
- **psycopg3 is Python 3.14 compatible** (pure Python + optional C extension)

## Files Changed

| File | Change |
| ---- | ------ |
| `alembic/env.py` | Use `create_engine()` with psycopg dialect (sync, top-level) |
| `infra/database/postgresql.conf` | Added `listen_addresses = '*'` to accept Docker bridge traffic |
| `infra/database/pg_hba.conf` | Docker bridge `172.16.0.0/12` → `scram-sha-256` (dev/prod parity) |
| `docker-compose.yml` | Mounts custom PostgreSQL config files for observability, tuning, logging |

## How to Use

```bash
# Generate auto migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one revision
uv run alembic downgrade -1

# View migration history
uv run alembic current
uv run alembic history
```

## Architecture

```text
FastAPI app (async)
  └─ asyncpg engine (all app queries)
  └─ lifespan hook: skips schema creation (migrations separate)

Alembic CLI (sync)
  └─ SQLAlchemy sync engine (psycopg dialect)
  └─ Top-level Python process (no event loop conflicts)
  └─ Workflow: create_engine() → connect() → configure() → run_migrations()
```

## Dev/Prod Auth Parity

`pg_hba.conf` uses `scram-sha-256` for all TCP connections (same as production). This ensures you catch auth issues in dev, not in production.

| Connection Type | Auth Method | Details |
| --- | --- | --- |
| **Unix socket + container loopback** | `trust` | pg_isready health checks, `docker compose exec db psql` |
| **Docker bridge (172.16.0.0/12)** | `scram-sha-256` | Host CLI, CI runners, alembic from host — production-like auth |
| **Everything else** | `reject` | Deny external connections |

**Why scram-sha-256 for Docker bridge**: Docker bridge traffic appears as `172.17.x.x` (non-loopback). Using the same auth method as production catches configuration and credential bugs early.

**Why `listen_addresses = '*'` is safe for dev**: Docker's port mapping (`0.0.0.0:5432`) controls what the host exposes. PostgreSQL just listens on all interfaces inside the container. `pg_hba.conf` auth rules provide the actual security layer.

## Migration Workflow Now Supported

**From host CLI** (no container rebuilds needed):

```bash
# DB must be running (can be alone, app container not needed)
docker compose up -d db

# Generate migration from schema changes
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Check history
uv run alembic current
uv run alembic history
```

**Inside Docker** (if needed):

```bash
# Using migration container (one-off, doesn't restart app)
docker compose run --rm -T app python -m alembic upgrade head
```

## Outcome

✅ `alembic upgrade head` succeeds from host CLI with custom PostgreSQL configs active
✅ Host connections use `scram-sha-256` auth (dev/prod parity)
✅ Container loopback uses `trust` for health checks
✅ Tests pass (in-memory SQLite)
✅ App uses async engine (asyncpg) unaffected
✅ No app container rebuild/restart needed for migrations

## Notes

- **Top-level migration tool**: Alembic CLI runs as its own process, not inside the app's async event loop.
- **Alternative for schema auto-creation**: If you need startup schema creation, use `Base.metadata.create_all()` in the lifespan hook (safe in async context).
- **Future**: Python 3.14.1+ may fix upstream greenlet issues; this solution is stable but could simplify later.

---

**Related**: `docs/gotchas.md` "Alembic Migrations on Python 3.14" and "PostgreSQL Authentication" sections
