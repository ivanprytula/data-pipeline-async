## Plan: Phase 10 — Service Hardening

Follows Phase 9 (Dockerfiles v3). All services are now containerized with uv workspaces, multi-stage
builds, non-root users, and `uv.lock`-based dependency management. Phase 10 closes the remaining gaps
in observability, operational readiness, and cross-service contracts.

---

### Current State Audit

| Service | `/health` | `/readyz` | Structured JSON logging | Graceful shutdown |
|---|---|---|---|---|
| `ingestor` | ✅ | ✅ (DB ping) | ✅ `python-json-logger` | ✅ lifespan |
| `ai_gateway` | ✅ | ❌ missing | ❌ stdlib `logging` only | ✅ lifespan |
| `query_api` | ✅ | ✅ (DB ping) | ❌ stdlib `logging` only | ❌ no lifespan |
| `dashboard` | ✅ | ✅ (shallow) | ❌ stdlib `logging` only | ❌ no lifespan |
| `processor` | ❌ no HTTP (script) | ❌ no HTTP | ❌ stdlib `logging` only | ✅ SIGTERM via asyncio |

---

### Critical Findings

**Bug 1 — `ai_gateway` has no `/readyz`**
`/health` returns a static `{"status": "ok"}`. No check that the vector store (Qdrant) is reachable.
K8s readiness probe + docker-compose `depends_on` condition: service_healthy cannot distinguish
"started" from "ready to serve traffic".

**Bug 2 — `query_api` has no `lifespan` context manager**
DB connection pool is created at module load, never explicitly torn down. Leads to connection leaks
on container restart and suppresses clean shutdown in docker-compose.

**Bug 3 — `dashboard` `/readyz` is shallow**
Returns `{"status": "ready"}` unconditionally. Does not verify `ingestor` upstream reachability.
Dashboard renders blank pages when ingestor is down; a real readiness check would let the
orchestrator route traffic away from it.

**Bug 4 — `processor` is a bare asyncio script**
Docker `HEALTHCHECK` runs `python -c "import sys; sys.exit(0)"` — always passes regardless
of Kafka consumer state. Redpanda outages and consumer crashes are invisible to the orchestrator.
No HTTP server means no health endpoints, no restart trigger on silent consumer failure, and no
extension point for future admin or DLQ requeue functionality.

**Gap 5 — Inconsistent structured logging across services**
`ingestor` uses `python-json-logger` with correlation IDs. All other services use stdlib
`logging.basicConfig` with plain text format. Makes log aggregation (Loki/ELK) unreliable:
filters on `correlation_id`, `service`, `level` fields only work for ingestor logs.

---

### Architecture Decisions

#### Readiness vs Liveness

| Probe | Purpose | Failure action |
|---|---|---|
| `/health` (liveness) | Is the process alive? | Kill + restart container |
| `/readyz` (readiness) | Can it serve traffic? | Remove from load balancer, do NOT restart |

**Rule:** Liveness must never depend on upstream services. Readiness should check one critical
upstream per service (DB for data services, vector store for ai_gateway, ingestor for dashboard).
Never check non-critical upstreams in readiness — a caching service being down should not mark
the service unready.

#### Processor Architecture: Script → FastAPI Service

Current state: `services/processor/main.py` is a pure asyncio script — entry point is
`asyncio.run(consume())`. No HTTP server. No health endpoints.

Target state: minimal FastAPI app, consistent with all other services. The `consume()` coroutine
becomes an `asyncio.Task` started in the lifespan context manager and cancelled on shutdown.

```
┌─────────────────────────────────────────┐
│  uvicorn (port 8002)                    │
│  ├─ FastAPI app                         │
│  │   ├─ GET /health  (liveness)         │
│  │   └─ GET /readyz  (readiness)        │
│  └─ lifespan                            │
│      ├─ startup: asyncio.create_task(   │
│      │    consume(state)                │
│      │  )                               │
│      └─ shutdown: task.cancel() + await │
└─────────────────────────────────────────┘
```

Why FastAPI over Prometheus `start_http_server()`:

- Consistent with all other services — same observability, same deployment pattern
- `asyncio.Task` runs in the same event loop as uvicorn — no extra thread, no thread-safety issues
- `/readyz` can introspect task state (`task.done()`, `task.cancelled()`) — Prometheus HTTP server
  cannot report consumer liveness
