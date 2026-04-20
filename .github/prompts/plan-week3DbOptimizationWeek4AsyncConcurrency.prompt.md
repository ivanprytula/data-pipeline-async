# Plan: Week 3–4 Feature Increment — DB Optimization + Async & Concurrency

## TL;DR
Two sequential phases. Phase 1 (DB) adds indexes, an N+1 benchmark endpoint, processed_at migration, and EXPLAIN ANALYZE habits. Phase 2 (Async) replaces example fetch.py with real httpx HTTP fan-out, a semaphore-limited batch enrichment endpoint, an idempotent upsert race-condition demo, and Prometheus metrics as the Pillar 4 bridge.

---

## Phase 1: Database Optimization (Week 3)

### Step 1 — Add missing indexes to models.py
- Add composite index `ix_records_timestamp` on `Record.timestamp`
- Add `ix_records_processed` on `Record.processed`
- Teaches: index design for range queries and status-based worker queries

### Step 2 — Add get_records_by_date_range CRUD
- `get_records_by_date_range(db, start, end, source?) → list[Record]`
- Uses timestamp index; real-world pattern: "all records from last 24h"
- Canonical query for EXPLAIN ANALYZE practice

### Step 3 — N+1 demo route in records_v2.py
- Add `get_records_with_tag_counts_naive` (N+1: loop + per-record query) and `get_records_with_tag_counts` (single query with subquery) to crud.py
- Add `GET /api/v2/records/n-plus-one-demo` that runs both, returns timing comparison
- Real-world: "show records with tag count" is the classic N+1 trap

### Step 4 — Add processed_at column + Alembic migration
- `processed_at: Mapped[datetime | None]` added to Record
- Keep `processed: bool` for backwards compat
- Update `mark_processed` CRUD to set `processed_at = utcnow()`
- Backfill existing `processed=True` rows: `processed_at = created_at` in migration
- New migration file in alembic/versions/

### Step 5 — EXPLAIN ANALYZE tests (PostgreSQL-only, skip on SQLite)
- `tests/integration/records/test_query_analysis.py`
- Uses `pytest.mark.skipif` when DATABASE_URL is sqlite
- Runs EXPLAIN ANALYZE on date-range query; asserts no Seq Scan

### Step 6 — Connection pool concurrency test
- Extend `tests/integration/records/test_performance.py`
- `test_concurrent_requests_under_pool_limit`: fire 20 concurrent POSTs via asyncio.gather; verify all succeed

---

## Phase 2: Async & Concurrency (Week 4)

*Steps 1–6 must be complete before starting here.*

### Step 7 — Rewrite fetch.py with real httpx.AsyncClient
- Add `httpx` to main dependencies (already in dev)
- Target: `https://jsonplaceholder.typicode.com/posts/{id}` (free, no key)
- Keep `simulate_failures` flag for controlled failure testing
- Teaches: real async HTTP, timeout handling

### Step 8 — Concurrent record enrichment endpoint
- `enrich_records_concurrent(db, record_ids, semaphore)` in crud.py
  - asyncio.gather + asyncio.Semaphore(10) to cap concurrency
- `POST /api/v2/records/enrich` in records_v2.py
- Real-world: "enrich 50 pipeline records with external metadata"

### Step 9 — Idempotent upsert + race condition demo
- `POST /api/v2/records/upsert` — source+timestamp unique constraint
- On conflict: return existing record (409 or 200 depending on mode)
- Teaches: IntegrityError handling, idempotent APIs, race conditions
- README TODO: "Duplicate detection — source+timestamp unique constraint"

### Step 10 — Prometheus metrics (Pillar 4 bridge)
- Add `prometheus-fastapi-instrumentator` to dependencies
- Instrument in app/main.py lifespan (3 lines)
- Add custom metrics: `records_created_total` counter, `batch_size_histogram`
- Exposes `/metrics` endpoint
- Test: GET /metrics returns 200 with prometheus format text

### Step 11 — Concurrency tests
- `tests/integration/records/test_concurrency.py` (new)
  - TestAsyncGather: N concurrent enrich requests all succeed
  - TestRaceConditionHandling: two concurrent upserts same key → one 201, one 409
- Update fetch unit tests to use httpx mock instead of mocking asyncio.sleep

---

## Relevant Files
- `app/models.py` — indexes, `processed_at`
- `app/crud.py` — `get_records_by_date_range`, N+1 demo pair, `enrich_records_concurrent`
- `app/fetch.py` — rewrite with `httpx`
- `app/schemas.py` — `EnrichRequest`, `UpsertRequest`
- `app/routers/records_v2.py` — `/enrich`, `/upsert`, `/n-plus-one-demo` routes
- `app/main.py` — Prometheus instrumentation in lifespan
- `alembic/versions/` — `processed_at` migration
- `pyproject.toml` — add `httpx` to main deps, `prometheus-fastapi-instrumentator`
- `tests/integration/records/test_query_analysis.py` — new (PostgreSQL only)
- `tests/integration/records/test_concurrency.py` — new
- `tests/integration/records/test_performance.py` — extend with pool test

---

## Decisions
- `processed` bool kept — additive change, migration stays small
- jsonplaceholder.typicode.com as external API — free, no key, stable
- Semaphore(10) — less than pool_size(5) + max_overflow(10), intentional headroom
- Prometheus = Pillar 4 entry point only — no Grafana yet (Week 5)

## Open Questions
- Semaphore sizing: 10 is conservative vs pool max of 15 — adjust after measuring?
- `processed_at` backfill: set `processed_at = created_at` for existing `processed=True` rows?
- Upsert conflict response: 200 (idempotent success) or 409 (explicit conflict)? Depends on client contract.
- httpx in main deps vs dev only: once fetch.py does real HTTP, promote to main.

## Scope Exclusions
- NO cursor-based pagination (standalone feature, no Week 3/4 dependency)
- NO Redis-backed rate limiting (Pillar 3)
- NO Grafana dashboard (Week 5)
- NO JWT auth changes (Pillar 5)
