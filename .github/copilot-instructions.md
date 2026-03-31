# Project Guidelines — data-pipeline-async

Async FastAPI + SQLAlchemy 2.0 REST API for ingesting and querying pipeline records.
Single `records` resource, full CRUD. Learning project demonstrating production-style async patterns.

## Build and Test

```bash
uv sync                                         # install deps
uv run pytest tests/ -v                         # run all tests (no Postgres needed)
uv run pytest tests/ --cov=app                  # with coverage
uv run ruff check . && uv run ruff format .     # lint + format
uv run uvicorn app.main:app --reload            # dev server (needs Postgres)
docker compose up --build                       # full stack (app + Postgres 16)
```

## Architecture

```
FastAPI routes (app/main.py)
  └─ Pydantic v2 validation (app/schemas.py)
  └─ DbDep = Annotated[AsyncSession, Depends(get_db)]
       └─ CRUD layer (app/crud.py)  ← pure async functions
            └─ AsyncSessionLocal (app/database.py)
                 └─ asyncpg → PostgreSQL 16
```

| File | Responsibility |
|------|---------------|
| `app/main.py` | Routes, lifespan hook (table creation), correlation-ID logging |
| `app/crud.py` | All DB operations — async functions, `AsyncSession` as first arg |
| `app/models.py` | SQLAlchemy 2.0 ORM — `Mapped[T]` / `mapped_column()` style only |
| `app/schemas.py` | Pydantic v2 request/response schemas |
| `app/database.py` | Engine, `async_sessionmaker`, `Base`, `get_db` dependency |
| `app/config.py` | `pydantic-settings` `Settings`, reads `.env` |

## Conventions

**SQLAlchemy models** — use SQLAlchemy 2.0 style exclusively. No legacy `Column()`:
```python
# CORRECT
class Record(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[float] = mapped_column(nullable=False)
```

**CRUD functions** — `AsyncSession` is always the first positional argument, return ORM model or `None`:
```python
async def get_record(db: AsyncSession, record_id: int) -> Record | None:
    result = await db.execute(select(Record).where(Record.id == record_id))
    return result.scalar_one_or_none()
```

**Route injection** — use the `DbDep` type alias defined in `main.py`:
```python
DbDep = Annotated[AsyncSession, Depends(get_db)]

@app.get("/api/v1/records/{id}")
async def read_record(record_id: int, db: DbDep) -> RecordResponse:
    ...
```

**Pydantic schemas** — separate request and response schemas; add `model_config = {"from_attributes": True}` on response schemas:
```python
class RecordResponse(BaseModel):
    model_config = {"from_attributes": True}
```

**Logging** — structured JSON via `python-json-logger`. Pass event name as first arg, context in `extra={}`:
```python
logger.info("record_created", extra={"cid": str(uuid4()), "record_id": record.id})
```

**Tests** — `asyncio_mode = "auto"` in `pyproject.toml`; do NOT add `@pytest.mark.asyncio` (redundant). Tests use `aiosqlite` in-memory SQLite — no Postgres required.

## Critical Gotchas

- **`expire_on_commit=False` is required** on the async sessionmaker. Without it, accessing model attributes after `await session.commit()` raises `MissingGreenlet`.
- **`DATABASE_URL` must use `postgresql+asyncpg://`** — not `postgresql://`. The `+asyncpg` dialect prefix is mandatory.
- **No Alembic** — schema is created via `Base.metadata.create_all` in the lifespan hook. For schema changes, modify the model and restart (dev only).
- **aiosqlite vs asyncpg** — avoid PostgreSQL-specific SQL in CRUD (`RETURNING`, `ON CONFLICT DO UPDATE`) because tests use SQLite and the tests won't cover them.

## Configuration

Key environment variables (see `app/config.py`, defaults from `.env`):

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline` | Must include `+asyncpg` |
| `SQL_ECHO` | `False` | SQLAlchemy query logging |
| `DEBUG` | `False` | |

## Learning Docs

- [ACTION_PLAN.md](../learning_docs/ACTION_PLAN.md) — 6-week study roadmap
- [DATA_PIPELINE_6WEEK_PLAN.md](../learning_docs/DATA_PIPELINE_6WEEK_PLAN.md) — async patterns theory
- [WEEK1_STARTER_KIT.md](../learning_docs/WEEK1_STARTER_KIT.md) — starter code reference
- [COMMUTE_STUDY_GUIDE_WEEK1-2.md](../learning_docs/COMMUTE_STUDY_GUIDE_WEEK1-2.md) — interview Q&A
