# Commands Reference

All CLI commands for daily development, testing, migrations, and infrastructure.
Use Ctrl+F to jump to any section.

---

## Daily Development

### Start All Services (Development + Testing)

**Recommended for active development** — starts all services including test databases:

```bash
# One command to start everything
bash scripts/dev_services.sh

# What it starts:
#   - PostgreSQL (main):   localhost:5432  (for app)
#   - PostgreSQL (test):   localhost:5433  (for concurrent tests)
#   - Redis:               localhost:6379
#   - Kafka (Redpanda):    localhost:9092
#   - MongoDB:             localhost:27017
#   - Jaeger (tracing):    localhost:16686

# Keep services running during development, run any test suite without setup:
uv run pytest tests/ -v                    # All tests work
uv run pytest tests/integration/ -v        # PostgreSQL tests work
uv run pytest -m browser                   # Browser tests work (if Playwright installed)

# Stop all services when done:
docker compose --profile test down
```

**Why use this?** Eliminates the need to manually start services before running tests. All 19 previously-skipped PostgreSQL concurrent tests and browser tests will run automatically.

### Start Full Stack

```bash
# Start app + Postgres + Redis
docker compose up --build

# Background mode
docker compose up -d --build

# Rebuild a single service
docker compose up --build app

# Stop and remove containers
docker compose down

# Stop and remove containers + volumes (wipes DB data)
docker compose down -v
```

### Run Dev Server (no Docker)

```bash
# Install deps
uv sync

# Start Uvicorn with auto-reload (requires Postgres running)
uv run uvicorn app.main:app --reload

# With custom port
uv run uvicorn app.main:app --reload --port 8001
```

### Health Check

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

---

## Migrations (Alembic)

```bash
# Show current revision applied to the DB
uv run alembic current

# Show full migration history
uv run alembic history --verbose

# Apply all pending migrations (upgrade to head)
uv run alembic upgrade head

# Apply one step forward
uv run alembic upgrade +1

# Rollback one step
uv run alembic downgrade -1

# Rollback to specific revision
uv run alembic downgrade <revision-id>

# Autogenerate migration from model diffs
uv run alembic revision --autogenerate -m "add_source_column_to_records"

# Create blank migration (for manual edits)
uv run alembic revision -m "create_indexes_on_records"

# Show the SQL without applying (dry run)
uv run alembic upgrade head --sql
```

> **Gotcha:** Python 3.14 + Alembic requires `sqlalchemy[asyncio]` in deps.
> See `docs/alembic-python314-fix.md` for details.

---

## Tests

### Run All Tests

```bash
# Full test suite (no Postgres required — uses aiosqlite)
uv run pytest tests/ -v

# Quiet output
uv run pytest tests/

# Stop on first failure
uv run pytest tests/ -x

# Show local variables on failure
uv run pytest tests/ -v --tb=long
```

### Run by Layer

```bash
# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests only
uv run pytest tests/integration/ -v

# A specific test file
uv run pytest tests/test_records.py -v

# A specific test by keyword (name match)
uv run pytest tests/ -k "test_create" -v

# A specific test by exact node ID
uv run pytest tests/test_records.py::test_create_record -v
```

### Run with Real PostgreSQL

**Quick method (using script):**

```bash
# Starts container, runs tests, cleans up automatically
./scripts/test_with_postgres.sh tests/integration/records/test_concurrency.py -v
```

**Manual method:**

```bash
# Start test DB
docker compose --profile test up -d db-test

# Verify health
docker compose ps

# Run tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/integration/records/test_query_analysis.py -v

# Run specific test
uv run pytest tests/integration/records/test_query_analysis.py::TestQueryAnalysis::test_date_range_query_uses_index -xvs

# Stop container
docker compose --profile test down
```

**Settings:**

- Port: 5433 (Docker), 5432 (inside container)
- Database: test_database
- User: postgres / Password: postgres

**Notes:**

- Default: SQLite in-memory tests only -> 192 passed, 10 skipped (PostgreSQL tests)
- With Docker container running -> 202 passed (all tests including EXPLAIN ANALYZE)
- Fixtures use NullPool to avoid cross-loop connection issues

---

## Coverage

