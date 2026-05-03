## Plan: Phase 13 — Infrastructure Security Hardening & Service Auth

Consolidates all items explicitly deferred to Phase 13 from prior plans, plus near-term out-of-scope items from Phases 10, 11, 12, and 14. Four pillars: Terraform ECS alignment, container filesystem hardening, service-to-service auth, and Redis cache enhancements.

---

### Source Cross-Reference

| Item | Origin Plan | OOS Note |
|---|---|---|
| Terraform ECS task defs — processor port 8002 | Phase 11 OOS | "Phase 13" explicitly named |
| Terraform ECS task defs — all services health checks | Phase 12 OOS | "Phase 13" explicitly named |
| `readOnlyRootFilesystem: true` + emptyDir mounts | Phase 12 OOS | "Phase 13 after tmpfs audit" |
| Service-to-service JWT propagation | Phase 10 OOS | "Service-to-service authentication" |
| Webhook API Key authentication | Phase 14 OOS | "Future phase (near-term)" |
| Webhook signature key rotation / versioning | Phase 14 OOS | "Future phase" |
| Webhook custom retry backoff strategies | Phase 14 OOS | "Currently hourly batch replay" |
| Redis list caching with namespace invalidation | Redis plan OOS | "Offset pagination key space too large" — deferred |
| Redis cache warming | Redis plan OOS | Deferred |
| Redis distributed locking (Redlock) | Redis plan OOS | For job deduplication |

Items not included (Phase 15+ or require baselines not yet available): Istio/mTLS, HPA/VPA, webhook UI dashboard, multi-tenant webhook isolation, end-to-end payload encryption.

---

### Current State Audit

| Concern | Current state |
|---|---|
| ECS task def — processor | No `portMappings` or `healthCheck` for port 8002 (blocked since Phase 10.4) |
| ECS task def — all services | Health checks reference `/health` but not verified against current path (`/health` vs `/readyz`) |
| `readOnlyRootFilesystem` | `false` on all K8s deployments; services write to `/tmp` paths not yet audited |
| Service-to-service auth | No JWT propagation; internal calls are unauthenticated (trust-the-network model) |
| Webhook auth | Admin API protected by bearer token from env; no per-source API key lifecycle |
| Webhook signature keys | Single key per source; no rotation/versioning; old key grace period not enforced |
| Webhook retry | Hourly batch replay only; no exponential backoff per source |
| Redis list caching | Single-record caching only; `GET /records` list endpoint cache-bypassed |
| Redis Redlock | No distributed locking; background jobs can double-run on multi-replica restart |

---

### Architecture Decisions

#### Phase 13.0 — Terraform ECS Task Definitions

The `cd-deploy.yml` comment inserted in Phase 11.3 documents the gap: processor now runs on port 8002 but the ECS task definition has no `portMappings` or `healthCheck`. This is the only service gap because all others had HTTP ports before Phase 10.

Task definition changes needed per service:

| Service | Port | `healthCheck.command` path |
|---|---|---|
| `ingestor` | 8000 | `/health` |
| `ai_gateway` | 8001 | `/health` |
| `processor` | 8002 | `/health` — **missing entirely** |
| `dashboard` | 8003 | `/health` |
| `query_api` | 8005 | `/health` |
| `webhook` | 8004 | `/health` — add after Phase 14 deploys |

Terraform module pattern to use (reuse from existing `ingestor` task def as reference):

```hcl
module "ecs_task_definition" {
  for_each = local.services
  container_definitions = {
    portMappings = [{ containerPort = each.value.port, protocol = "tcp" }]
    healthCheck  = {
      command = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${each.value.port}/health', timeout=5)\""]
    }
  }
}
```

All 5 service task definitions should be unified into a single Terraform module using `for_each` over a `local.services` map — removes per-service duplication and ensures consistency.

#### Phase 13.1 — `readOnlyRootFilesystem` Hardening

Phase 12 deferred this with: _"Auditing each service's tmpfs usage deferred to Phase 13; keeping it false is safe but not hardened; Phase 13 adds emptyDir mounts."_

Audit approach: for each service, run `docker compose run --rm <service> find / -writable 2>/dev/null | grep -v proc | grep -v sys` to enumerate all writable paths. Map each path to an `emptyDir` volume mount.

Expected findings per service:

| Service | Expected writable paths | `emptyDir` mount |
|---|---|---|
| `ingestor` | `/tmp`, `/app/logs` (if log file configured) | `emptyDir: {}` at `/tmp` |
| `ai_gateway` | `/tmp`, `/app/model_cache` (sentence-transformers cache) | `emptyDir: {medium: Memory}` at model cache |
| `processor` | `/tmp` | `emptyDir: {}` at `/tmp` |
| `dashboard` | `/tmp`, Jinja2 template cache | `emptyDir: {}` at `/tmp` |
| `query_api` | `/tmp` | `emptyDir: {}` at `/tmp` |

