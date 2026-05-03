# Monorepo Microservice Restructure (Pre-Phase 15)

**TL;DR**: Five phases (0–4). Phase 0 establishes the import convention that makes all subsequent renames safe. Phase 1 (high risk) moves `ingestor/` under `services/`. Phase 2 (medium) renames `ai_gateway` → `inference` and `query_api` → `analytics` — full dir + module rename, using a shim bridge. Phases 3–4 are skeletons + governance.

**What does NOT change**: single `uv.lock`, root `pyproject.toml` tooling, root `alembic/`, `libs/` at root, single Git repository.

---

## Repo State (confirmed, Phase 14 complete)

| Inconsistency | Location |
|---|---|
| `ingestor/` lives at repo root, not under `services/` | Breaks team-per-service symmetry |
| Compose keys use hyphens (`ai-gateway`, `query-api`) but dirs use underscores (`ai_gateway`, `query_api`) | Mixed naming conventions |
| `query-api` develop.watch path is `./services/query-api` but actual dir is `services/query_api` | Active bug — hot-reload broken |
| No CODEOWNERS file | No ownership mapping |
| All tests in root `tests/` | Not co-located with services |
| `check_service_boundaries.py` maps `ingestor` to `REPO_ROOT / "ingestor"` | Will need updating in Phase 1 |

Already consistent — no change needed:
- All `services/` subdirs already use underscores (`ai_gateway`, `query_api`, `processor`, `dashboard`, `webhook`)
- All 5 services in `services/` already have Dockerfiles and `pyproject.toml`

---

## Target directory shape post-restructure

```
services/
├── ingestor/      ← write-side CQRS, Postgres owner
├── inference/     ← AI vendor adapter (embeddings + LLM)
├── analytics/     ← read-side CQRS, materialized views
├── processor/     ← Kafka enrichment consumer
├── dashboard/     ← UI
└── webhook/       ← inbound webhooks
```

---

## Phase 0 — Intra-Service Import Convention + Registry *(no risk, do first)*

> Microservices communicate over the network (HTTP, Kafka) — never via Python imports across service boundaries. `check_service_boundaries.py` already enforces this at CI time. The convention below is about keeping each service's *own internal* structure clean as it grows.

The "single control center" for imports — a triad, no new files needed:

**1. `__init__.py` as the service's intra-service public surface** — re-export everything other modules *within the same service* need from the package root. This prevents internal import churn as the service grows:

```python
# CORRECT — ingestor/routers/records.py importing from its own service
from ingestor.crud import get_record, create_record
from ingestor.schemas import RecordResponse

# WRONG — brittle if crud.py is split into crud/records.py later
from ingestor.crud.records import get_record
```

When `crud.py` gets split into submodules, only `ingestor/__init__.py` (or `crud/__init__.py`) needs updating — every router stays unchanged. Payoff scales with service size.

**2. Compatibility shim pattern for directory renames** — when renaming a package dir, leave the old `__init__.py` as a one-commit bridge before removing it:

```python
# services/ai_gateway/__init__.py — temporary shim, remove in next commit
from services.inference import *  # noqa: F401, F403
```

This decouples "rename the dir" from "update all internal callers" into separate, safe commits.

**3. `SERVICE_ROOTS` in `check_service_boundaries.py` as the canonical service registry** — it already exists; make it authoritative. All tooling (CI, CODEOWNERS generation, future scripts) derives service names/paths from it. Rename a service = update `SERVICE_ROOTS` first.

**Action for Phase 0:** audit each service's `__init__.py` — ensure intra-service imports go through the package root, not deep into submodule paths. No cross-service Python imports should exist; if any are found during Phase 1 grep, treat as bugs to delete (replace with HTTP client calls).

---

## Phase 1 — Move `ingestor/` → `services/ingestor/` *(high risk, single atomic commit)*

1. `git mv ingestor/ services/ingestor/`
2. `Dockerfile` (root): `COPY ingestor/ → COPY services/ingestor/`; CMD `ingestor.main:app → services.ingestor.main:app`
3. `alembic/env.py`: 3 import lines — `ingestor.models`, `ingestor.config`, `ingestor.database` → `services.ingestor.*`
4. `docker-compose.yml` ingestor service: develop.watch `./ingestor → ./services/ingestor`
5. `pyproject.toml`: `--cov=ingestor → --cov=services/ingestor`; `source = ["ingestor"] → ["services.ingestor"]`; `[[tool.ty.overrides]] include` — replace `"ingestor"` with `"services/ingestor"`
6. `scripts/ci/check_service_boundaries.py`: `SERVICE_ROOTS["ingestor"] = REPO_ROOT / "services" / "ingestor"`
7. `.github/workflows/ci.yml`: path filter `ingestor/** → services/ingestor/**`
8. All absolute imports inside `ingestor/` itself: `from ingestor.X → from services.ingestor.X` (relative imports within the package unchanged)
9. All `tests/**/*.py`: `from ingestor.X → from services.ingestor.X` and `import ingestor.X → import services.ingestor.X`

**Verification:** `uv run pytest tests/ -q`; `uv run ruff check .`; `docker compose build ingestor`; `uv run alembic heads`

---

## Phase 2 — Full Service Renames: Dirs + Modules + Compose *(medium risk)*

**Final names** — suffix-free, domain-signal nouns:

