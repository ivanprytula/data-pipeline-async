# Plan: Close Foundation Gaps + Production-Ready CI/CD

## Status Assessment (April 17, 2026)

**90% complete.** Pillar 1/2/3 Foundation is nearly done. The project exceeds Foundation
expectations in many areas (3 auth patterns, 2 rate limiting strategies, batch CRUD, retry logic,
E2E tests).

### Gaps Found (3 items)

| # | Pillar / Tier | Gap | Impact |
|---|---------------|-----|--------|
| 1 | P2 Foundation | No indexes on `Record` model — only PK exists | Full table scans on every `get_records()` query |
| 2 | P1 Middle | `/health` returns static dict, never pings DB (`SELECT 1`) | Reports healthy even when DB is down |
| 3 | P3 Middle | No `.github/workflows/` — no CI/CD pipeline | No automated quality gate on commits |

---

## Phase 1 — Database Indexes (Surgical, Write-Heavy Aware)

### Context

Business logic is a data pipeline / scraper → **many writes per second**.
Every index = extra B-tree update on every INSERT/UPDATE/DELETE.
3 naive `index=True` columns ≈ 30–90% extra write overhead per row.

### Actual Query Patterns (from `crud.py`)

```python
# get_records():  WHERE deleted_at IS NULL [AND source = ?]  ORDER BY id
# get_record():   WHERE id = ? AND deleted_at IS NULL
# mark_processed(): session.get(Record, pk)        — PK only
# soft_delete():    session.get(Record, pk)        — PK only
```

**Findings:**
- `ORDER BY id` already uses PK index — no work needed
- `timestamp` is **never** filtered in any query — adding an index is pure write overhead
- Both read queries share the same filter shape: `deleted_at IS NULL [AND source = ?]`

### Decision: 1 Partial Composite Index (not 3 full-column indexes)

```python
# app/models.py — add __table_args__ to Record class
from sqlalchemy import Index, text

class Record(Base, TimestampMixin):
    __tablename__ = "records"
    __table_args__ = (
        Index(
            "ix_records_active_source",
            "source",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
    # ... existing columns unchanged
```

**Why partial beats full-column index here:**
- Index only covers non-deleted rows → far smaller than full table
- Write overhead is asymmetric: INSERT adds 1 entry (new row is always `deleted_at IS NULL`);
  soft-delete UPDATE removes it. Both are single B-tree ops.
- Serves both query shapes: `WHERE deleted_at IS NULL` and
  `WHERE deleted_at IS NULL AND source = ?`
- PostgreSQL uses it for the COUNT query too (covering index for `get_records()` pagination)

**Why NOT standalone `timestamp` index:**
No query in `crud.py` filters by timestamp. `ORDER BY id` uses PK. Zero benefit, pure cost.

**Why NOT standalone `deleted_at` index:**
99% of rows have `deleted_at IS NULL` → poor selectivity. PostgreSQL may ignore it anyway.
The partial index handles this filter case better.

| Approach | Write overhead | Query coverage | Index size |
|---|---|---|---|
| 3× naive `index=True` | HIGH (3 B-tree ops/row) | Full | Full table × 3 |
| 1× partial `(source) WHERE deleted_at IS NULL` | LOW (1 B-tree op/row) | Both queries ✅ | Active rows only |

### Steps

1. Add `__table_args__` to `Record` in `app/models.py`
2. Generate migration:
   ```bash
   uv run alembic revision --autogenerate -m "add_partial_index_active_source"
   ```
3. Inspect generated file in `alembic/versions/` — should contain:
   ```sql
   CREATE INDEX ix_records_active_source ON records (source)
   WHERE (deleted_at IS NULL)
   ```
4. Verify: `uv run pytest tests/ -v` — all tests pass

**Note:** `TimestampMixin.deleted_at` needs no change — the partial index definition lives on
`Record.__table_args__` and references the column by name.

---

