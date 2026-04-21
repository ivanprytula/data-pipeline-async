# Environment Configuration Strategy

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
bash scripts/dev-services.sh  # Starts all services (services use Docker networking)
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
bash scripts/dev-services.sh

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
   bash scripts/dev-services.sh
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

## Best Practices

### ✅ DO

- Use `.env` for local development only
- Store all sensitive values in CI/deployment secrets managers
- Use `override=False` so CI/deployment vars take precedence
- Check `.env` into `.gitignore` (don't commit secrets)
- Document required env vars in `.env.example`

### ❌ DON'T

- Commit `.env` to version control
- Use `override=True` (breaks CI/deployment priorities)
- Hardcode secrets in code or configuration
- Assume `.env` exists in CI/deployed environments
- Skip validation of required env vars

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

---

## See Also

- [docs/commands.md](commands.md) — Quick command reference
- [README.md](../README.md) — Getting started
- [.env.example](../.env.example) — Template
