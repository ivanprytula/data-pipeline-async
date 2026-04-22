# First-Time Project Setup

> Initialize Data Zoo locally: clone, install dependencies, generate HTTPS certs, start services, create database schema.
>
> **Time**: 5–10 minutes (mostly waiting for Docker to pull images).

---

## Step 1: Clone & Navigate to Project

```bash
git clone https://github.com/ivanp/data-pipeline-async.git
cd data-pipeline-async
```

---

## Step 2: Run Automated Setup

The entire setup is automated in a single bash script:

```bash
bash scripts/quick-setup.sh
```

This script will:
- ✅ Install `uv` if missing
- ✅ Sync Python dependencies (`uv sync`)
- ✅ Generate local HTTPS certificates (via `mkcert`)
- ✅ Copy `.env.example` to `.env` (use defaults or customize)
- ✅ Start all Docker services (PostgreSQL, Redis, Redpanda, MongoDB, Jaeger)
- ✅ Wait for services to be healthy
- ✅ Apply database migrations (`alembic upgrade head`)
- ✅ Print access URLs

**Expected output:**
```
✓ uv installed (v0.11.7)
✓ Dependencies synced
✓ HTTPS certificates generated in ~/.local/share/mkcert/
✓ .env created with defaults
✓ Services starting...
✓ PostgreSQL ready (localhost:5432)
✓ Redis ready (localhost:6379)
✓ Migrations applied
✓ Setup complete!

Access the app at:
  https://localhost/                    (dashboard + API via nginx)
  https://localhost:8000/api/docs       (API documentation)
  http://localhost:9090                 (Prometheus metrics)
  http://localhost:16686                (Jaeger tracing)
```

---

## Step 3: Verify Setup

```bash
# Check PostgreSQL is running
docker compose ps

# Check app is responding
curl -k https://localhost/health
# Should return: {"status":"healthy"}

# Run quick test
uv run pytest tests/unit/ -q
# Should show: X passed
```

---

## Step 4 (Optional): Customize Environment

The setup creates a `.env` file with defaults. Edit it if needed:

```bash
# View current configuration
cat .env

# Edit if needed (most defaults are fine for local dev)
nano .env

# Restart services if you changed DATABASE_URL or service URLs
docker compose restart
```

**Common customizations:**

| Variable | Default | Why Change |
|----------|---------|-----------|
| `LOG_LEVEL` | `INFO` | Change to `DEBUG` for verbose logging |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline` | Change if using different host/port |
| `REDIS_URL` | `redis://localhost:6379/0` | Change if using external Redis |
| `BACKGROUND_WORKERS_ENABLED` | `true` | Set to `false` to disable background job queue |

---

## What Just Happened?

### Services Started

```
PostgreSQL 17          localhost:5432   → Main application database
PostgreSQL (test)      localhost:5433   → Separate DB for parallel tests
Redis                  localhost:6379   → Cache + session store
Redpanda (Kafka)       localhost:9092   → Event streaming
MongoDB                localhost:27017  → Document store (for scraper data)
Jaeger                 localhost:16686  → Distributed tracing UI
nginx                  localhost:443    → Reverse proxy (HTTPS termination)
```

### Database Schema Created

Alembic migrations were applied, creating tables:
- `records` — ingested data records
- `pipeline_jobs` — job execution history
- And others based on current phase

### Dependencies Installed

Python dependencies are installed in `.venv/`:
- FastAPI, Pydantic v2, SQLAlchemy 2.0
- APScheduler, pytest, Prometheus client, OpenTelemetry
- And many more (see `pyproject.toml`)

### HTTPS Certificates Generated

Self-signed certificates for local development. Installed in system trust store by `mkcert` (no browser warnings).

---

## Common Next Steps

For canonical command workflows, use **[03 — Daily Development](03-daily-development.md)** and **[Dev Commands](dev/commands.md)**.

### Access the Application

| URL | Purpose |
|-----|---------|
| `https://localhost/` | Dashboard (if frontend built) |
| `https://localhost/api/docs` | Swagger UI (interactive API docs) |
| `https://localhost/api/redoc` | ReDoc (alternative API docs) |
| `http://localhost:9090` | Prometheus metrics |
| `http://localhost:16686` | Jaeger tracing |

### Submit a Test Request

```bash
# Create a record via API
curl -X POST https://localhost/api/v1/records \
  -H "Content-Type: application/json" \
  -d '{"source": "test", "timestamp": "2024-04-22T12:00:00", "data": {}}' \
  -k  # -k ignores self-signed certificate warning

# Query records
curl -X GET https://localhost/api/v1/records -k
```

For additional API usage and request patterns, use Swagger at `https://localhost/api/docs`.

---

## Stopping Services

```bash
# Stop without removing (data persists)
docker compose stop

# Stop and remove containers (data persists in named volumes)
docker compose down

# Stop, remove containers, AND delete data
docker compose down -v
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check Docker is running
docker ps

# Check for port conflicts
lsof -i :5432      # PostgreSQL
lsof -i :6379      # Redis
lsof -i :443       # nginx

# If ports in use, either:
# 1. Stop the other service using that port
# 2. Edit docker-compose.yml to use different ports
```

### Migrations Failed

```bash
# Check migration status
uv run alembic current

# View migration history
uv run alembic history --verbose

# Reapply from scratch
docker compose exec db psql -U postgres -c "DROP DATABASE data_pipeline;"
uv run alembic upgrade head
```

### Certificate Trust Issues on macOS

```bash
# Reinstall certificates
bash scripts/setup-https.sh

# Or manually:
mkcert -install
```

### Python Dependencies Conflict

```bash
# Clean and reinstall
rm -rf .venv
uv sync --upgrade
```

---

## Next Steps

1. **Understand daily workflows**: See **[03 — Daily Development](03-daily-development.md)**
2. **Explore the architecture**: See **[04 — Architecture Overview](04-architecture-overview.md)**
3. **Run full test suite**: `bash scripts/test.sh all`
4. **Start the dev server**: `uv run uvicorn ingestor.main:app --reload`

---

## Important: Environment for Testing

Most unit tests use **in-memory SQLite** and don't require a running PostgreSQL. Integration tests do require PostgreSQL.

To run tests:

```bash
# Run all (unit + integration)
uv run pytest tests/ -v

# Just unit tests (fast, no DB required)
uv run pytest tests/unit/ -v

# Just integration tests (requires PostgreSQL)
uv run pytest tests/integration/ -v
```

See **[Dev Commands](dev/commands.md)** for detailed testing and CI-related command workflows.
