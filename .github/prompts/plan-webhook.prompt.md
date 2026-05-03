## Plan: Phase 14 — Webhook Service Blueprint

Follows Phase 13 (Terraform ECS Task Definitions). All 5 core services now deployable to Kubernetes.
Phase 14 adds the **Webhook Gateway** service (`services/webhook/` on port 8004), completing the
ingestion triptych: ingestor (batch REST), processor (async consumer), and webhook (event-driven).
Webhook service validates HMAC signatures, deduplicates payloads, publishes to Kafka, and maintains
an audit trail in PostgreSQL for compliance and debugging.

---

### Current State Audit

| Concern | Current state |
|---|---|
| Webhook ingestion | Only ingestor (batch) + processor (consumer); no event-driven ingest |
| HMAC signature validation | No webhook signature verification (security gap) |
| Duplicate detection | No idempotency key deduplication for webhooks |
| Audit trail | No webhook event audit log in database |
| Retry logic | No per-webhook retry budget or backoff strategy |
| Webhook management | No UI/API to register, pause, test, or inspect webhooks |
| Integration with existing flow | Ingestor-specific CRUD; webhook service isolated |
| Error tracking | Failed webhook deliveries not correlated with DLQ events |
| Rate limiting | No per-source rate limit (Stripe API, Segment source, etc.) |
| Port 8004 unused | Architecture gap identified in Phase 12 |

---

### Critical Findings

**Gap 1 — No event-driven ingestion path**
Current architecture: batch (ingestor REST) → Kafka → processor. Missing: external webhook sources
(Stripe, Segment, Plaid, Zapier, custom integrations) → data pipeline. Many SaaS platforms provide
webhooks as primary or only integration method; lack of support limits adoption.

**Security Gap 2 — No signature verification**
Without HMAC-SHA256 validation, a malicious actor can send forged webhook payloads impersonating
Stripe, Segment, etc. The service must:
- Store webhook signing keys per source (encrypted in Secrets Manager)
- Validate `X-Signature` header matches `HMAC-SHA256(payload, key)`
- Reject unsigned or invalid-signature requests with 401 Unauthorized

**Gap 3 — No idempotency / duplicate detection**
External APIs may retry webhook delivery (network timeout, 5xx response). Without deduplication,
duplicate events cause duplicate records/processing (e.g., same payment charged twice).
Solution: Idempotency key (webhook ID, sequence number) with uniqueness constraint in database.

**Gap 4 — No audit trail for webhook events**
Failed or delayed webhooks are hard to debug without a durable audit log. The service must store:
- Raw payload, headers, signature, source IP
- Processing status (pending, processed, failed, retried)
- Error messages (if applicable)
- Timestamp and trace ID for correlation

**Gap 5 — No webhook management interface**
Operators need to:
- Register new webhook sources and signing keys (without redeploying)
- Pause/resume webhook ingestion (incident response)
- Replay historical webhook batches (incident recovery)
- Inspect webhook delivery history (debugging)
Solution: Admin API endpoints + future UI (Phase 15+).

---

### Architecture Decisions

#### Webhook Service Design Philosophy

```text
External Webhook Source (Stripe, Segment, Zapier, ...)
  │
  ├─ HTTP POST /webhooks/{source}
  │   Headers: X-Signature, X-Timestamp, X-Delivery-ID, User-Agent
  │   Body: JSON (or form-encoded if API requires)
  │
  ├─ Signature Validation (HMAC-SHA256)
  │   ├─ Fetch key from Secrets Manager (cached, 5min TTL)
  │   ├─ Compute HMAC(body, key)
  │   ├─ Compare with X-Signature
  │   └─ 401 if mismatch
  │
  ├─ Idempotency Check
  │   ├─ Extract idempotency_key (webhook_id, event_id, delivery_id)
  │   ├─ Query PostgreSQL: SELECT id FROM webhook_events WHERE idempotency_key = ?
  │   ├─ 200 OK (already processed) if exists
  │   └─ Continue if new
  │
  ├─ Audit Log Entry (PostgreSQL)
  │   ├─ INSERT webhook_event {
  │   │     source, delivery_id, idempotency_key,
  │   │     raw_payload, headers, signature_valid,
  │   │     status=pending, created_at
  │   │   }
  │   └─ Reserve entry; update status as processing progresses
  │
  ├─ Kafka Publish (async fire-and-forget)
  │   ├─ Topic: webhook.events.{source}
  │   ├─ Key: source (partition by source for ordering)
  │   ├─ Value: {webhook_id, delivery_id, payload, timestamp}
  │   ├─ On success: mark webhook_event.status = published
  │   └─ On failure: mark webhook_event.status = failed, store error
  │
  └─ Response
      ├─ 202 Accepted (async processing initiated)
      └─ Return: {delivery_id, status, created_at}
```

