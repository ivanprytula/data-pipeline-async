# Daily Development Workflows

> Common commands and workflows for active development.
>
> **Note**: Use bash scripts in `scripts/` for automation. This document explains what each workflow does.

---

## Quick Reference

Most workflows are available as bash scripts:

```bash
bash scripts/daily/01-start-dev-services.sh          # Start all dev services
bash scripts/ops/02-compose-profile.sh dev up -d     # Dev resource profile (override file)
bash scripts/ops/02-compose-profile.sh prod-like up -d  # Prod-like resource profile
docker compose --profile monitoring up -d            # Optional monitoring stack
docker compose --profile vector up -d                # Optional vector stack (qdrant + inference)
docker compose --profile worker up -d                # Optional processor worker
bash scripts/ops/02-compose-profile.sh dev up -d     # Dev resource profile (override file)
bash scripts/ops/02-compose-profile.sh prod-like up -d  # Prod-like resource profile
docker compose --profile monitoring up -d            # Optional monitoring stack
docker compose --profile vector up -d                # Optional vector stack (qdrant + inference)
docker compose --profile worker up -d                # Optional processor worker
bash scripts/daily/03-run-tests.sh all         # Run all tests
bash scripts/daily/03-run-tests.sh unit        # Run unit tests only
bash scripts/daily/03-run-tests.sh integration # Run integration tests only
uv run alembic upgrade head                   # Apply migrations
uv run alembic downgrade -1                   # Rollback migration
bash scripts/daily/04-quality-checks.sh   # Lint, format, type-check
bash scripts/setup/03-bootstrap-k3d.sh        # Bootstrap local k3d cluster
## Validate PR checks (manual merge via GitHub UI)

Use the GitHub web UI to review required checks and perform merges. Alternatively you can inspect check-run status with the `gh` CLI:

```bash
gh pr checks <pr-number-or-branch>                      # Show checks for the PR
gh pr checks <pr-number-or-branch> --watch --interval 10  # Watch checks until completion
```

```text

## Practical Cadence

Use this cadence to keep fast feedback on every commit while running heavy security scans less often.

```text
Push/PR update (main, develop, feature/*)
  |
  +--> CI
       01 Quality
       02 Unit
       03 Migrations
       04 Integration
       05 E2E
       06 Dependency Audit (PR only)
       06 Docker Build (push/manual only after all checks pass)

Nightly / Weekly
  |
  +--> Security Full Scan (Scheduled and Manual)
  +--> Scheduled CodeQL / CodeQL Analyze

Manual dispatch
  |
  +--> CI
      01 Quality -> 02 Unit -> 03 Migrations -> 04 Integration -> 05 E2E -> 06 Dependency Audit (PR only) -> 06 Docker Build
  +--> Manual Docker Build (standalone validation)
  +--> Security Full Scan (Scheduled and Manual)
    +--> Scheduled CodeQL / CodeQL Analyze
  +--> Release Promote / CD Deploy
```

Policy summary:

- Run one queued CI workflow on every push and PR update
- Run migrations before integration/e2e so schema failures stop the pipeline early
- Run dependency audit inside the main PR CI chain instead of as a separate workflow
- Run the full security scan on schedule and manual dispatch for broad security coverage
- Run scheduled/manual CodeQL from the separate lightweight security workflow
- Run Docker build only after prior CI checks pass, with standalone manual Docker build kept for ad hoc validation

---

## Workflow 1: Start Development Environment

### What It Does

Starts all services (PostgreSQL, Redis, Kafka, MongoDB, Jaeger) in the background so you can run tests and the dev server without manual setup.

### Command

```bash
bash scripts/daily/01-start-dev-services.sh
```

### Expected Output

```text
✓ PostgreSQL ready (localhost:5432)
✓ Redis ready (localhost:6379)
✓ Services are healthy
```

### What's Running

After this script:

