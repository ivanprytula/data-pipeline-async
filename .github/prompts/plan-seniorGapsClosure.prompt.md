# Plan: Gaps Closure — Pillars 1–6 (Revised Build Order)

## Status at a Glance

| Pillar | Done | Gaps |
|--------|------|------|
| P1 | gather, Semaphore, cursor, rate-limit | `StreamingResponse`, `TaskGroup` |
| P2 | ORM, Alembic, soft-delete, JSONB+GIN, pgvector | `SELECT FOR UPDATE`, RLS |
| P3 | Docker, CI/CD, K8s probes+securityContext, Terraform ECS module written | HPA, broken `develop.watch` targets, cloud not deployed |
| P4 | Prometheus, Grafana, Jaeger, Alertmanager config+rules exist | receiver is placeholder webhook, no Loki |
| P5 | JWT, RBAC, User model+migration, argon2-cffi+redis-py already in deps | `_session_store` is in-memory dict, no real register/login/logout |
| P6 | sentence-transformers, Qdrant, RAG ingest→inference bridge | no OpenAI SDK, no LLM generation, no streaming |

---

## Revised Build Order Summary

```
Phase 1 (2–3d)   Auth completeness (Redis sessions + user CRUD)   ← closes open "next planned" item
Phase 2 (3–4d)   LLM API + RAG generation + StreamingResponse     ← P6 Middle + P1 Middle gap
Phase 3 (1–2d)   TaskGroup + SELECT FOR UPDATE + wait_for         ← P1/P2 Senior interview differentiators
Phase 4 (0.5d)   HPA manifest                                     ← completes K8s story
Phase 5 (2–3d)   Docker Compose polish + ECS Fargate deploy       ← first real cloud deployment
Phase 6 (1–2d)   Alertmanager real receiver + Loki                ← completes observability story
Phase 7 (1–2d)   PostgreSQL RLS                                     ← Senior DB (LangGraph → separate plan)
```

---

## Phase 1 — Pillar 5: Auth Completeness (2–3 days)

### 1a. Redis Session Backend

Replace `_session_store: dict[str, dict]` in `services/ingestor/auth.py` with `redis.asyncio` operations. Both `redis>=5.2.0` and `fakeredis` are already in deps — nothing to add.

- Key pattern: `session:{token}` → Redis hash `{user_id, role, created_at}` with 24h TTL
- Initialize the async Redis client as a singleton in the `lifespan` hook in `services/ingestor/main.py`
- `create_session()` → `await redis.hset(...); await redis.expire(...)`
- `get_session()` → `await redis.hgetall(...)` returns `{}` if expired/missing
- `delete_session()` → `await redis.delete(...)`
- Tests swap real Redis with `fakeredis.aioredis.FakeRedis()`; use `dependency_overrides` or a module-level fixture

### 1b. Persisted User CRUD

Create new `services/ingestor/routers/auth.py` with four endpoints:

| Endpoint | Body | Returns | Notes |
|----------|------|---------|-------|
| `POST /auth/register` | `{username, email, password}` | `UserResponse` | `argon2.PasswordHasher().hash(password)` |
| `POST /auth/token` | OAuth2 form `{username, password}` | `{access_token, token_type}` | `ph.verify(hash, password)` → issue JWT |
| `GET /auth/me` | — | `UserResponse` | decode JWT sub claim → DB lookup |
| `POST /auth/logout` | — | 204 | delete session from Redis |

`User` model and Alembic migration already exist. Add `get_current_user` Dependency that resolves a `User` ORM from the JWT claim and protects write routes on records.

Tests: `test_register`, `test_login_returns_jwt`, `test_me_requires_auth`, `test_logout_invalidates_session`.

---

## Phase 2 — Pillar 6: LLM Integration + Pillar 1: StreamingResponse (3–4 days)

### 2a. OpenAI integration

Add `openai>=1.0.0` to `pyproject.toml`. Create two endpoints in `services/ingestor/routers/records.py`:

**Non-streaming**: `POST /api/v1/records/analyze`
- Fetch record from DB → call `vector_search.index_record_documents` for context
- Build augmented prompt → `openai.AsyncOpenAI().chat.completions.create(response_format=RecordClassification)` (Pydantic structured output)
- Log `prompt_tokens` as a Prometheus counter (directly clears the tiktoken/cost-awareness checkpoint)

**Streaming**: `POST /api/v1/records/analyze/stream` — returns `StreamingResponse(media_type="text/event-stream")`

```python
async def event_gen() -> AsyncGenerator[str, None]:
    async with client.stream("POST", ...) as response:
        async for chunk in response.aiter_text():
            yield f"data: {chunk}\n\n"
return StreamingResponse(event_gen(), media_type="text/event-stream")
```

This clears the `StreamingResponse` Pillar 1 Middle gap in the same commit.

Tests: mock `AsyncOpenAI` client; assert streaming response `content-type: text/event-stream`.

---