#### Webhook Event Schema (PostgreSQL)

Table: `webhook_events`

```sql
CREATE TABLE webhook_events (
  id BIGSERIAL PRIMARY KEY,
  source VARCHAR(64) NOT NULL,                 -- stripe, segment, zapier, ...
  delivery_id UUID UNIQUE NOT NULL,            -- webhook provider delivery ID
  idempotency_key VARCHAR(256) UNIQUE,         -- X-Delivery-ID or event.id + timestamp
  raw_payload JSONB NOT NULL,                  -- exact JSON/form data received
  headers JSONB NOT NULL,                      -- {X-Signature, X-Timestamp, User-Agent, ...}
  signature_valid BOOLEAN NOT NULL,            -- true = HMAC validated
  status VARCHAR(32) NOT NULL DEFAULT 'pending',  -- pending, processing, published, failed, replay_queued
  processing_attempts INT DEFAULT 0,           -- retry count (0 = first attempt)
  last_error TEXT,                             -- error message if failed
  published_to_kafka BOOLEAN DEFAULT FALSE,    -- successful publish to webhook.events.{source}?
  kafka_offset BIGINT,                         -- Kafka offset if published
  processed_at TIMESTAMPTZ,                    -- when status changed to published/failed
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT valid_status CHECK (status IN ('pending', 'processing', 'published', 'failed', 'replay_queued')),
  INDEX idx_source_created (source, created_at),
  INDEX idx_delivery_id (delivery_id),
  INDEX idx_idempotency_key (idempotency_key),
  INDEX idx_status (status)
);
```

#### Webhook Registration & Key Management

Table: `webhook_sources`

```sql
CREATE TABLE webhook_sources (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(64) UNIQUE NOT NULL,            -- stripe, segment, zapier, ...
  description TEXT,
  signing_key_secret_name VARCHAR(256) NOT NULL,  -- reference to Secrets Manager
  signing_algorithm VARCHAR(32) DEFAULT 'HMAC-SHA256',
  rate_limit_per_minute INT DEFAULT 60,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  INDEX idx_name_active (name, is_active)
);
```

**Signing keys stored in AWS Secrets Manager:**
- Secret name: `data-zoo/webhook/{source}/signing-key`
- Format: JSON `{"key": "sk_...", "algorithm": "HMAC-SHA256", "rotated_at": "2026-05-03T..."}`
- Rotated on-demand; old keys kept for grace period (7 days)

#### Signature Validation Algorithm

```python
# pseudocode
def validate_webhook_signature(request_body: bytes, header_signature: str, signing_key: str) -> bool:
    """
    Validate HMAC-SHA256 signature.

    Stripe format: X-Stripe-Signature = t=timestamp,v1=computed_hash
    Segment format: X-Segment-Signature = SHA256=computed_hash (no timestamp)
    Generic: X-Signature = computed_hash
    """
    # 1. Use raw body bytes (not parsed JSON) to prevent tampering via whitespace
    # 2. Compute HMAC-SHA256(body_bytes, key_bytes)
    # 3. Compare with header_signature (constant-time to prevent timing attacks)

    import hmac
    import hashlib

    computed = hmac.new(
        signing_key.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison (prevents timing-based forgery)
    return hmac.compare_digest(computed, header_signature)
```

#### Deduplication Strategy

**Idempotency key sources** (in priority order):

1. `X-Delivery-ID` header (Stripe, Segment, Mailgun use this)
2. `event.id` + `event.timestamp` (Zapier, custom)
3. `event_id` field in JSON payload
4. Hash of `(source, payload)` if no explicit ID available (last resort)

**Collision resolution**:

