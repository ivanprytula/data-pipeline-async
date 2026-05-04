# analytics

Read-side CQRS service. Exposes materialized views and aggregated query endpoints
over the records dataset in PostgreSQL.

## Quick Start

### Prerequisites

- Docker, Docker Compose

### Spin Up

```bash
docker compose up analytics db
```

### Check Health

```bash
curl http://localhost:8005/health
```

## Port

| Environment    | Port   |
| -------------- | ------ |
| Docker Compose | `8005` |
| Local dev      | `8005` |

## Key Environment Variables

| Variable       | Default                    | Notes                                  |
| -------------- | -------------------------- | -------------------------------------- |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Read replica recommended in production |
| `DB_ECHO`      | `false`                    | Set `true` to log all SQL              |
| `LOG_LEVEL`    | `INFO`                     | Logging verbosity                      |

## Architecture

```text
FastAPI routes (routers/)
  └─ AsyncSession (database.py)
       └─ asyncpg → PostgreSQL 17
            └─ records_hourly_stats  (materialized view)
            └─ records_archive       (partitioned table)
```

## API Endpoints

| Method | Path                             | Description                               |
| ------ | -------------------------------- | ----------------------------------------- |
| GET    | `/health`                        | Liveness probe                            |
| GET    | `/api/v1/analytics/hourly-stats` | Hourly aggregation from materialized view |
| GET    | `/api/v1/analytics/sources`      | Per-source record counts                  |

## Running Tests

```bash
# From repo root
uv run pytest services/analytics/tests/ -v
```

## Cleanup

```bash
docker compose down analytics
```

## Further Reading

- [Architecture Overview](../../docs/04-architecture-overview.md)