After adding `emptyDir` mounts: set `readOnlyRootFilesystem: true` in all K8s deployment `securityContext` blocks. Also set same in ECS task definitions (`readonlyRootFilesystem: true` in container config).

#### Phase 13.2 — Service-to-Service JWT Propagation

Phase 10 OOS: _"Service-to-service authentication (JWT propagation, mTLS)"_ — mTLS is Phase 15; JWT propagation is Phase 13.

Pattern: each service generates a short-lived internal JWT (`iss: data-zoo-internal`, `sub: <service-name>`, `exp: now + 60s`) signed with a shared `INTERNAL_JWT_SECRET` (from Secrets Manager). Outbound requests include `Authorization: Bearer <token>`. Inbound routers validate the claim.

```text
ingestor → ai_gateway (embeddings): Authorization: Bearer <internal-jwt>
ingestor → processor (trigger replay): Authorization: Bearer <internal-jwt>
dashboard → ingestor (admin reruns): already authenticated via session; add internal JWT for M2M
```

Shared library in `libs/platform/auth.py`:

- `generate_internal_token(service_name: str) -> str`
- `verify_internal_token(token: str) -> ServiceClaims`
- Middleware class `InternalAuthMiddleware` — validates on routes tagged `@require_internal`

Routes that require internal-only access (no user auth):

- `POST /api/v1/background/ingest/batch` — ingestor (currently open)
- Processor `/admin/*` endpoints
- `query_api` projection update endpoints

#### Phase 13.3 — Webhook Auth & Key Lifecycle

Three specific Phase 14 OOS items addressed here:

**API Key authentication** — extend `webhook_sources` table with an `api_key_hash` column (Argon2-hashed). Sources can optionally require API key in `X-API-Key` header in addition to HMAC signature. Admin API endpoints create/rotate/revoke keys:

- `POST /admin/sources/{source_id}/api-keys` — generate key, return plaintext once
- `DELETE /admin/sources/{source_id}/api-keys/{key_id}` — revoke
- Store only hash in DB (OWASP A02: never store raw API keys)

**Signature key rotation / versioning** — `webhook_sources` currently stores a single signing key reference. Extend to support versioned keys:

- Add `signing_key_version` column to `webhook_events` — records which key version validated each event
- On rotation: mark old key as `deprecated` with `deprecated_at` timestamp; keep for 7-day grace period
- During grace period: try new key first, fall back to deprecated key on failure, log warning
- Admin API: `POST /admin/sources/{source_id}/rotate-key` → creates new version in Secrets Manager

**Custom retry backoff** — replace hourly batch replay with per-source configurable backoff:

- Add `retry_config` JSONB column to `webhook_sources`: `{"max_attempts": 5, "backoff_base_seconds": 30, "backoff_multiplier": 2}`
- Replay daemon respects per-source config; default: 5 attempts, 30s/60s/120s/240s/480s backoff
- `webhook_events.next_retry_at` column: computed from `processing_attempts` + backoff config

#### Phase 13.4 — Redis Cache Enhancements

Three Redis plan OOS items:

**List caching** — Redis plan deferred this: _"offset pagination key space (`source × skip × limit`) too large to invalidate cleanly without namespace-flush strategy."_ Solution: namespace keys by `source` tag, use `SCAN + DEL pattern:source:*` on write (new record with that source). Cache TTL: 30s for lists (short — write-heavy workload). Only cache small pages (`limit ≤ 50`); skip cache for large offsets (`skip > 500`).

**Cache warming** — on application startup (lifespan hook), pre-populate top-N most-queried source keys using a short background task. Source: `SELECT source, COUNT(*) FROM records GROUP BY source ORDER BY count DESC LIMIT 10`. Avoids cold-cache latency spike after deploy.

**Redlock distributed locking** — APScheduler jobs can double-run during rolling deploys (two instances briefly overlap). Use `redis-py`'s `SET NX PX` pattern to acquire a named lock before running scheduled jobs:

```python
async with redis_lock("job:daily_rollup", ttl_seconds=300) as acquired:
    if not acquired:
        logger.info("job skipped, lock held by another instance")
        return
    await run_daily_rollup()
```

Implement `redis_lock()` async context manager in `ingestor/cache.py`.

---

### Steps

**Phase 13.0: Terraform ECS task definition alignment**

