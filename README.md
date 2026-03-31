# Week 1 — Data Pipeline Starter Kit

Two self-contained, production-shaped implementations of the same data-pipeline API.
Pick one (or study both side-by-side to understand the difference).

```
week1_data_pipeline/
├── sync/   ← pip + requirements.txt + SQLAlchemy sync + psycopg2
└── async/  ← uv + pyproject.toml  + SQLAlchemy async + asyncpg
```

Both use **Python 3.14**, **FastAPI**, **Pydantic v2**, and **python-json-logger**.

---

## Sync vs Async — What Changes and Why

| Concern | sync/ | async/ |
|---------|-------|--------|
| Dep management | `pip` + `requirements.txt` | `uv` + `pyproject.toml` |
| DB driver | `psycopg2-binary` (C extension, blocking) | `asyncpg` (pure async, fastest PG driver) |
| SQLAlchemy session | `Session` (thread-local) | `AsyncSession` (coroutine-safe) |
| Route handlers | `def` | `async def` |
| CRUD calls | direct `session.commit()` | `await session.commit()` |
| Test fixtures | `pytest` fixtures, `TestClient` | `pytest-asyncio`, `AsyncClient` (httpx) |
| In-proc test DB | `sqlite:///:memory:` | `sqlite+aiosqlite:///:memory:` |
| Dockerfile base image | `python:3.14-slim` | `python:3.14-slim` + uv layer |

**When to choose async**: Any production service that handles concurrent I/O (database
queries, external HTTP calls). FastAPI is async-first; `async def` routes process
multiple requests concurrently on a single thread without blocking the event loop.

**When sync is fine**: Early prototypes, scripts, CLIs, or when your team is unfamiliar
with asyncio and the performance headroom permits it.

---

## Quick Start — sync

```bash
cd sync

# 1. Create venv and install deps
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run tests (SQLite in-memory — no Docker needed)
pytest tests/ -v

# 3. Start the full stack (FastAPI + PostgreSQL)
cp .env.example .env
docker compose up --build

# 4. Open API docs
open http://localhost:8000/docs
```

---

## Quick Start — async

```bash
cd async

# 1. Install uv (if missing)
pip install uv   # or: curl -Ls https://astral.sh/uv/install.sh | sh

# 2. Sync dependencies
uv sync

# 3. Run tests (aiosqlite in-memory — no Docker needed)
uv run pytest tests/ -v

# 4. Start the full stack
cp .env.example .env
docker compose up --build

# 5. Open API docs
open http://localhost:8000/docs
```

---

## Database Migrations (Alembic)

Schema is managed by Alembic — **never** run `Base.metadata.create_all` alongside migrations.

```bash
# Apply all pending migrations (inside Docker Compose — uses db:5432 from .env)
docker compose run --rm app uv run alembic upgrade head

# Run Alembic locally (outside Docker — use localhost instead of db)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline \
  uv run alembic upgrade head

# Create a new revision after changing a model
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline \
  uv run alembic revision --autogenerate -m "describe_your_change"

# Roll back one revision
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline \
  uv run alembic downgrade -1
```

> **Hostname note**: `.env` uses `db:5432` (Docker Compose service name). When running
> Alembic directly on the host, override with `localhost:5432` via the `DATABASE_URL`
> environment variable as shown above.

Migration files live in `alembic/versions/` and are named
`YYYYMMDD_HHmmss_<revhash>_<slug>.py` — the datetime prefix keeps them sorted
chronologically; the rev hash guarantees uniqueness.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/records` | Create a record |
| `POST` | `/api/v1/records/batch` | Bulk create (up to 1 000) |
| `GET` | `/api/v1/records` | List with pagination + source filter |
| `GET` | `/api/v1/records/{id}` | Get by ID |
| `PATCH` | `/api/v1/records/{id}/process` | Mark as processed |
| `DELETE` | `/api/v1/records/{id}` | Hard-delete a record |

### Create a record (curl)

```bash
curl -s -X POST http://localhost:8000/api/v1/records \
  -H "Content-Type: application/json" \
  -d '{
    "source": "api.example.com",
    "timestamp": "2024-01-15T10:00:00",
    "data": {"price": 123.45},
    "tags": ["Stock", "NASDAQ"]
  }' | jq
