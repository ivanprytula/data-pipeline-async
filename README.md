# Data Pipeline — Async

Async FastAPI + SQLAlchemy 2.0 REST API for ingesting and querying pipeline records.

> **Historical reference**: [docs/sync-vs-async.md](docs/sync-vs-async.md)

---

## Quick Start

```bash
# 1. One-time setup:
cp .env.example .env
# Edit .env with your local values (PostgreSQL running in Docker, etc.)

# 2. From now on, everything "just works"
docker compose up -d db      # Start container

# 3. Install uv (if missing)
pip install uv   # or: curl -Ls https://astral.sh/uv/install.sh | sh

# 4. Sync dependencies
uv sync

# 5. Run tests (aiosqlite in-memory — no Docker needed)
uv run pytest tests/ -v

# 6. Start the app (auto-reloads on code changes)
uv run alembic upgrade head   # Alembic reads from settings
uv run uvicorn app.main:app   # App reads settings

# 7. Open API docs
open http://localhost:8000/docs
```

---

## Database Migrations (Alembic)

Schema is managed by Alembic — **never** run `Base.metadata.create_all` alongside migrations.

```bash
# Apply all pending migrations (inside Docker Compose — uses db:5432 from .env)
docker compose run --rm app uv run alembic upgrade head

# Run Alembic locally (outside Docker — use localhost instead of db)
# No prepending needed
uv run alembic upgrade head

# This reads DATABASE_URL from:
# 1. Environment variable (if set)
# 2. .env file (if exists)
# 3. Settings default (if neither exists)
```

Migration files live in `alembic/versions/` and are named
`YYYYMMDD_HHmmss_<revhash>_<slug>.py` — the datetime prefix keeps them sorted
chronologically; the rev hash guarantees uniqueness.

---

## API Endpoints

| Method   | Path                           | Description                          |
| -------- | ------------------------------ | ------------------------------------ |
| `GET`    | `/health`                      | Health check                         |
| `POST`   | `/api/v1/records`              | Create a record                      |
| `POST`   | `/api/v1/records/batch`        | Bulk create (up to 1 000)            |
| `GET`    | `/api/v1/records`              | List with pagination + source filter |
| `GET`    | `/api/v1/records/{id}`         | Get by ID                            |
| `PATCH`  | `/api/v1/records/{id}/process` | Mark as processed                    |
| `DELETE` | `/api/v1/records/{id}`         | Hard-delete a record                 |

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

```text
async/
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
- [x] **Milestone 4** — Confirm JSON logs appear on every request (`docker compose logs app`)
- [x] **Milestone 5** — Run `test_performance.py -s`, note the numbers; revisit after
  adding caching in Week 3

---

## TODO / Next Steps

### Week 2 additions (do these yourself — they're the exercises)

- [x] **Cursor-based pagination** — opaque base64-encoded cursors; `GET /api/v2/records/cursor`
- [x] **Duplicate detection** — `source + timestamp` unique constraint; idempotent upsert with race-condition tests
- [x] **Rate limiting** — `slowapi` integration; custom rate limiters in `app/rate_limiting.py`, `app/rate_limiting_advanced.py`
- [x] **Retry with exponential backoff** — `app/fetch.py` with httpx AsyncClient, per-event-loop management, graceful failure handling

### Week 3 database optimisations

- [x] Run `EXPLAIN ANALYZE` on the list query; add a covering index on `(source, id)` — PostgreSQL-only integration tests
- [x] Introduce a `processed_at` column (nullable `DateTime`); remove `processed` bool — Alembic migration complete
- [x] Add Alembic migrations — `alembic/versions/` with timestamped revisions

### Week 4 async upgrades (async version)

- [x] Replace the single `await create_record(...)` with `asyncio.gather(...)` to fan out 100 concurrent writes — concurrent record enrichment
- [x] Add a `semaphore` to cap concurrency at 20 — semaphore-limited concurrent operations, pooling tests
- [x] Test a race condition: two concurrent writes with the same `source + timestamp` — concurrency tests with race-condition detection

### Production hardening

- [x] Add Prometheus metrics (`prometheus-fastapi-instrumentator`) — `GET /metrics` endpoint; instrumentation middleware
- [x] Add `X-Request-ID` middleware — `CorrelationIdMiddleware` injects `cid` UUID into all logs; correlation tracking
- [x] Health check endpoint should also verify DB connectivity — `GET /readyz` runs `SELECT 1` (readiness probe); `GET /health` is lightweight liveness
- [x] `docker compose` healthcheck for the app container (should hit `/readyz` for readiness-based restart)
- [x] **Load test harness** — k6 + Locust comparing cursor vs offset at scale; see [Load Testing](#load-testing)
- [x] **E2E test with external API retry loop** — `tests/integration/records/test_e2e_fetch.py` validates fetch.py + exponential backoff live behavior

## Gaps to Cover

*All major features completed. Optional enhancements:*

- Distributed tracing with OpenTelemetry (Jaeger/Zipkin)
- Sync version parity with async (Postgres-backed integration tests)
- Cache layer (Redis) benchmarks

---

## Load Testing

Compare **cursor** vs **offset** pagination performance at scale using k6 or Locust.

### Quick start

```bash
# 1. Start the app
docker compose up -d app

