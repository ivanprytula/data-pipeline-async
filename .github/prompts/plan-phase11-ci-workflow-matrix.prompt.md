## Plan: Phase 11 — CI Workflow Matrix Updates

Follows Phase 10 (Service Hardening). All 5 services now have `/health` and `/readyz` endpoints,
structured JSON logging, graceful shutdown, and `processor` runs as FastAPI on port 8002.
Phase 11 makes the CI pipeline aware of these guarantees: automated health gate, JSON log
validation, and ECS container definition alignment.

---

### Current State Audit

| Concern | Current state |
|---|---|
| Compose health gate | No job curls `/readyz` after `docker compose up` |
| JSON log validation | No job verifies services emit parseable JSON |
| `processor` port in CI | `cd-deploy.yml` has no container port / healthcheck for processor |
| `processor` path filter | Covers `services/processor/**` but not `services/processor/pyproject.toml` |
| Service smoke tests | No per-service health + readiness assertion in CI |
| Kubernetes infra change | `infra_change` filter covers `infra/**` — picks up K8s manifest changes ✅ |

---

### Critical Findings

**Bug 1 — No compose health gate in CI**
`docker compose up --build` is never run in CI as a correctness check. A broken `CMD`,
misconfigured port, or missing env var will only be caught in production. Phase 10's new
endpoints (`/readyz` for all services) make a compose smoke-test job tractable.

**Bug 2 — `cd-deploy.yml` missing processor container port**
`processor` is mapped as an ECS service in `cd-deploy.yml`, but because it was previously
a bare asyncio script with no HTTP port, the ECS task definition has no `portMappings` or
`healthCheck` entry for processor. After Phase 10.4, processor runs on port 8002 — the
task definition and the deploy workflow must be updated to match.

**Gap 3 — JSON log validation is untested**
Phase 10 adds structured JSON logging to all services. Nothing in CI verifies the output
is actually parseable. A `logging.basicConfig` call left in place would silently emit plain
text that breaks log aggregation downstream.

---

### Architecture Decisions

#### Compose Smoke-Test Job Design

The job runs inside the CI runner (not in a container), uses `docker compose up -d --build`,
polls each service's `/readyz` with a retry loop (30s timeout per service), asserts HTTP 200,
then validates at least one log line per service is valid JSON. On completion (pass or fail),
runs `docker compose down -v` to clean up.

```
compose-smoke-test job
  │
  ├─ docker compose build (uses uv.lock — deterministic)
  ├─ docker compose up -d
  ├─ wait-for-healthy: poll /readyz × 5 services (max 90s each)
  ├─ assert all readyz → 200
  ├─ assert docker compose logs <svc> | head -5 | python3 -c "json.loads(line)"
  └─ docker compose down -v
```

This job runs only on `workflow_dispatch` with `run_slow_checks: true` (same gate as migrations
and integration tests) — keeps the fast path (push → prechecks → unit) under 5 minutes.

#### ECS Task Definition for `processor`

After Phase 10.4, processor exposes port 8002. The ECS task definition must add:
- `portMappings: [{containerPort: 8002, protocol: tcp}]`
- `healthCheck.command: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health', timeout=5)\""]`

The `cd-deploy.yml` workflow resolves ECS service names from GitHub vars at deploy time.
No workflow logic changes — only the task definition template (in Terraform/CDK, Phase 13)
or the ECS task definition JSON needs the new port. Document the requirement here; actual
infrastructure change tracked as Phase 13.

---

### Steps

**Phase 11.0: Path filter alignment**

1. In `ci.yml` `change-impact` job, verify `processor_change` filter includes
   `services/processor/pyproject.toml` — add if missing. This ensures a dep bump
   (e.g., adding `fastapi>=0.135`) triggers the processor build path.

**Phase 11.1: Compose smoke-test job**

2. Add `compose-smoke-test` job to `ci.yml` under Wave 4+ slow-check gate
   (`if: ${{ github.event_name == 'workflow_dispatch' && inputs.run_slow_checks }}`);
   `needs: [prechecks, unit, change-impact]`
3. Job steps:
   - `docker compose build` using repo-root `docker-compose.yml`
   - `docker compose up -d`
   - Retry loop: for each port in `8000 8001 8002 8003 8005`, poll
     `http://localhost:$PORT/readyz` every 5s up to 90s; fail job if any service
     does not return `200` within timeout
   - Assert response body contains `"status"` key (basic shape check)
   - `docker compose logs` per service: pipe first 10 lines through
     `python3 -c "import sys,json; [json.loads(l) for l in sys.stdin if l.strip()]"`;
     fail job if any service emits non-JSON
   - `docker compose down -v` in `if: always()` step
4. Add job to `ci.yml` job dependency graph so `release-preflight` needs it:
   `needs: [compose-smoke-test]` on the slow path.

**Phase 11.2: JSON log schema assertion**

5. Extend the log validation in step 3 to also assert required fields per line:
   `service`, `level`, `message` — using inline Python; fail on missing field.
   This enforces the logging contract from Phase 10's Structured JSON Logging Architecture.

**Phase 11.3: `cd-deploy.yml` documentation update**

6. Add an inline comment block to `cd-deploy.yml` above the `processor` case in the
   `resolve` step noting that processor now exposes port `8002` and requires
   `portMappings + healthCheck` in the ECS task definition. This makes the gap visible
   to anyone modifying the deploy workflow before Phase 13 (Terraform) closes it.

**Phase 11.4: `release-preflight.yml` service coverage**

7. Add an optional step to `release-preflight.yml`: if target environment is `prod`,
   check that all 5 service image URIs exist in ECR before proceeding (prevents
   deploy with a missing image). This is a no-op locally and in dev; blocks prod
   releases from proceeding without a full image set.

---

### Relevant Files

- `.github/workflows/ci.yml` — add `compose-smoke-test` job; verify processor path filter
- `.github/workflows/cd-deploy.yml` — add documentation comment for processor port 8002
- `.github/workflows/release-preflight.yml` — add image existence gate for prod releases
- `docker-compose.yml` — must have `8002:8002` port binding for processor (Phase 10.4 step 18)

---

### Verification

```bash
# Trigger slow-checks manually
gh workflow run ci.yml -f run_slow_checks=true -f run_docker_build=false

# Expect:
# compose-smoke-test job: PASS
# All 5 services: readyz 200
# All 5 services: JSON log lines parseable

# Verify processor port filter fires on pyproject.toml change
git stash
echo " " >> services/processor/pyproject.toml
git add services/processor/pyproject.toml
gh workflow run ci.yml  # processor_change should be true in change-impact output

# Manual path-filter smoke test (local)
# Verify the 5-service health loop locally:
docker compose up -d --build
for port in 8000 8001 8002 8003 8005; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port/readyz")
  echo "port $port: $code"
done
docker compose down -v
```

---

### Decisions

- **Slow-check gate only**: Compose smoke-test adds ~5 minutes (build + startup + teardown);
  gating on `workflow_dispatch + run_slow_checks` keeps the fast PR path under 5 minutes
- **JSON log assertion in CI**: Enforces the Phase 10 logging contract mechanically;
  any service reverting to `basicConfig` will break the job
- **Port 8002 in cd-deploy.yml as documentation only**: Actual ECS task definition update
  is infrastructure code (Terraform/CDK) — Phase 13 scope; Phase 11 documents the requirement

---

### Out of Scope

- Terraform / CDK task definition update for processor port 8002 (Phase 13)
- Kubernetes manifest liveness/readiness probes (Phase 12)
- Contract versioning CI (already implemented in ci.yml contracts-versioning-gate job)
