# Architecture Overview

> High-level system design, component interactions, and implementation details by phase.
>
> For detailed design decisions with rationale, see **[Design Decisions](design/decisions.md)**.

---

## Start Here: Architecture Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│                         NGINX (HTTPS)                           │
└────────────────┬────────────────────────────────┬────────────────┘
                 │                                │
         ┌───────▼─────────┐         ┌────────────▼────────┐
         │ REST API        │         │ Metrics Scraper    │
         │ (FastAPI)       │         │ (Prometheus)       │
         └───────┬─────────┘         └────────────────────┘
                 │
         ┌───────▼──────────────────────────────┐
         │  Request Middleware                  │
          │  (Auth, Security Headers, Logging, Correlation IDs)    │
         └───────┬──────────────────────────────┘
                 │
    ┌────────────┼────────────┬────────────────┐
    │            │            │                │
┌───▼────┐  ┌───▼────┐  ┌───▼────┐  ┌──────▼──────┐
│ Routers│  │ CRUD   │  │ Schemas│  │  Background │\n│        │  │ Layer  │  │ (Pydantic) │  │  Workers    │
└───┬────┘  └───┬────┘  └────────┘  └─────────────┘\n    │       │\n    └───┬────┬───┘\n        │    │\n  ┌─────▼────┴───┐\n  │  SQLAlchemy  │\n  │  ORM (Async) │\n  └─────┬────────┘\n        │\n   ┌────▼────────┐\n   │ PostgreSQL  │\n   │ (asyncpg)   │\n   └─────────────┘\n\n┌──────────────────────────────┐\n│ Cache (Redis)                │\n│ - Session store              │\n│ - Query result caching       │\n└──────────────────────────────┘\n\n┌──────────────────────────────┐\n│ Message Streaming (Kafka)    │\n│ - Event ingestion stream     │\n│ - Event fanout               │\n└──────────────────────────────┘\n
```

---

## Phase-by-Phase Implementation

### Phase 1 & 2: Core API + Data Ingestion ✅ Done

| Component       | Technology                             | Purpose                                       |
| --------------- | -------------------------------------- | --------------------------------------------- |
| REST API        | FastAPI                                | HTTP endpoints for record ingestion, querying |
| Data Validation | Pydantic v2                            | Request/response schema validation            |
| Database        | PostgreSQL 17 + SQLAlchemy 2.0 (async) | Persistent storage of records                 |
| Migrations      | Alembic                                | Schema versioning                             |
| Event Streaming | Redpanda (Kafka)                       | High-throughput event ingestion               |

**Example flow**: Client POSTs record → FastAPI router → CRUD layer → SQLAlchemy ORM → PostgreSQL

### Phase 3 & 4: Resilience + Caching ✅ Done

| Component               | Technology                        | Purpose                          |
| ----------------------- | --------------------------------- | -------------------------------- |
| Caching                 | Redis                             | Session store, query caching     |
| Circuit Breaker         | Custom implementation             | Prevent cascading failures       |
| Dead Letter Queue (DLQ) | Kafka topic                       | Capture failed events for replay |
| Retry Logic             | APScheduler + exponential backoff | Graceful error recovery          |

**Example flow**: Request → Cache (hit) → Return / (miss) → DB → Cache result → Return

### Phase 5: Background Processing + Analytics ✅ Active

| Component          | Technology                              | Purpose                                               |
| ------------------ | --------------------------------------- | ----------------------------------------------------- |
| Background Workers | In-process queue (BackgroundWorkerPool) | Async batch processing                                |
| Job Scheduling     | APScheduler                             | Recurring tasks (daily rollups, cleanup)              |
| Metrics            | Prometheus                              | Performance monitoring (job duration, throughput)     |
| Tracing            | OpenTelemetry + Jaeger                  | Distributed request tracing                           |
| Error Tracking     | Sentry SDK                              | Exception aggregation, release-level error visibility |

**Example flow**: Client POST batch → API returns 202 (accepted) → Worker pool processes → Metrics updated → Client polls status

### Security/Auth/RBAC Baseline (Pillar 6) ✅ Implemented

| Component         | Technology                    | Purpose                                                                    |
| ----------------- | ----------------------------- | -------------------------------------------------------------------------- |
| Docs Auth         | HTTP Basic                    | Protect `/docs`, `/redoc`, `/openapi.json` when enabled                    |
| v1 API Auth       | Bearer token + session cookie | Stateful and simple token auth learning path                               |
| v2 API Auth       | JWT (HS256)                   | Stateless auth with role claims                                            |
| RBAC              | Session/JWT role guards       | Enforce `viewer`/`writer`/`admin` per endpoint                             |
| Security Headers  | HTTP middleware               | Browser hardening (`nosniff`, `DENY`, referrer policy, permissions policy) |
| Secret Guardrails | Startup validation            | Fail fast in production-like envs with weak default secrets                |
| Security CI       | `pip-audit`, Trivy            | Dependency and container vulnerability scanning                            |

Implemented protected route examples:

- `PATCH /api/v1/records/{record_id}/secure/archive` (writer/admin)
- `DELETE /api/v1/records/{record_id}/secure/delete` (admin only)
- `POST /api/v2/records/jwt` (writer/admin via JWT claim)

### Admin UI and User Workflows Baseline (Pillar 7) ✅ Implemented

| Component                  | Technology                   | Purpose                                          |
| -------------------------- | ---------------------------- | ------------------------------------------------ |
| Dashboard Admin Page       | HTMX + Jinja2                | Operational control surface at `/admin`          |
| Worker Health Panel        | HTMX partial + ingestor API  | Check worker-pool state without CLI              |
| Task Lookup Workflow       | HTMX partial + ingestor API  | Inspect one task by ID                           |
| Manual Rerun Workflow      | HTMX form + batch ingest API | Submit operational reruns from UI                |
| Session Bootstrap Workflow | HTMX form + auth login API   | Create role-aware session for secure flow checks |
| Integration Tests          | pytest + httpx               | Verify admin page and all partial workflows      |

Implemented admin workflow endpoints (dashboard):

- `GET /admin`
- `GET /partials/admin/workers/health`
- `GET /partials/admin/tasks`
- `POST /partials/admin/rerun`
- `POST /partials/admin/session`

### Phase 7: Cloud Deployment ✅ Done

| Component              | Technology               | Purpose                       |
| ---------------------- | ------------------------ | ----------------------------- |
| Containerization       | Docker                   | Application packaging         |
| Orchestration          | Kubernetes / AWS Fargate | Container management at scale |
| Infrastructure-as-Code | Terraform                | AWS resource provisioning     |
| Secrets Management     | AWS Secrets Manager      | Secure credential storage     |

### Phase 8: Production Hardening ⏹️ Queued

| Component         | Technology                            | Purpose                                  |
| ----------------- | ------------------------------------- | ---------------------------------------- |
| Backup & Recovery | pg_dump + S3                          | Data durability                          |
| Chaos Testing     | network partitions, latency injection | Resilience validation                    |
| Observability     | Prometheus + Grafana + Sentry         | Production monitoring + exception triage |
| Security Scanning | Trivy + Snyk                          | Vulnerability detection                  |

---

## Service Boundary Extraction Plan (5 Services)

Goal: move from shared-data assumptions to independent deployable services with explicit boundaries.

### Target Service Map

| Service      | Primary Responsibility                                          | Owned Data Store                     | Exposed Interface                        |
| ------------ | --------------------------------------------------------------- | ------------------------------------ | ---------------------------------------- |
| `ingestor`   | Ingestion API, write path, record validation                    | `ingestor_db`                        | REST first, events out                   |
| `processor`  | Async enrichment, retries, DLQ handling, workflow orchestration | `processor_db`                       | Events in/out, optional gRPC for control |
| `query_api`  | Read API, analytics/query projections                           | `query_db` (read model)              | REST first, optional gRPC read API       |
| `ai_gateway` | Embeddings, vector indexing/search integration                  | `ai_db` (metadata) + vector store    | REST first, optional gRPC                |
| `dashboard`  | Admin UI and operational workflows                              | `dashboard_db` (UI/session metadata) | REST to gateway/backend-for-frontend     |

### DB-Per-Service Rule

Each service owns one database/schema and is the only writer for it.

Cross-service table reads are forbidden. Data sharing is allowed only through APIs or events.

### Communication Progression

```text