- PostgreSQL (main) is accepting connections on port 5432
- PostgreSQL for DB-dependent tests is auto-provisioned by testcontainers when needed
- Redis is running on port 6379
- Redpanda (Kafka) is running on port 9092
- MongoDB is running on port 27017
- Jaeger is running on port 16686

**Services stay running in the background** until you stop them:

```bash
docker compose stop     # Stop but keep containers
docker compose down     # Stop and remove containers
```

---

## Workflow 2: Run Tests

### Full Test Suite

Runs unit tests (in-memory SQLite) first, then integration tests (PostgreSQL):

```bash
bash scripts/daily/03-run-tests.sh all
```

Expected: ~100+ tests passing

### Unit Tests Only (Fast)

In-memory SQLite, no external services needed:

```bash
bash scripts/daily/03-run-tests.sh unit
```

Expected: ~50 tests, <5 seconds

### Integration Tests Only (PostgreSQL)

Requires dev environment running (`bash scripts/daily/01-start-dev-services.sh`):

```bash
bash scripts/daily/03-run-tests.sh integration
```

Expected: ~50 tests, 10–30 seconds

### Single Test File

```bash
uv run pytest tests/unit/crud/test_records.py -v
```

### Single Test by Name

```bash
uv run pytest tests/ -k test_create_record -v
```

### With Coverage Report

```bash
uv run pytest tests/unit/ --cov=ingestor --cov-report=html
open htmlcov/index.html  # View coverage report
```

---

## Workflow 3: Database Migrations

### Show Current Schema Version

```bash
uv run alembic current
```

Returns the current migration head applied to the database.

### Apply All Pending Migrations

```bash
uv run alembic upgrade head
```

Applies all new migrations from `alembic/versions/` to the database.

### Rollback One Step

```bash
uv run alembic downgrade -1
```

Reverts the most recent migration.

### Create New Migration from Model Changes

After modifying `ingestor/models.py`:

```bash
uv run alembic revision --autogenerate -m "add_user_status_field"
```

This generates a new migration file in `alembic/versions/` based on model diffs.

### Dry Run (Show SQL Without Applying)

```bash
uv run alembic upgrade head --sql
```

Shows SQL that would be executed.

### Reset Database (Wipe All Data)

```bash
docker compose exec db psql -U postgres -c "DROP DATABASE data_pipeline;"
uv run alembic upgrade head
```

---

## Workflow 4: Code Quality

### Format & Lint

```bash
bash scripts/daily/04-quality-checks.sh
```

This runs:

- **Ruff format**: Auto-format code to PEP 8 style
- **Ruff lint**: Check for code errors and style issues
- **Type check**: Verify type hints with `pyright`

Expected output: "All checks passed ✓"

### Manual Commands

```bash
# Format code
uv run ruff format ingestor/ tests/

# Check for lint issues
uv run ruff check ingestor/ tests/

# Type check
uv run pyright ingestor/
```

---

## Workflow 5: Start Dev Server

### With Auto-Reload

```bash
uv run uvicorn ingestor.main:app --reload
```

Server starts at `https://localhost:8000`

**Features**:

- Auto-reloads when you save Python files
- Shows detailed error messages
- Hot-reload for dependency injection changes

### Access API Documentation

Once server is running:

- **Swagger UI**: `https://localhost:8000/api/docs`
- **ReDoc**: `https://localhost:8000/api/redoc`
- **OpenAPI JSON**: `https://localhost:8000/openapi.json`

---

## Workflow 6: Auth and RBAC Smoke Checks

Use these quick checks after touching auth, middleware, or route dependencies.

### Session Login with Explicit Role

```bash
curl -k -i -X POST "https://localhost:8000/api/v1/records/auth/login?user_id=alice&role=writer"
```

Expected: `Set-Cookie: session_id=...` in response headers.

### Writer Route (Should Succeed for writer/admin)

```bash
curl -k -i -X PATCH "https://localhost:8000/api/v1/records/1/secure/archive" \
  --cookie "session_id=<SESSION_ID>"
```

