## Plan: Revise All Service Dockerfiles (v3)

Audit found 3 critical bugs, multiple security issues, and inconsistent patterns across 4 service Dockerfiles. Standardize on multi-stage `builder → final`, non-root users, `UV_LINK_MODE=copy`, service-scoped `pyproject.toml` with uv workspaces, Python stdlib health checks, and fix `.dockerignore`.

---

### Critical Findings (fix regardless of anything else)

**Bug 1 — `.dockerignore` excludes `alembic/versions/`**
`COPY alembic/ ./alembic/` in ingestor Dockerfile, but `.dockerignore` strips all migration `.py` files. Container cannot run `alembic upgrade head`. Migration runner is silently broken.

**Bug 2 — `analytics` HEALTHCHECK calls `requests` (not installed)**
`python -c "import requests; ..."` — service uses `httpx`, not `requests`. Health check always fails silently.

**Bug 3 — docker-compose healthchecks use `curl` which is absent from slim images**
`inference`, `dashboard`, `analytics` docker-compose healthchecks call `curl`. `python:3.14-slim` does not ship curl. All three checks fail silently from first container start.

---

### Architecture Decision: HEALTHCHECK Paradigm

Production orchestrators do NOT run health checks inside the container:

| Platform | Who checks | Tool needed in image | Dockerfile HEALTHCHECK |
|---|---|---|---|
| Kubernetes | kubelet (external HTTP) | nothing | completely ignored |
| Cloud Run / ACA / App Runner | platform HTTP probe | nothing | completely ignored |
| ECS / Docker Swarm | Docker daemon (exec inside) | tool must exist | used |
| Docker Compose | Docker daemon (exec inside) | tool must exist | used |

K8s uses `livenessProbe` / `readinessProbe` / `startupProbe` in the pod spec — all `httpGet`, no exec, no tools required in the container.

**Decision: Python stdlib `urllib.request` everywhere for Dockerfile + docker-compose; `httpGet` probe in K8s pod spec when Phase 7 (Terraform/ECS) arrives.**

Pattern for Dockerfiles:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:PORT/health', timeout=5)"
```

Pattern for docker-compose:

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:PORT/health', timeout=5)"]
```

Use `http://127.0.0.1` (not `localhost`) — avoids `/etc/hosts` lookup and IPv6 fallback latency.
Zero image bloat. Already available in every Python image.

---

### Architecture Decision: Dependency Lock — Use `uv.lock` as Single Source of Truth

Do NOT add `[tool.uv] exclude-newer` to any `pyproject.toml`. Do NOT use `ARG UV_EXCLUDE_NEWER`.

**Strategy:**
- `pyproject.toml` uses `>=` version ranges (flexible, expresses intent)
- `uv.lock` is the immutable source of truth (reproducible builds)
- Local dev config: `~/.config/uv/uv.toml` has `exclude_newer = "7 days"` (controls freshness locally)
- All builds (Docker, CI, local): `uv sync --frozen` reads from `uv.lock`
- **Never regenerate `uv.lock` in CI** — only via `uv lock --upgrade` locally after testing

All Dockerfiles simplify to:
```dockerfile
RUN uv sync --package <service_name> --no-dev
```

No build args. No conditional logic. Pure determinism from `uv.lock`.

---

### Architecture Decision: uv Workspaces

Root `pyproject.toml` becomes the workspace root. Add:

```toml
[tool.uv.workspace]
members = ["services/inference", "services/dashboard", "services/processor", "services/analytics"]
```

Remove from root `dependencies`: `sentence-transformers`, `qdrant-client` (→ inference), `jinja2`, `python-multipart` (→ already in dashboard pyproject.toml). Keep: `aiokafka`, `motor`, `playwright`, `beautifulsoup4` (used by ingestor directly).

Local dev: `uv sync --all-packages` → one `.venv`.
Docker build: `uv sync --package SERVICE_NAME --no-dev` → lean image.

---

### Architecture Decision: Dependabot Docker

Existing `dependabot.yml` already has `package-ecosystem: docker` with `directory: "/"`. Dependabot scans recursively — covers `Dockerfile` (root) and all `services/*/Dockerfile`. No new entries needed.

---

### Steps

**Phase 0: `.dockerignore` surgery** *(unblock first — no service rebuild needed)*

1. Remove `alembic/versions/` — unblocks migration runner in ingestor *(critical)*
2. Add missing exclusions: `_archive/`, `.git/`, `.github/`, `docs/`, `secrets-findings.json`, `CV.md`

**Phase 1: Per-service `pyproject.toml` files** *(prerequisite for Phases 3–6)*