Phase A (simple)
Dashboard -> API Gateway -> REST -> Services
Services -> Events (optional minimal)

Phase B (scale)
Gateway -> REST + selective gRPC for hot paths
Services <-> Event bus (Kafka/Redpanda), outbox/inbox

Phase C (high-load distributed)
CQRS projections + event-driven choreography + bounded gRPC

```

### Concrete Contracts by Interaction Type

1. REST (start here)
   - Use for all service-to-service calls initially.
   - Add strict timeouts, retry budgets, and circuit breakers.
   - Version endpoints (`/v1`, `/v2`) and keep backward compatibility windows.
2. gRPC (add for high-throughput internal calls)
   - Use for low-latency internal APIs where payload size and call volume are high.
   - Keep REST edge-facing for UI/external clients.
   - Introduce protobuf schemas and compatibility checks in CI.
3. Events (add for decoupled workflows)
   - Use for async processing and integration boundaries.
   - Start with topics:
      - `records.created.v1`
      - `records.enrichment.requested.v1`
      - `records.enrichment.completed.v1`
      - `records.indexing.requested.v1`
      - `records.indexing.completed.v1`
   - Enforce outbox/inbox + idempotency keys before critical fanout.

### API Gateway and Service Discovery

Gateway responsibilities:

- Authentication and authorization (JWT/session validation)
- Request routing and coarse rate limiting
- Unified error mapping and correlation IDs
- No domain business logic

Service discovery rollout:

- Start: static internal DNS/service names from orchestrator.
- Scale: health-aware discovery/registry with per-service load balancing.

### Extraction Sequence (Implementation Ready)

1. Baseline boundaries (Week 1)
   - Freeze cross-service imports.
   - Define ownership matrix and interface contracts per service.
   - Add CI guard: fail on forbidden imports between service packages.
2. Data split (Week 2-3)
   - Create `ingestor_db`, `processor_db`, `query_db`, `ai_db`, `dashboard_db`.
   - Move write models to service-owned stores.
   - Keep legacy reads behind adapters during transition only.
3. Read model isolation (Week 3-4)
   - `query_api` consumes events and builds its own projection tables.
   - Remove direct dependency on ingestion write tables.
4. Async workflow isolation (Week 4-5)
   - Move enrichment/indexing orchestration fully into `processor` events.
   - Add DLQ replay runbook and idempotent consumers.
5. Gateway consolidation (Week 5-6)
   - Route dashboard calls through gateway/BFF endpoints.
   - Standardize auth propagation and request tracing.
6. High-load optimization phase (after stabilization)
   - Promote hot internal REST calls to gRPC.
   - Add per-service autoscaling signals (p95 latency, queue lag, CPU/memory).
   - Introduce bulkheads and adaptive retry limits.

### Non-Negotiable Guardrails

- No shared database writes across services.
- No synchronous call chains deeper than 2 hops for critical paths.
- Every external call must define timeout, retry policy, and fallback behavior.
- Every emitted event must include idempotency key, schema version, and correlation ID.

### Done Criteria

- Each service can run, deploy, and rollback independently.
- Removing one service DB does not corrupt another service's correctness domain.
- Query surfaces (`query_api`, `dashboard`) rely only on published APIs/events, not foreign tables.
- SLOs are defined and measured per service (latency, error rate, queue lag, freshness).

---

## Key Design Patterns

## Local Runtime Modes

Use the same codebase in two local runtime modes depending on the task.

| Mode | Entry Point | Best For |
| --- | --- | --- |
| Docker Compose (resource overlays) | `bash scripts/ops/02-compose-profile.sh dev up -d` | Daily API/backend iteration |
| Docker Compose (optional stacks) | `docker compose --profile monitoring up -d`, `docker compose --profile vector up -d`, `docker compose --profile worker up -d` | Enabling only needed subsystems |
| k3d (local Kubernetes) | `bash scripts/setup/03-bootstrap-k3d.sh` | Infra validation and K8s manifests rehearsal |

Guardrails:

- Service-boundary direction is enforced in CI via `scripts/ci/check_service_boundaries.py`.
- Shared code is limited to `libs.platform` and `libs.contracts`; reverse imports into services are forbidden.

### Dependency Injection (FastAPI)

All external dependencies (DB session, config, services) are injected via `Annotated[T, Depends(...)]`:

```python
type DbDep = Annotated[AsyncSession, Depends(get_db)]
type ConfigDep = Annotated[Settings, Depends(get_settings)]

