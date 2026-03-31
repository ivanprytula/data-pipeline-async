# Pattern Implementation Guides

Detailed implementation steps for each async pattern. Loaded by SKILL.md on demand.

---

## `batch` — Bulk Insert Optimisation

**Concept**: `session.add_all()` batches all `INSERT` statements into a single round-trip. Single-record inserts send one `INSERT` per record — O(n) round-trips vs O(1).

**Implementation** (already present in `app/crud.py` as `create_records_batch`):

- Verify the existing `add_all` + single `commit` + per-record `refresh` pattern
- Add a performance test to measure the speedup empirically

**Test to write** (`tests/test_performance.py`):

```python
import time
import pytest
from httpx import AsyncClient

_RECORD = {
    "source": "perf.test",
    "timestamp": "2024-01-15T10:00:00",
    "data": {"value": 1.0},
    "tags": [],
}

async def test_batch_vs_single_throughput(client: AsyncClient) -> None:
    n = 100

    # Single inserts
    start = time.perf_counter()
    for _ in range(n):
        await client.post("/api/v1/records", json=_RECORD)
    single_time = time.perf_counter() - start

    # Batch insert
    start = time.perf_counter()
    await client.post("/api/v1/records/batch", json={"records": [_RECORD] * n})
    batch_time = time.perf_counter() - start

    speedup = single_time / batch_time
    print(f"\nSingle: {single_time:.2f}s | Batch: {batch_time:.2f}s | Speedup: {speedup:.1f}x")
    assert speedup > 5, f"Expected >5x speedup, got {speedup:.1f}x"
```

**Key insight**: The speedup comes from reducing round-trips to the database, not from SQL optimisation. Each `await session.commit()` is a network call.

---

## `pagination` — Offset/Limit with Count

**Concept**: Never load unbounded result sets into memory. Count + data in two queries within the same session keeps the response predictable in size.

**Already implemented** in `get_records`. When extending:

- Always pair a `count_q` with the `data_q` — never guess total from len(results)
- Apply the same `WHERE` clause to both queries or counts will be wrong
- Return `(list[Model], int)` from CRUD, assemble `PaginationMeta` in the route

**Extending for a new model** (e.g. Pipeline):

```python
async def list_pipelines(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
) -> tuple[list[Pipeline], int]:
    count_q = select(func.count()).select_from(Pipeline)
    data_q = select(Pipeline).order_by(Pipeline.id).offset(skip).limit(limit)
    if status:
        count_q = count_q.where(Pipeline.status == status)
        data_q = data_q.where(Pipeline.status == status)
    total = (await session.execute(count_q)).scalar_one()
    rows = list((await session.execute(data_q)).scalars().all())
    return rows, total
```

**Test**:

```python
async def test_pagination_has_more(client: AsyncClient) -> None:
    for i in range(5):
        await client.post("/api/v1/records", json={**_RECORD, "source": f"src-{i}"})
    r = await client.get("/api/v1/records?skip=0&limit=3")
    body = r.json()
    assert len(body["records"]) == 3
    assert body["pagination"]["has_more"] is True
    assert body["pagination"]["total"] == 5
```

---

## `retry` — Async Exponential Backoff

**Concept**: Transient failures (network blips, 503s) should be retried with increasing delay. The `asyncio.sleep` must be used — `time.sleep` blocks the event loop.

**Add `app/fetch.py`**:

```python
"""Async HTTP fetch utilities with retry."""

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def fetch_with_retry(
    url: str,
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """GET url with exponential backoff. Raises on final failure."""
    _client = client or httpx.AsyncClient()
    try:
        for attempt in range(max_retries):
            try:
                response = await _client.get(url, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                if attempt == max_retries - 1:
                    logger.error(
                        "fetch_failed",
                        extra={"url": url, "attempts": max_retries, "error": str(exc)},
                    )
                    raise
                delay = base_delay * (2**attempt)
                logger.warning(
                    "fetch_retry",
                    extra={"url": url, "attempt": attempt + 1, "delay_s": delay},
                )
                await asyncio.sleep(delay)
    finally:
        if client is None:
            await _client.aclose()
    return {}  # unreachable, satisfies type checker
```

**Test** (uses `respx` to mock HTTP — add `respx` to dev deps):

```python
import respx
import httpx
import pytest
from app.fetch import fetch_with_retry

async def test_retry_succeeds_after_transient_failure() -> None:
    call_count = 0

    async def flaky_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    with respx.mock:
        respx.get("http://api.example.com/data").mock(side_effect=flaky_handler)
        async with httpx.AsyncClient() as client:
            result = await fetch_with_retry(
                "http://api.example.com/data", base_delay=0.01, client=client
            )
    assert result == {"ok": True}
    assert call_count == 3
```

