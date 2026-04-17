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

# With coverage report (auto-enabled, see next section)
uv run pytest tests/ -v

# Parallel execution (requires pytest-xdist)
uv run pytest tests/ -v -n auto
```

## Coverage Reports

Test coverage is **automatically collected** when running pytest (configured in `pyproject.toml`).

### Terminal-Based Coverage Report

```bash
# Run tests and see coverage in terminal
uv run pytest tests/ -v

# Output shows:
# - Lines covered/missed per file
# - Percentage coverage by module
# - Missing line numbers
```

Example output:

```
app/crud.py          42      8    81%   15-20, 45-48
app/schemas.py       28      2    93%   55-56
app/main.py          65      3    95%   120, 145, 200
─────────────────────────────────────────────────
TOTAL               135     13    90%
```

### HTML Coverage Report (Interactive View)

```bash
# Generate and open HTML coverage report
uv run pytest tests/ -v

# Open in browser
open htmlcov/index.html            # macOS
xdg-open htmlcov/index.html        # Linux
start htmlcov/index.html           # Windows
```

**What the HTML report shows:**

- Line-by-line coverage highlighting (green = covered, red = missed)
- Branch coverage (which code paths were tested)
- Drill down into any file to see exactly which lines weren't executed
- Time statistics and coverage trends

### Coverage Only (Skip Tests)

```bash
# Combine reports from multiple test runs
coverage combine
coverage report
coverage html

# Then open: open htmlcov/index.html
```

### High-Level Coverage Metrics

```bash
# Just the summary (no per-file details)
uv run pytest tests/ -q

# Set minimum threshold (fail if below 80%)
uv run pytest tests/ --cov=app --cov-fail-under=80
```