| Old dir/module | New dir/module | Rationale |
|---|---|---|
| `ai_gateway` | `inference` | Covers embeddings + future /chat, /prompt. No collision with API Gateway pattern. |
| `query_api` | `analytics` | Matches existing `analytics.py` router. CQRS read-side domain signal. |

**Pre-step** — bound the cross-service import surface before starting:

```bash
grep -r "from services\.ai_gateway\|from services\.query_api" --include="*.py" .
```

**Steps:**

1. `git mv services/ai_gateway/ services/inference/` and `git mv services/query_api/ services/analytics/`
2. Add shim `__init__.py` at old paths re-exporting from new locations (one-commit bridge)
3. `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.prod-like.yml`: keys `ai-gateway → inference`, `query-api → analytics`; fix broken watch path `./services/query-api → ./services/analytics`
4. `infra/nginx.conf`: update upstream block names
5. `scripts/ci/check_service_boundaries.py`: `SERVICE_ROOTS` keys `"inference"`, `"analytics"`; remove old keys
6. `.github/workflows/ci.yml`: path filters updated to `services/inference/**`, `services/analytics/**`
7. Update all Python imports: `from services.ai_gateway.X → from services.inference.X`; `from services.query_api.X → from services.analytics.X` (shim covers callers during transition)
8. Remove shims

**Verification:** `docker compose config` exits 0; `uv run ruff check .`; `uv run pytest -q`; `uv run python scripts/ci/check_service_boundaries.py`

---

## Phase 3 — Per-Service Skeletons + Test Co-location *(medium risk, incremental per service)*

### 3a. README.md per service

Add to: `services/ingestor/`, `services/inference/`, `services/analytics/`, `services/processor/`, `services/dashboard/`, `services/webhook/`

Minimum content: service purpose, port, key env vars, `docker compose up <name>`, how to run its tests.

### 3b. Validate `pyproject.toml` metadata

All 5 existing `services/*/pyproject.toml` files already exist — verify each has a `[project]` metadata section (name, version, description). Add to `services/ingestor/` after Phase 1. No separate dependency resolution — deps stay at root. These act as namespace markers and future extraction points.

### 3c. Migrate tests into services

| From | To |
|---|---|
| `tests/unit/records/`, `tests/integration/records/` | `services/ingestor/tests/` |
| `tests/unit/auth/`, `tests/unit/core/`, `tests/unit/storage/`, `tests/unit/settings/` | `services/ingestor/tests/unit/` |
| `tests/unit/test_cache*.py`, `tests/unit/test_redis_lock.py`, `tests/unit/test_internal_auth.py` | `services/ingestor/tests/unit/` |
| `tests/unit/test_webhook_api_keys.py`, `tests/integration/webhook/` | `services/webhook/tests/` |
| `tests/unit/dashboard/`, `tests/integration/dashboard/` | `services/dashboard/tests/` |
| `tests/unit/query_api/` | `services/analytics/tests/` |

Root `tests/` keeps: `conftest.py` (shared fixtures), `shared/` (payloads, factories), `e2e/` (cross-service tests), `integration/schema/` (cross-service schema tests).

**Config changes:**
- `pyproject.toml`: `testpaths = ["tests", "services/*/tests"]`
- `check_service_boundaries.py`: add co-located test exemption — service tests may import their own service

**Verification:** `uv run pytest -q` passes with new testpaths; coverage report shows `services/ingestor` source

---

## Phase 4 — Governance Layer *(low risk)*

1. `.github/CODEOWNERS`: map `services/<name>/` to placeholder `@org/team-*`

   ```
   services/ingestor/   @org/team-ingestor
   services/inference/  @org/team-ai
   services/analytics/  @org/team-query
   services/processor/  @org/team-processor
   services/dashboard/  @org/team-dashboard
   services/webhook/    @org/team-webhook
   libs/                @org/platform-team
   ```

2. `docs/monorepo-structure.md`: single-uv.lock rationale, why `alembic/` stays at root, how to add a new service, path to repo extraction

3. Final pass on `check_service_boundaries.py`: verify `ingestor` path post-Phase 1, document test co-location exemption

4. `.github/workflows/ci.yml`: add `inference` and `analytics` change-detection path filter jobs if missing

**Verification:** `uv run python scripts/ci/check_service_boundaries.py` exits 0; CODEOWNERS syntax valid

---

## Future design decisions (deferred, not in this restructure)

- **Adding /chat, /prompt to `inference`**: start co-located; split only when chat needs its own DB or different team ownership
- **New processor-like consumers**: create new services with separate Kafka consumer groups; name by domain role (`notifier`, `archiver`, `scorer`) — never by index (`processor-2`)
- **Service mesh / service discovery**: not needed until K8s autoscaling or mTLS requirement; current env-var + Compose DNS is sufficient

---

## Migration order & risk

| Phase | Risk | Constraint |
|---|---|---|
| 0 — facade convention | None | Do before any rename; audit cross-service imports |
| 1 — move ingestor | High | Single atomic commit; full test suite must pass before merge |
| 2 — full renames (dirs + modules + compose) | Medium | Grep cross-service surface first; shim pattern |
| 3 — skeletons + tests | Medium | Incremental per service; do not merge partial test moves |
| 4 — governance | Low | Docs + CODEOWNERS only |
