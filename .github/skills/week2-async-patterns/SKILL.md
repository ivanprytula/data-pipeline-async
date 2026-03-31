---
name: week2-async-patterns
description: "Implement and understand async Python patterns for this data pipeline project. Use when: implementing batch inserts, pagination, retry with exponential backoff, rate limiting, Pydantic validators, FastAPI background tasks, or asyncpg connection pool tuning. Teaches the why behind each pattern alongside working code. USE FOR: async patterns, week 2 milestones, batch operations, connection pooling, background tasks, streaming, retry logic."
argument-hint: "Pattern to implement: batch | pagination | retry | rate-limit | background-tasks | connection-pool | validator"
---

# Week 2 Async Patterns

Implements async Python patterns step-by-step, explaining the reasoning alongside each code change, then verifies with a test.

## When to Use

Type `/week2-async-patterns <pattern>` to implement any of:

| Pattern | What it teaches |
|---------|----------------|
| `batch` | Bulk insert vs single-insert throughput; `session.add_all()` |
| `pagination` | Offset/limit queries; `has_more` flag; count + data in one async function |
| `retry` | Async exponential backoff; cancellation-safe sleep; when NOT to retry |
| `rate-limit` | `slowapi` + `asynccontextmanager`; 429 responses; per-IP vs global |
| `background-tasks` | `FastAPI.BackgroundTasks`; fire-and-forget vs awaited tasks; lifecycle |
| `connection-pool` | `asyncpg` pool sizing; `pool_pre_ping`; measuring pool exhaustion |
| `validator` | Pydantic v2 `@field_validator`, `@model_validator`; cross-field rules |

## Procedure

### Step 1 — Identify the pattern

Read the `$ARGUMENTS`. Match to one of the patterns above. If ambiguous or omitted, list available patterns and ask which one.

### Step 2 — Read current state

Before writing code, read the relevant files:
- [app/main.py](../../app/main.py) — routes and middleware
- [app/crud.py](../../app/crud.py) — database operations
- [app/schemas.py](../../app/schemas.py) — Pydantic schemas
- [app/database.py](../../app/database.py) — engine and session config
- [tests/test_api.py](../../tests/test_api.py) — existing tests
- [pyproject.toml](../../pyproject.toml) — current dependencies

### Step 3 — Explain the concept first

Before writing any code, give a 3-5 sentence explanation of:
- **What** the pattern does
- **Why** it matters (production impact: latency, throughput, reliability)
- **The trade-off** it introduces (complexity, memory, ordering guarantees)

Then show a before/after mental model:
```
❌ Without: [describe the problem]
✅ With:    [describe the solution]
```

### Step 4 — Implement

Follow the pattern-specific guide in [./references/patterns.md](./references/patterns.md).

Always follow existing project conventions:
- SQLAlchemy 2.0 `select()` style — no legacy ORM
- `AsyncSession` as first positional arg in CRUD functions
- `DbDep = Annotated[AsyncSession, Depends(get_db)]` in routes
- Structured logging: `logger.info("event_name", extra={"cid": cid, ...})`
- `asyncio_mode = "auto"` in tests — no `@pytest.mark.asyncio`

### Step 5 — Write a test

Every pattern gets at least one test demonstrating it works. Where possible, write a test that **shows the contrast** (e.g., single vs batch timing, retry succeeding after simulated failure).

### Step 6 — Run and verify

```bash
uv run pytest tests/ -v -k "<relevant_test>"
```

Report results. Fix failures before finishing.

### Step 7 — Summarise the learning

End with 2-3 bullet points:
- What was implemented
- The key insight (the "aha" moment)
- What to explore next (natural follow-up pattern)
