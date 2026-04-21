# Plan: Data Zoo Platform — 16-Week Expansion Roadmap

## TL;DR

Expand `data-pipeline-async` from a single-service FastAPI CRUD app into a full-stack distributed systems learning platform ("Data Zoo"). The platform adds event streaming (Redpanda), document storage (MongoDB), vector search (Qdrant), AI gateway (Ollama + LangChain), a backend-friendly dashboard (HTMX), production IaC (Terraform/AWS), and comprehensive observability. Work proceeds in 8 phases (2 weeks each), monorepo-first, docs consolidated before any new service is added.

---

## Pre-Phase 0: Foundations (Before Any Coding)

### 0A: Docs Consolidation (1–2 days)

**Goal:** "Decrease descriptive and repetitive text spread across docs/" — stated user priority.

1. Audit `docs/` for duplicate coverage — identify which pillar file owns each concept
2. Create `docs/adr/` directory and 3 ADR stubs:
   - `docs/adr/001-kafka-vs-rabbitmq.md`
   - `docs/adr/002-qdrant-vs-pgvector.md`
   - `docs/adr/003-htmx-vs-react.md`
3. Ensure `docs/architecture.md` references the monorepo target structure (single source of truth for system design)
4. Update `learning_docs/ACTION_PLAN.md` Weeks 3–6 with the 8-phase milestones derived from this plan
5. All new docs: kebab-case filenames, MD040 fenced code blocks with language tag, no MD036 bold-as-heading

**Files:** `docs/architecture.md`, `docs/adr/` (new), `learning_docs/ACTION_PLAN.md`

---

### 0B: Monorepo Restructure (half-day)

**Goal:** Current `app/` = ingestor service. Add `services/` top-level directory to house new services.

**Decision:** Keep `app/` in-place as-is (no rename). New services go to `services/processor/`, `services/query_api/`, `services/ai_gateway/`, `services/dashboard/`. Rename is deferred until Phase 7 (cloud deploy makes it necessary).

**Steps:**

1. Create `services/` directory (empty, with `README.md`)
2. Update `docs/architecture.md` with monorepo layout diagram
3. No changes to `app/`, `docker-compose.yml`, or `pyproject.toml` yet

**Files:** `services/README.md` (new), `docs/architecture.md`

---

## Phase 1: EDA Foundation — Redpanda + Event Bus (Weeks 1–2)

**Goal:** First data crosses a service boundary. POST /records → Kafka topic → processor consumer prints/logs event. The "unlock" for everything else.

**Steps:**

1. Add Redpanda service to `docker-compose.yml` (Redpanda, not Zookeeper-dependent Kafka; exposes 9092 + 8082 admin UI)
2. Add `aiokafka>=0.11` to `pyproject.toml` dependencies
3. Create `app/events.py` — Kafka producer module modeled on `app/cache.py`:
   - `AIOKafkaProducer` singleton
   - `connect_producer()` / `disconnect_producer()` for lifespan wiring
   - `publish_record_created(record_id, payload)` coroutine
   - Fail-open: log error on KafkaError, don't crash the request
4. Wire `publish_record_created` into `app/routers/records.py` POST handler (after successful DB write)
5. Update `app/main.py` lifespan to connect/disconnect Kafka producer alongside Redis
6. Create `services/processor/main.py` — `AIOKafkaConsumer` loop, prints event to stdout *(depends on steps 1–3)*
7. Add `processor` service to `docker-compose.yml` (depends_on redpanda) *(depends on step 6)*

**Parallel with step 2:** Steps 1 and 2 are independent.
**Depends on step 3:** Steps 4 and 5 require `app/events.py` to exist.

**Files:**

- `docker-compose.yml` — add `redpanda`, `processor` services
- `pyproject.toml` — add `aiokafka`
- `app/events.py` — NEW
- `app/main.py` — lifespan hook update
- `app/routers/records.py` — wire publish call
- `services/processor/main.py` — NEW
- `services/processor/Dockerfile` — NEW

**Verification:**

1. `docker compose up --build` → all 6 services healthy
2. `curl -X POST /api/v1/records` → 201; `docker logs processor` → event JSON logged
3. Stop Redpanda: POST still returns 201 (fail-open confirmed)
4. `uv run pytest tests/ -v` → all pass (Kafka fail-open, no test changes needed)