@app.get("/records/{id}")
async def read_record(record_id: int, db: DbDep, config: ConfigDep):
    return await crud.get_record(db, record_id)
```

**Why?** Enables testing (easy to mock), loose coupling, and Pythonic style.

### Async Throughout

All I/O is async (`await db.execute()`, `await redis.get()`, `await http_client.get()`):

```python
async def get_record(db: AsyncSession, record_id: int) -> Record | None:
    result = await db.execute(select(Record).where(Record.id == record_id))
    return result.scalar_one_or_none()
```

**Why?** Efficient concurrency: 1000+ concurrent requests with a single Python process.

### Layered Architecture

```text
Routes (HTTP concerns)
  ↓
CRUD (Database concerns)
  ↓
Models (Schema/validation)
  ↓
Database (Connection, transactions)
```

Each layer has one responsibility, making testing and refactoring straightforward.

---

## Database Schema

### Current Tables

```sql
-- records: core data records ingested via API
CREATE TABLE records (
    id SERIAL PRIMARY KEY,
    source VARCHAR NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_records_source ON records(source);
CREATE INDEX idx_records_created_at ON records(created_at);

-- pipeline_jobs: job execution history (APScheduler)
CREATE TABLE pipeline_jobs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status VARCHAR,
    result TEXT,
    error TEXT
);