- Natural extension point for future admin endpoints and manual DLQ requeue
- No new root dependency: `fastapi` + `uvicorn` already in the uv workspace

Consumer state tracking (in-memory, sufficient for single-instance worker):

```python
@dataclass
class ConsumerState:
    started: bool = False
    messages_consumed: int = 0
    messages_failed: int = 0
    last_event_ts: float | None = None
    task: asyncio.Task | None = None
```

`/readyz` checks: `state.started and state.task is not None and not state.task.done()`

`/health` is static: always `{"status": "ok"}` (process alive = healthy).

#### Structured JSON Logging Architecture

All services — current and future — adopt `python-json-logger` via a shared setup function.
This is the canonical logging contract. Never call `logging.basicConfig()` anywhere.

Log record schema (every line emitted to stdout):

| Field | Type | Source | Example |
|---|---|---|---|
| `timestamp` | ISO-8601 | auto | `"2026-05-02T10:30:00.000Z"` |
| `level` | string | auto | `"INFO"` |
| `service` | string | `setup_json_logger(name)` | `"processor"` |
| `message` | string | log call | `"record_created"` |
| `correlation_id` | UUID str | `extra={"cid": ...}` | `"abc123..."` |
| `logger` | string | auto | `"ingestor.main"` |

Shared setup function in `libs/platform/logging.py`:

```python
def setup_json_logger(service_name: str) -> None:
    """Configure root logger with JSON formatter.

    Call once in lifespan startup (or at module level for non-FastAPI services).
    Respects LOG_LEVEL env var; defaults to INFO.
    """
```

Adoption checklist for every service (new and existing):

1. Import: `from libs.platform.logging import setup_json_logger`
2. Call once in lifespan startup: `setup_json_logger("my_service")`
3. Never call `logging.basicConfig()` — it conflicts with JSON formatter
4. Log events as `noun_verb` noun: `logger.info("record_created", extra={"record_id": 123})`
5. Always pass `cid` (correlation ID) in `extra={}` for request-scoped logs
6. Never log PII, tokens, or credentials — even at DEBUG level

Future service convention: every new `services/<name>/main.py` calls `setup_json_logger` before
the first log statement, inside the lifespan startup block.

---

### Steps

**Phase 10.0: Shared logging module** *(prerequisite for 10.1–10.4)*

1. Create or extend `libs/platform/logging.py` — `setup_json_logger(service_name: str) -> None`
   using `python-json-logger`; adds `service`, `correlation_id` fields; respects `LOG_LEVEL` env var

**Phase 10.1: `ai_gateway` hardening**

2. Add `/readyz` endpoint — check Qdrant reachability via `qdrant_client.health()` or
   `GET http://qdrant:6333/healthz`; return `503` if unreachable
3. Replace `logging.basicConfig` → `setup_json_logger("ai_gateway")` from shared module
4. Add `lifespan` context manager — move vector store init into lifespan startup; graceful teardown
   on shutdown (flush pending embeddings, close client)

**Phase 10.2: `query_api` hardening**

5. Add `lifespan` context manager — create DB engine in startup, dispose in shutdown; eliminates
   connection leak on restart
6. Replace `logging.basicConfig` → `setup_json_logger("query_api")`
7. `/readyz` already performs DB ping — verify it returns `503` (not `500`) on failure

**Phase 10.3: `dashboard` hardening**

8. Improve `/readyz` — HTTP probe to `ingestor` `/health` with 2s timeout; return `503` if
   ingestor unreachable; cache result for 5s to avoid hammering ingestor on probe loop
9. Replace `logging.basicConfig` → `setup_json_logger("dashboard")`
10. Add `lifespan` context manager — create `httpx.AsyncClient` for upstream calls in startup;
    close cleanly on shutdown (currently leaks open connections)

**Phase 10.4: `processor` — script → FastAPI service**

11. Add `fastapi>=0.135` and `uvicorn[standard]>=0.45` to `services/processor/pyproject.toml`
12. Introduce `ConsumerState` dataclass — tracks `started`, `messages_consumed`, `messages_failed`,
    `last_event_ts`, `task` (asyncio.Task handle); module-level singleton
13. Refactor `main.py` entry point: replace `asyncio.run(consume())` with a FastAPI `app` with
    `lifespan` — startup calls `asyncio.create_task(consume(state))`, shutdown cancels and awaits
    the task; `consume()` accepts `state: ConsumerState` and updates counters on each message
