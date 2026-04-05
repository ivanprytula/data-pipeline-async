# Milestone Checklist: Junior → Strong Middle/Senior

> **Coverage guide**: 🟢 Junior threshold (90-95% of JDs) | 🟡 Middle threshold (90%+ of middle JDs) | 🔴 Senior differentiator (50-60% of senior JDs)
> **Project tag**: skill + what to build in `data-pipeline-async` to prove it

---

## Pillar 1 — Core Backend (Python + FastAPI)

### 🟢 Foundation — locks in 90%+ Junior/Middle positions

- **Python 3.x internals you must own**
  - OOP: inheritance, dunders, dataclasses, ABCs
  - `asyncio`: event loop, `await`, `Task`, `gather`, `Semaphore`, `shield`
  - Type hints: fully annotated code, generics, `TypeAlias`, `Annotated`
  - Comprehensions, generators, context managers (`async with`)
  - Exception hierarchy, custom exceptions, `__cause__` chaining

- **FastAPI**
  - Routes, path/query/body params, status codes
  - `Annotated` dependencies + `Depends` — the modern DI pattern
  - `APIRouter` to split app into modules (extract `routers/records.py`)
  - `lifespan` context manager (startup/shutdown, replaces `@on_event`)
  - `BackgroundTasks` for fire-and-forget post-response work
  - Custom exception handlers + middleware (logging, CORS, request ID)

- **Pydantic v2**
  - `BaseModel`, `Field`, `model_config = {"from_attributes": True}`
  - `field_validator`, `model_validator`, `@computed_field`
  - `pydantic-settings` for typed env config (`Settings`, `.env` loading)
  - `TypeAdapter` for validating primitives outside a model

- **Testing**
  - `pytest`: fixtures, parametrize, `tmp_path`
  - `pytest-asyncio` (`asyncio_mode = "auto"`)
  - `httpx.AsyncClient` + `ASGITransport` for integration tests
  - `dependency_overrides` to swap DB for `aiosqlite` in tests
  - Coverage: `pytest --cov=app` ≥ 80%

- **Project build**: ✅ most already done; add `BackgroundTasks` after `PATCH /process`, write 15+ integration tests

---

### 🟡 Middle tier — unlocks 90%+ Middle positions

- **Concurrency patterns**
  - `asyncio.gather` fan-out: batch-write 100 records concurrently
  - `asyncio.Semaphore` to cap fan-out without pool exhaustion
  - Retry with exponential backoff + jitter — implement via `tenacity`
  - Timeout semantics: `asyncio.wait_for`, cancel cleanup
  - Backpressure: bounded queue (`asyncio.Queue(maxsize=N)`)

- **API patterns**
  - Cursor-based pagination (replace `skip`/`limit` with opaque cursor)
  - Idempotent upsert (`ON CONFLICT DO NOTHING` or `MERGE`)
  - Rate limiting: `slowapi` + Redis backend; test with 101-request scenario
  - Streaming responses (`StreamingResponse` over generator)
  - Request ID middleware (`X-Request-ID` header, UUID injected into every log line)
  - Health check that pings DB (`SELECT 1`) — not just `{"status": "ok"}`

- **Project build**: cursor pagination, batch fan-out with semaphore, slowapi rate limiter, request-ID middleware, deep health check

---

### 🔴 Senior differentiators

- Inter-service communication: gRPC basics or ZeroMQ; WebSockets
- Custom ASGI middleware stack; profiling with `py-spy` or `Pyinstrument`
- Advanced cancellation semantics (structured concurrency, `TaskGroup` Python 3.11+)
- Profiling async code: identifying blocking sync calls inside `async def`

---

## Pillar 2 — Database Layer (PostgreSQL + SQLAlchemy)

### 🟢 Foundation

- **SQL you must write from memory**
  - `JOIN` types: INNER, LEFT, cross; when to use each
  - `GROUP BY` + aggregates (`COUNT`, `SUM`, `AVG`, window functions)
  - CTEs (`WITH ... AS`) for readable multi-step queries
  - `EXPLAIN` output: understand `Seq Scan` vs `Index Scan` vs `Bitmap Heap Scan`

- **SQLAlchemy 2.0 ORM**
  - `mapped_column`, `Mapped[T]`, `relationship`, `ForeignKey`
  - `select()`, `where()`, `scalar_one_or_none()`, `scalars().all()`
  - `AsyncSession` lifecycle, `expire_on_commit=False` (know why)
  - `async_sessionmaker`, `get_db` dependency injection