-- background_tasks: background job tracking (WorkerPool)
CREATE TABLE background_tasks (
    task_id UUID PRIMARY KEY,
    status VARCHAR,
    submitted_at TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    result JSONB,
    error TEXT
);

-- users: auth and RBAC identity table (baseline)
CREATE TABLE users (
   id SERIAL PRIMARY KEY,
   username VARCHAR(64) UNIQUE NOT NULL,
   email VARCHAR(255) UNIQUE NOT NULL,
   password_hash VARCHAR(255) NOT NULL,
   role VARCHAR(32) NOT NULL DEFAULT 'viewer',
   is_active BOOLEAN NOT NULL DEFAULT TRUE,
   created_at TIMESTAMP NOT NULL,
   updated_at TIMESTAMP,
   deleted_at TIMESTAMP
);
```

See [docs/design/architecture.md](design/architecture.md) for full schema details.

---

## Request Flow (Example: Create Record)

```text
1. Client sends POST /api/v1/records with JSON body
   ↓
2. nginx (reverse proxy) receives, forwards to FastAPI app
   ↓
3. Request middleware:
   - Extract/generate correlation ID
   - Log request_start with method, path, user agent
   ↓
4. FastAPI router (ingestor/routers/records.py):
   - Validate request via Pydantic schema
   - Check authorization (if auth enabled)
   ↓
5. CRUD layer (ingestor/crud.py):
   - Build SQLAlchemy ORM object
   - Execute INSERT via async DB session
   ↓
6. SQLAlchemy → asyncpg dialect:
   - Convert ORM to SQL
   - Execute via PostgreSQL async connection
   ↓
7. PostgreSQL:
   - Validate constraints
   - INSERT row
   - Return inserted row
   ↓
8. Response middleware:
   - Log request_end with status_code, duration_ms
   - Add correlation ID to response headers
   ↓
9. Return 201 Created + JSON response
   ↓
10. nginx HTTPS termination
   ↓
11. Client receives response
```

---

## Request Flow (Example: Secured Archive with RBAC)

```text
1. Client logs in: POST /api/v1/records/auth/login?user_id=alice&role=writer
   ↓
2. Client calls PATCH /api/v1/records/{id}/secure/archive with session cookie
   ↓
3. Request middleware runs
   - correlation/logging context
   - security headers attached on response
   ↓
4. Session dependency validates session_id
   ↓
5. RBAC guard checks role ∈ {writer, admin}
   ├─ fail → 403 Insufficient role permissions
   └─ pass → continue
   ↓
