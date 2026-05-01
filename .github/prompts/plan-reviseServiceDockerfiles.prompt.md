## Plan: Revise All Service Dockerfiles

Audit found 2 critical bugs, multiple security issues, and inconsistent patterns across 4 service Dockerfiles. The approach: standardize on multi-stage `builder → final` pattern, non-root user in all final stages, `UV_LINK_MODE=copy`, service-scoped `pyproject.toml` where needed, and fix the `.dockerignore` critical exclusion.

---

### Critical Findings (fix regardless of anything else)

**Bug 1 — `.dockerignore` excludes `alembic/versions/`**
The ingestor `Dockerfile` does `COPY alembic/ ./alembic/` but `.dockerignore` has `alembic/versions/` — meaning all migration `.py` files are excluded from the image. The container cannot run `alembic upgrade head` or verify schema revision. The migration runner is silently broken.

**Bug 2 — `query_api` health check calls `requests`**
`HEALTHCHECK` runs `python -c "import requests; ..."` but `requests` is not in the service's dependencies (it uses `httpx`). The health check always fails silently on a fresh container start.

---

### Steps

**Phase 0: `.dockerignore` surgery** *(no service impact, unblock first)*

1. Remove `alembic/versions/` exclusion — unblocks migration runner in ingestor image *(critical fix)*
2. Add missing exclusions that inflate build context sent to Docker daemon:
   - `_archive/`, `.git/`, `.github/`, `docs/`, `secrets-findings.json`, `CV.md`
   - `*.json` at root (e.g., `secrets-findings.json`)
3. Fix `Dockerfile*` exclusion — currently excludes all Dockerfiles from context including service ones; this is fine since they're never `COPY`'d, but add a note

**Phase 1: `ai_gateway/Dockerfile` — Full rewrite** *(independent)*

4. Split into 2 stages: `builder` and `final`
5. In `builder`: keep `build-essential` + `libopenblas-dev` for compiling numpy/sentence-transformers; add `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`; install via `uv sync` from a service-level `pyproject.toml`
6. In `final`: only `libopenblas0` (runtime, not build, ~20MB vs ~300MB); copy `.venv` from builder; create non-root `appuser:appgroup (1001:1001)`; set `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`
7. Requires creating `services/ai_gateway/pyproject.toml` with pinned but current versions of: `fastapi`, `uvicorn[standard]`, `pydantic`, `sentence-transformers`, `qdrant-client` — current inline-pinned versions are from 2023 (`fastapi==0.104.1`, `pydantic==2.5.0`); these need updating.
8. HEALTHCHECK already exists, keep as-is

**Phase 2: `dashboard/Dockerfile` — Multi-stage + non-root** *(independent)*

9. Add `builder` stage with `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy`; run `uv sync --no-dev --frozen`
10. Add `final` stage: non-root user, copy `.venv` from builder, copy `services/dashboard/` source
11. Replace `CMD ["uv", "run", "uvicorn", ...]` with `CMD ["/app/.venv/bin/uvicorn", ...]` — uv not needed at runtime
12. Add `EXPOSE 8003`
13. Add `HEALTHCHECK` using `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health')"` — docker-compose has one but Dockerfile HEALTHCHECK is defense-in-depth
14. Add `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1`; `ENV PATH="/app/.venv/bin:$PATH"`

**Phase 3: `query_api/Dockerfile` — Fix root user + dep strategy** *(independent)*

15. Add non-root user `appuser:appgroup (1001:1001)` in final stage *(critical security fix)*
16. Replace `COPY site-packages` approach with `.venv` copy — current approach breaks on Python minor version changes; use `uv sync --venv .venv` in builder and `COPY --from=builder /app/.venv /app/.venv`
17. Remove `-e` (editable install flag) — editable installs in containers create `.pth` symlink files to source directories; after multi-stage copy only the `.venv` exists, source is gone, import fails
18. Fix HEALTHCHECK: replace `requests.get(...)` with `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')"` OR add `curl` to final stage
19. Add `EXPOSE 8005`
20. Add `UV_COMPILE_BYTECODE=1`, `UV_LINK_MODE=copy` to builder
21. Recommendation: create `services/query_api/pyproject.toml` with only `fastapi`, `sqlalchemy[asyncio]`, `asyncpg`, `uvicorn[standard]`, `python-json-logger` — current setup installs the entire monorepo (aiokafka, playwright, mongodb drivers, etc.) into query_api