## Phase 2 — Health Check with DB Ping

### Problem

Current `/health` returns `{"status": "healthy", "version": "1.0.0"}` unconditionally.
Kubernetes liveness probes and load balancers trust this. If the DB goes down, the app reports
healthy → traffic routed to a broken pod.

### Solution

Two endpoints with different responsibilities:

- `/health` — liveness probe: "is the process alive?" (lightweight, no DB)
- `/readyz` — readiness probe: "can this pod serve traffic?" (pings DB)

```python
# app/main.py changes

@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe — process is alive (no DB check)."""
    return {"status": "healthy", "version": settings.app_version}

@app.get("/readyz", tags=["ops"])
async def readyz(db: DbDep) -> dict[str, str]:
    """Readiness probe — DB reachable, pod can serve traffic."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "ok"}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "degraded", "db": "unreachable"},
        )
```

**Design note:** Separating liveness from readiness is the Kubernetes-correct pattern.
K8s uses liveness to decide whether to restart a pod and readiness to decide whether to
route traffic. A DB hiccup should pull the pod from the load balancer (readiness=fail)
but NOT restart it (liveness=pass).

### Steps

1. Keep `/health` as liveness — remove `DbDep`, keep it lightweight
2. Add `/readyz` endpoint with `DbDep` + `text("SELECT 1")` + 503 on failure
3. Add `from sqlalchemy import text` import to `app/main.py`
4. Add tests:
   - `test_readyz_returns_200()` — happy path
   - `test_readyz_returns_503_when_db_down()` — override `get_db` to raise

**Rate limiting note:** `/readyz` should NOT be rate-limited (K8s probes call it frequently).
Keep `@limiter.limit(HEALTH_RATE_LIMIT)` only on `/health` or remove it entirely from both
since probe traffic shouldn't count against IP limits.

---

## Phase 3 — GitHub Actions CI/CD

### Goal

Automated quality gate on every push and PR to `main`:
- Lint → Test → Build (in dependency order)
- Cache uv dependencies between runs
- Fail fast: linting failure stops tests from running

### Files to Create

**`.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  quality:
    name: Lint & Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"   # 3.14 not yet on GitHub-hosted runners

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Cache uv dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: uv-${{ runner.os }}-${{ hashFiles('pyproject.toml') }}
          restore-keys: uv-${{ runner.os }}-

      - name: Install dependencies
        run: uv sync --frozen

      - name: Ruff lint
        run: uv run ruff check .

      - name: Ruff format check
        run: uv run ruff format --check .

  test:
    name: Test
    runs-on: ubuntu-latest
    needs: quality
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.13"

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Cache uv dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: uv-${{ runner.os }}-${{ hashFiles('pyproject.toml') }}
          restore-keys: uv-${{ runner.os }}-

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run tests with coverage
        run: uv run pytest tests/ --cov=app --cov-fail-under=80 --cov-report=term-missing
```

**`.github/workflows/docker-build.yml`**

```yaml
name: Docker Build

on:
  push:
    branches: [main]

jobs:
  build:
    name: Build Image
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t data-pipeline-async:ci .
```

### Python version note

GitHub-hosted runners don't yet have Python 3.14 pre-installed. Use `3.13` in CI while
developing locally with 3.14. Ruff and tests are compatible with both. Update the workflow
once `actions/setup-python@v5` ships 3.14 support.

---

## Execution Order

All 3 phases are independent. Recommended order by ROI:

```
Phase 1 (indexes)     ~30 min   Highest ROI — Foundation compliance + real perf impact
Phase 2 (readyz)      ~45 min   Correct K8s probe semantics
Phase 3 (CI/CD)       ~60 min   Quality gate for all future commits
```

## Post-Implementation Coverage

| Tier | Before | After |
|------|--------|-------|
| P1 + P2 + P3 Foundation | ~95% | **100%** |
| P1 + P2 + P3 Middle (partial) | ~40% | ~70% |
