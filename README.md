# Data Zoo — 8-Phase Backend Platform Learning

**Comprehensive full-stack backend learning journey**: Event streaming → Data scraping → CI/CD → AI/embeddings → Testing → Database optimization → Security → Infrastructure as Code.

Build production-ready capabilities across all major backend domains while creating interview-ready portfolio artifacts.

---

## 8-Phase Platform Overview

| Phase       | Focus            | Core Interview Q                               | Tech Stack                                       | Status     |
| ----------- | ---------------- | ---------------------------------------------- | ------------------------------------------------ | ---------- |
| **Phase 1** | Event Streaming  | Design real-time ETL for 1000+ events/sec      | Redpanda, Celery, partitioning                   | ✅ Done    |
| **Phase 2** | Data Scraping    | Design scraper for 100K URLs without ban       | GraphQL, Playwright, rate limiting               | ✅ Done    |
| **Phase 3** | AI + Vector DB   | Design semantic search over 100K docs          | SentenceTransformers, Qdrant, LRU cache          | 🚀 Active  |
| **Phase 4** | Docker + CI/CD   | Walk me through dev → prod pipeline            | Multi-stage Docker, GitHub Actions, ECR          | ⏹️ Queued  |
| **Phase 5** | Testing          | How do you test code that calls external APIs? | pytest (10 fixtures), async mocking, chaos tests | ⏹️ Queued  |
| **Phase 6** | Database Mastery | This query is slow (5s). Fix it.               | 40 SQL patterns, EXPLAIN ANALYZE, indexing       | ⏹️ Queued  |
| **Phase 7** | Security         | Design JWT auth for multi-service app          | JWT + refresh tokens, rate limiting, secrets     | ⏹️ Queued  |
| **Phase 8** | Infrastructure   | Design multi-env Terraform (dev/staging/prod)  | Terraform, AWS (RDS/Fargate), state mgmt         | ⏹️ Queued  |

**Timeline**: 16 weeks / 2 weeks per phase
**Deliverables**: 100+ commits, 8 LinkedIn posts, 8 portfolio items, 100% test coverage

---

## Getting Started — Phase 1

### Prerequisites

```bash
# Install uv (one-time)
pip install uv   # or: curl -Ls https://astral.sh/uv/install.sh | sh

# One-time setup
cp .env.example .env
# Edit .env with your local values (PostgreSQL running in Docker, etc.)
```

> **Phase 5+**: This project uses PostgreSQL with pgvector extension for vector embeddings. See [pgvector Setup Guide](docs/pgvector-setup-guide.md) for details (automated setup, no manual steps required).

### Quick Start

**Option 1: Full Development Setup (Recommended)**

Run all services needed for development and testing:

```bash
# Start ALL services (db, test db, redis, kafka, mongodb, jaeger)
bash scripts/dev-services.sh

# Sync dependencies
uv sync

# Run all tests (including PostgreSQL concurrent tests)
uv run pytest tests/ -v

# Apply database migrations
uv run alembic upgrade head

# Start the app (auto-reloads on code changes)
uv run uvicorn app.main:app --reload

# Open API docs
open http://localhost:8000/docs
```

**Option 2: Minimal Setup (Basic testing only)**

```bash
# Start only core containers (db + redis)
docker compose up -d db redis

# Sync dependencies
uv sync

# Run tests with aiosqlite (PostgreSQL tests skipped)
uv run pytest tests/ -v

# Apply database migrations
uv run alembic upgrade head

# Start the app (auto-reloads on code changes)
uv run uvicorn app.main:app --reload
```

> **Tip:** Use Option 1 during active development to run the full test suite without manual service management. See [docs/commands.md](docs/commands.md) for details.

### Tracking Your Progress

See [`.github/instructions/middle-tier-grind-tracking.md`](.github/instructions/middle-tier-grind-tracking.md) for:

- 8-phase timeline with weekly checklist
- 40 SQL patterns (to master by Phase 6)
- 10 pytest fixtures (by Phase 5)
- 5 async gotchas (quick reference)
- Weekly interview Q checkpoint (8 total)
- Success metrics per phase

---

## Phase Guides (Scaffolding Blueprint)

All 8 phases have complete execution blueprints in `learning_docs/`:

### Phase 3: AI Gateway & Semantic Search (Current) 🚀

