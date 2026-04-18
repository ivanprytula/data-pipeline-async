# Testing with PostgreSQL via Docker

The project includes EXPLAIN ANALYZE query optimization tests that require a real PostgreSQL database. If you don't have PostgreSQL installed locally, you can use the Docker Compose service.

## Quickstart

### Start the PostgreSQL Test Container

```bash
# Start only the PostgreSQL test service (port 5433)
docker compose --profile test up -d db-test

# Verify it's running
docker compose ps
```

### Run Tests

```bash
# Run all tests (EXPLAIN ANALYZE tests will use Docker)
uv run pytest tests/

# Run only EXPLAIN ANALYZE tests
uv run pytest tests/integration/records/test_query_analysis.py -v

# Run specific test
uv run pytest tests/integration/records/test_query_analysis.py::TestQueryAnalysis::test_date_range_query_uses_index -xvs
```

### Stop the Container

```bash
docker compose --profile test down
```

## How It Works

### Without Docker PostgreSQL

If `db-test` container is not running:

```bash
uv run pytest tests/
# Output: 192 passed, 10 skipped (PostgreSQL EXPLAIN ANALYZE tests)
```

Tests skip gracefully with message:

```
PostgreSQL not available at localhost:5433. Start with: docker compose --profile test up db-test
```

### With Docker PostgreSQL

```bash
docker compose --profile test up -d db-test
uv run pytest tests/
# Output: 193 passed (all tests including EXPLAIN ANALYZE)
```

## Configuration

**Docker Service** (`docker-compose.yml`):

- Container: `data-pipeline-db-test`
- Port: `5433` (mapped to container port 5432)
- Database: `test_database`
- User: `postgres`
- Password: `postgres`

**Pytest Fixture** (`tests/conftest.py`):

- Uses `postgresql_async_session` fixture for EXPLAIN ANALYZE tests
- Automatically detects Docker service via connection check
- Creates fresh schema for each test
- Cleans up after test completes

## Fixture Behavior

The `postgresql_async_session` fixture:

1. **Manual Setup** (no Docker):
   - Attempts connection to `localhost:5433`
   - If connection fails → skips test with helpful message
   - Zero configuration needed

2. **Automatic Connection** (Docker running):
   - Detects running container
   - Connects using asyncpg driver
   - Creates `records` table schema
   - Runs test against real PostgreSQL
   - Drops schema after test

## Example Test Session

```bash
# Terminal 1: Start PostgreSQL
docker compose --profile test up db-test

# Terminal 2: Run tests
$ uv run pytest tests/integration/records/test_query_analysis.py::TestQueryAnalysis::test_timestamp_index_is_present -xvs

============================= test session starts ==============================
tests/integration/records/test_query_analysis.py::TestQueryAnalysis::test_timestamp_index_is_present PASSED

============================= 1 passed in 2.34s ===============================
```

## What Gets Tested

EXPLAIN ANALYZE tests verify:

- ✅ Index usage (ix_records_timestamp, ix_records_processed, ix_records_active_source)
- ✅ Query plan efficiency (planning time, execution time)
- ✅ Partial index effectiveness (soft-delete filter)
- ✅ Multi-column filter optimization
- ✅ Array aggregation performance

See [test_query_analysis.py](../tests/integration/records/test_query_analysis.py) for full test suite.

## CI/CD Integration

In GitHub Actions, the PostgreSQL service is typically provided by:

- Service containers in the workflow
- Or a Docker Compose setup similar to this

Example `.github/workflows/ci.yml`:

```yaml
services:
  postgres:
    image: postgres:17
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
    env:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: test_database
    ports:
      - 5433:5432
```

## Troubleshooting

### Tests skip: "PostgreSQL not available"

```bash
# Check if container is running
docker compose ps db-test

# Start it if needed
docker compose --profile test up -d db-test

# Verify connectivity
docker exec data-pipeline-db-test pg_isready -U postgres
```

### Connection refused

```bash
# Check port 5433 is available
lsof -i :5433

# Or use Docker Compose logs
docker compose logs db-test
```

### Permission denied / auth failed

```bash
# Clear volumes and restart
docker compose --profile test down -v
docker compose --profile test up -d db-test

# Verify user/password in docker-compose.yml
docker compose -f docker-compose.yml config | grep -A5 db-test
```

## Learn More

- [postgres:17 Docker Image](https://hub.docker.com/_/postgres)
- [pytest-postgresql Documentation](https://pytest-postgresql.readthedocs.io/)
- [SQLAlchemy Async Testing](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