```python
# On INSERT conflict:
# 1. Check if previous record has status = 'published' → idempotent 200 OK
# 2. Check if previous record has status = 'pending' → wait / return 202 Accepted
# 3. Check if previous record has status = 'failed' → optionally mark for replay
```

#### Rate Limiting & Backpressure

Per-source rate limit with token bucket:

```python
# Pseudo-config
RATE_LIMITS = {
    "stripe": 100,      # per minute
    "segment": 200,
    "zapier": 50,
    "default": 60
}

# On request:
# 1. Check Redis: redis.incr(f"webhook:rate:{source}:{minute}")
# 2. If over limit → 429 Too Many Requests
# 3. If under limit → process, log attempt
```

#### Error Handling & Retry

**Immediate failures** (synchronous validation):

- Invalid signature → 401 Unauthorized (no retry)
- Duplicate (idempotency key exists, status=published) → 200 OK (idempotent)
- Duplicate (idempotency key exists, status=pending) → 202 Accepted (wait)
- Rate limited → 429 Too Many Requests (backoff)
- Malformed JSON → 400 Bad Request (no retry)

**Async failures** (Kafka publish):

- Kafka unavailable → mark webhook_event.status = 'failed', retry loop runs hourly
- Circuit breaker open → mark failed, log warning
- Timeout → log, increment processing_attempts, mark for replay

**Replay mechanism** (manual or automatic):

```python
# Admin API
POST /admin/webhooks/replay
{
  "source": "stripe",
  "date_range": {"from": "2026-05-01T00:00:00Z", "to": "2026-05-02T00:00:00Z"},
  "status_filter": "failed",  # replay only failed events
  "limit": 1000
}
# → Marks matching webhook_events.status = 'replay_queued'
# → Daemon re-publishes to Kafka with new delivery_id (trace ID)
```

#### Service Architecture

```
Port 8004: Webhook Gateway (FastAPI)
  │
  ├─ POST /webhooks/{source}
  │   ├─ Signature validation
  │   ├─ Deduplication check
  │   ├─ Audit log INSERT
  │   ├─ Async Kafka publish (fire-and-forget)
  │   └─ Return 202 Accepted
  │
  ├─ GET /health
  │   ├─ Postgres connectivity
  │   ├─ Secrets Manager connectivity
  │   └─ Return 200 OK
  │
  ├─ GET /readyz
  │   ├─ All health checks + Kafka connectivity
  │   └─ Return 200 OK if all healthy
  │
  ├─ Admin API (internal only, behind auth)
  │   ├─ GET /admin/sources
  │   ├─ POST /admin/sources (register new webhook source)
  │   ├─ PATCH /admin/sources/{name} (pause/resume, rotate key)
  │   ├─ GET /admin/webhooks/events (inspect delivery history)
  │   └─ POST /admin/webhooks/replay (manual replay)
  │
  └─ Background task: Replay daemon
      ├─ Query webhook_events WHERE status = 'replay_queued'
      ├─ Re-publish to Kafka (new delivery_id)
      ├─ Update status = 'published'
      └─ Run every 5 minutes
```

---

### Steps

**Phase 14.0: Data model & migrations**

1. Create Alembic migration: `alembic/versions/004_webhook_tables.py`
   - `webhook_sources` table (signing keys reference)
   - `webhook_events` table (audit log)
   - Indexes for idempotency, status, source
2. Seed initial webhook source in migration:
   - `INSERT INTO webhook_sources (name, signing_key_secret_name, is_active)`
     `VALUES ('stripe', 'data-zoo/webhook/stripe/signing-key', TRUE)`
   - Repeat for Segment, Zapier (as examples)
3. Test migration: `pytest tests/migrations/test_webhook_tables.py`

**Phase 14.1: Webhook service scaffolding**

4. Create `services/webhook/` directory structure:
   ```
   services/webhook/
     ├─ pyproject.toml
     ├─ Dockerfile
     ├─ main.py                    # FastAPI app, lifespan, routes
     ├─ models.py                  # SQLAlchemy WebhookEvent, WebhookSource
     ├─ schemas.py                 # Pydantic request/response
     ├─ routers/
     │   ├─ webhooks.py            # POST /webhooks/{source}
     │   ├─ admin.py               # Admin API routes
     │   └─ health.py              # /health, /readyz
     ├─ services/
     │   ├─ signature.py           # HMAC validation
     │   ├─ idempotency.py         # Dedup logic
     │   ├─ kafka_publisher.py     # Async Kafka publish
     │   └─ replay_daemon.py       # Background replay task
     ├─ core/
     │   ├─ config.py              # Environment vars
     │   ├─ logging.py             # Structured logging
     │   └─ secrets.py             # Secrets Manager client
     └─ tests/
         ├─ test_signature.py
         ├─ test_idempotency.py
         └─ test_routers.py
   ```