**Advanced Python here:** `TypeVar` + `Generic` for typed `EventPayload[T]`; Observer pattern (event publish on record create)

---

## Phase 2: Scrapers + MongoDB — Data Ingestion Layer (Weeks 3–4)

**Goal:** Three scraping paradigms (httpx REST, BeautifulSoup HTML, Playwright browser) feed scraped data into MongoDB.

**Steps:**

1. `uv add motor playwright beautifulsoup4` → `pyproject.toml`
2. Add `mongodb:7` service to `docker-compose.yml` (port 27017)
3. Create `app/scrapers/` package — 3 scrapers:
   - `http_scraper.py` — httpx + public REST API (e.g., JSONPlaceholder)
   - `html_scraper.py` — BeautifulSoup (e.g., Hacker News front page)
   - `browser_scraper.py` — Playwright async, JS-rendered content
4. Create `app/storage/mongo.py` — Motor async client, `insert_scraped_doc()`, `find_by_source()` helpers
5. Create `app/routers/scraper.py` — `POST /api/v1/scrape/{source}` → scrape → MongoDB → Kafka event *(depends on Phase 1)*
6. Wire Motor connect/disconnect into `app/main.py` lifespan

**Files:**

- `pyproject.toml` — add `motor`, `playwright`, `beautifulsoup4`
- `docker-compose.yml` — add `mongodb` service
- `app/scrapers/__init__.py` — NEW
- `app/scrapers/http_scraper.py` — NEW
- `app/scrapers/html_scraper.py` — NEW
- `app/scrapers/browser_scraper.py` — NEW
- `app/storage/mongo.py` — NEW
- `app/routers/scraper.py` — NEW
- `app/main.py` — lifespan update (Motor connect/disconnect)

**Verification:**

1. `POST /api/v1/scrape/hn` → 200 + stored records
2. MongoDB shell: `db.scraped.find()` returns docs
3. Processor logs show scraper events
4. `uv run pytest tests/` → pass (scrapers behind new routes, fixtures unaffected)

**Advanced Python here:** `Protocol` for scraper interface; Bloom Filter for URL dedup; `__slots__` on scraper data class; `Factory` pattern (`ScraperFactory.create(source)`); Strategy pattern (pluggable backends)

---

## Phase 3: AI Gateway + Qdrant — Embeddings + Semantic Search (Weeks 5–6)

**Goal:** Scraped text embedded and stored in Qdrant, searchable by similarity.

**Steps:**

1. Add `qdrant-client[fastembed]>=1.9`, `sentence-transformers>=3.0` to ai_gateway service deps
2. Add `qdrant` service to `docker-compose.yml` (port 6333)
3. Create `services/ai_gateway/` service:
   - `embeddings.py` — lazy-loaded `all-MiniLM-L6-v2` singleton (LRU cache over embeddings)
   - `vector_store.py` — Qdrant async client, `upsert_collection()`, `search()`
   - `main.py` — FastAPI: `POST /embed`, `GET /search?q=...`
   - `Dockerfile`
4. Wire: processor consumer calls ai_gateway `/embed` → Qdrant upsert *(depends on Phase 1 processor)*
5. Finalize `docs/adr/002-qdrant-vs-pgvector.md`

**Files:**

- `docker-compose.yml` — add `qdrant`, `ai_gateway` services
- `services/ai_gateway/main.py` — NEW
- `services/ai_gateway/embeddings.py` — NEW
- `services/ai_gateway/vector_store.py` — NEW
- `services/ai_gateway/Dockerfile` — NEW
- `services/processor/main.py` — update to call ai_gateway `/embed`
- `docs/adr/002-qdrant-vs-pgvector.md` — finalize

**Verification:**

1. `POST /api/v1/scrape/hn` → full pipeline: scrape → MongoDB → Kafka → processor → embed → Qdrant
2. `GET /search?q=startups` → semantically ranked results
3. Qdrant dashboard (port 6333) shows collection with vectors

**Advanced Python here:** LRU Cache for embedding dedup; lazy singleton pattern for model loader

---

## Phase 4: Resilience Patterns (Weeks 7–8)

**Goal:** Circuit breaker, Dead Letter Queue, OpenTelemetry distributed tracing. System handles downstream failures gracefully.