**Phase 4: `processor/Dockerfile` — Minor fixes** *(independent)*

22. Add `UV_LINK_MODE=copy` to builder *(prevents hardlink warnings in Docker)*
23. Recommendation: create `services/processor/pyproject.toml` with only `aiokafka`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `opentelemetry-instrumentation` — current setup installs ALL monorepo deps (~50+ packages) for a service that only needs ~4
24. Add `HEALTHCHECK` — for a Kafka consumer with no HTTP, use a process liveness check: `CMD ["python", "-c", "import sys; sys.exit(0)"]` or skip and rely on restart policy; docker-compose has no healthcheck for processor

**Phase 5: `Dockerfile` (ingestor) — Minor alignment** *(independent)*

25. Add `UV_LINK_MODE=copy` to builder stage (currently missing)
26. Verify digest `sha256:5b3879b6...` is the same image as `sha256:bc389f7d...` used by services — they appear different; standardize to one digest across all services

---

### Relevant Files

- `.dockerignore` — remove `alembic/versions/`, add missing exclusions
- `services/ai_gateway/Dockerfile` — full rewrite (multi-stage + non-root)
- `services/ai_gateway/pyproject.toml` — create new file with current dep versions
- `services/dashboard/Dockerfile` — multi-stage + non-root + CMD fix
- `services/processor/Dockerfile` — add `UV_LINK_MODE=copy`; optionally create `pyproject.toml`
- `services/query_api/Dockerfile` — non-root user + fix site-packages copy + fix health check
- `Dockerfile` — add `UV_LINK_MODE=copy`; align Python digest
- Optionally create: `services/processor/pyproject.toml`, `services/query_api/pyproject.toml`

---

### Verification

1. `docker build -f services/ai_gateway/Dockerfile .` — builds without error, image size < 1.2GB (sentence-transformers is heavy)
2. `docker build -f services/dashboard/Dockerfile .` — builds, `docker run` starts process as `appuser` (`docker inspect` shows user = 1001)
3. `docker build -f services/query_api/Dockerfile .` — health check passes on container start
4. `docker build -f services/processor/Dockerfile .` — builds without hardlink warnings
5. `docker build .` (ingestor) — `alembic/versions/` is present inside image (`docker run ... ls /app/alembic/versions/`)
6. `docker compose up ingestor` — `alembic upgrade head` would not fail with "no such file" errors

---

### Decisions

- `ai_gateway/pyproject.toml` creation: required to move away from inline pinned deps; deps need version-bumping (2023 → 2026)
- Service-specific `pyproject.toml` for processor/query_api: strongly recommended to keep images lean; each service needs ~4-6 packages, not 50+
- Ingestor digest mismatch: `5b3879b6` (ingestor) vs `bc389f7d` (services) — both are `python:3.14-slim` but different pull-times; standardize to one
- Out of scope: changing application logic, docker-compose topology, CI workflows

---

### Critical Highlights

| Severity | Issue | File |
|---|---|---|
| CRITICAL | `alembic/versions/` excluded — migration runner broken | `.dockerignore` |
| CRITICAL | Health check uses `requests` (not installed) — always fails | `query_api/Dockerfile` |
| HIGH | No non-root user — runs as root | `ai_gateway`, `dashboard`, `query_api` |
| HIGH | Single-stage — build tools (300MB+) in final image | `ai_gateway`, `dashboard` |
| HIGH | Editable `-e` install in multi-stage — source not copied, imports fail | `query_api` |
| MEDIUM | `UV_LINK_MODE=copy` missing — hardlink errors across layer boundaries | all services + ingestor |
| MEDIUM | Full monorepo deps in lightweight services — 50+ packages for 4 needed | `processor`, `query_api` |
| MEDIUM | Inline stale dep pinning (2023 versions) — no lockfile reproducibility | `ai_gateway` |