**Learning Objective**: Build a multi-service architecture for semantic search using embeddings + vector DB.

**Documentation**:

- [**PHASE_3_QUICK_START.md**](learning_docs/PHASE_3_QUICK_START.md) — 15-minute setup guide
- [**PHASE_3_AI_GATEWAY.md**](learning_docs/PHASE_3_AI_GATEWAY.md) — Complete implementation guide
- [**ADR 005: Phase 3 Architecture**](docs/adr/005-phase-3-ai-gateway.md) — Design decisions

**Stack**: SentenceTransformers, Qdrant (HNSW indexes), FastAPI

**Quick Start**:

```bash
# Boot all services (Qdrant + AI Gateway + app)
docker-compose up --build

# Test embeddings
curl -X POST http://localhost:8001/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "semantic search example"}'

# Search for similar documents
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning models", "top_k": 5}'

# Browse Qdrant vector DB
open http://localhost:6334
```

**Key Concepts**:

- **Lazy Loading**: Load embedding model once, reuse forever
- **LRU Cache**: Avoid redundant embeddings in batch operations
- **Service Separation**: API tier ↔ AI tier ↔ Qdrant
- **Async Patterns**: Lifespan context managers, health checks

**Interview Q**: "Walk me through your semantic search system. How would you handle 100K documents? Where's the bottleneck?"

---

### Other Phases (Roadmap)

| File                     | Phase  | Focus                              | Use When                    |
| ------------------------ | ------ | ---------------------------------- | --------------------------- |
| **phase-1-events.md**    | Phase 1| Redpanda + Celery real-time ETL  | Already implemented (base)  |
| **phase-2-scrapers.md**  | Phase 2| GraphQL scraper + rate limiting   | Already implemented         |
| **docker-ci-guide.md**   | Phase 4| Multi-stage Docker + GitHub Actions| Starting next               |
| **phase-4-testing.md**   | Phase 5| 10 pytest fixtures + async mocking | Phase 5 (see above) |
| **phase-5-database.md**  | Phase 6| 40 SQL patterns + EXPLAIN ANALYZE | Phase 6                     |
| **phase-6-security.md**  | Phase 7| JWT + refresh tokens + rate limiting| Phase 7                    |
| **phase-7-terraform.md** | Phase 8| Terraform modules + multi-env     | Phase 8                     |

Each guide includes:
✅ Core interview question + suggested answer
✅ 2 follow-up questions you'll face
✅ Concrete real world production example to build
✅ Weekly checklist (8–15 commits per phase)
✅ Interview prep talking points
✅ Success criteria + metrics

---

## Project Structure (Phase 1–3)

This codebase implements Phase 1's foundation: async FastAPI + SQLAlchemy 2.0 for event ingestion.

```text
app/
├── main.py               — FastAPI routes, lifespan, middleware
├── config.py             — Pydantic settings (from .env)
├── database.py           — Engine, session factory, migrations
├── models.py             — SQLAlchemy ORM (Record, ProcessedEvent models)
├── schemas.py            — Pydantic v2 request/response schemas
├── crud.py               — Ingestor CRUD: Record operations (async)
├── cache.py              — Redis caching layer (fail-open)
├── rate_limiting.py      — slowapi + custom limiters
├── rate_limiting_advanced.py — Token bucket, sliding window
├── auth.py               — JWT validation, Bearer tokens
├── metrics.py            — Prometheus middleware
├── fetch.py              — httpx + exponential backoff retry
├── fetch_aiohttp.py      — aiohttp alternative (comparison)
├── events.py             — Kafka producer singleton (Phase 1)
├── storage/              — Platform-wide storage layer (shared across services)
│   ├── __init__.py
│   ├── events.py         — ProcessedEvent CRUD (Phase 1: idempotency, DLQ, status tracking)
│   └── mongo.py          — MongoDB client (Phase 2)
└── core/
    └── circuit_breaker.py — Resilience patterns (Phase 4)

tests/
├── conftest.py           — Fixtures (in-memory DB, client, redis)
├── test_api.py           — Integration tests
├── test_performance.py   — Baseline timing tests
└── integration/          — E2E tests (cache, fetch, auth)

.github/instructions/
├── middle-tier-grind-tracking.md  — Weekly checklist (root)
├── phase-1-events.md              — Redpanda + Celery blueprint
├── phase-2-scrapers.md            — GraphQL + rate limiting
├── docker-ci-guide.md             — CI/CD pipeline
├── phase-3-ai-qdrant.md           — AI + embeddings
├── phase-4-testing.md             — pytest + mocking
├── phase-5-database.md            — 40 SQL patterns
├── phase-6-security.md            — JWT + auth
└── phase-7-terraform.md           — Infrastructure as Code

docs/templates/
├── linkedin-post-template.md      — 280-char technical tone
├── portfolio-item-template.md     — GitHub link + learning
└── github-commit-template.md      — Structured commits
```

