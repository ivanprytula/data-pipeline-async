# Environment Configuration Strategy

> **Before you start:** See [system-requirements.md](system-requirements.md) for required system packages (PostgreSQL, MongoDB, Docker tools).

This document explains how environment variables are managed across development, CI/CD, and deployed environments.

---

## Strategy Overview

### Local Development

**File**: `.env` in project root
**Priority**: Low (overridden by any env vars already set)
**Usage**: `python-dotenv` loads `.env` file automatically when tests run

```bash
# .env file (local development only)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline
DATABASE_URL_TEST=postgresql+asyncpg://postgres:postgres@localhost:5433/test_database
```

**Start services + tests:**

```bash
bash scripts/dev_services.sh  # Starts all services (services use Docker networking)
uv run pytest tests/ -v       # Tests load .env automatically → uses DATABASE_URL_TEST
```

### CI/CD Pipeline (GitHub Actions, etc.)

**File**: None (`.env` not in repo)
**Priority**: High (secrets injected by CI system)
**Usage**: GitHub Actions injects secrets as environment variables

```yaml
# .github/workflows/test.yml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL_TEST }}
  REDIS_URL: ${{ secrets.REDIS_URL }}

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_PASSWORD: ${{ secrets.TEST_DB_PASSWORD }}
```

**What happens in CI:**

1. `pytest` runs, `conftest.py` calls `load_dotenv()`
2. `.env` file doesn't exist in CI container → `load_dotenv()` is a no-op
3. Environment variables already set by GitHub Actions are used
4. No conflicts; CI vars have priority

### Deployed Environments (AWS ECS, Kubernetes, etc.)

**File**: None (`.env` not deployed)
**Priority**: High (secrets from secrets manager)
**Usage**: Secrets manager injects env vars into application container

```yaml
# Kubernetes secret (example)
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
data:
  DATABASE_URL: <base64-encoded-production-db-url>
  REDIS_URL: <base64-encoded-production-redis-url>
```

**What happens on deployment:**

1. Application starts with secrets injected by orchestrator
2. `conftest.py` (in tests) or `app/config.py` (in app) uses env vars
3. `.env` file doesn't exist → `load_dotenv()` is no-op
4. Application uses secrets from orchestrator

---

## Implementation Details

### For Tests (`tests/conftest.py`)

```python
from dotenv import load_dotenv
from pathlib import Path

# Load .env only if it exists (local development)
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=False)

# override=False: Environment variables set by CI/deployment take precedence
```

**Key points:**

- `override=False`: CI/deployment env vars are NOT overwritten by .env
- Conditional check: Only tries to load if file exists
- Safe in CI: If .env doesn't exist, no error; just a no-op

### For Application (`app/config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    redis_url: str

    class Config:
        env_file = ".env"  # Loaded only if it exists
        env_file_encoding = "utf-8"
```

**Key points:**

- `pydantic-settings` handles `.env` loading automatically
- Returns error if required env var is missing (good for detecting config issues)

---

## Secrets Management Priority

The precedence for environment variables (highest to lowest):

1. **Explicitly exported** (on command line): `DATABASE_URL=... pytest tests/`
2. **CI/Deployment system** (GitHub Actions, Kubernetes, AWS): Injected env vars
3. **.env file** (local development): `load_dotenv()` reads this
4. **Application defaults**: Pydantic `Field(default=...)`

---

## Local Development Workflow

### Setup (one time)

```bash
cp .env.example .env
# Edit .env with local values (db passwords, URLs, etc.)

# Start all services
bash scripts/dev_services.sh

# Install dependencies
uv sync
```

### Run Tests

```bash
# Tests auto-load DATABASE_URL_TEST from .env
uv run pytest tests/ -v

# Specific test file
uv run pytest tests/integration/records/test_query_analysis.py -v
```

### Override Specific Variable

```bash
# CI/deployment env vars override .env
DATABASE_URL=postgresql://... uv run pytest tests/ -v
```

---

## CI/CD Workflow

### GitHub Actions Setup

**Store secrets:**

```bash
gh secret set DATABASE_URL_TEST --body "postgresql+asyncpg://..."
gh secret set REDIS_PASSWORD --body "secret-redis-pass"
```

**Use in workflow:**

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      DATABASE_URL_TEST: ${{ secrets.DATABASE_URL_TEST }}
      REDIS_PASSWORD: ${{ secrets.REDIS_PASSWORD }}
    steps:
      - uses: actions/checkout@v4
      - run: uv sync
      - run: uv run pytest tests/ -v
        # conftest.py will:
        # 1. Check if .env exists (it doesn't in CI) → no-op
        # 2. Use DATABASE_URL_TEST already set by GitHub Actions
```

---

## Deployment Workflow

### AWS ECS Task Definition