14. Add `GET /health` — static liveness: `{"status": "ok", "service": "processor"}`
15. Add `GET /readyz` — checks `state.started and not state.task.done()`; returns `200` when
    consumer is running, `503` with reason when task has exited (crash or Redpanda down)
16. Replace `logging.basicConfig` → `setup_json_logger("processor")`
17. Update `services/processor/Dockerfile`: change `CMD` from `python main.py` to
    `CMD ["/app/.venv/bin/uvicorn", "services.processor.main:app", "--host", "0.0.0.0", "--port", "8002"]`;
    update `HEALTHCHECK` from no-op `sys.exit(0)` to HTTP probe at `http://127.0.0.1:8002/health`
18. Update `docker-compose.yml` — add `healthcheck` for processor (HTTP to port 8002);
    expose port `8002:8002`

**Phase 10.5: `ingestor` alignment** *(already well-structured; minor gaps only)*

19. Verify `/readyz` returns `503` (not `200` with error body) on DB failure — check response
    code on exception path in `main.py:readyz()`
20. Add `service` field to all `extra={}` log calls — currently missing from most log sites

---

### Relevant Files

- `libs/platform/logging.py` — create/extend shared JSON logger setup
- `services/ai_gateway/main.py` — add `/readyz`, lifespan, structured logging
- `services/query_api/main.py` — add lifespan, fix `/readyz` status code, structured logging
- `services/dashboard/main.py` — improve `/readyz`, lifespan, structured logging
- `services/processor/main.py` — refactor to FastAPI app; `consume()` as `asyncio.Task` in lifespan;
  add `/health`, `/readyz`, `ConsumerState`; structured logging
- `services/processor/pyproject.toml` — add `fastapi>=0.135`, `uvicorn[standard]>=0.45`
- `services/processor/Dockerfile` — change `CMD` to uvicorn; update `HEALTHCHECK` to port 8002
- `docker-compose.yml` — update processor healthcheck to port 8002; expose `8002:8002`
- `libs/platform/logging.py` — verify or create `setup_json_logger` with `service` filter

---

### Verification

```bash
# All readyz probes return correct status codes
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/readyz   # ingestor: 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/readyz   # ai_gateway: 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8002/readyz   # processor: 200 when consuming
curl -s -o /dev/null -w "%{http_code}" http://localhost:8005/readyz   # query_api: 200
curl -s -o /dev/null -w "%{http_code}" http://localhost:8003/readyz   # dashboard: 200

# Processor consumer state
curl -s http://localhost:8002/health   # {"status": "ok", "service": "processor"}
curl -s http://localhost:8002/readyz   # {"status": "ready"} or 503 with reason
# Simulate crash: stop Redpanda, wait 30s → readyz returns 503

# All services show healthy in compose
docker compose up --build
docker compose ps   # all app services: healthy

# Structured JSON logging — every service emits parseable JSON
for svc in ingestor ai_gateway processor query_api dashboard; do
  echo "=== $svc ==="
  docker compose logs "$svc" | head -3 | python3 -c "import sys,json; [print(json.loads(l).get('service')) for l in sys.stdin if l.strip()]"
done

# Graceful shutdown — no connection leak errors on stop
docker compose stop query_api && docker compose logs query_api | tail -5
```

---

### Decisions

- **Processor as FastAPI service**: Consistent deployment pattern; `asyncio.Task` in uvicorn's
  event loop avoids extra thread; `/readyz` can introspect task liveness directly; natural
  extension point for future admin endpoints and manual DLQ requeue
- **Port 8002 for processor**: Consistent port numbering — 8000 ingestor, 8001 ai_gateway,
  8002 processor, 8003 dashboard, 8005 query_api
- **Shared logging module in `libs/platform/`**: Single implementation, no duplication across 5
  services; every future service imports `setup_json_logger` rather than calling `basicConfig`
- **`/readyz` returns `503` (not `500`)**: `503 Service Unavailable` is the correct HTTP signal
  for "not ready"; `500` implies a bug; load balancers treat them differently
- **Shallow liveness, deep readiness**: Liveness (`/health`) must be trivial — never call external
  services; Readiness (`/readyz`) checks one critical upstream only

---

### Out of Scope

- Service-to-service authentication (JWT propagation, mTLS)
- OpenAPI contract versioning between services
- CI workflow matrix updates (Phase 11)
- Kubernetes pod spec probes (Phase 12)