3. Create `services/inference/pyproject.toml` — deps with `>=` constraints: `fastapi>=0.135`, `uvicorn[standard]>=0.34`, `pydantic>=2.13`, `sentence-transformers>=5.4`, `qdrant-client>=1.12`; no `[tool.uv]` section (exclude-newer via ARG)
4. Create `services/processor/pyproject.toml` — deps: `aiokafka>=0.11`, `opentelemetry-sdk>=1.41`, `opentelemetry-exporter-otlp>=1.41`, `opentelemetry-instrumentation>=0.46b0`
5. Create `services/analytics/pyproject.toml` — deps: `fastapi>=0.135`, `uvicorn[standard]>=0.45`, `sqlalchemy[asyncio]>=2.0`, `asyncpg>=0.30`, `python-json-logger>=4.1`
6. Update `services/dashboard/pyproject.toml` — already has correct `>=` deps; no changes needed unless workspace member declaration requires it

**Phase 2: Root `pyproject.toml` — uv workspace** *(depends on Phase 1)*

7. Add `[tool.uv.workspace]` section with 4 service members
8. Remove from root `dependencies`: `sentence-transformers`, `qdrant-client`, `jinja2`, `python-multipart`
9. Verify `uv sync --all-packages` resolves cleanly for localhost dev

**Phase 3: `inference/Dockerfile` — Full rewrite** *(depends on step 3)*

10. Builder stage: keep `build-essential` + `libopenblas-dev`; add `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`; `uv sync --package inference --no-dev --no-install-project`
11. Final stage: `libopenblas0` runtime only (~20 MB vs 300 MB build tools); copy `.venv` from builder; non-root `appuser:appgroup (1001:1001)`; `PYTHONUNBUFFERED=1`; `ENV PATH="/app/.venv/bin:$PATH"`
12. HEALTHCHECK: `CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5)"`
13. Replace existing `CMD ["uvicorn", ...]` with `CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]`

**Phase 4: `dashboard/Dockerfile` — Multi-stage + non-root** *(depends on step 6)*

14. Builder stage: `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`; `uv sync --package dashboard --no-dev --no-install-project`
15. Final stage: non-root `appuser:appgroup (1001:1001)`; copy `.venv` from builder; `EXPOSE 8003`; `PYTHONUNBUFFERED=1`; `ENV PATH="/app/.venv/bin:$PATH"`
16. Replace `CMD ["uv", "run", "uvicorn", ...]` → `CMD ["/app/.venv/bin/uvicorn", ...]`
17. HEALTHCHECK: `CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/health', timeout=5)"`

**Phase 5: `analytics/Dockerfile` — Fix root user + healthcheck + deps** *(depends on step 5)*

18. Builder stage: add `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`; replace `uv pip install --system -e .` with `uv sync --package analytics --no-dev --no-install-project`
19. Final stage: add non-root `appuser:appgroup (1001:1001)` *(critical security fix)*; replace `COPY site-packages` → `COPY --from=builder /app/.venv /app/.venv`; `EXPOSE 8005`
20. Remove `-e` flag entirely (editable installs break in multi-stage — source directory not copied to final)
21. HEALTHCHECK: `CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8005/health', timeout=5)"` *(fixes Bug 2)*

**Phase 6: `processor/Dockerfile` — Minor fixes** *(depends on step 4)*

22. Builder stage: add `UV_LINK_MODE=copy`; switch to `uv sync --package processor --no-dev --no-install-project` (4 packages instead of 50+)
23. HEALTHCHECK: processor has no HTTP endpoint — use process liveness `CMD python -c "import sys; sys.exit(0)"` as heartbeat, or omit and rely on restart policy

**Phase 7: `Dockerfile` (ingestor) — Minor alignment** *(independent)*

24. Builder stage: add `UV_LINK_MODE=copy`; ensure `uv sync --no-dev --frozen --no-install-project`
25. Align Python digest: `sha256:5b3879b6...` (ingestor) vs `sha256:bc389f7d...` (services) — standardize to one (run `docker buildx imagetools inspect python:3.14-slim` to get current, update all)

**Phase 8: `docker-compose.yml` fixes** *(independent)*

26. Replace all `curl`-based healthchecks with Python stdlib pattern for `inference`, `dashboard`, `analytics` *(fixes Bug 3)*
26a. Also fixed `ingestor` healthcheck (same Bug 3 — originally out of scope, fixed alongside Phase 8)
27. Add `develop.watch` to `processor` service (only service currently missing it): `action: sync+restart`, `path: ./services/processor`, `target: /app/services/processor`

**Phase 9: SHA maintenance script** *(new tooling)*

28. Create `scripts/update-base-image-digest.sh` — runs `docker buildx imagetools inspect python:3.14-slim`, parses the digest, `sed -i` replaces old digest in all Dockerfiles in one pass

---

### Relevant Files

