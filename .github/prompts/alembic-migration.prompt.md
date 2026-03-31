---
description: "Set up Alembic (async/asyncpg) from scratch OR generate a migration for a model change. Use when: adding Alembic to this project for the first time, or creating a migration after modifying app/models.py."
argument-hint: "Describe the schema change, e.g. 'add status column to Record'"
agent: "agent"
---

You are helping with Alembic database migrations in an async FastAPI + SQLAlchemy 2.0 project using asyncpg and PostgreSQL 16.

Read [app/models.py](../app/models.py), [app/database.py](../app/database.py), [app/config.py](../app/config.py), and [pyproject.toml](../pyproject.toml) to understand the current state.

## Step 1 — Detect Alembic setup state

Check whether Alembic is already configured:
- Does `alembic/` directory exist?
- Does `alembic.ini` exist in the project root?
- Is `alembic` listed in `pyproject.toml` dependencies?

## Step 2 — Initial setup (if Alembic is NOT configured)

If no Alembic setup exists, perform the full bootstrap:

### 2a. Add dependency
Add `alembic>=1.13` to `[project.dependencies]` in `pyproject.toml`, then remind the user to run:
```bash
uv sync
```

### 2b. Initialise Alembic with async template
Create `alembic.ini` and `alembic/` directory structure. Use the async template:
```bash
uv run alembic init --template async alembic
```

### 2c. Patch `alembic/env.py` for asyncpg

Replace the generated `env.py` with an async-compatible version that:
- Imports `app.database.Base` to get the `target_metadata`
- Imports `app.config.settings` and reads `settings.DATABASE_URL` for the connection URL — never hardcode credentials
- Uses `run_async_migrations()` via `asyncio.run()` for the `run_migrations_online()` path
- Sets `compare_type=True` on the `MigrationContext`

Key pattern for async env.py:
```python
import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.database import Base

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 2d. Update `alembic.ini`
Set `script_location = alembic` and ensure `sqlalchemy.url` is commented out (we supply it from `settings` at runtime, not from `alembic.ini`, to avoid hardcoding credentials).

### 2e. Create initial migration
Generate the baseline migration capturing the current schema:
```bash
uv run alembic revision --autogenerate -m "initial_schema"
```
Explain what `--autogenerate` does: Alembic compares `target_metadata` (from `Base`) with the actual database state and generates `upgrade()` and `downgrade()` functions.

---

## Step 3 — Generate migration for a schema change

The user's requested change is: **$ARGUMENTS**

Apply the change to `app/models.py` following the project's SQLAlchemy 2.0 style (`Mapped[T]` / `mapped_column()` — never legacy `Column()`).

Then generate a descriptive migration:
```bash
uv run alembic revision --autogenerate -m "<short_description_of_change>"
```

Open the generated file under `alembic/versions/` and verify:
- `upgrade()` contains the expected `op.add_column` / `op.create_table` / etc.
- `downgrade()` correctly reverses the change
- No unintended table drops or data-loss operations are present

Highlight any dangerous operations (e.g. `op.drop_column`, `op.drop_table`) and ask the user to confirm before proceeding.

---

## Step 4 — Apply and verify

Show the user how to apply the migration:
```bash
# Apply to dev database (Docker Compose must be running)
uv run alembic upgrade head

# Check current revision
uv run alembic current

# Roll back one step
uv run alembic downgrade -1
```

Explain the difference between `upgrade head` (all pending migrations) and `upgrade +1` (next migration only).

---

## Notes for learning

- Alembic tracks applied migrations in a `alembic_version` table in the database.
- `--autogenerate` detects: new tables, dropped tables, added/removed columns, type changes (when `compare_type=True`), and index changes. It does **not** detect: renamed columns (it sees a drop + add), data migrations, or custom constraint names reliably.
- In production, never run `create_all` AND Alembic together — pick one. Once Alembic is in use, remove `Base.metadata.create_all` from the lifespan hook in `app/main.py`.