```json
{
  "containerDefinitions": [
    {
      "name": "app",
      "secrets": [
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:prod/db-url"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789:secret:prod/redis-url"
        }
      ]
    }
  ]
}
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  template:
    spec:
      containers:
      - name: app
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: redis-url
```

---

## Troubleshooting

### "DATABASE_URL_TEST not set" in Tests

**Symptom**: Tests fail with `pytest.skip("DATABASE_URL_TEST not set")`

**Solution:**

1. Verify `.env` exists:

   ```bash
   ls -la .env
   ```

2. Verify it has `DATABASE_URL_TEST`:

   ```bash
   grep DATABASE_URL_TEST .env
   ```

3. Start test services:

   ```bash
   bash scripts/dev_services.sh
   ```

4. Run tests:

   ```bash
   uv run pytest tests/ -v
   ```

### "Secrets not injected" in CI

**Symptom**: CI tests fail: `Error: DATABASE_URL_TEST not set`

**Solution:**

1. Verify GitHub secret is set:

   ```bash
   gh secret list
   ```

2. Verify workflow uses `${{ secrets.DATABASE_URL_TEST }}`:

   ```yaml
   env:
     DATABASE_URL_TEST: ${{ secrets.DATABASE_URL_TEST }}
   ```

3. Check workflow logs for env var resolution

---

## Docker BuildKit Configuration

BuildKit is required for optimized Dockerfile builds with layer caching, resulting in 3-5x faster rebuild times.

### Option 1: Per-Command (Temporary)

Enable for a single build:

```bash
export DOCKER_BUILDKIT=1
docker build -t ingestor:latest .

# Second build should be 3-5x faster due to cache reuse
docker build -t ingestor:latest .
```

### Option 2: Permanent (Linux/macOS/All Shells)

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
# ~/.bashrc or ~/.zshrc
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

Then reload:

```bash
source ~/.bashrc  # or ~/.zshrc
```

### Option 3: Docker Daemon Configuration (System-wide)

**Linux** — Edit `/etc/docker/daemon.json`:

```json
{
  "features": {
    "buildkit": true
  }
}
```

Restart Docker:

```bash
sudo systemctl restart docker
```

**macOS/Docker Desktop** — Settings → Docker Engine → Add to JSON:

```json
{
  "features": {
    "buildkit": true
  }
}
```

### Verify BuildKit is Enabled

```bash
# Check buildkit is available
docker build --help | grep -i buildkit

# Or check during build (verbose output shows cache mount lines)
DOCKER_BUILDKIT=1 docker build -t test:latest . --progress=plain
# Output should include: "COPY --mount=type=cache,target=/var/cache/apt,sharing=locked"
```

**What to expect:**

- First build: ~3-5 minutes (downloads apt packages, compiles dependencies)
- Second build: ~30-60 seconds (reuses cache)
- Rebuild after code change: ~1-2 minutes (only re-runs affected layers)

### Why BuildKit?

- **3-5x faster rebuilds**: `--mount=type=cache` persists apt package cache across builds
- **Fail-fast**: `SHELL` directive with `pipefail` catches errors in piped commands
- **Smaller images**: Multi-stage builds separate build tools from runtime (no bloat in final image)
- **Reproducibility**: Digest-pinned base images ensure identical builds across environments

See [ADR 004: Docker BuildKit & Security Scanning](../../docs/adr/004-docker-buildkit-and-security-scanning.md) for full rationale.

---

## Docker Security Scanning

Pre-commit hooks and GitHub Actions automate vulnerability scanning locally and in CI/CD.

### Local Pre-Commit Hook

**Install** (one-time):

```bash
pip install pre-commit
pre-commit install
```

**Usage** — runs automatically before each commit:

```bash
# Manually trigger all checks
pre-commit run --all-files

# Or run only pip-audit
pre-commit run pip-audit --all-files
```

The `.pre-commit-config.yaml` includes `pip-audit` which scans for known CVEs in Python dependencies. Vulnerable packages will block commit (can be overridden with `git commit --no-verify`).

### GitHub Actions Pipeline

When you push to `main` or `develop`, two security workflows run:

1. **Python dependency scan** (`pip-audit`) — catches vulnerable pip packages
2. **Docker image scan** (`Trivy`) — scans container images for OS-level vulnerabilities