- **Alembic**
  - `alembic revision --autogenerate -m "reason"`
  - `alembic upgrade head`, `downgrade -1`
  - Data migrations (not just schema) via `op.execute()`

- **Project build**: ✅ already set up; write raw SQL for one complex list query, then match it in ORM

---

### 🟡 Middle tier

- **Query optimization**
  - `EXPLAIN ANALYZE` — read: actual vs estimated rows, cost, filter rows
  - B-tree index for single columns; composite index column order rule: equality before range
  - Partial index: `WHERE processed = false` — only index active rows
  - Covering index: include non-key columns to avoid heap fetch
  - N+1 detection: enable `SQL_ECHO=True`, count queries per endpoint; fix with `selectinload` / explicit JOIN

- **PostgreSQL advanced**
  - Connection pooling: `pool_size`, `max_overflow`, `pool_pre_ping=True`; formula: `(max_connections / instances)`
  - Transactions: isolation levels, `SELECT FOR UPDATE` for concurrent updates
  - MVCC: why SELECT doesn't block UPDATE; what causes table bloat
  - `JSONB` column: `@>`, `?`, `->>` operators; GIN index on JSONB
  - Soft deletes: `deleted_at TIMESTAMPTZ` nullable; partial index on active rows
  - Schema migrations with zero-downtime: add nullable column → backfill → add constraint

- **Project build**: add `EXPLAIN ANALYZE` query to README, add partial index on `processed=false`, add JSONB `data` column with GIN index, add `deleted_at` soft-delete column via Alembic migration

---

### 🔴 Senior differentiators

- Row-Level Security (RLS) for multi-tenancy — policies in PostgreSQL
- `pgvector` extension for embedding storage (AI pivot)
- Read replica routing (`asyncpg` multi-host; SQLAlchemy write/read session routing)
- Table bloat: autovacuum tuning, `pg_stat_user_tables` monitoring
- Cursor-based pagination at scale vs keyset pagination

---

## Pillar 3 — Ops & Infrastructure

### 🟢 Foundation

- **Docker**
  - `Dockerfile`: multi-stage build (builder + runtime, non-root user `USER appuser`)
  - `.dockerignore`, layer caching order (deps before code)
  - `docker compose`: services, volumes, env files, `depends_on`, `healthcheck`
  - Debugging in containers: `docker exec -it`, `docker logs --follow`

- **Git**
  - Conventional commits (`feat:`, `fix:`, `chore:`)
  - Feature branch workflow, PRs, squash merge
  - `git bisect` for finding regressions (know the concept)

- **Linux**
  - `grep`, `awk`, `sed`, `jq` for log parsing
  - `ps`, `top`, `htop`, `lsof`, `netstat` for process/network inspection
  - `systemd` service basics (if deploying bare-metal)

- **Project build**: ✅ `docker-compose.yml` exists; harden `Dockerfile` with multi-stage build + non-root user; add `healthcheck` to compose

---

### 🟡 Middle tier

- **CI/CD — GitHub Actions**
  - Workflow structure: `on:`, `jobs:`, `steps:`, `env:`, `secrets:`
  - Job chain: `lint` → `test` → `build` → `push` to registry (sequential)
  - Caching: `actions/cache` for `uv` lockfile/venv (fast re-runs)
  - Matrix: test on Python 3.12 + 3.13 simultaneously
  - PR check: block merge if tests fail or coverage drops

- **Configuration & Secrets**
  - 12-factor app: all config from env vars, never hardcoded
  - `pydantic-settings` with `.env.example` checked in, `.env` gitignored
  - Secrets: AWS Secrets Manager / Docker secrets concept (never `os.environ["SECRET"]` hardcoded)

- **Cloud basics (AWS/GCP — pick one)**
  - Deploy a containerized FastAPI app: ECR (registry) + ECS Fargate OR Cloud Run
  - S3: upload/download files from Python (`boto3`)
  - RDS: production PostgreSQL, connection string, SSL mode
  - Secrets Manager: load secrets at runtime

- **Project build**: `.github/workflows/ci.yml` with lint + test + build; add `.env.example`; deploy to Cloud Run or ECS (even once, document in README)

---

### 🔴 Senior differentiators