5. Dependencies: same as ingestor (FastAPI, SQLAlchemy, Pydantic, httpx, aiokafka, boto3)

**Phase 14.2: Core signature validation**

6. Implement `services/webhook/services/signature.py`:
   - `validate_signature(body: bytes, header_signature: str, source: str) -> bool`
   - Fetch signing key from Secrets Manager (cache with 5min TTL)
   - Use `hmac.compare_digest()` (constant-time)
   - Unit tests: valid, invalid, missing key, tampered body
7. Implement `services/webhook/core/secrets.py`:
   - Secrets Manager client singleton
   - Cache with TTL and refresh logic
   - Fallback to environment vars if Secrets Manager unavailable (local dev)

**Phase 14.3: Deduplication & audit log**

8. Implement `services/webhook/services/idempotency.py`:
   - Extract idempotency key from payload
   - Query PostgreSQL for existing entry
   - Return: (is_duplicate: bool, existing_event: WebhookEvent | None)
9. Implement `services/webhook/routers/webhooks.py::create_webhook()`:
   - Parse request, validate JSON
   - Call `validate_signature()` → 401 if invalid
   - Call `idempotency.check()` → 200 OK if duplicate (published)
   - INSERT webhook_event row (status=pending)
   - Async publish to Kafka (fire-and-forget, errors logged)
   - Return 202 Accepted with delivery_id
   - Tests: happy path, duplicate, invalid signature, Kafka failure, rate limit

**Phase 14.4: Admin API**

10. Implement `services/webhook/routers/admin.py`:
    - `GET /admin/sources` — list webhook sources
    - `POST /admin/sources` — register new source + signing key
    - `PATCH /admin/sources/{name}` — pause/resume, rotate key
    - `GET /admin/webhooks/events?source=stripe&status=failed&limit=50` — inspect history
    - `POST /admin/webhooks/replay` — bulk replay failed events
    - Require `Authorization: Bearer {ADMIN_TOKEN}` (from env, not a user)
11. Add admin routes to `main.py`; only expose under `admin_enabled` flag

**Phase 14.5: Background replay daemon**

12. Implement `services/webhook/services/replay_daemon.py`:
    - Async task: query webhook_events WHERE status='replay_queued'
    - For each: re-publish to Kafka with new delivery_id
    - Update status='published' on success, 'failed' on error
    - Log metrics (replayed_count, failed_count)
13. Register daemon in `main.py` lifespan: runs every 5 minutes via `asyncio.create_task()`

**Phase 14.6: Health & readiness endpoints**

14. Implement `services/webhook/routers/health.py`:
    - `GET /health` → check Postgres, Secrets Manager, return 200 OK
    - `GET /readyz` → same as /health + check Kafka connectivity
    - Both return JSON: `{"status": "healthy", "checks": {...}}`

**Phase 14.7: Docker & compose**

15. Create `services/webhook/Dockerfile`:
    - Multi-stage build, same pattern as ingestor/processor
    - Port 8004
    - `CMD ["uvicorn", "webhook.main:app", "--host", "0.0.0.0", "--port", "8004"]`
16. Update `docker-compose.yml`:
    - Add webhook service on port 8004
    - Depends on: db, redis, redpanda, jaeger
    - Environment: DATABASE_URL, KAFKA_BROKER_URL, OTEL_ENABLED, ADMIN_TOKEN (local: `dev-only`)
    - Health check: `curl -f http://localhost:8004/readyz`
    - Profiles: default (always up) or `integrations` (optional heavy services)

**Phase 14.8: Integration tests**