Results appear in the [Code Scanning tab](https://github.com/yourusername/data-pipeline-async/security/code-scanning).

**Manual trigger** (optional):

```bash
# Build and scan a service locally
export DOCKER_BUILDKIT=1
docker build -t ingestor:local .
trivy image ingestor:local
```

See [docker-security-scanning-setup.md](docker-security-scanning-setup.md) for detailed security scanning instructions.

### Compliance Dashboard & SBOM Tracking (Phase 3)

**Automatic SBOM Generation**: Every push to `main`/`develop` generates CycloneDX SBOMs (Software Bill of Materials) for all 6 services.

**Access Compliance Dashboard**:

1. Go to **Actions** → **Security Scan (Full Pipeline)** workflow
2. Click latest run
3. Download from **Artifacts**:
   - `sbom-cyclonedx/` — All service SBOMs (90-day retention)
   - `compliance-reports/` — Compliance audit trail (365-day retention)

**Use Cases**:

- License compliance audits (identify OSS licenses)
- Vulnerability tracking (link CVEs to components)
- Supply chain security (audit all dependencies)
- Compliance investigations (SOC2, ISO27001)

See [compliance-dashboard-guide.md](compliance-dashboard-guide.md) for detailed usage and workflows.

### Automated Dependency Updates (Dependabot)

Dependabot automatically creates PRs for dependency updates targeting the `develop` branch:

**Python Packages** (Weekly - Mondays):

```bash
# pip + uv packages scanned (pyproject.toml, uv.lock, requirements.txt)
# Config: .github/dependabot.yml
# Target: develop branch
```

**Docker Base Images** (Weekly - Tuesdays):

```bash
# All 6 service Dockerfiles + infra/database/Dockerfile
# Monitors: Docker Hub, GitHub Container Registry (ghcr.io)
# Target: develop branch
```

**Workflow**: Dependabot PR → Review & test on develop → Merge to main after validation

### Monthly Base Image Digest Review

Base image digests must be reviewed monthly for security patches. See [digest-update-runbook.md](digest-update-runbook.md) for complete procedures:

**Schedule**: 1st Monday of each month at 9:00 AM UTC

**What's included**:

- Vulnerability scanning (Trivy) of current base images
- Research and validation of new digests
- Local testing before deployment
- Monthly checklist + decision tree

**Recent security action (April 22, 2026)**:

- ⚠️ Discovered `postgres:17` has 1 CRITICAL + 13 HIGH vulnerabilities
- ✅ Switched to `postgres:17-bookworm` with pinned digest
- ✅ Benefits: Significantly smaller than vulnerable postgres:17, reliable pgvector builds, Debian tools available
- ℹ️ Note: Alpine evaluated but pgvector requires `/bin/bash` + Debian build toolchain

---

## Best Practices

### ✅ DO

- Use `.env` for local development only
- Store all sensitive values in CI/deployment secrets managers
- Use `override=False` so CI/deployment vars take precedence
- Check `.env` into `.gitignore` (don't commit secrets)
- Document required env vars in `.env.example`
- Enable BuildKit for all Docker builds (`export DOCKER_BUILDKIT=1`)
- Run `pre-commit run --all-files` before pushing
- Review security scan results in GitHub Code Scanning tab

### ❌ DON'T

- Commit `.env` to version control
- Use `override=True` (breaks CI/deployment priorities)
- Hardcode secrets in code or configuration
- Assume `.env` exists in CI/deployed environments
- Skip validation of required env vars
- Build Docker images without BuildKit (`DOCKER_BUILDKIT=0` or unset)
- Ignore pre-commit hook warnings or failures
- Bypass security scanning with `--no-verify`

---

## Environment Variable Reference

| Variable | Local Dev | CI/CD | Deployed | Source |
|----------|-----------|-------|----------|--------|
| `DATABASE_URL` | `.env` | GitHub Secrets | Secrets Manager | Primary app DB |
| `DATABASE_URL_TEST` | `.env` | GitHub Secrets | N/A (tests don't run) | PostgreSQL test DB |
| `REDIS_URL` | `.env` | GitHub Secrets | Secrets Manager | Redis service |
| `ENVIRONMENT` | `.env` or override | `development`/`staging`/`production` | Injected by orchestrator | App mode |
| `LOG_LEVEL` | `.env` | `INFO` (GitHub) | Injected | Logging verbosity |
| `OTEL_ENDPOINT` | `.env` | GitHub Secrets | Secrets Manager | Tracing endpoint |
| `DOCKER_BUILDKIT` | `1` (recommended) | `1` (CI default) | N/A | Enable BuildKit for faster builds |
| `COMPOSE_DOCKER_CLI_BUILD` | `1` (recommended) | `1` (CI default) | N/A | Use BuildKit in docker-compose |

---

## See Also

- [docker-security-scanning-setup.md](docker-security-scanning-setup.md) — Pre-commit hooks, Trivy, pip-audit setup
- [docs/adr/004-docker-buildkit-and-security-scanning.md](../../docs/adr/004-docker-buildkit-and-security-scanning.md) — ADR for BuildKit & security scanning decisions
- [docs/commands.md](commands.md) — Quick command reference
- [README.md](../README.md) — Getting started
- [.env.example](../.env.example) — Template