**Steps:**

1. Add OTel deps to `pyproject.toml`: `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp`
2. Add `jaeger` (all-in-one) to `docker-compose.yml` (port 16686)
3. Create `app/core/circuit_breaker.py` — `@circuit_breaker(failure_threshold=5, recovery_timeout=30)` decorator; states: CLOSED → OPEN → HALF_OPEN
4. Apply circuit breaker to `app/events.py` publish and `app/storage/mongo.py` writes
5. Add DLQ: processor routes failed messages to `records.events.dlq` topic after 3 retries
6. Wire OTel into `app/main.py` and `services/processor/main.py` (auto-instrument FastAPI + manual consumer span)
7. Inject `trace_id` into structured log output in `app/core/logging.py`

**Files:**

- `pyproject.toml` — add OTel deps
- `docker-compose.yml` — add `jaeger`
- `app/core/circuit_breaker.py` — NEW
- `app/events.py` — apply circuit breaker
- `app/storage/mongo.py` — apply circuit breaker
- `services/processor/main.py` — DLQ routing + OTel span
- `app/main.py` — OTel init
- `app/core/logging.py` — inject trace_id

**Verification:**

1. Stop Qdrant → circuit opens → logs show `OPEN` state, no cascading failure
2. Jaeger UI → trace for POST /records shows spans: ingestor → processor
3. Force 3 bad messages → appear in `records.events.dlq` via `rpk topic consume`

**Advanced Python here:** `ContextVar` for trace ID propagation across async task boundaries; Saga pattern for distributed transaction (scrape → embed → store)

---

## Phase 5: Advanced SQL + CQRS Read Side (Weeks 9–10)

**Goal:** Materialized views, window functions, table partitioning, CTEs. CQRS: query_api as decoupled read service.

**Steps:**

1. Create `services/query_api/` FastAPI service (read-only SQLAlchemy, same PostgreSQL)
2. Write Alembic migration:
   - `records_hourly_stats` materialized view (count, avg, min, max per hour)
   - `records_archive` table partitioned by month (range partitioning)
3. Implement analytics endpoints in `services/query_api/routers/analytics.py`:
   - `GET /analytics/summary` — CTE-based multi-step aggregation
   - `GET /analytics/percentile` — `PERCENT_RANK()` window function
   - `GET /analytics/top-pipeline` — `RANK() OVER (PARTITION BY pipeline_id)`
4. CQRS: query_api subscribes to `records.events` Kafka topic → maintains own read-optimized projections *(depends on Phase 1)*
5. `REFRESH MATERIALIZED VIEW` background task (APScheduler or FastAPI `BackgroundTasks`)
6. Add `pgvector` extension for comparison alongside Qdrant; update `docs/adr/002-qdrant-vs-pgvector.md`

**Files:**

- `alembic/versions/` — new migration (materialized view + partitioned table)
- `services/query_api/main.py` — NEW
- `services/query_api/routers/analytics.py` — NEW
- `services/query_api/Dockerfile` — NEW
- `docker-compose.yml` — add `query_api` service

**Verification:**

1. `GET /analytics/summary` → correct CTE-computed aggregates
2. `EXPLAIN ANALYZE` on view query → Index Scan (not Sequential Scan)
3. `GET /analytics/percentile` → correct `PERCENT_RANK` values
4. Pause ingestor; query_api projection stays consistent (eventual consistency)

**Advanced Python here:** Min-heap for top-N analytics; consistent hashing for Kafka partition key selection; Repository pattern for query_api read model abstraction

---

## Phase 6: HTMX Dashboard (Weeks 11–12)

**Goal:** 3-page backend-rendered dashboard — data explorer, semantic search UI, live metrics via SSE. No JavaScript framework.

**Steps:**

1. Add `jinja2>=3.1`, `python-multipart` to dashboard service deps
2. Create `services/dashboard/` service:
   - `templates/` — `base.html`, `index.html`, `search.html`, `metrics.html`
   - `static/` — minimal CSS + vendored `htmx.min.js`
   - `routers/pages.py`, `routers/sse.py`
   - `main.py`, `Dockerfile`