17. Create `tests/integration/webhook/test_webhooks.py`:
    - Happy path: POST /webhooks/stripe with valid signature → 202 Accepted
    - Duplicate: same delivery_id twice → first 202, second 200 OK
    - Invalid signature → 401 Unauthorized
    - Kafka failure (circuit open) → 202 (async), webhook_event.status=failed
    - Rate limit exceeded → 429 Too Many Requests
    - Admin replay: POST /admin/webhooks/replay → marks events as replay_queued
18. Create `tests/integration/webhook/test_signature.py`:
    - Valid HMAC → True
    - Tampered body → False
    - Wrong key → False
    - Constant-time comparison (timing attack immunity)

**Phase 14.9: Documentation**

19. Create `docs/webhook-integration.md`:
    - Webhook sources table (Stripe, Segment, Zapier, custom)
    - Per-source setup: how to get signing key, endpoint URL, retry config
    - Example requests (curl)
    - Error handling and retry strategy
    - Admin API reference
20. Create `docs/webhook-debugging.md`:
    - How to query webhook_events table
    - How to manually replay failed events
    - How to rotate signing keys
    - Troubleshooting: signature mismatch, duplicate delivery, rate limit

**Phase 14.10: Kubernetes manifests**

21. Create `infra/kubernetes/manifests/webhook/deployment.yaml`:
    - `containerPort: 8004`, named `http`
    - `startupProbe`: `failureThreshold: 6`, `periodSeconds: 10`
    - `livenessProbe`: `/health`, `periodSeconds: 20`
    - `readinessProbe`: `/readyz`, `periodSeconds: 10`
    - Resources: CPU 100m/500m, Memory 256Mi/512Mi (same as processor)
    - Env: ADMIN_TOKEN from Secret, DATABASE_URL, KAFKA_BROKER_URL
22. Create `infra/kubernetes/manifests/webhook/service.yaml`:
    - ClusterIP, port 8004 (internal only initially; expose via Ingress in Phase 15)
23. Update `infra/kubernetes/overlays/local/`:
    - Add webhook to `kustomization.yaml`
    - Create `webhook-deployment.yaml` patch (image tag=latest)
24. Update `infra/kubernetes/overlays/local/ingress.yaml`:
    - Add route: `webhook.127.0.0.1.nip.io:8080` → webhook service:8004

---

### Relevant Files

**Core Implementation**:
- `services/webhook/` — new service directory (all files as listed above)
- `alembic/versions/004_webhook_tables.py` — database migration

**Configuration & Integration**:
- `docker-compose.yml` — add webhook service + environment vars
- `pyproject.toml` — add webhook service to dev dependencies (optional)

**Testing**:
- `tests/integration/webhook/` — integration + unit tests
- `tests/migrations/test_webhook_tables.py` — schema verification

**Documentation**:
- `docs/webhook-integration.md` — operator reference
- `docs/webhook-debugging.md` — troubleshooting guide
- `README.md` — update architecture diagram to include webhook service

**Kubernetes**:
- `infra/kubernetes/manifests/webhook/` — deployment + service
- `infra/kubernetes/overlays/local/webhook-deployment.yaml` — local patch
- `infra/kubernetes/overlays/local/ingress.yaml` — add webhook route
- `infra/kubernetes/charts/webhook/` — Helm chart scaffold (similar to ingestor)

---

### Verification