- **Kubernetes**
  - `Deployment`, `Service`, `Ingress`, `ConfigMap`, `Secret`
  - Resource requests/limits on every container
  - `livenessProbe` + `readinessProbe` (HTTP health endpoint → required)
  - HPA (horizontal pod autoscaler on CPU metric)
  - `securityContext`: `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, drop all capabilities
  - Rolling update strategy: `maxSurge: 1`, `maxUnavailable: 0`

- **Terraform basics**
  - Provision one resource (RDS instance or Cloud Run service)
  - State files, `terraform plan` vs `terraform apply`, workspaces

- **Docker hardening**
  - `readOnlyRootFilesystem: true`, capabilities `drop: [ALL]`, non-root UID

---

## Pillar 4 — Observability

### 🟡 Middle tier (required for most middle+ roles)

- **Structured logging**
  - `python-json-logger`: every log entry is valid JSON
  - Required fields on every log: `timestamp`, `level`, `cid` (correlation ID), `event`
  - Request lifecycle: log on entry (method, path, cid) + exit (status, duration_ms)
  - Never log secrets or PII; log IDs, not values

- **Metrics (Prometheus)**
  - Metric types: `Counter` (requests_total), `Gauge` (active_connections), `Histogram` (request_duration_seconds)
  - `prometheus-fastapi-instrumentator`: auto-instrument FastAPI with one line
  - `/metrics` endpoint for Prometheus scraping
  - Grafana: connect data source, build dashboard (request rate, error rate, latency P95)

- **Project build**: ✅ correlation ID logging already exists; add `prometheus-fastapi-instrumentator`, expose `/metrics`; add `docker-compose` with Prometheus + Grafana

---

### 🔴 Senior differentiators

- **OpenTelemetry (distributed tracing)**
  - Traces + spans across service calls
  - Auto-instrumentation for FastAPI, SQLAlchemy, httpx
  - Send to Jaeger or OTLP collector
  - Trace IDs in logs (correlate logs ↔ traces)

- Alerting: Prometheus alertmanager rules; alert on error rate > 1%, P95 > 500ms
- Log aggregation: Loki or ELK stack (ingest, query, dashboards)
- SLO/SLI concepts: define error budget, burn rate alerts

---

## Pillar 5 — Security

### 🟡 Middle tier

- **Authentication / Authorization**
  - JWT: creation (`python-jose`), validation, expiry, refresh token pattern
  - OAuth2 password flow with FastAPI's `OAuth2PasswordBearer`
  - Auth0 / Cognito integration (delegate auth, validate JWT in middleware)
  - RBAC: `Depends` on a permission-check function

- **Input validation & injection prevention**
  - Pydantic validates all input at system boundary — know what it prevents
  - Parameterized queries via SQLAlchemy ORM (never f-strings in SQL)
  - `enum` for status fields (prevents arbitrary string injection)

- **API hardening**
  - CORS: restrict `allow_origins` to known domains
  - `SecurityHeaders` middleware: `X-Content-Type-Options`, `X-Frame-Options`
  - Rate limiting + account lockout (prevent brute force on `/login`)
  - `422` vs `400` error responses (Pydantic 422 is auto; know the difference)

- **Project build**: add JWT auth middleware; add `POST /auth/token` endpoint; protect records endpoints with `Depends(get_current_user)`

---

### 🔴 Senior differentiators

- HMAC webhook verification (validate `X-Signature-256` header before processing)
- Docker security: non-root, read-only FS, no `--privileged`
- CI secret scanning: `truffleHog` or `gitleaks` in pipeline
- PostgreSQL RLS policies for row-level tenant isolation
- OWASP Top 10 — explain each with a Python/FastAPI example from memory

---

## Pillar 6 — AI / LLM Integration (the 2025-2030 multiplier)

### 🟡 Middle tier — already in 60%+ of JDs, growing fast

- **LLM API usage**
  - OpenAI + Anthropic Python SDKs: chat completions, async calls, streaming (`stream=True`)
  - Token counting and cost awareness (`tiktoken`)
  - Structured output: Pydantic model + function calling / `response_format`
  - Parallel LLM calls with `asyncio.gather` (fan-out to multiple models)
  - Error handling: rate limits (429), context-length exceeded (400), retry strategy

- **RAG pipeline (Retrieval-Augmented Generation) — required at Middle+**
  - Embeddings: `text-embedding-3-small` via OpenAI or local via `sentence-transformers`
  - Vector store: `pgvector` (best fit — already using PostgreSQL) or `Chroma`
  - Retrieval: cosine similarity search, top-K, re-ranking
  - Full pipeline: ingest text → embed → store → query → augment prompt → generate
  - LangChain or raw implementation (raw = more impressive)

- **GenAI tool proficiency (now explicitly in JDs)**
  - GitHub Copilot: code generation, test scaffolding, docstrings
  - Claude: architecture review, code review, complex refactoring
  - Cursor / Windsurf: context-aware multi-file editing
  - Treat AI tools as a 3x productivity multiplier, not a crutch

- **Project build**: add `POST /api/v1/records/analyze` endpoint that sends record `data` as context to OpenAI and returns a classification; add `pgvector` column to Record model; build a simple semantic search endpoint

---

### 🔴 Senior differentiators

- **Agent frameworks**
  - `LangGraph`: stateful multi-step agent, conditional edges, human-in-the-loop
  - `CrewAI`: multi-agent orchestration with roles and tool use
  - Guardrails: input/output validation for LLM responses (hallucination prevention)
  - Feedback loops: store generations + user ratings, retrain/fine-tune pipeline

- Local LLM deployment: `Ollama` / `vLLM` — serve `llama3` or `mistral` locally
- MCP (Model Context Protocol): build a custom MCP server that exposes your API to Claude Desktop / Copilot agents
- Evaluation pipelines: `ragas`, `deepeval` for measuring RAG quality (faithfulness, relevance, context precision)
- `Prefect` / `Airflow` DAGs for orchestrating LLM batch processing pipelines

---

## Pillar 7 — Data & ETL (bonus niche)

### 🟡 Valuable add-on — differentiates in data-heavy JDs (DataOX, Fornova, ETL roles)

- **Pandas fundamentals**
  - `read_csv`, `DataFrame`, `groupby`, `merge`, `pivot`, `apply`
  - Cleaning: `dropna`, `fillna`, `astype`, duplicates
  - Export: `to_csv`, `to_parquet`, `to_sql`

- **ETL design pattern**
  - Extract → Transform → Load as three pure functions
  - Idempotent loads: `ON CONFLICT DO UPDATE` or truncate+reload
  - Incremental vs full refresh; watermark column (`updated_at > last_run`)
  - Error isolation: failed rows go to a dead-letter table, not crash pipeline

- **Queues / task orchestration**
  - Celery + Redis broker: task definition, retries, ETA/countdown, canvas (chord, group)
  - OR `arq` (async Redis Queue — fits better in async-first codebase)
  - Task monitoring: Flower for Celery, or custom `/tasks/status/{id}` endpoint

- **Scraping (if targeting DataOX/Fornova type roles)**
  - `httpx`/`aiohttp`: async HTTP, session management, retries
  - `BeautifulSoup4`: HTML parsing, CSS selectors, XPath concepts
  - `Playwright`: headless browser automation, `page.wait_for_selector`, intercept requests
  - Anti-bot basics: user-agent rotation, request delays, residential proxies concept
  - Proxy rotation, CAPTCHA handling (2captcha API)

- **Project build**: add `app/fetch.py` — an `httpx` client with tenacity retry; add `POST /api/v1/records/ingest` endpoint that accepts a URL, fetches JSON, validates with Pydantic, and bulk-inserts; add a Celery/arq task for async processing

---

## Coverage Summary

| What you can do | JD Coverage |
|---|---|
| Pillars 1 (Foundation) + 2 (Foundation) + 3 (Foundation) + Git | 90-95% Junior |
| + Pillars 1-3 Middle tiers + Redis basics + CI/CD + JWT auth | 90%+ Middle |
| + Observability + Cloud deploy (once) + LLM API + RAG basics | ~60% Middle+ / Junior Senior |
| + Kubernetes + Distributed tracing + Agent frameworks + RLS | 50-60% Senior |

---

## Build Order for `data-pipeline-async`

Work through these additions in sequence — each proves a new tier:

1. **Now**: cursor pagination, batch fan-out + semaphore, `slowapi` rate limiter, request-ID middleware, deep health check → proves Middle Foundation
2. **Next**: GitHub Actions CI, Dockerfile hardening (non-root, multi-stage), `prometheus-fastapi-instrumentator` + Grafana compose → proves Middle Ops
3. **Then**: JWT auth (`POST /auth/token` + `Depends(get_current_user)` on records) + `EXPLAIN ANALYZE` study + soft-delete migration → proves Middle Security + DB Optimization
4. **Then**: OpenAI integration (`POST /records/analyze`), `pgvector` column, semantic search endpoint → proves AI-capable Middle/Middle+
5. **Then**: `LangGraph` or `CrewAI` agent that processes batches of records → proves Middle+ / entry Senior
6. **Then**: Kubernetes manifests (`deployment.yaml`, `service.yaml`, `ingress.yaml` with probes + resource limits) + Terraform for RDS → proves Senior Ops