```

### Batch create (100 records)

```bash
python3 -c "
import json, datetime
records = [{'source': f'src-{i}', 'timestamp': '2024-01-15T10:00:00',
            'data': {'value': i}, 'tags': []} for i in range(100)]
print(json.dumps({'records': records}))
" | curl -s -X POST http://localhost:8000/api/v1/records/batch \
    -H 'Content-Type: application/json' -d @- | jq
```

---

## Project Structure

```
sync/ (and async/ — identical layout)
├── app/
│   ├── __init__.py
│   ├── config.py      — Pydantic BaseSettings (reads from .env)
│   ├── database.py    — Engine, session factory, get_db() dependency
│   ├── models.py      — SQLAlchemy ORM (Record)
│   ├── schemas.py     — Pydantic request / response models
│   ├── crud.py        — DB operations (create, batch, list, get, mark_processed)
│   └── main.py        — FastAPI app, lifespan, route handlers
├── tests/
│   ├── conftest.py    — Fixtures (in-memory DB, test client)
│   ├── test_api.py    — Integration tests (all happy + error paths)
│   └── test_performance.py — Baseline timing tests
├── scripts/
│   └── run_tests.sh
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt / pyproject.toml
```

---

## Week 1 Milestones

- [x] **Milestone 1** — App runs, `/docs` loads, can create a record via Swagger UI
- [x] **Milestone 2** — All tests pass (`pytest tests/ -v`)
- [x] **Milestone 3** — Understand the `PATCH /process` endpoint you got for free; add a
  `DELETE /api/v1/records/{id}` that hard-deletes; `TimestampMixin` adds `deleted_at` for future soft-delete
- [ ] **Milestone 4** — Confirm JSON logs appear on every request (`docker compose logs app`)
- [ ] **Milestone 5** — Run `test_performance.py -s`, note the numbers; revisit after
  adding caching in Week 3

---

## TODO / Next Steps

### Week 2 additions (do these yourself — they're the exercises)

- [ ] **Cursor-based pagination** — replace `skip`/`limit` with an opaque cursor for
  stable pages under concurrent inserts
- [ ] **Duplicate detection** — add a `source + timestamp` unique constraint and handle
  `IntegrityError` gracefully (idempotent upsert)
- [ ] **Rate limiting** — add `slowapi` to the sync version; write a test that sends 101
  requests and asserts the 101st returns 429
- [ ] **Retry with exponential backoff** — add `app/fetch.py` that wraps an external
  HTTP call with jitter-backoff using `tenacity`

### Week 3 database optimisations

- [ ] Run `EXPLAIN ANALYZE` on the list query; add a covering index on `(source, id)`
- [ ] Introduce a `processed_at` column (nullable `DateTime`); remove `processed` bool —
  presence of timestamp is the state
- [ ] Add Alembic migrations (`alembic init migrations`)

### Week 4 async upgrades (async version)

- [ ] Replace the single `await create_record(...)` with `asyncio.gather(...)` to fan out
  100 concurrent writes; measure throughput difference
- [ ] Add a `semaphore` to cap concurrency at 20 and prevent DB pool exhaustion
- [ ] Test a race condition: two concurrent writes with the same `source + timestamp`

### Production hardening

- [ ] Add Prometheus metrics (`prometheus-fastapi-instrumentator`)
- [ ] Add `X-Request-ID` middleware that injects a UUID into every log entry
- [ ] Health check endpoint should also verify DB connectivity (run a `SELECT 1`)
- [ ] `docker compose` healthcheck for the app container (hits `/health`)

---

## Key Concepts to Understand Before Week 2

1. **Why `expire_on_commit=False`** (async version) — after `await session.commit()`,
   SQLAlchemy would expire every attribute. In an async context you cannot lazily reload
   them; `expire_on_commit=False` keeps the values in-memory.

2. **Why `StaticPool` in sync tests** — SQLite `:memory:` creates a new database per
   connection. `StaticPool` forces all connections to share one, so the test session sees
   the same data as the app.

3. **Why `aiosqlite` in async tests** — `asyncpg` requires a real PostgreSQL server.
   `aiosqlite` is a drop-in async wrapper for SQLite that lets tests run without Docker.

4. **`asynccontextmanager` lifespan** — replaces the deprecated `@app.on_event("startup")`
   pattern. Everything before `yield` is startup; after `yield` is shutdown.
