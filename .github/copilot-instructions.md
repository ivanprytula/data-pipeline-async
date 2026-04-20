# Project Guidelines — data-pipeline-async

Async FastAPI + SQLAlchemy 2.0 REST API for ingesting and querying pipeline records.
Single `records` resource, full CRUD. Learning project demonstrating production-style async patterns.

## Communication Style

**Concise and direct.**
- Minimize explanations; assume technical competence.
- No filler: skip "Here's the answer," "Let me show you," "Thank you," "Thank you for," "Let me explain," "First, let me," etc.
- No rephrasing/redundancy: state information once, move on.
- No transitions: get straight to the point.
- Code > prose. Facts only.
- Single line answers when possible.

**Response structure**:
- State what was done/found (or ask for clarity).
- Provide code or specifics immediately.
- Optional: Brief rationale if not obvious.
- Avoid: Explanations, pleasantries, second statements of the same fact.

**When implementation is requested**: Apply changes directly to files, not code blocks in chat. Large code blocks waste tokens and force manual copy-paste. Use file tools (replace_string_in_file, multi_replace_string_in_file, create_file) to deliver code changes directly. Summary message in chat only (what changed, why, if noteworthy).

## Build and Test

```bash
uv sync                                              # install deps
uv run pytest tests/ -v                            # run all tests (no Postgres needed)
uv run pytest tests/ --cov=app                     # with coverage
uv run ruff check . && uv run ruff format .        # lint + format
uv run uvicorn app.main:app --reload               # dev server (needs Postgres)
docker compose up --build                          # full stack (app + Postgres 17)
```

## Architecture

```
FastAPI routes (app/main.py)
  └─ Pydantic v2 validation (app/schemas.py)
  └─ DbDep = Annotated[AsyncSession, Depends(get_db)]
       └─ CRUD layer (app/crud.py)  ← pure async functions
            └─ AsyncSessionLocal (app/database.py)
                 └─ asyncpg → PostgreSQL 17
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

**FastAPI Dependency Injection** — always use `Annotated[T, Depends(...)]` pattern, never bare `Depends()` in defaults:
```python
# ✓ CORRECT — FastAPI-approved pattern, Ruff-compliant
type DbDep = Annotated[AsyncSession, Depends(get_db)]
type SessionDep = Annotated[dict[str, Any], Depends(verify_session)]

@app.get("/api/v1/records/{id}")
async def read_record(record_id: int, db: DbDep, session: SessionDep) -> RecordResponse:
    ...

# ✗ WRONG — bare Depends() in default violates Ruff E275
@app.get("/api/v1/records/{id}")
async def read_record(record_id: int, db: DbDep, session: dict[str, Any] = Depends(verify_session)) -> RecordResponse:
    ...
```

**Why:** Dependency resolution happens at request time, not module load. Type aliases eliminate repetition and are testable. This is the official FastAPI pattern (Ruff linting enforces it via E275).

**Pydantic schemas** — separate request and response schemas; add `model_config = {"from_attributes": True}` on response schemas:
```python
class RecordResponse(BaseModel):
    model_config = {"from_attributes": True}
```

**Docstring style** — use [Google Python docstring style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for all functions, classes, and modules:
```python
def get_record(db: AsyncSession, record_id: int) -> Record | None:
    """Fetch a single record by primary key.

    Args:
        db: Active async database session.
        record_id: Primary key of the record to retrieve.

    Returns:
        The matching Record ORM instance, or None if not found.
    """
```

**Comments vs docstrings** — if an inline comment would cause Ruff's line-length violation, use a docstring on the field's class, function, or module instead of a `# noqa: E501` suppression:
```python
# WRONG — inline comment breaks line length, suppressed with noqa
log_level: str = "INFO"  # Override with LOG_LEVEL env var (DEBUG, INFO, WARNING, ERROR, CRITICAL)  # noqa: E501

# CORRECT — move explanation to Field(description=) or a docstring
log_level: str = "INFO"
"""Logging verbosity. Override with LOG_LEVEL env var. Accepts: DEBUG, INFO, WARNING, ERROR, CRITICAL."""
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
| `DB_ECHO` | `False` | SQLAlchemy query logging |
| `LOG_LEVEL` | `INFO` | Logging verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL |

## Namespaces & Module Decomposition

> *"Namespaces are one honking great idea — let's do more of those!"* — PEP 20

**Module split rule** — a module has one reason to exist. When a module starts doing two things, split it:

| Signal | Action |
|--------|--------|
| A file has >1 conceptual responsibility | Extract the second responsibility to a new module |
| A function exceeds ~30 lines | Break it into named sub-functions in the same or a sibling module |
| A router file imports from >3 unrelated domains | Extract a service/use-case layer |
| Related constants appear in >1 file | Centralise in `app/constants.py` |

**Current namespace map** — where things live:

| Module | Owns |
|--------|------|
| `app/constants.py` | All magic numbers, string literals, and limit values |
| `app/rate_limiting.py` | slowapi `Limiter` singleton |
| `app/rate_limiting_advanced.py` | `TokenBucketLimiter`, `SlidingWindowLimiter` |
| `app/routers/records.py` | v1 CRUD routes |
| `app/routers/records_v2.py` | v2 rate-limit showcase routes |

**Constants rule** — no magic numbers or string literals in route handlers, CRUD functions, or models:
```python
# WRONG — magic number inline
limit: Annotated[int, Query(ge=1, le=1000)] = 100