---

## API Endpoints (Phase 1—Core)

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

## Database Migrations (Alembic)

Schema is managed by Alembic — **never** run `Base.metadata.create_all` alongside migrations.

```bash
# Apply pending migrations (inside Docker — uses db:5432)
docker compose run --rm app uv run alembic upgrade head

# Apply locally (outside Docker — uses localhost)
uv run alembic upgrade head

# This reads DATABASE_URL from: env var → .env → settings default
```

Migration files in `alembic/versions/` use format: `YYYYMMDD_HHmmss_<revhash>_<slug>.py` (chronologically sorted)

---

## Caching

A Redis read cache for single-record lookups (`GET /api/v1/records/{id}`).
Transparent fail-open — Redis down → DB fallback. `fakeredis` in tests (no Redis container in CI).

```text
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
```

**Configuration**:

- `REDIS_ENABLED=false` (opt-in; CI stays Redis-free)
- `REDIS_URL=redis://localhost:6379/0`
- TTL: 1 hour (single records are stable)

**Metrics**:

- `pipeline_cache_hits_total{operation="get"}` — successful cache hits
- `pipeline_cache_misses_total{operation="get"}` — cache misses (DB fetch)
- `pipeline_cache_errors_total{operation="get|set|invalidate"}` — errors logged as warnings

---

## 8-Phase Execution Roadmap

### Phase 1: Event Streaming (Weeks 1–2)

**Goal**: Build real-time event processor with Redpanda + Celery
**Deliverables**: Event topic, consumer group, exactly-once processing, partition-aware consumer
**Interview Q**: "Design real-time ETL for 1000+ events/sec" ([phase-1-events.md](.github/instructions/phase-1-events.md))
**Artifacts**: 8–10 commits, LinkedIn post, portfolio item

**Core Components**:

- **Event Producer** (`app/events.py`): Kafka singleton, fail-open publishing
- **Event Storage** (`app/storage/events.py`): ProcessedEvent CRUD for idempotency, DLQ routing, status tracking
- **Processor** (`services/processor/`): Standalone consumer with retry logic and JSON logging

**Checklist**:

- [ ] Set up Redpanda container + event producer
- [ ] Implement Celery consumer (retry logic, DLQ)
- [ ] Design partitioning by source_id
- [ ] Monitor consumer lag
- [ ] Test exactly-once semantics (idempotency via ProcessedEvent)

### Phase 2: Data Scraping (Weeks 3–4)

**Goal**: Build concurrent scraper with rate limiting
**Deliverables**: GraphQL endpoint, 3 scraper types (REST/HTML/browser), rate limiter
**Interview Q**: "Design scraper for 100K URLs without ban" ([phase-2-scrapers.md](.github/instructions/phase-2-scrapers.md))
**Artifacts**: 8–10 commits, LinkedIn post, portfolio item

- [ ] Implement async scraper (GraphQL + Playwright)
- [ ] Add exponential backoff retry
- [ ] Design semaphore-based rate limiting
- [ ] Validate output with Pydantic
- [ ] Test ban mitigation strategies

### Phase 3: Docker + CI/CD (Weeks 5–6)

**Goal**: Production-ready Docker image + GitHub Actions pipeline
**Deliverables**: Multi-stage Dockerfile, CI workflow (lint/test/build), ECR push
**Interview Q**: "Walk me through dev → prod pipeline" ([docker-ci-guide.md](.github/instructions/docker-ci-guide.md))
**Artifacts**: 8–10 commits, LinkedIn post, portfolio item

- [ ] Create multi-stage Dockerfile (build / runtime)
- [ ] Set up GitHub Actions: lint → test → build → push
- [ ] Add image scanning for vulnerabilities
- [ ] Implement health check endpoints
- [ ] Test full CI/CD cycle locally

