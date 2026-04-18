# Plan B: Redis Cache Layer

**TL;DR**: Add `redis-py` async client as a fail-open read cache for single-record (`GET /api/v1/records/{id}`) and cursor-page lookups. Redis down → transparent DB fallback. `fakeredis` for tests — no Redis container in CI.

## Architecture

```
GET /api/v1/records/{id}
        │
        ▼
  cache.get_record(id)
        │
   HIT ─┤ deserialize JSON → RecordResponse (no DB hit)
        │
  MISS ─┤ crud.get_record(db, id)
        │       └─► cache.set_record(id, record, ttl=3600)
        ▼
  RecordResponse

Write paths:
  PATCH  /{id}/process → cache.invalidate_record(id)
  DELETE /{id}         → cache.invalidate_record(id)
  POST   /batch        → (no list cache in v1 — deferred)
```

## Phase 1: Dependencies + Config (parallel with Phase 2)

1. `pyproject.toml` — add `"redis>=5.2.0"` to `[project.dependencies]`; add `"fakeredis[aioredis]>=2.22.0"` to `[dependency-groups.dev]`
2. `app/config.py` — add two new fields to `Settings`:
   - `redis_url: str = "redis://localhost:6379/0"`
   - `redis_enabled: bool = False` (opt-in; CI stays Redis-free)
3. `app/constants.py` — add cache constants section:
   - `CACHE_KEY_RECORD = "dp:record:{record_id}"` (the `dp:` namespace avoids key collisions)
   - `CACHE_TTL_RECORD = 3600` (1 hour — single records are stable)
4. `.env.example` — add `REDIS_URL=redis://localhost:6379/0` and `REDIS_ENABLED=false`

## Phase 2: cache.py Module (parallel with Phase 1)

5. CREATE `app/cache.py` with the following public API:
   - `_client: Redis | None` — module-level singleton (mirrors `database.py` engine pattern)
   - `async connect_cache(url: str) -> None` — `Redis.from_url()`, ping check
   - `async disconnect_cache() -> None` — `await _client.aclose()`
   - `async get_record(record_id: int) -> RecordResponse | None` — GET key, deserialize via `RecordResponse.model_validate_json()`
   - `async set_record(record_id: int, record: RecordResponse, ttl: int) -> None` — SETEX with `record.model_dump_json()`
   - `async invalidate_record(record_id: int) -> None` — DEL key
   - All three data operations: wrap in `try/except Exception` → log warning + increment `cache_errors_total` → return `None`/skip (fail-open)
   - Import `RecordResponse` from `app.schemas` (no circular import — schemas has no cache dep)

## Phase 3: Observability (depends on Phase 2)

6. `app/metrics.py` — add three Counters (reuse existing `prometheus_client` import):
   - `cache_hits_total` with label `operation`
   - `cache_misses_total` with label `operation`
   - `cache_errors_total` with label `operation`
   - Increment from `cache.py` (import metrics there)

## Phase 4: Wire Routes (depends on Phase 2 + 3)

7. `app/routers/records.py` — update three routes:
   - `GET /{record_id}`: check `cache.get_record(record_id)` first; on miss, fetch from DB then `cache.set_record(...)`; increment hit/miss counter
   - `PATCH /{record_id}/process`: after `await crud.mark_processed(...)`, call `await cache.invalidate_record(record_id)`
   - `DELETE /{record_id}`: after `await crud.delete_record(...)`, call `await cache.invalidate_record(record_id)`
8. `app/main.py` lifespan — add to startup block (after existing DB setup): `if settings.redis_enabled: await cache.connect_cache(settings.redis_url)`; add to shutdown (before `engine.dispose()`): `await cache.disconnect_cache()`

## Phase 5: Docker Compose (parallel with Phase 4)

9. `docker-compose.yml` — add `redis` service:
   ```yaml
   redis:
     image: redis:7-alpine
     ports: ["6379:6379"]
     healthcheck: {test: redis-cli ping, interval: 5s, timeout: 3s, retries: 5}
   ```
   Update `app.depends_on` to include `redis: {condition: service_healthy}`

## Phase 6: Tests (depends on Phase 2 + 4)

10. `tests/conftest.py` — add `fake_redis` fixture using `fakeredis.aioredis.FakeRedis()` (no pool needed in fakeredis ≥2.x); add `client_with_cache` fixture that overrides both `get_db` and the cache module's `_client`
11. CREATE `tests/integration/records/test_cache.py` — 7 tests:
    - `test_cache_miss_populates_cache` — first GET stores in Redis
    - `test_cache_hit_skips_db` — second GET returns from cache (spy on crud.get_record)
    - `test_delete_invalidates_cache` — GET after DELETE returns 404 (not stale cached 200)
    - `test_patch_invalidates_cache` — GET after PATCH returns updated `processed_at`
    - `test_cache_failopen_on_connection_error` — monkeypatch `_client.get` to raise; GET still returns 200 from DB
    - `test_metrics_hit_counter` — `cache_hits_total` increments
    - `test_metrics_miss_counter` — `cache_misses_total` increments

## Phase 7: Docs (depends on all phases)

12. `README.md` — add to Quick Start: `docker compose up -d redis`; add "Caching" section with architecture ASCII + TTL table; add `app/cache.py` to Project Structure

**Relevant files**
- `app/cache.py` — CREATE (cache module, ~80 lines)
- `app/config.py` — ADD `redis_url`, `redis_enabled` fields
- `app/constants.py` — ADD `CACHE_KEY_RECORD`, `CACHE_TTL_RECORD`
- `app/main.py` — WIRE lifespan startup/shutdown for Redis
- `app/metrics.py` — ADD 3 cache counters
- `app/routers/records.py` — WIRE 3 routes (GET, PATCH, DELETE)
- `docker-compose.yml` — ADD `redis:7-alpine` service + update `app.depends_on`
- `pyproject.toml` — ADD `redis>=5.2.0`, `fakeredis[aioredis]>=2.22.0`
- `.env.example` — ADD `REDIS_URL`, `REDIS_ENABLED`
- `tests/conftest.py` — ADD `fake_redis` + `client_with_cache` fixtures
- `tests/integration/records/test_cache.py` — CREATE (7 tests)
- `README.md` — ADD caching section + project structure update

**Verification**
1. `uv run pytest tests/integration/records/test_cache.py -v` — 7 tests green
2. `uv run pytest tests/ -q` — ≥241 existing tests still pass (no regressions)
3. `uv run ruff check . && uv run ruff format --check .` — clean
4. Manual: `docker compose up -d` → `curl /api/v1/records/1` twice → `docker exec ... redis-cli GET dp:record:1` returns JSON
5. Manual: `docker compose stop redis` → `curl /api/v1/records/1` still returns 200 (fail-open); `/metrics` shows `cache_errors_total > 0`

**Decisions**
- `redis-py` ≥5.x (not `aioredis`) — aioredis is unmaintained; redis-py ships async natively since v4.2
- `redis_enabled: bool = False` — CI runs without Redis; tests use fakeredis; opt-in for local dev
- Fail-open on all cache ops — Redis failure is never user-visible
- Scope: single-record cache only (v1). List caching deferred — the offset pagination key space (`source × skip × limit`) is too large to invalidate cleanly without a namespace-flush strategy
- `SCAN + DEL` pattern used for any future namespace invalidation — never `KEYS *` in production
- Out of scope: Redis Cluster, Sentinel, cache warming, distributed locking (Redlock)