```bash
# Local development
docker compose up webhook
# or with profile
docker compose --profile integrations up webhook

# Health check
curl http://localhost:8004/health
# Expected: 200 OK, {"status": "healthy"}

curl http://localhost:8004/readyz
# Expected: 200 OK, {"status": "healthy", "postgres": "ok", "kafka": "ok"}

# Test Stripe webhook (mock)
export STRIPE_KEY="sk_test_..."
export STRIPE_SIGNATURE=$(python3 -c "
import hmac, hashlib, json
body = json.dumps({'event_id': '123', 'type': 'charge.succeeded'})
sig = hmac.new(b'$STRIPE_KEY', body.encode(), hashlib.sha256).hexdigest()
print(sig)
")

curl -X POST http://localhost:8004/webhooks/stripe \
  -H "X-Signature: $STRIPE_SIGNATURE" \
  -H "X-Delivery-ID: evt_123" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "123", "type": "charge.succeeded"}'
# Expected: 202 Accepted, {"delivery_id": "...", "status": "pending", "created_at": "..."}

# Verify audit log
psql postgresql://postgres:postgres@localhost:5432/data_pipeline \
  -c "SELECT delivery_id, source, signature_valid, status FROM webhook_events LIMIT 5;"

# Verify Kafka publish
docker compose exec redpanda rpk topic list
# Expected: webhook.events.stripe, webhook.events.segment, ...

docker compose exec redpanda rpk topic consume webhook.events.stripe
# Expected: messages appear as webhooks are received

# Duplicate test
curl -X POST http://localhost:8004/webhooks/stripe \
  -H "X-Signature: $STRIPE_SIGNATURE" \
  -H "X-Delivery-ID: evt_123" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "123", "type": "charge.succeeded"}'
# Expected: 200 OK (idempotent, already processed)

# Admin API
curl -X GET http://localhost:8004/admin/sources \
  -H "Authorization: Bearer dev-only"
# Expected: 200 OK, list of webhook sources

curl -X GET "http://localhost:8004/admin/webhooks/events?source=stripe&status=published&limit=10" \
  -H "Authorization: Bearer dev-only"
# Expected: 200 OK, list of webhook events

# Replay failed events
curl -X POST http://localhost:8004/admin/webhooks/replay \
  -H "Authorization: Bearer dev-only" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "stripe",
    "date_range": {"from": "2026-05-01T00:00:00Z", "to": "2026-05-02T00:00:00Z"},
    "status_filter": "failed",
    "limit": 100
  }'
# Expected: 200 OK, {"replayed_count": 5, "total": 5}

# Kubernetes verification
kubectl apply -k infra/kubernetes/overlays/local
kubectl -n data-zoo get deployments
# Expected: webhook listed

kubectl -n data-zoo rollout status deployment/webhook
# Expected: deployment rolled out successfully

kubectl -n data-zoo get pods -l app=webhook
# Expected: pod running (1/1 Ready)

# Ingress routing
curl -H "Host: webhook.127.0.0.1.nip.io" http://localhost:8080/health
# Expected: 200 OK (via nginx ingress → webhook service)

# Integration test
uv run pytest tests/integration/webhook/ -v
# Expected: all tests pass
```

---

### Decisions

- **Port 8004**: Completes the 5-service quartet (8000-8003) + new webhook service
- **Async Kafka publish (fire-and-forget)**: Webhooks return 202 immediately; Kafka errors logged but don't block response (fail-open)
- **Audit log in PostgreSQL**: Immutable record of all webhook deliveries for compliance + debugging (audit trail)
- **HMAC-SHA256 only**: Most common standard; if other algorithms needed, extend later (Phase 15+)
- **Per-source rate limiting**: Prevents any single source from overwhelming the system; tunable per environment
- **Secrets Manager for keys**: Production-grade key rotation; local dev falls back to env vars
- **Admin API over HTTP** (not GraphQL): Simpler, same stack as ingestor; auth via bearer token (not mTLS yet)
- **Replay daemon**: Async background task, not event-driven (simpler than subscribing to failure events)
- **Single-replica Deployment**: Like processor, webhook is stateless; scale by increasing topic partitions if needed
- **No API Gateway auth yet**: Assume webhook service lives behind ALB/internal VPC; future phase adds OAuth2/API keys (Phase 15+)

---

### Out of Scope

- **API Key authentication** — future phase (currently bearer token for admin only)
- **Webhook UI dashboard** — future phase (Phase 15+: list sources, inspect delivery history, replay UI)
- **Rate limiting per customer** — future phase (currently global per source)
- **Payload transformation rules** — future phase (currently raw pass-through to Kafka)
- **Custom retry backoff strategies** — future phase (currently hourly batch replay)
- **End-to-end encryption of webhook payloads** — future phase (currently TLS in transit only)
- **Multi-tenant webhook isolation** — future phase (single tenant assumed)
- **Webhook signature rotation / key versioning** — future phase (currently single key per source, manual rotation via admin API)
- **Circuit breaker for slow Postgres/Secrets Manager** — out of scope (normal Phase 4 circuit breaker applies)
- **Support for webhook format variants** (XML, protocol buffers, Avro) — future phase (JSON only for now)
- **Bulk webhook ingestion** (batch endpoint) — future phase (single event per HTTP request for now)
- **Dynamic source registration via self-service** — future phase (manual admin API for now)