### Phase 4: AI + Vector DB (Weeks 7–8)

**Goal**: Embeddings + semantic search over 100K documents
**Deliverables**: Embedding service, Qdrant client, LRU cache, similarity search API
**Interview Q**: "Design semantic search over 100K docs" ([phase-3-ai-qdrant.md](.github/instructions/phase-3-ai-qdrant.md))
**Artifacts**: 8–10 commits, LinkedIn post, portfolio item

- [ ] Integrate OpenAI embeddings API
- [ ] Spin up Qdrant vector database
- [ ] Implement LRU cache for embeddings
- [ ] Build similarity search endpoint
- [ ] Measure NDCG ranking metrics

### Phase 5: Testing Mastery (Weeks 9–10)

**Goal**: 100% test coverage with 10 pytest patterns + async mocking
**Deliverables**: Parametrized fixtures, Celery mocking, chaos tests, time travel
**Interview Q**: "How do you test code that calls external APIs?" ([phase-4-testing.md](.github/instructions/phase-4-testing.md))
**Artifacts**: 8–10 commits, LinkedIn post, portfolio item

- [ ] Implement 10 core pytest fixtures
- [ ] Mock external APIs + Celery tasks
- [ ] Add time travel testing (freezegun)
- [ ] Design chaos tests (network failures, timeouts)
- [ ] Achieve 100% code coverage

### Phase 6: Database Optimization (Weeks 11–12)

**Goal**: Master 40 SQL patterns + query optimization
**Deliverables**: Indexed queries <50ms p99, EXPLAIN ANALYZE walkthroughs, materialized views
**Interview Q**: "This query is slow (5s). Fix it." ([phase-5-database.md](.github/instructions/phase-5-database.md))
**Artifacts**: 8–10 commits, LinkedIn post, portfolio item

- [ ] Implement 40 SQL patterns (foundations to advanced)
- [ ] Analyze slow queries with EXPLAIN ANALYZE
- [ ] Add covering indices for key queries
- [ ] Build materialized views for complex joins
- [ ] Measure latency improvements

### Phase 7: Security (Weeks 13–14)

**Goal**: JWT auth, token rotation, rate limiting, input validation
**Deliverables**: Bearer token auth, refresh token flow, API key rotation, HMAC webhooks
**Interview Q**: "Design JWT auth for multi-service app" ([phase-6-security.md](.github/instructions/phase-6-security.md))
**Artifacts**: 8–10 commits, LinkedIn post, portfolio item

- [ ] Implement JWT + refresh token flow
- [ ] Add rate limiting on auth endpoints
- [ ] Integrate AWS Secrets Manager
- [ ] Design API key rotation strategy
- [ ] Implement input validation layer

### Phase 8: Infrastructure as Code (Weeks 15–16)

**Goal**: Terraform multi-env (dev/staging/prod) with GitOps deployment
**Deliverables**: Reusable Terraform modules, state locking, drift detection, Fargate deployment
**Interview Q**: "Design multi-env Terraform (dev/staging/prod)" ([phase-7-terraform.md](.github/instructions/phase-7-terraform.md))
**Artifacts**: 8–10 commits, LinkedIn post, portfolio item

- [ ] Create Terraform modules (VPC, RDS, ECS, ALB, Secrets)
- [ ] Set up S3 + DynamoDB state backend
- [ ] Implement GitHub Actions Terraform workflow
- [ ] Test rollback and drift detection
- [ ] Deploy full stack to AWS

---

## Success Checklist

**All 8 Phases:**

- [ ] 100+ total commits (12–15 per phase)
- [ ] 8 LinkedIn posts (280 chars, technical tone, metrics-driven)
- [ ] 8 portfolio items (GitHub link + interview prep per phase)
- [ ] 100% test coverage (all phases)
- [ ] Zero CVEs in dependencies (pip-audit clean)
- [ ] Interview Q + 2 follow-ups mastered per phase
- [ ] Production-ready infrastructure (Terraform)

**Final CV Narrative:**
> "Backend engineer specializing in event-driven architectures, async Python, and full-stack platform design. I've shipped multi-service systems with 10M+ daily events, optimized databases from 5s to 50ms queries, and automated infrastructure with Terraform across dev/staging/prod environments."

---

## Quick Reference

**Run all tests:**

```bash
uv run pytest tests/ -v
```

**Check code quality:**