3. Implement 3 pages:
   - **Records Explorer** (`/`) — HTMX infinite scroll via `hx-get` + `hx-trigger="revealed"`
   - **Semantic Search** (`/search`) — HTMX form → calls ai_gateway `/search` → renders partial *(depends on Phase 3)*
   - **Metrics View** (`/metrics`) — `<div hx-ext="sse" sse-connect="/sse/metrics">` streaming Prometheus counters *(depends on Phase 4)*
4. SSE endpoint in `routers/sse.py` — streams Prometheus counters or Kafka consumer group lag
5. Finalize `docs/adr/003-htmx-vs-react.md`

**Files:**

- `docker-compose.yml` — add `dashboard` service
- `services/dashboard/main.py` — NEW
- `services/dashboard/routers/pages.py` — NEW
- `services/dashboard/routers/sse.py` — NEW
- `services/dashboard/templates/*.html` — 4 NEW files
- `services/dashboard/static/` — CSS + htmx.min.js
- `services/dashboard/Dockerfile` — NEW

**Verification:**

1. `localhost:8003/` → paginated table, scroll triggers HTMX load
2. `/search?q=startup` → results rendered server-side, no JS framework
3. `/metrics/` → live SSE counter increments without page refresh

---

## Phase 7: IaC + Cloud Deployment (Weeks 13–14)

**Goal:** Single `terraform apply` deploys all services to AWS. ECR → ECS Fargate + RDS + ElastiCache + MSK.

**Steps:**

1. Create `infra/terraform/` directory structure:

   ```text
   infra/terraform/
   ├── main.tf
   ├── variables.tf
   ├── outputs.tf
   ├── modules/
   │   ├── network/     (VPC, subnets, security groups)
   │   ├── database/    (RDS PostgreSQL 17)
   │   ├── cache/       (ElastiCache Redis)
   │   ├── messaging/   (MSK Serverless — Kafka-compatible)
   │   └── compute/     (ECS Fargate task definitions per service)
   └── environments/
       ├── dev/
       └── prod/
   ```

2. Write ECS task definition for `ingestor` as reference pattern
3. Write RDS module (PostgreSQL 17, `multi_az = false` for dev, `true` for prod)
4. Write ECR repositories for all 5 service images
5. Create `.github/workflows/docker-build.yml` — push images to ECR on merge to main
6. Extend `infra/terraform/modules/compute/` with ECS Fargate for remaining 4 services
7. Create `docs/cloud-deployment.md` — why ECS Fargate over EKS for this project

**Decision:** ECS Fargate over EKS (simpler, lower cost, still production-grade; Kubernetes = separate dedicated project)

**Files:**

- `infra/terraform/` — 15+ NEW files
- `.github/workflows/docker-build.yml` — NEW
- `docs/cloud-deployment.md` — NEW

**Verification:**

1. `terraform plan` → no errors
2. `terraform apply environments/dev` → ingestor running on Fargate
3. `curl https://<alb-dns>/api/v1/records` → 200
4. `terraform destroy` → clean teardown

---

## Phase 8: Production Hardening (Weeks 15–16)

**Goal:** Backups, alerting, SLO dashboards, chaos testing. Monitored, maintainable, OWASP-compliant.

**Steps:**

1. Add `prometheus`, `grafana`, `alertmanager` to `docker-compose.yml`; create `infra/monitoring/prometheus.yml` scrape config
2. Create `infra/monitoring/grafana/slo-dashboard.json` — golden signals for all 5 services (latency, traffic, errors, saturation)
3. Alertmanager rules: P95 latency > 500ms, error rate > 1%, Kafka consumer lag > 1000
4. Create `infra/scripts/backup.sh` — pg_dump cron; document WAL-G → S3 two-tier strategy in `docs/pillar-2-database.md`
5. Create `infra/scripts/chaos.sh` — random service kill + `tc netem` network partition simulation
6. Rate limiting final audit — all public endpoints covered; update `docs/milestone-3-rate-limiting.md`
7. OWASP final pass — input validation, auth on all routes, no hardcoded secrets, security headers middleware

**Files:**

- `docker-compose.yml` — add prometheus, grafana, alertmanager
- `infra/monitoring/prometheus.yml` — NEW
- `infra/monitoring/grafana/slo-dashboard.json` — NEW
- `infra/scripts/backup.sh` — NEW
- `infra/scripts/chaos.sh` — NEW
- `docs/pillar-2-database.md` — backup strategy section

