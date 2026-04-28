# Project Guidelines — data-pipeline-async

Async FastAPI + SQLAlchemy 2.0 REST API for ingesting and querying pipeline records.
Single `records` resource, full CRUD. Learning project demonstrating production-style async patterns.

## Self-Enforced Discipline

**Read instruction files at task start.** Before implementing code, writing docs, or handling complex requests:
1. Read `.github/copilot-instructions.md` (this file)
2. Read any applicable instruction files from `.github/instructions/` (e.g., `fastapi.instructions.md` for routes, `tests.instructions.md` for test files)
3. Read relevant skill files if a skill applies (search `.github/skills/` for matching SKILL.md)

This ensures I follow **current guidance**, not stale context. Show the read in my reasoning process.

## Communication Style

**Maximum concision for context optimization.**
- Output only what user needs: actions taken, results, next steps.
- **No internal flow/processing**: Skip intermediate reasoning, hypotheticals, "I will now," "Let me check," step-by-step narration of what you're doing, tool/skill names.
- **No filler**: Omit "Here's the answer," "Thank you," transitional phrases, pleasantries.
- **No rephrasing**: State facts once, never repeat.
- Code > prose. Facts only. Single line answers when possible.
- Assume technical competence; skip explanations unless non-obvious.

**Response structure**:
- Result or change (one line).
- Code/specifics if needed (no markdown block for simple output; use file tools for large changes).
- Brief rationale only if non-obvious (one sentence).

**Token optimization rules**:
- Direct all code changes to files via file tools, never chat code blocks.
- Omit "Changes Made" sections; user sees diffs directly.
- Omit tool names, reasoning traces, or "I'm going to do X now."
- Skip examples unless explicitly asked.
- Process files one-by-one: complete and write/update each file fully before moving to the next. Avoid accumulating many open file edits or retaining large file contents in memory — this reduces context growth and token usage.
- No internal monologue about task planning, skill loading, or process steps.

When creating shell scripts or other `*.sh` files, keep comments minimal and avoid embedding specific file or folder names or paths in comments (this reduces future refactoring churn).

- Avoid embedding literal environment variable names or secret identifiers in descriptions or comments; keep descriptions generic and do not reveal secret identifiers in human-readable text.

## Build and Test

Execution note: always invoke Python scripts using `uv run` so the project's pinned
environment is used (for example `uv run python scripts/ci/dependabot_age_gate.py` or
`uv run pytest`). Avoid calling `python` or `python3` directly in CI, scripts, or
developer commands — use `uv run` to ensure reproducible dependencies.

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
FastAPI routes (ingestor/main.py)
  └─ Pydantic v2 validation (ingestor/schemas.py)
  └─ DbDep = Annotated[AsyncSession, Depends(get_db)]
       └─ CRUD layer (ingestor/crud.py)  ← pure async functions
            └─ AsyncSessionLocal (ingestor/database.py)
                 └─ asyncpg → PostgreSQL 17
```

| File | Responsibility |
|------|---------------|
| `ingestor/main.py` | Routes, lifespan hook (table creation), correlation-ID logging |
| `ingestor/crud.py` | All DB operations — async functions, `AsyncSession` as first arg |
| `ingestor/models.py` | SQLAlchemy 2.0 ORM — `Mapped[T]` / `mapped_column()` style only |
| `ingestor/schemas.py` | Pydantic v2 request/response schemas |
| `ingestor/database.py` | Engine, `async_sessionmaker`, `Base`, `get_db` dependency |
| `ingestor/config.py` | `pydantic-settings` `Settings`, reads `.env` |

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

**TypedDict for test data and unstructured dicts** — use `TypedDict` to define the shape of test fixtures, JSON payloads, and dictionary return types. Eliminates `# ty:ignore` suppressions and improves type-checking accuracy:
```python
from typing import TypedDict

# Test data fixtures
class RecordData(TypedDict):
    """Test record fixture shape."""
    source: str
    timestamp: str
    data: dict[str, float]
    tags: list[str]

_RECORD: RecordData = {
    "source": "api.example.com",
    "timestamp": "2024-01-15T10:00:00",
    "data": {"price": 123.45},
    "tags": ["Stock", "NASDAQ"],
}

# Function return types for dict results
class QueryResult(TypedDict):
    """API query result shape."""
    records: list[dict[str, Any]]
    total: int
    has_more: bool

async def query_records(...) -> QueryResult:
    """Fetch records with pagination."""
    return {
        "records": [...],
        "total": 100,
        "has_more": True,
    }

# When TypedDict fields are optional, use Required[] or mark fields separately:
class OptionalResult(TypedDict, total=False):
    """Optional fields: all fields are optional."""
    error: str
    suggestion: str

class MixedResult(TypedDict):
    """Mixed required/optional fields."""
    id: int
    name: str
    email: NotRequired[str]  # Python 3.11+ syntax

# In tests, use type aliases for HTTP response shapes:
type ResponseShape = dict[str, Any]  # Fallback if exact shape varies
type CreateResponse = TypedDict("CreateResponse", {"id": int, "status": str})
```

