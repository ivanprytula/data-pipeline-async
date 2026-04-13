# Hands-On Commands

## Configuration Precedence

### The Mature Solution: Layer Your Configuration

Priority (highest first):

1. Container/k8s environment variables (production)
2. CI/CD job env vars (GitHub Actions, GitLab CI)
3. .env file (local development)
4. Settings defaults (fallback)

Example:
DATABASE_URL = k8s secret > CI env > .env > default

Alternative representation: bottom to top direction:

```text
Development (local)
    ↓
Testing (CI — secrets injected)
    ↓
Staging (k8s env vars)
    ↓
Production (secrets manager + k8s)
```

### Testing Different Environments Locally

```bash
# Development (uses .env)
docker compose up

# Testing (uses isolated DB)
ENV_FILE=.env.testing docker compose up

# Staging simulation
ENV_FILE=.env.staging docker compose up
```

## Testing Pyramid Commands

Run different layers of the test suite. Default excludes e2e tests (marked as slow/long-running).

### Quick Development Cycle (Unit + Integration)

```bash
# Default: run fast tests (unit + integration, skip e2e)
uv run pytest tests/ -v

# Even faster: show only failures
uv run pytest tests/ -q
```

### By Test Layer

```bash
# Unit tests only (pure logic, no I/O)
uv run pytest tests/unit/ -v

# Integration tests only (ASGI + DB)
uv run pytest tests/integration/ -v

# E2E tests only (long-running, normally skipped)
uv run pytest tests/e2e/ -v -m e2e

# All tests including E2E
uv run pytest tests/ -v -m "unit or integration or e2e"
```

### With Performance Metrics & Logging

```bash
# See performance test timings
uv run pytest tests/integration/records/test_performance.py -v --log-cli-level=INFO

# Full test output with logs (useful for debugging failures)
uv run pytest tests/ -v --log-cli-level=DEBUG

# See slow tests (pytest-durations)
uv run pytest tests/ -v --durations=10
```

### Specific Tests

```bash
# Single test file
uv run pytest tests/integration/records/test_api.py -v

# Single test function
uv run pytest tests/integration/records/test_api.py::test_create_single_record -v

# Tests matching keyword pattern
uv run pytest tests/ -v -k "batch"

# Tests NOT matching keyword (e.g., skip performance tests)
uv run pytest tests/ -v -k "not performance"
```

### CI/CD Simulation

```bash
# Fail fast on first error (good for CI)
uv run pytest tests/ -v -x

# With coverage report
uv run pytest tests/ -v --cov=app --cov-report=term-missing

# Parallel execution (requires pytest-xdist)
uv run pytest tests/ -v -n auto
```