Expected: `200 OK` for `writer`/`admin`, `403` for `viewer`.

### Admin Route (Should Fail for writer)

```bash
curl -k -i -X DELETE "https://localhost:8000/api/v1/records/1/secure/delete" \
  --cookie "session_id=<SESSION_ID>"
```

Expected: `403` unless session role is `admin`.

### JWT Write Route (v2)

## Workflow 7: Manage GitHub Actions Config (Daily Ops)

Use `scripts/ops/01-gh-actions-config.sh` for day-to-day CI/CD configuration updates.

### Common Tasks

```bash
repo="ivanprytula/data-pipeline-async"

# Rotate/update environment variable values
scripts/ops/01-gh-actions-config.sh vars set ECS_SERVICE_NAME ingestor --env dev --repo "$repo"
scripts/ops/01-gh-actions-config.sh vars set ECS_SERVICE_NAME_AI_GATEWAY inference --env dev --repo "$repo"
scripts/ops/01-gh-actions-config.sh vars set ECS_TASK_DEFINITION_FAMILY_AI_GATEWAY inference --env dev --repo "$repo"

# Update signer identity policy used by CD verification
scripts/ops/01-gh-actions-config.sh vars set COSIGN_CERTIFICATE_IDENTITY \
  "https://github.com/${repo}/.github/workflows/docker-build-reusable.yml@refs/heads/main" \
  --env prod --repo "$repo"

# Rotate secret value
scripts/ops/01-gh-actions-config.sh secrets set SENTRY_AUTH_TOKEN "$SENTRY_AUTH_TOKEN" --env prod --repo "$repo"

# Inspect current settings
scripts/ops/01-gh-actions-config.sh vars list --env prod --repo "$repo"
scripts/ops/01-gh-actions-config.sh secrets list --env prod --repo "$repo"
```

### OIDC Template Operations

```bash
repo="ivanprytula/data-pipeline-async"

# View current OIDC subject template
scripts/ops/01-gh-actions-config.sh oidc get --repo "$repo"

# Set custom claims list
scripts/ops/01-gh-actions-config.sh oidc set --claims repo,context,job_workflow_ref --repo "$repo"

# Reset to GitHub default subject template
scripts/ops/01-gh-actions-config.sh oidc reset --repo "$repo"
```

### Safety Notes

- Prefer environment-scoped updates (`--env`) for deploy-related values.
- Update production values via protected branches and approved change windows.
- Keep all script usage in terminal history for auditability.

```bash
TOKEN=$(curl -k -s -X POST "https://localhost:8000/api/v2/records/auth/token" | jq -r '.access_token')

curl -k -i -X POST "https://localhost:8000/api/v2/records/jwt" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"source":"rbac-check","timestamp":"2026-01-01T00:00:00","data":{"ok":true},"tags":["smoke"]}'
```

Expected: `201` with writer/admin token; `403` when token roles are insufficient.

### Health Check

```bash
curl -k https://localhost:8000/health
```

Should return: `{"status":"healthy"}`

---

## Workflow 7: Test API Endpoints

### Dashboard Admin UI (Pillar 7)

Use the new dashboard control surface for operator workflows:

- Open `http://localhost:8003/admin` for Admin Workflows.
- Refresh worker health from the Worker Health panel.
- Lookup one task ID from the Task Lookup panel.
- Trigger one-record reruns from Manual Rerun.
- Create role-aware test sessions from Session Bootstrap (RBAC).

These UI actions call existing ingestor APIs and are useful for fast operational checks without crafting manual curl commands.

### Manual HTTP Requests

```bash
# Create a record
curl -X POST https://localhost:8000/api/v1/records \
  -H "Content-Type: application/json" \
  -d '{"source": "cli", "timestamp": "2024-04-22T12:00:00", "data": {}}' \
  -k

# Fetch records
curl -X GET https://localhost:8000/api/v1/records -k

# With pagination
curl -X GET 'https://localhost:8000/api/v1/records?limit=10&offset=0' -k
```