**Caution**: Do NOT retry on `4xx` (client errors — retrying won't help). Retry only on `5xx` / network failures.

---

## `rate-limit` — Per-Route Throttling with `slowapi`

**Concept**: Protect endpoints from abuse. `slowapi` wraps `limits` and integrates with FastAPI's middleware stack.

**Add dependency** in `pyproject.toml`:

```toml
"slowapi>=0.1.9",
```

Then `uv sync`.

**Integrate in `app/main.py`**:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to a specific route
@app.get("/health", tags=["ops"])
@limiter.limit("60/minute")
async def health(request: Request) -> dict[str, str]:
    return {"status": "healthy", "version": settings.app_version}
```

**Note**: `slowapi` requires the `request: Request` parameter — it reads the client IP.

**Test** (use `override_default_limits`):

```python
from slowapi.errors import RateLimitExceeded

async def test_rate_limit_exceeded(client: AsyncClient) -> None:
    # This test is best run against real app (not overridden),
    # or use slowapi's testing utilities to lower the limit.
    # See slowapi docs: https://slowapi.readthedocs.io/en/latest/testing/
    pass  # Document: integration test only, not unit-testable via aiosqlite client
```

**Key insight**: Rate limiting state is in-process (memory). For multi-process deployments, use a Redis backend: `Limiter(key_func=..., storage_uri="redis://localhost")`.

---

## `background-tasks` — Fire-and-Forget with FastAPI

**Concept**: `BackgroundTasks` runs a function *after the response is sent*. Use for non-blocking side effects (notifications, audit logs, async cleanup). It is NOT parallel — it runs in the same event loop after the response.

**Example** — send an audit event after record creation:

```python
from fastapi import BackgroundTasks

async def _audit_log(record_id: int, action: str) -> None:
    """Runs after response — never blocks the client."""
    logger.info("audit", extra={"record_id": record_id, "action": action})
    # Could also: write to audit table, send to queue, notify webhook

@app.post("/api/v1/records", response_model=RecordResponse, status_code=201, tags=["records"])
async def create_record_endpoint(
    request: RecordRequest, db: DbDep, background_tasks: BackgroundTasks
) -> RecordResponse:
    cid = str(uuid.uuid4())
    record = await create_record(db, request)
    background_tasks.add_task(_audit_log, record.id, "created")  # non-blocking
    return record  # type: ignore[return-value]
```

**When NOT to use**: If the background work can fail and the client needs to know about it, use a task queue (Celery, ARQ) instead.

---

## `connection-pool` — Tuning asyncpg Pool

**Concept**: The connection pool caps concurrent DB connections. Too small → requests queue up under load. Too large → PostgreSQL runs out of connections.

**Current config** in `app/database.py`:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=10,       # steady-state connections kept open
    max_overflow=20,    # burst connections (pool_size + max_overflow = 30 max)
    pool_pre_ping=True, # test connection health before handing out
)
```

**How to measure exhaustion**: Run a load test with `k6` or `httpx` and watch for `asyncpg.exceptions.TooManyConnectionsError` or slow P99 latency.

**Tuning formula**: `pool_size ≈ num_workers × avg_concurrent_db_calls_per_request`. For a single Uvicorn worker handling async requests: start at 10, monitor P95 latency under load, increase if you see queuing.

**Test to expose exhaustion**:

```python
import asyncio
from httpx import AsyncClient

async def test_concurrent_requests_dont_exhaust_pool(client: AsyncClient) -> None:
    """All 20 concurrent requests should succeed without pool errors."""
    tasks = [
        client.get("/api/v1/records")
        for _ in range(20)
    ]
    results = await asyncio.gather(*tasks)
    assert all(r.status_code == 200 for r in results)
```

---

## `validator` — Pydantic v2 Deep Dive

**Concept**: Validators run at model construction time, before your route handler sees the data. They are the boundary between untrusted input and your domain.

**Single-field validator** (already in `schemas.py`):

```python
@field_validator("tags")
@classmethod
def lowercase_tags(cls, v: list[str]) -> list[str]:
    return [t.lower() for t in v]
```

**Cross-field validator** (`@model_validator`):

```python
from pydantic import model_validator

class RecordRequest(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def end_after_start(self) -> "RecordRequest":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self
```

**`mode="before"` vs `mode="after"`**:

- `"before"` — receives raw dict, runs before type coercion (use to normalise input)
- `"after"` — receives the fully validated model instance (use for cross-field rules)

**Test**:

```python
async def test_validator_end_before_start_rejected(client: AsyncClient) -> None:
    r = await client.post("/api/v1/records", json={
        **_RECORD,
        "start": "2024-01-15T12:00:00",
        "end": "2024-01-15T10:00:00",  # before start
    })
    assert r.status_code == 422
    assert "end must be after start" in r.json()["detail"][0]["msg"]
```