## Phase 3 — Pillar 1: TaskGroup + Pillar 2: SELECT FOR UPDATE (1–2 days)

### 3a. `asyncio.TaskGroup` refactor

In `services/ingestor/jobs.py`, find the gather-based fan-out and replace with:

```python
async with asyncio.TaskGroup() as tg:
    tasks = [tg.create_task(process(record)) for record in batch]
```

The key interview story documented in the function docstring: `TaskGroup` raises an `ExceptionGroup` on first child failure **and cancels siblings**; `gather(return_exceptions=True)` silently swallows all exceptions and returns them as values — a silent correctness bug in job processing.

### 3b. `asyncio.wait_for` + cancel cleanup

In `services/ingestor/scrapers/http_scraper.py`, wrap the HTTP call:

```python
try:
    result = await asyncio.wait_for(self._fetch(url), timeout=settings.scraper_timeout)
except asyncio.TimeoutError as e:
    raise ScraperTimeoutError(f"Timeout fetching {url}") from e  # __cause__ chaining
```

### 3c. `SELECT FOR UPDATE SKIP LOCKED`

Add `claim_pending_events(db, batch_size)` to `services/ingestor/crud.py`:

```python
stmt = (
    select(ProcessedEvent)
    .where(ProcessedEvent.status == "pending")
    .with_for_update(skip_locked=True)
    .limit(batch_size)
)
```

Update claimed rows to `status="processing"` in the same transaction. This prevents double-processing in multi-instance deployments — the job-queue isolation levels pattern.

### 3d. Isolation level demo

Add a `REPEATABLE READ` usage in the analytics rollup job:

```python
async with db.begin():
    await db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
    # ... rollup queries
```

Document MVCC reasoning: readers don't block writers; `REPEATABLE READ` prevents phantom reads during multi-query rollups.

---

## Phase 4 — Pillar 3: HPA (0.5 days)

Create `infra/kubernetes/manifests/ingestor/hpa.yaml`:

- `minReplicas: 2`, `maxReplicas: 10`
- CPU target: 60% (triggers scale-out before saturation)
- `scaleDown.stabilizationWindowSeconds: 300` (prevents flapping after traffic spike)
- Rolling update: verify `deployment.yaml` has `maxSurge: 1, maxUnavailable: 0`
- Note in K8s README: requires `metrics-server` — install via:
  `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml`

---

## Phase 5 — Pillar 3: Docker Compose Polish + Cloud Deployment (2–3 days)

### 5a. Fix `develop.watch` targets

Three services have `target: /app` instead of their correct subpath — hot-reload is broken:

| Service | Current target | Correct target |
|---------|---------------|---------------|
| processor | `/app` | `/app/services/processor` |
| webhook | `/app` | `/app/services/webhook` |
| dashboard | verify | `/app/services/dashboard` |

### 5b. Workflow shortcuts

Add a `Justfile` (or `Makefile`) with named recipes — avoids memorizing profile flags:

```
just up           # core: db, redis, redpanda, ingestor
just up-vector    # + qdrant, inference
just up-monitor   # + prometheus, grafana, alertmanager, loki
just up-all       # full stack
just logs svc     # docker compose logs -f <svc>
just migrate      # uv run alembic upgrade head
```

### 5c. ECS Fargate first cloud deployment

The Terraform module is complete (`infra/terraform/modules/compute/` with `ecs-fargate` launch type). Steps:

1. Create `infra/terraform/environments/dev/terraform.tfvars` from `.tfvars.example` — fill in `aws_region`, `availability_zones`, `acm_certificate_arn`, `image_tag`
2. `cd infra/terraform/environments/dev && terraform init -backend-config=backend.hcl && terraform plan`
3. Build and push image to ECR (CI workflow `docker-build.yml` already does this on main push)
4. `terraform apply` — provisions VPC, RDS, ECR, ECS cluster, ALB, Fargate service
5. Run migrations as a one-shot ECS task: `aws ecs run-task --task-definition data-zoo-ingestor-migrate ...`
6. Document the runbook in `docs/cloud-deployment.md` (file exists, update it)

### 5d. k3s → EKS path (option B)

- Local: `curl -sfL https://get.k3s.io | sh -` → apply existing K8s manifests → test HPA
- Cloud: change `compute_type = "eks"` in `infra/terraform/environments/dev/main.tf` — the compute module already models both ECS and EKS

**Decision confirmed**: ECS Fargate first — Terraform is already written and it's faster to validate. EKS adds ~15 minutes to apply time and more IAM complexity. Return to EKS once ECS is verified.

---

## Phase 6 — Pillar 4: Alertmanager Wire-up + Loki (1–2 days)

### 6a. Alertmanager receiver

Prometheus is already configured to send to `alertmanager:9093`. The alert rules exist. The only gap is the receiver sends to `http://localhost:5001/alert` — a placeholder.