```bash
# Run with coverage report in terminal
uv run pytest tests/ --cov=app

# Coverage with per-file breakdown
uv run pytest tests/ --cov=app --cov-report=term-missing

# Generate HTML report (opens in browser)
uv run pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# Fail if below threshold
uv run pytest tests/ --cov=app --cov-fail-under=80

# Coverage for a specific module
uv run pytest tests/ --cov=app.crud --cov-report=term-missing
```

---

## Code Quality

### Ruff (Linting + Formatting)

```bash
# Check for lint errors
uv run ruff check .

# Check + auto-fix
uv run ruff check . --fix

# Format code
uv run ruff format .

# Check formatting without changing (CI mode)
uv run ruff format . --check

# Lint + format in one command
uv run ruff check . && uv run ruff format .
```

### Pre-commit

```bash
# Install hooks (one-time, per repo)
pre-commit install

# Run all hooks against all files (initial setup / full check)
pre-commit run --all-files

# Run all hooks against staged files only
pre-commit run

# Run a specific hook
pre-commit run ruff --all-files
pre-commit run end-of-file-fixer --all-files

# Skip hooks for a specific commit (use sparingly)
git commit -m "wip" --no-verify

# Update hook versions
pre-commit autoupdate

# Uninstall hooks
pre-commit uninstall
```

> See `docs/pre-commit-setup.md` for hook configuration details.

---

## API Testing (curl)

### Authentication

**HTTP Basic Auth (Docs endpoints):**

```bash
# Access protected docs (prompts for username/password)
curl -u admin:admin http://localhost:8000/docs

# Set credentials in .env
# DOCS_USERNAME=admin
# DOCS_PASSWORD=changeme
```

**Bearer Token (v1 API, stateless):**

```bash
# Static token from .env: API_V1_BEARER_TOKEN=dev-secret-bearer-token
curl -X POST http://localhost:8000/api/v1/records/batch/protected \
  -H "Authorization: Bearer dev-secret-bearer-token" \
  -H "Content-Type: application/json" \
  -d '[{"source": "curl", "value": 42.0, "metadata": {}}]'
```

**Session-Based Auth (v1 API, stateful):**

```bash
# 1. Login (creates session, returns Set-Cookie header)
curl -v -X POST "http://localhost:8000/api/v1/records/auth/login?user_id=alice"

# 2. Extract session_id from Set-Cookie header (curl stores automatically with -b)
curl -b "session_id=<EXTRACTED_SESSION_ID>" \
  -X GET "http://localhost:8000/api/v1/records/1/secure"
```

### Records CRUD

```bash
# List all records (paginated)
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/records?skip=0&limit=10"

# Get single record
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v1/records/1

# Create a record
curl -X POST http://localhost:8000/api/v1/records \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"source": "test", "value": 42.0, "metadata": {}}'

# Batch create
curl -X POST http://localhost:8000/api/v1/records/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '[{"source":"a","value":1.0},{"source":"b","value":2.0}]'

# Update a record
curl -X PATCH http://localhost:8000/api/v1/records/1 \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"value": 99.0}'

# Delete a record
curl -X DELETE http://localhost:8000/api/v1/records/1 \
  -H "X-API-Key: $API_KEY"

# Bulk delete
curl -X DELETE http://localhost:8000/api/v1/records \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"ids": [1, 2, 3]}'
```

### Filter & Search

```bash
# Filter by source
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/records?source=test"

# Filter by value range
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/records?min_value=10&max_value=100"

# Aggregate stats
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v1/records/stats
```

### OpenAPI Docs

```bash
# Interactive Swagger UI
open http://localhost:8000/docs

# Raw OpenAPI JSON
curl http://localhost:8000/openapi.json
```

---

## Docker Compose Profiles

### Development (`docker-compose.dev.yml`)

```bash
# Dev stack: hot-reload, source mount
docker compose -f docker-compose.dev.yml up --build

# Shell into app container
docker compose -f docker-compose.dev.yml exec app bash

# View app logs
docker compose -f docker-compose.dev.yml logs app -f
```

### Production-like (`docker-compose.prod-like.yml`)

```bash
# Prod-like: built image, no source mount
docker compose -f docker-compose.prod-like.yml up --build

# Check health endpoint in prod-like
curl http://localhost:8000/health
```

### Profiles (selective service start)