# 2. Seed 10 000 test records
./scripts/load_test.sh seed 10000

# 3a. Run k6 (install: brew install k6  |  snap install k6)
./scripts/load_test.sh k6
VUS=20 DURATION=60s ./scripts/load_test.sh k6

# 3b. Run Locust headless
./scripts/load_test.sh locust

# 3c. Run Locust with web UI → http://localhost:8089
./scripts/load_test.sh locust --web
```

### What it measures

```text
Strategy  │  Shallow page (skip=0–200)   │  Deep page (skip=5000–9000)
──────────┼──────────────────────────────┼──────────────────────────────
Offset    │  fast (small index scan)     │  SLOW — full table scan O(skip)
Cursor    │  fast (indexed seek)         │  fast — O(1) at any depth
```

### Files

| File | Tool | Purpose |
|------|------|---------|
| [scripts/seed_data.py](scripts/seed_data.py) | httpx | Seed N records via batch API |
| [scripts/load_test_pagination.js](scripts/load_test_pagination.js) | k6 | Two parallel scenarios, p50/p95/p99 summary table |
| [scripts/locustfile.py](scripts/locustfile.py) | Locust | `OffsetPaginationUser` + `CursorPaginationUser` |
| [scripts/load_test.sh](scripts/load_test.sh) | bash | Wrapper: seed / k6 / locust commands |

---

## E2E Tests — External API Retry Logic

Validate `app/fetch.py` resilience patterns: retry with exponential backoff, timeout handling, graceful failure.

```bash
# Run only non-E2E tests (default — 241 tests, ~25s)
uv run pytest tests/ -v

# Run E2E tests against live external API (jsonplaceholder) — 11+ tests
uv run pytest tests/integration/records/test_e2e_fetch.py -v -m e2e

# Run all tests including E2E
uv run pytest tests/ -v -m ""
```

### What's tested

| Test | Tool | Coverage |
|------|------|----------|
| Successful fetch (no retries) | httpx + jsonplaceholder | Basic happy path |
| Retry with exponential backoff | Mock + timing | 1s, 2s, 4s delays; attempt counting |
| Exhaustion after max retries | Mock | Exception propagation |
| Timeout handling | Mock | httpx.TimeoutException |
| HTTP client lifecycle | Direct | Create, reuse, close, idempotent cleanup |
| Concurrent fetches | asyncio.gather | Multi-VU stress test |

**File**: [tests/integration/records/test_e2e_fetch.py](tests/integration/records/test_e2e_fetch.py)