1. Locate existing Terraform ECS task definition module in `infra/terraform/` — read current `ingestor` task def as template
2. Refactor to `for_each` over `local.services` map with `port`, `cpu`, `memory`, `image_uri` per service
3. Add `processor` entry: `port = 8002`, same health check pattern as ingestor
4. Verify all 5 service entries have matching `portMappings` + `healthCheck.command`
5. Run `terraform plan` — confirm zero diff for existing services, one new `aws_ecs_task_definition` diff for processor
6. Update `cd-deploy.yml`: remove the Phase 11.3 documentation comment (gap is now closed)

**Phase 13.1: `readOnlyRootFilesystem` audit and hardening**

7. For each service, run writable-path audit: `docker compose run --rm <svc> find / -writable -not -path "*/proc/*" -not -path "*/sys/*" 2>/dev/null`
8. Document findings in `docs/dev/filesystem-audit.md`
9. Update each K8s deployment under `infra/kubernetes/manifests/*/deployment.yaml`:
   - Add `emptyDir` volume + `volumeMount` for each writable path identified
   - Set `securityContext.readOnlyRootFilesystem: true`
10. Update corresponding ECS task definition in Terraform: add `readonlyRootFilesystem: true` to each container config
11. Verify locally: `docker compose run --rm <svc> touch /tmp/test` should succeed; `touch /app/test` should fail with "Read-only file system"

**Phase 13.2: Service-to-service JWT propagation**

12. Create `libs/platform/auth.py` with `generate_internal_token()`, `verify_internal_token()`, `InternalAuthMiddleware`
13. Add `INTERNAL_JWT_SECRET` to `ingestor/config.py`, `services/*/config.py` (reads from env/Secrets Manager)
14. Tag internal-only routes with a dependency that calls `verify_internal_token()`
15. Update `ingestor` outbound calls to `ai_gateway` and `processor` to inject `Authorization: Bearer <internal-jwt>`
16. Write unit tests: valid token, expired token, wrong issuer, missing header
17. Update `docker-compose.yml` and `infra/kubernetes/manifests/*/deployment.yaml` to pass `INTERNAL_JWT_SECRET` from Secret

**Phase 13.3: Webhook auth & key lifecycle**

18. Alembic migration `alembic/versions/005_webhook_auth_hardening.py`:
    - Add `api_key_hash`, `signing_key_version` to `webhook_sources`
    - Add `signing_key_version`, `next_retry_at`, `retry_config` to `webhook_events` / `webhook_sources`
19. Implement `services/webhook/services/api_keys.py` — generate/revoke/verify API keys (Argon2 hash)
20. Implement versioned key lookup in `services/webhook/services/signature.py` — try current version, fall back to deprecated if within 7-day grace period
21. Implement per-source retry backoff in `services/webhook/services/replay_daemon.py` — replace fixed hourly schedule with `next_retry_at`-based dispatch
22. Add admin API endpoints to `services/webhook/routers/admin.py`:
    - `POST /admin/sources/{id}/api-keys`
    - `DELETE /admin/sources/{id}/api-keys/{key_id}`
    - `POST /admin/sources/{id}/rotate-key`
23. Write tests: key generation/revocation, key rotation grace period, backoff timing

**Phase 13.4: Redis cache enhancements**

24. Implement namespace-based list cache in `ingestor/cache.py`:
    - Key pattern: `records:list:{source}:{skip}:{limit}`
    - On write: `await redis.scan_iter(f"records:list:{source}:*")` then delete matched keys
    - Skip cache for `skip > 500` or `limit > 50`
25. Implement cache warming in lifespan hook (`ingestor/main.py`): background task pre-warms top-10 source keys
26. Implement `redis_lock()` async context manager in `ingestor/cache.py` using `SET NX PX` (single-node; upgrade to multi-node quorum in Phase 15)
27. Apply `redis_lock()` to all APScheduler jobs in `ingestor/jobs.py`
28. Write tests using `fakeredis` for all three: list cache namespace invalidation, cache warming, lock acquire/release

---

### Relevant Files

**Terraform (Phase 13.0):**

- `infra/terraform/` — ECS task definition modules
- `.github/workflows/cd-deploy.yml` — remove Phase 11.3 documentation comment block once gap is closed

**Kubernetes (Phase 13.1):**

- `infra/kubernetes/manifests/*/deployment.yaml` — all 5 services, add emptyDir + readOnlyRootFilesystem
- `docs/dev/filesystem-audit.md` — create (writable path findings per service)

**Internal Auth (Phase 13.2):**