- `.dockerignore` — remove `alembic/versions/`, add missing exclusions *(Bug 1 fix)*
- `services/inference/Dockerfile` — full rewrite (multi-stage, non-root, stdlib healthcheck, ARG UV_EXCLUDE_NEWER)
- `services/inference/pyproject.toml` — create with `>=` deps
- `services/dashboard/Dockerfile` — multi-stage + non-root + CMD fix + stdlib healthcheck
- `services/dashboard/pyproject.toml` — exists; no changes needed
- `services/processor/Dockerfile` — add `UV_LINK_MODE=copy`, `ARG UV_EXCLUDE_NEWER`; switch to package-scoped sync
- `services/processor/pyproject.toml` — create with 4 deps
- `services/analytics/Dockerfile` — non-root + `.venv` copy + stdlib healthcheck + remove `-e`
- `services/analytics/pyproject.toml` — create with slim deps
- `Dockerfile` — add `UV_LINK_MODE=copy`, `ARG UV_EXCLUDE_NEWER`; align Python digest
- `pyproject.toml` — add `[tool.uv.workspace]`, remove 2 service-specific dep entries
- `docker-compose.yml` — fix 3 curl healthchecks → stdlib; add `develop.watch` to processor
- `scripts/update-base-image-digest.sh` — create SHA maintenance script
- `.github/dependabot.yml` — no changes needed

---

### Verification

**Local builds (deterministic from `uv.lock`):**

```bash
# inference only
docker compose build inference

# dashboard only
docker compose build dashboard

# analytics only
docker compose build analytics

# processor only
docker compose build processor

# all services
docker compose build

# all services + ingestor
docker compose build && docker build -f Dockerfile .
```

**CI builds (same as local — both use `uv.lock`):**

No build-arg passing needed. All builds read deterministically from `uv.lock`.

```bash
# inference
docker compose build inference

# dashboard
docker compose build dashboard

# analytics
docker compose build analytics

# processor
docker compose build processor

# ingestor (root Dockerfile)
docker build -f Dockerfile .

# all services at once
docker compose build
```

**Upgrading dependencies (controlled via `uv lock --upgrade`):**

```bash
# On local dev machine, update lock file
uv lock --upgrade

# Test thoroughly, then commit uv.lock
git add uv.lock
git commit -m "chore: update dependencies"

# CI and all downstream builds automatically use new versions from uv.lock
```

**Runtime tests:**

1. Healthchecks: `docker compose up --build` → `docker compose ps` — all app services show `healthy`
2. Non-root: `docker run --rm data-pipeline-async-inference id` — output shows `uid=1001(appuser) gid=1001(appgroup)`
3. Migrations included: `docker run --rm data-pipeline-async ls /app/alembic/versions/` — shows `.py` files *(Bug 1 verified)*
4. Deterministic from lock: `docker compose build inference` uses exact versions from `uv.lock` every time
5. Code sync: `docker compose watch` — change in `services/processor/main.py` triggers auto-restart
6. Workspace resolution: `uv sync --all-packages` on localhost — single `.venv` resolves 188 packages (4 workspace members + root)
7. Service-scoped sync: `uv sync --package inference --no-dev` — installs only 5 packages (inference deps)

---

### Decisions

- **Python stdlib urllib for all health checks**: zero image bloat, consistent across Dockerfile and docker-compose, forward-compatible with K8s (`httpGet` probe ignores Dockerfile HEALTHCHECK entirely)
- **`http://127.0.0.1` not `http://localhost`**: avoids `/etc/hosts` lookup and IPv6 fallback; deterministic
- **`uv.lock` as source of truth**: All builds deterministic; no build-args needed; freshness controlled via `~/.config/uv/uv.toml` on dev machine; `uv lock --upgrade` for upgrades
- **uv workspaces**: lean Docker images per-service + one localhost `.venv` via `--all-packages`; root loses 2 dep entries
- **dependabot.yml**: existing `docker` entry with `directory: "/"` already scans all service Dockerfiles recursively; no new entries needed
- **Out of scope**: application logic, docker-compose network topology, CI workflow jobs

---

### Critical Highlights (final)

| Severity | Issue | File |
|---|---|---|
| CRITICAL | `alembic/versions/` excluded — migration runner broken | `.dockerignore` |
| CRITICAL | HEALTHCHECK uses `requests` (not installed) — always fails | `analytics/Dockerfile` |
| CRITICAL | `curl` in 3 docker-compose healthchecks, not in slim images — all fail | `docker-compose.yml` |
| HIGH | No non-root user | `inference`, `dashboard`, `analytics` Dockerfiles |
| HIGH | Single-stage — 300 MB+ build tools in final image | `inference`, `dashboard` |
| HIGH | Editable `-e` in multi-stage — source not in final stage, imports fail | `analytics/Dockerfile` |
| MEDIUM | `UV_LINK_MODE=copy` + `UV_COMPILE_BYTECODE=1` missing — hardlink/startup errors | all services + ingestor |
| MEDIUM | `processor` missing `develop.watch` | `docker-compose.yml` |
| MEDIUM | Full monorepo deps (50+) in lightweight services | `processor`, `analytics` |
| MEDIUM | Stale inline dep pinning (2023 versions, no lockfile) | `inference/Dockerfile` |
| LOW | Python digest mismatch between ingestor and services | `Dockerfile` vs service Dockerfiles |