```bash
uv run ruff check . && uv run ruff format .
```

**Start development server:**

```bash
uv run uvicorn app.main:app --reload
```

**Load test performance (Phase 1):**

```bash
./scripts/load_test.sh seed 10000
./scripts/load_test.sh k6
```

**View API docs:**
Open `http://localhost:8000/docs` after starting the app

---

## TODO / Next Steps

### Week 1 Milestones

- [x] **Milestone 1** — App runs, `/docs` loads, can create a record via Swagger UI
- [x] **Milestone 2** — All tests pass (`pytest tests/ -v`)
- [x] **Milestone 3** — Understand the `PATCH /process` endpoint; implement `DELETE /{id}`
- [x] **Milestone 4** — Confirm JSON logs appear on every request
- [x] **Milestone 5** — Run `test_performance.py -s`, establish baseline metrics

### Week 2 Exercises

- [x] **Cursor-based pagination** — opaque base64 cursors; `GET /api/v2/records/cursor`
- [x] **Duplicate detection** — `source + timestamp` unique constraint; idempotent upsert
- [x] **Rate limiting** — `slowapi` + custom limiters (`app/rate_limiting.py`)
- [x] **Retry logic** — httpx with exponential backoff (`app/fetch.py`)

### Week 3+ Database Optimizations

- [x] Run `EXPLAIN ANALYZE`; add covering index on `(source, id)`
- [x] Introduce `processed_at` column (nullable DateTime)
- [x] Add Alembic migrations (`alembic/versions/`)

### Phase 2+ Next Phases

Follow the phase guides in `.github/instructions/`:

1. **Next**: Start [Phase 1: Events](

.github/instructions/phase-1-events.md) with Redpanda + Celery
2. See [`.github/instructions/middle-tier-grind-tracking.md`](.github/instructions/middle-tier-grind-tracking.md) for weekly tracking
3. Reference [templates](docs/templates/) for LinkedIn posts + portfolio items

---

## Load Testing (Phase 1 Optional)

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

| File                                                               | Tool   | Purpose                                           |
| ------------------------------------------------------------------ | ------ | ------------------------------------------------- |
| [scripts/seed_data.py](scripts/seed_data.py)                       | httpx  | Seed N records via batch API                      |
| [scripts/load_test_pagination.js](scripts/load_test_pagination.js) | k6     | Two parallel scenarios, p50/p95/p99 summary table |
| [scripts/locustfile.py](scripts/locustfile.py)                     | Locust | `OffsetPaginationUser` + `CursorPaginationUser`   |
| [scripts/load_test.sh](scripts/load_test.sh)                       | bash   | Wrapper: seed / k6 / locust commands              |

---

## E2E Tests — External API Resilience

Validate `app/fetch.py` resilience patterns: retry with exponential backoff, timeout handling, graceful failure.

```bash
# Run only core tests (default — no external APIs)
uv run pytest tests/ -v

# Run E2E tests against live external API (jsonplaceholder)
uv run pytest tests/integration/records/test_e2e_fetch.py -v -m e2e
```

**Test Coverage**:

- Successful fetch (no retries)
- Retry with exponential backoff (1s, 2s, 4s delays)
- Exhaustion after max retries
- Timeout handling
- HTTP client lifecycle (create, reuse, close, idempotent cleanup)
- Concurrent fetches (asyncio.gather)

**File**: [tests/integration/records/test_e2e_fetch.py](tests/integration/records/test_e2e_fetch.py)

---

## Learn More

**Historical Deep Dives:**

- [docs/sync-vs-async.md](docs/sync-vs-async.md) — Why this project uses async
- [docs/testing-postgres.md](docs/testing-postgres.md) — Testing with real PostgreSQL
- [docs/architecture.md](docs/architecture.md) — System design decisions

**Phase-Specific Learning:**

- [`.github/instructions/`](.github/instructions/) — All 8 phase guides + tracking
- [`docs/templates/`](docs/templates/) — Commit + portfolio templates
- [`.github/copilot-instructions.md`](.github/copilot-instructions.md) — Project conventions

**External References:**

- [FastAPI Docs](https://fastapi.tiangolo.com/) — Official guide
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/) — ORM patterns
- [pytest Documentation](https://docs.pytest.org/) — Testing framework
- [PostgreSQL 17 Docs](https://www.postgresql.org/docs/current/) — Database