- `libs/platform/auth.py` — create (internal JWT generate/verify + middleware)
- `ingestor/config.py`, `services/*/config.py` — add `INTERNAL_JWT_SECRET`
- `docker-compose.yml`, `infra/kubernetes/manifests/*/deployment.yaml` — add secret env var

**Webhook (Phase 13.3):**

- `services/webhook/services/api_keys.py` — create
- `services/webhook/services/signature.py` — extend for versioned key lookup
- `services/webhook/services/replay_daemon.py` — extend for per-source retry backoff
- `services/webhook/routers/admin.py` — add 3 new API key + rotation endpoints
- `alembic/versions/005_webhook_auth_hardening.py` — migration

**Redis (Phase 13.4):**

- `ingestor/cache.py` — list caching + cache warming + `redis_lock()` context manager
- `ingestor/main.py` — add cache warm task to lifespan
- `ingestor/jobs.py` — apply `redis_lock()` to scheduled jobs

---

### Verification

```bash
# Phase 13.0: Terraform plan shows only processor task def change
terraform -chdir=infra/terraform plan | grep "aws_ecs_task_definition"
# Expected: 1 resource to change (processor); 4 unchanged

# Phase 13.1: readOnlyRootFilesystem enforced
for svc in ingestor ai-gateway processor dashboard query-api; do
  kubectl -n data-zoo exec deploy/$svc -- touch /app/test 2>&1 | grep -q "Read-only" \
    && echo "$svc: HARDENED" || echo "$svc: FAIL"
done
# All 5 show HARDENED

# emptyDir /tmp still writable
kubectl -n data-zoo exec deploy/ingestor -- touch /tmp/test && echo "tmp: OK"

# Phase 13.2: Internal JWT propagation
uv run pytest tests/unit/test_internal_auth.py -v
# Expected: valid token passes, expired token rejected, missing header rejected

# Integration: ingestor → ai_gateway call succeeds with valid internal JWT
uv run pytest tests/integration/test_service_to_service_auth.py -v

# Phase 13.3: Webhook API key lifecycle
curl -X POST http://localhost:8004/admin/sources/stripe/api-keys \
  -H "Authorization: Bearer dev-only"
# Expected: {"key_id": "...", "api_key": "wk_...", "created_at": "..."}

# Rotation grace period: old key still works within 7 days
curl -X POST http://localhost:8004/admin/sources/stripe/rotate-key \
  -H "Authorization: Bearer dev-only"
# Expected: new key active; old key deprecated with deprecated_at set

# Phase 13.4: List cache with namespace invalidation
uv run pytest tests/unit/test_cache_list.py -v
# Expected: list is cached; POST invalidates source namespace; list re-populated

# Redlock: two concurrent job starts — second is skipped
uv run pytest tests/unit/test_redis_lock.py -v

# Full test run
uv run pytest tests/ -v
```

---

### Decisions

- **Terraform `for_each` refactor**: eliminates per-service task definition duplication; five services can drift independently without this — unacceptable as webhook (port 8004) joins
- **`readOnlyRootFilesystem: true` with `emptyDir`**: container security best practice; forces explicit declaration of all tmpfs usage; Phase 12 deferred after identifying the audit was non-trivial
- **JWT propagation not mTLS**: mTLS requires cert rotation infrastructure (Phase 15 scope); JWT with a shared internal secret is sufficient for Phase 13 and deployable with existing Secrets Manager setup
- **API key hash with Argon2**: storing raw API keys violates OWASP A02; Argon2 is the current recommended password hashing algorithm (preferred over bcrypt) per OWASP Password Storage Cheat Sheet
- **Single-node `SET NX PX` Redlock**: multi-node quorum Redlock requires ≥3 Redis nodes (we have 1); `SET NX PX` is safe for single-node; document upgrade path to multi-node in Phase 15
- **List cache TTL 30s + source-namespace invalidation**: write-heavy workload makes long list cache impractical; 30s TTL plus source-scoped invalidation balances freshness vs hit rate; large offset queries (`skip > 500`) bypass cache entirely to avoid memory bloat

---

### Out of Scope

- Istio / Linkerd mTLS service mesh (Phase 15)
- Horizontal Pod Autoscaler / Vertical Pod Autoscaler (requires load testing baselines — Phase 14+)
- Webhook UI dashboard (Phase 15+)
- Multi-tenant webhook isolation (future)
- End-to-end payload encryption for webhooks (future)
- Multi-node Redlock quorum (requires ≥3 Redis nodes — Phase 15)
- OpenAPI contract versioning between services (handled in `ci.yml` `contracts-versioning-gate` already)
- Redis Cluster / Sentinel HA (Phase 15 infrastructure uplift)