6. Route handler performs soft-delete (archive)
   ↓
7. Response returns with security headers
```

---

## Request Flow (Example: Manual Rerun from Admin UI)

```text
1. Operator opens GET /admin
   ↓
2. Submits Manual Rerun form (source + value)
   ↓
3. Dashboard route POST /partials/admin/rerun validates input
   ↓
4. Dashboard calls ingestor POST /api/v1/background/ingest/batch
   ↓
5. Background worker pool queues task and returns task_id
   ↓
6. Dashboard renders HTMX result fragment with task status
   ↓
7. Operator can query task via GET /partials/admin/tasks?task_id=...
```

---

## Metrics & Observability

### Prometheus Metrics

```text
http_requests_total{method="POST", endpoint="/api/v1/records", status="201"}
http_request_duration_seconds{quantile="0.95"} 0.045
pipeline_records_ingested_total 15234
background_jobs_submitted_total 450
background_jobs_active 3
```

### Distributed Traces

Every request generates a trace:

```text
POST /api/v1/records
├─ Request middleware (0.1ms)
├─ Route handler (0.5ms)
│  ├─ Pydantic validation (0.1ms)
│  └─ CRUD create (0.3ms)
│     └─ SQLAlchemy ORM (0.2ms)
│        └─ PostgreSQL INSERT (0.1ms)
├─ Response middleware (0.1ms)
└─ Total: 0.8ms
```

### Logs

```json
{
  "timestamp": "2024-04-22T12:00:00.123Z",
  "level": "INFO",
  "event": "request_end",
  "correlation_id": "abc-123-def",
  "method": "POST",
  "path": "/api/v1/records",
  "status_code": 201,
  "duration_ms": 15,
  "user_id": "user_123"
}
```

---

## Configuration Management

All configuration is environment-driven (12-factor app):

```python
# ingestor/config.py
class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://..."
    log_level: str = "INFO"
    redis_url: str = "redis://localhost:6379"
    background_workers_enabled: bool = True
    # ... more
```

**Sources (in order of precedence)**:

1. Environment variables
2. `.env` file (local dev only)
3. Defaults in code

---

## Testing Architecture

### Unit Tests (Fast, In-Memory)

```python
# Uses aiosqlite in-memory SQLite (no DB server needed)
@pytest.fixture
async def test_db():
    async with create_async_engine("sqlite+aiosqlite:///:memory:") as engine:
        yield AsyncSession(engine)

def test_create_record(test_db):
    record = await crud.create_record(test_db, data)
    assert record.id is not None
```

### Integration Tests (PostgreSQL)

```python
# Uses real PostgreSQL (started by docker compose)
@pytest.fixture
async def db_with_postgres(postgres_url):
    async with create_async_engine(postgres_url) as engine:
        yield AsyncSession(engine)
```

Why two layers?

- Unit tests: Fast feedback (<1 second), run in CI without external deps
- Integration tests: Realistic environment, catch SQL-specific issues

---

## Deployment Target

### Local Development

```sh
docker compose up --build
```

Services on localhost with HTTP/2 via nginx.

### Cloud (AWS Fargate)

```sh
terraform apply -var-file=prod.tfvars
```

Auto-scaling ECS tasks behind ALB, RDS PostgreSQL, ElastiCache Redis.

---

## Performance Characteristics

| Operation                      | Typical Duration | Limit                     |
| ------------------------------ | ---------------- | ------------------------- |
| Create record                  | 5–15ms           | 100+ req/sec per instance |
| Query records (no cache)       | 20–50ms          | 1000 queries in parallel  |
| Query records (cached)         | 2–5ms            | 10000+ req/sec            |
| Background batch (100 records) | 500–1000ms       | Queue depth unlimited     |

See **[docs/progress/phase-5-advanced-sql-cqrs.md](../progress/phase-5-advanced-sql-cqrs.md)** for detailed benchmarks.

---

## Next Steps

- **Understand design decisions**: [Design Decisions](design/decisions.md)
- **Learn test and CI command workflows**: [Dev Commands](dev/commands.md)
- **Deploy to cloud**: [Cloud Deployment](cloud-deployment.md)
