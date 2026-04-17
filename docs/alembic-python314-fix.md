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

3. **Network Config**: Initial failures also due to incomplete Docker network setup (Postgres wasn't listening on the docker bridge).

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
| `infra/database/postgresql.conf` | Removed `listen_addresses = '*'` (default localhost dev config) |
| `infra/database/pg_hba.conf` | Removed Docker subnet rule; kept localhost `trust` for dev |
| `docs/gotchas.md` | Documented Python 3.14 issue + auth patterns |

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

## Dev Auth Strategy

`pg_hba.conf` supports two scenarios:

- **Localhost (dev)**: `trust` auth, no password
  - `docker compose exec db psql -U postgres`
  - `alembic upgrade head`
  - Host psql/psycopg via 127.0.0.1

- **Network (prod/external)**: `scram-sha-256` auth, password required
  - DBeaver, pgAdmin (VPN-only recommended)
  - Production app replicas outside localhost

## Outcome

✅ `alembic upgrade head` succeeds on Python 3.14
✅ Migrations apply cleanly to PostgreSQL
✅ Tests pass (in-memory SQLite)
✅ App uses async engine (asyncpg) unaffected
✅ No greenlet conflicts or connection issues

## Notes

- **Top-level migration tool**: Alembic CLI runs as its own process, not inside the app's async event loop.
- **Alternative for schema auto-creation**: If you need startup schema creation, use `Base.metadata.create_all()` in the lifespan hook (safe in async context).
- **Future**: Python 3.14.1+ may fix upstream greenlet issues; this solution is stable but could simplify later.

---

**Related**: `docs/gotchas.md` "Alembic Migrations on Python 3.14" and "PostgreSQL Authentication" sections