```bash
# Start only DB and Redis (no app)
docker compose --profile db-only up -d

# Start with monitoring stack (Prometheus + Grafana)
docker compose --profile monitoring up -d

# Start everything
docker compose --profile full up --build
```

> See individual `docker-compose.*.yml` files for exact profile names.

---

## Database Operations

### Connect to PostgreSQL

```bash
# Via Docker
docker compose exec db psql -U postgres -d data_pipeline

# Direct psql (if Postgres installed locally)
psql "postgresql://postgres:postgres@localhost:5432/data_pipeline"
```

### Useful psql Commands

```sql
-- List tables
\dt

-- Describe a table
\d records

-- Show active connections
SELECT pid, usename, application_name, state FROM pg_stat_activity;

-- Show table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC;

-- Explain a query
EXPLAIN ANALYZE SELECT * FROM records WHERE source = 'test' LIMIT 10;
```

### Redis

```bash
# Connect to Redis CLI via Docker
docker compose exec redis redis-cli

# Check all keys (dev only)
docker compose exec redis redis-cli KEYS "*"

# Flush all cache (dev only)
docker compose exec redis redis-cli FLUSHALL

# Monitor live commands
docker compose exec redis redis-cli MONITOR
```

---

## Observability

### Prometheus Metrics

```bash
# View raw metrics
curl http://localhost:8000/metrics

# Prometheus UI (if compose profile started)
open http://localhost:9090

# Grafana UI (if compose profile started)
open http://localhost:3000
# Default credentials: admin / admin
```

### Logs

```bash
# Tail app logs (Docker)
docker compose logs app -f

# Filter for errors only
docker compose logs app -f | grep '"level":"ERROR"'

# Filter by correlation ID
docker compose logs app | grep '"cid":"<value>"'
```

---

## Load Testing

### k6

```bash
# Install k6 (Linux)
sudo apt-get install k6

# Run a load test script
k6 run scripts/load_test.js

# With custom VUs and duration
k6 run --vus 50 --duration 30s scripts/load_test.js

# Output results to JSON
k6 run --out json=results.json scripts/load_test.js
```

### Locust (if configured)

```bash
# Start Locust web UI
uv run locust -f scripts/locustfile.py --host http://localhost:8000

# Headless mode
uv run locust -f scripts/locustfile.py \
  --host http://localhost:8000 \
  --users 100 --spawn-rate 10 --run-time 60s --headless
```

---

## Git & Conventional Commits

```bash
# Commit format: <type>(<scope>): <description>
git commit -m "feat(records): add batch delete endpoint"
git commit -m "fix(auth): handle expired JWT token gracefully"
git commit -m "docs(commands): add load testing section"
git commit -m "refactor(crud): extract pagination helper"
git commit -m "test(records): add integration test for batch create"
git commit -m "chore(deps): bump SQLAlchemy to 2.0.36"

# Types: feat, fix, docs, style, refactor, test, chore, perf, ci
```

---

## Data Zoo Platform Services (Phases 1–8)

Commands will be added here as each phase is built.

### Phase 1: Kafka/Redpanda (Event Streaming)

```bash
# Start Redpanda
docker compose -f docker-compose.dataZoo.yml up redpanda -d

# Create a topic
docker exec -it redpanda rpk topic create records-raw --partitions 3

# List topics
docker exec -it redpanda rpk topic list

# Produce test message
docker exec -it redpanda rpk topic produce records-raw

# Consume from beginning
docker exec -it redpanda rpk topic consume records-raw --from-beginning
```

### Phase 2: MongoDB (Document Store)

```bash
# Start MongoDB via compose
docker compose -f docker-compose.dataZoo.yml up mongo -d

# Connect to Mongo shell
docker exec -it mongo mongosh

# Switch database
use dataZoo

# List collections
show collections
```

### Phase 3: Qdrant (Vector Store)

```bash
# Start Qdrant
docker compose -f docker-compose.dataZoo.yml up qdrant -d

# Qdrant UI
open http://localhost:6333/dashboard

# Check health
curl http://localhost:6333/healthz
```

### Phase 5: Ollama (Local LLM)

```bash
# Pull a model
ollama pull llama3.2

# Run interactively
ollama run llama3.2

# List models
ollama list

# Check running models
ollama ps
```