**Why TypedDict**: Provides static type checking for dictionaries without runtime overhead (unlike Pydantic models for simple cases). Essential for:
- Test fixtures (eliminates `# ty:ignore[not-iterable]`, `# ty:ignore[call-overload]`)
- JSON response payloads (documents API contract)
- Function return types (improves IDE autocomplete)

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

Key environment variables (see `ingestor/config.py`, defaults from `.env`):

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
| Related constants appear in >1 file | Centralise in `ingestor/constants.py` |

**Current namespace map** — where things live:

| Module | Owns |
|--------|------|
| `ingestor/constants.py` | All magic numbers, string literals, and limit values |
| `ingestor/rate_limiting.py` | slowapi `Limiter` singleton |
| `ingestor/rate_limiting_advanced.py` | `TokenBucketLimiter`, `SlidingWindowLimiter` |
| `ingestor/routers/records.py` | v1 CRUD routes |
| `ingestor/routers/records_v2.py` | v2 rate-limit showcase routes |

**Constants rule** — no magic numbers or string literals in route handlers, CRUD functions, or models:
```python
# WRONG — magic number inline
limit: Annotated[int, Query(ge=1, le=1000)] = 100

# CORRECT — named constant from ingestor/constants.py
from app.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, MAX_BATCH_SIZE

limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE
```

**`ingestor/constants.py` is the single source of truth** for:
- Pagination defaults (`DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`)
- Batch limits (`MAX_BATCH_SIZE`)
- Rate-limit parameters (`TOKEN_BUCKET_CAPACITY`, `TOKEN_BUCKET_REFILL_PER_SEC`, `SLIDING_WINDOW_LIMIT`, `SLIDING_WINDOW_SECONDS`)
- API prefix strings (`API_V1_PREFIX`, `API_V2_PREFIX`)

## Documentation

**File naming in `docs/`** — all `.md` files must be lowercase with hyphens as separators (kebab-case):
- ✅ CORRECT: `alembic-python314-fix.md`, `database-auth-strategy.md`
- ❌ WRONG: `ALEMBIC_PYTHON314_FIX.md`, `DatabaseAuthStrategy.md`, `alembic_fix.md`

**Markdown linting** — all `.md` files **must** comply with markdownlint rules. When writing or editing docs, follow these strictly:

**Hard rule (non-negotiable):** Never violate this rule: "bold-only heading detected (use markdown headings)."
Always use proper markdown heading syntax (`#`, `##`, `###`, etc.) and never use bold text as a heading substitute. If this will lead to duplicate headings, adjust the heading level or rephrase to maintain unique headings while following markdown syntax.

**Explicit anti-pattern ban:** Never write standalone label lines like `**Manual method:**`, `**Settings:**`, `**Notes:**`, `**Expected output:**`. These are treated as emphasis-only headings and will fail the docs quality hook. Use `###`/`####` headings or plain paragraph text instead.

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

**MD032: Lists must be surrounded by blank lines** — Always place a blank line before and after every list (ordered or unordered). Never start a list immediately after a heading, paragraph, or code block without a blank line in between.

**Pre-flight markdown check** — before finishing any `.md` edit:
1. Search for standalone emphasis lines (`^\*\*.*\*\*$`).
2. Convert each to a proper heading or inline sentence.
3. Re-check heading hierarchy (no skips).

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

### Prefer Diagrams Over Prose

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

### Where To Add Diagrams
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