**Decision confirmed — local `alert-sink`**: add a tiny `alert-sink` service to `docker-compose.yml` under the `monitoring` profile (10-line FastAPI that logs alert payloads to stdout — visible in `docker compose logs`). No external dependency required.

To test manually: send a high-latency request burst to trigger `HighP95Latency`, watch Alertmanager UI at `:9093`.

### 6b. Loki + Promtail

**Why Loki over ELK**: single binary, no JVM, native Docker log scraping via Promtail, first-class Grafana datasource. ELK requires Elasticsearch + Logstash + Kibana — 3× the ops surface.

Add to `docker-compose.yml` under `monitoring` profile:

```yaml
loki:
  image: grafana/loki:2.9.0
  ports: ["3100:3100"]
  command: -config.file=/etc/loki/local-config.yaml

promtail:
  image: grafana/promtail:2.9.0
  volumes:
    - /var/lib/docker/containers:/var/lib/docker/containers:ro
    - /var/run/docker.sock:/var/run/docker.sock
    - ./infra/monitoring/promtail.yml:/etc/promtail/config.yml:ro
```

Create `infra/monitoring/promtail.yml` with a pipeline stage that parses the JSON logs and extracts `level`, `cid`, `event` as labels.

Add Loki as a provisioned datasource in `infra/monitoring/grafana/provisioning/datasources/`. In Grafana: filter `{container="data-pipeline-ingestor"} |= "record_created"` — instantly correlatable with traces via the `cid` field.

### 6c. Alert rules expansion

`alert.rules.yml` currently only covers `job="ingestor"`. Add:

- `HighErrorRate` for `analytics`, `webhook`, `inference`
- `BackgroundJobQueueDepth > 50` using the existing `background_jobs_in_queue` Prometheus gauge from `metrics.py`

---

## Phase 7 — Pillar 2: RLS (1–2 days) + LangGraph deferred

> **Decision confirmed**: LangGraph (P6 Senior) will be planned in a separate document once Phases 1–6 are complete. Phase 7 here covers only PostgreSQL RLS.

### PostgreSQL RLS (P2 Senior)

Alembic migration:

```sql
ALTER TABLE records ADD COLUMN tenant_id INTEGER;
ALTER TABLE records ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON records
  USING (tenant_id IS NULL OR tenant_id = current_setting('app.tenant_id', true)::int);
CREATE INDEX ix_records_tenant_id ON records (tenant_id) WHERE tenant_id IS NOT NULL;
```

FastAPI middleware: extract `X-Tenant-ID` header → `SET LOCAL app.tenant_id = :tid` at session start.

Test that proves isolation: create two records with `tenant_id=1` and `tenant_id=2`, verify that a session scoped to tenant 1 cannot read tenant 2's records.

---

## Files to Modify / Create

| File | Action |
|------|--------|
| `services/ingestor/auth.py` | Replace `_session_store` dict with `redis.asyncio` |
| `services/ingestor/routers/auth.py` | NEW — register, token, me, logout |
| `services/ingestor/crud.py` | Add `claim_pending_events` (SELECT FOR UPDATE SKIP LOCKED) |
| `services/ingestor/jobs.py` | TaskGroup refactor |
| `services/ingestor/scrapers/http_scraper.py` | `asyncio.wait_for` + cancel cleanup |
| `services/ingestor/routers/records.py` | Add `/analyze` and `/analyze/stream` |
| `infra/kubernetes/manifests/ingestor/hpa.yaml` | NEW |
| `docker-compose.yml` | Fix `develop.watch` targets, add Loki + Promtail |
| `infra/monitoring/promtail.yml` | NEW |
| `infra/monitoring/rules/alert.rules.yml` | Add multi-service rules |
| `infra/monitoring/alertmanager.yml` | Replace placeholder receiver |
| `alembic/versions/...` | NEW — `tenant_id` migration + RLS |

---

## Verification Checkpoints

| After Phase | Verification |
|-------------|-------------|
| 1 | `uv run pytest services/ingestor/tests/ -k auth -v` → all auth tests green |
| 2 | mock `AsyncOpenAI`; streaming test checks `content-type: text/event-stream` |
| 3 | `uv run python scripts/ci/check_service_boundaries.py` exits 0 |
| 4 | `kubectl get hpa -n data-zoo` shows min/max/current replicas |
| 5 | `terraform plan` shows 0 changes after initial apply; ECS task running |
| 6 | `docker compose --profile monitoring up` → Grafana shows Loki logs, Alertmanager UI at :9093 |
| 7 | RLS test proves cross-tenant isolation |

---

## Confirmed Decisions

1. **Cloud target** — ECS Fargate first (Terraform already written), then EKS via `compute_type = "eks"` switch after ECS is verified.
2. **Alertmanager receiver** — Local `alert-sink` dev container (zero external dependency); Slack integration deferred.
3. **LangGraph scope** — Deferred to a separate `plan-langgraphAgent.prompt.md` once Phases 1–6 are complete.