### Using HTTP Client Script

```bash
python scripts/tools/http-clients-demo.py
```

This script demonstrates various API calls (create, read, update, delete).

---

## Workflow 8: Background Worker Testing

### Submit Batch Ingestion Job

```bash
curl -X POST https://localhost:8000/api/v1/background/ingest/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"source": "batch1", "timestamp": "2024-04-22T12:00:00", "data": {"value": 100}},
    {"source": "batch1", "timestamp": "2024-04-22T12:00:01", "data": {"value": 200}}
  ]' \
  -k
```

Returns: `{"task_id": "uuid-here", "status": "queued", ...}`

### Poll Task Status

```bash
curl -X GET https://localhost:8000/api/v1/background/tasks/UUID-HERE -k
```

Returns: `{"task_id": "...", "status": "running|succeeded|failed", ...}`

### Check Worker Health

```bash
curl -X GET https://localhost:8000/api/v1/background/workers/health -k
```

Returns: Queue depth, active workers, submitted/processed counters

---

## Workflow 9: Metrics & Observability

### Prometheus Metrics

```bash
# Raw metrics endpoint
curl http://localhost:9000/metrics

# Or visit dashboard:
open http://localhost:9090
```

### Available Metrics

- `http_requests_total` — All HTTP requests by method/endpoint/status
- `http_request_duration_seconds` — Response time histogram
- `pipeline_records_ingested_total` — Records processed
- `pipeline_job_executions_total` — Scheduled job runs
- `background_jobs_submitted_total` — Batch jobs submitted

### Distributed Tracing (Jaeger)

```bash
# View traces and spans
open http://localhost:16686
```

Traces show:

- Request flow through middleware → router → CRUD
- Database query timing
- External HTTP calls (if traced)

---

## Workflow 10: Database Inspection

### Connect via psql

```bash
docker compose exec db psql -U postgres -d data_pipeline
```

Then:

```sql
-- List tables
\dt

-- Show schema of records table
\d records

-- Query records
SELECT id, source, created_at FROM records LIMIT 10;

-- Check migrations applied
SELECT version, description, installed_on FROM alembic_version;
```

### Export Data

```bash
# Backup to SQL file
docker compose exec db pg_dump -U postgres data_pipeline > backup.sql

# Restore from backup
docker compose exec db psql -U postgres data_pipeline < backup.sql
```

---

## Workflow 11: Load Testing

### Run Load Test

```bash
bash scripts/testing/03-load-test.sh
```

This script runs k6 load tests with:

- 10 virtual users
- Ramp-up over 30 seconds
- 5-minute test duration
- Checks for errors and performance thresholds

### Locust Web UI

Alternative load testing tool with web dashboard:

```bash
# Start Locust
uv run locust -f scripts/testing/locustfile.py --host=https://localhost:8000

# Visit: http://localhost:8089
```

---

## Common Issues & Solutions

### "Connection refused: PostgreSQL"

```bash
# Check if services are running
docker compose ps

# If not running, start them
bash scripts/daily/01-start-dev-services.sh

# If stuck, restart
docker compose restart db
```

### "Port already in use"

```bash
# Find process using port
lsof -i :5432  # PostgreSQL

# Kill process or edit docker-compose.yml to use different port
```

### "Test database locked"

```bash
# Restart test PostgreSQL
docker compose restart db_test

# Or drop test database and recreate
docker compose exec db_test psql -U postgres -c "DROP DATABASE test_database;"
```

### "Module not found" After Git Pull

```bash
# Dependencies may have changed
uv sync

# Then re-run tests
bash scripts/daily/03-run-tests.sh unit
```

---

## Next Steps

- **Explore the architecture**: [04 — Architecture Overview](04-architecture-overview.md)
- **Use test/quality commands reference**: [Dev Commands](dev/commands.md)
- **Review design decisions**: [Design Decisions](design/decisions.md)
