# Running tests with PostgreSQL

This project runs the full test suite against SQLite by default (fast, in-memory), but some tests require PostgreSQL to validate DB-specific behavior and concurrency. Use the instructions below to run Postgres-backed tests locally.

Quick script (recommended):

```bash
./scripts/test_with_postgres.sh tests/integration/records/test_concurrency.py -v
```

The script will:

- start a Docker Compose test service (`db-test`)
- wait for Postgres to be ready
- run pytest with `DATABASE_URL_TEST` set to the container URL
- stop the test container on exit

Manual steps (alternative):

1. Start the test DB:

```bash
docker compose --profile test up -d db-test
```

1. Set the `DATABASE_URL_TEST` environment variable:

```bash
export DATABASE_URL_TEST='postgresql+asyncpg://postgres:postgres@localhost:5433/test_database'
```

1. Run the Postgres-backed tests (a subset is recommended for speed):

```bash
# run concurrency tests only
pytest tests/integration/records/test_concurrency.py -v

# or run full suite (slower)
pytest -q
```

1. Stop the test DB:

```bash
docker compose --profile test down
```

Notes:

- The test fixtures create engines/sessionmakers lazily and use `NullPool` or isolated engines for Postgres-only concurrent tests to avoid cross-event-loop pooled connections.
- Prefer running the Postgres-focused tests in CI (nightly or gated) rather than on every local run due to time and resource cost.