**Verification:**

1. Grafana: all 5 services golden signals visible
2. Kill `processor` → Alertmanager fires within 2 min
3. Restore from pg_dump → data intact
4. Chaos script → degradation graceful, system recovers

---

## Advanced Python / DSA / Patterns — Woven Into Phases

Not standalone phases — each implemented as the natural solution to a real problem:

| Concept | Phase | Location |
|---------|-------|----------|
| `TypeVar` + `Generic` | 1 | `events.py` typed `EventPayload[T]` |
| `Protocol` | 2 | Scraper interface `class Scraper(Protocol)` |
| `__slots__` | 2 | High-frequency scraper data class |
| `ContextVar` | 4 | Trace ID propagation across async tasks |
| Bloom Filter | 2 | URL dedup before scraping |
| LRU Cache | 3 | Embedding cache (avoid re-embedding same text) |
| Min-Heap | 5 | Top-N records in analytics query |
| Sliding Window | 1 | Already in `rate_limiting_advanced.py` |
| Consistent Hashing | 5 | Kafka partition key selection |
| Factory Pattern | 2 | `ScraperFactory.create(source)` |
| Strategy Pattern | 2 | Pluggable scraper backends |
| Observer Pattern | 1 | Event publish on record creation |
| Circuit Breaker | 4 | `app/core/circuit_breaker.py` |
| Repository Pattern | 5 | query_api read model abstraction |
| Saga Pattern | 4 | Distributed transaction: scrape → embed → store |

---

## File Map — What Changes When

| File | Phase | Change |
|------|-------|--------|
| `docker-compose.yml` | 1–8 | New service added each phase |
| `pyproject.toml` | 1–6 | New deps added per phase |
| `app/main.py` | 1, 2, 4 | Lifespan additions (Kafka, Mongo, OTel) |
| `app/events.py` | 1 | NEW — Kafka producer |
| `app/cache.py` | — | Reference pattern for `app/events.py` |
| `app/core/logging.py` | 4 | Inject trace_id |
| `app/core/circuit_breaker.py` | 4 | NEW |
| `app/routers/records.py` | 1 | Wire publish call |
| `app/scrapers/` | 2 | NEW — 4 files |
| `app/storage/mongo.py` | 2 | NEW |
| `app/routers/scraper.py` | 2 | NEW |
| `services/processor/` | 1 | NEW, updated in 2, 3, 4 |
| `services/ai_gateway/` | 3 | NEW — 4 files |
| `services/query_api/` | 5 | NEW — 3 files |
| `services/dashboard/` | 6 | NEW — 10+ files |
| `infra/terraform/` | 7 | NEW — 15+ files |
| `infra/monitoring/` | 8 | NEW — prometheus, grafana |
| `infra/scripts/backup.sh` | 8 | NEW |
| `infra/scripts/chaos.sh` | 8 | NEW |
| `docs/adr/` | 0, 3, 6, 7 | NEW ADR per key decision |
| `docs/architecture.md` | 0 | Monorepo layout diagram |
| `learning_docs/ACTION_PLAN.md` | 0 | Backfill Weeks 3–6 milestones |

---

## Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Message broker | Redpanda | No Zookeeper, Kafka-compatible API, simpler Docker local dev |
| Vector store | Qdrant (primary) | Self-hosted, purpose-built; pgvector added Phase 5 for contrast |
| Frontend | HTMX + Jinja2 | Backend-friendly; no JS SSR complexity; reinforces Python skills |
| Cloud compute | ECS Fargate | Lower ops burden vs EKS; still production-grade; Kubernetes = separate project |
| `app/` rename | Deferred to Phase 7 | Avoids breaking Docker paths mid-project |
| Local LLM | Ollama + sentence-transformers | Free, offline, teaches self-hosting; OpenAI SDK documented in pillar-6 as reference |

---

## Scope Excluded

- Kubernetes (EKS/GKE) — separate dedicated learning project
- Multi-cloud (GCP/Azure) — AWS is the target; others referenced in `docs/references.md`
- Production Alembic migration strategy — covered in docs; schema-creation-only for local dev
- Mobile/native frontend
- Full e2e test suite — integration tests per service are sufficient