# CORRECT — named constant from app/constants.py
from app.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, MAX_BATCH_SIZE

limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE
```

**`app/constants.py` is the single source of truth** for:
- Pagination defaults (`DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`)
- Batch limits (`MAX_BATCH_SIZE`)
- Rate-limit parameters (`TOKEN_BUCKET_CAPACITY`, `TOKEN_BUCKET_REFILL_PER_SEC`, `SLIDING_WINDOW_LIMIT`, `SLIDING_WINDOW_SECONDS`)
- API prefix strings (`API_V1_PREFIX`, `API_V2_PREFIX`)

## Documentation

**File naming in `docs/`** — all `.md` files must be lowercase with hyphens as separators (kebab-case):
- ✅ CORRECT: `alembic-python314-fix.md`, `database-auth-strategy.md`
- ❌ WRONG: `ALEMBIC_PYTHON314_FIX.md`, `DatabaseAuthStrategy.md`, `alembic_fix.md`

**Markdown linting** — all `.md` files **must** comply with markdownlint rules. When writing or editing docs, follow these strictly:

**MD036: No emphasis as headings** — Never use bold/italic as section headings. Always use proper heading syntax (`#`, `##`, `###`, etc).
```markdown
# ✅ CORRECT
## Configuration Setup

Use this section to explain configuration.

### Subsection
More details here.

# ❌ WRONG
**Configuration Setup**
Use this section to explain configuration.

**Subsection**
More details here.
```
**Why**: Markdown emphasis is for text highlighting, not document structure. Headings enable table of contents generation, screen reader navigation, and proper semantic HTML.

**MD040: Fenced code blocks must have language tag** — Always specify the code language (`` ```python ``, `` ```bash ``, `` ```text ``, etc). Never use bare `` ``` ``.
```markdown
# ✅ CORRECT
```python
def foo():
    pass
```

```bash
docker compose up
```

# ❌ WRONG
```
def foo():
    pass
```
```

## Visual Documentation

**Prefer diagrams over prose for flows, chains, and complex processes.**

When explaining workflows, dependency chains, data flows, or multi-step processes:

1. **Use ASCII art / box diagrams** for:
   - Request/response flows (what calls what, when)
   - Dependency chains (what depends on what succeeding first)
   - Execution order and conditional paths
   - System architecture (components and connections)

   Example (pipeline execution):
   ```
   Push to main
       │
       ├─► ci.yml (linting + testing)
       │   ├─► quality (Ruff lint/format)
       │   └─► test (pytest) [waits for quality ✅]
       │       │
       │       └─► CI Success? ─┐
       │                        │
       └────────────────────────► docker-build.yml [only if ✅]
   ```

2. **Use Mermaid diagrams** (via `renderMermaidDiagram` tool) for:
   - State machines (auth flow, request lifecycle)
   - Entity relationships (data model connections)
   - Complex conditional branching
   - Timeline or Gantt-style dependencies

3. **Use tables** for:
   - Comparisons (when to use X vs Y, pros/cons)
   - Configuration mappings (variables → values)
   - Feature matrices

**Never use prose alone** for:
- ❌ "First the request comes in, then the middleware validates it, then the dependency injection resolves the session..."
- ✅ Use a diagram showing the request flow with each step labeled

**Rationale:** Readers scan visual diagrams in 2 seconds. Reading equivalent prose takes 30+ seconds and is harder to recall. For learning projects, diagrams are especially critical.

**Where to add diagrams:**
- Code comments: Small ASCII diagrams inline (2–5 lines max)
- Documentation files: Full flowcharts and ASCII art (no size limit)
- Chat responses: ASCII diagrams explaining complex concepts (this file shows examples)

## Learning Docs

- [ACTION_PLAN.md](../learning_docs/ACTION_PLAN.md) — 6-week study roadmap
- [DATA_PIPELINE_6WEEK_PLAN.md](../learning_docs/DATA_PIPELINE_6WEEK_PLAN.md) — async patterns theory
- [WEEK1_STARTER_KIT.md](../learning_docs/WEEK1_STARTER_KIT.md) — starter code reference
- [COMMUTE_STUDY_GUIDE_WEEK1-2.md](../learning_docs/COMMUTE_STUDY_GUIDE_WEEK1-2.md) — interview Q&A

## Copilot Integration

- **Local Copilot config:** This repository includes a project-level Copilot configuration at [.copilot/project-config.yaml](.copilot/project-config.yaml). It extends any global `~/.copilot` defaults with project-specific skills, instruction overrides, conventions, and hook settings.
- **Local skills & instructions:** Prefer the local copies under `.github/skills/` and `.github/instructions/` when present; they are purpose-built for `data-pipeline-async` and will override global equivalents.
- **Hooks & safety:** Project hooks live under `.github/hooks/` and the repository also ships safe runtime hooks in `.github/hooks` (secrets-scanner, governance-audit, tool-guardian). These are already active in this workspace and should run alongside any global hooks.
- **Memories:** Project-scoped memories (if used) should live in `.copilot/memories/` per `project-config.yaml` — keep sensitive notes out of repo history.
- **How I use this:** When asked to perform tasks, I will consult `.copilot/project-config.yaml` and local SKILL.md files to follow your project conventions and available skills. If you prefer I do not consult local Copilot config, tell me and I'll skip it.
