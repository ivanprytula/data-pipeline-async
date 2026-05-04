# webhook

Inbound webhook gateway. Validates HMAC signatures, enforces idempotency,
writes an audit log to PostgreSQL, and publishes events to Redpanda.

## Quick Start

### Prerequisites

- Docker, Docker Compose

### Spin Up

```bash
docker compose up webhook db redpanda
```

### Check Health

```bash
curl http://localhost:8004/health
```

## Port

| Environment    | Port   |
| -------------- | ------ |
| Docker Compose | `8004` |
| Local dev      | `8004` |

## Key Environment Variables

| Variable                  | Default                    | Notes                                  |
| ------------------------- | -------------------------- | -------------------------------------- |
| `DATABASE_URL`            | `postgresql+asyncpg://...` | Must include `+asyncpg` dialect prefix |
| `KAFKA_BOOTSTRAP_SERVERS` | `redpanda:9092`            | Redpanda/Kafka broker list             |
| `KAFKA_TOPIC`             | `webhook-events`           | Outbound event topic                   |
| `LOG_LEVEL`               | `INFO`                     | Logging verbosity                      |

## Architecture

```text
FastAPI routes (routers/)
  └─ HMAC verification (core/security.py)
  └─ Idempotency check (crud.py)
  └─ Audit log (PostgreSQL via asyncpg)
       └─ Kafka publish (aiokafka)
```

## API Endpoints

| Method | Path                                      | Description                    |
| ------ | ----------------------------------------- | ------------------------------ |
| GET    | `/health`                                 | Liveness probe                 |
| POST   | `/api/v1/webhooks/{source}`               | Receive a signed webhook event |
| GET    | `/api/v1/webhooks/{source}/{delivery_id}` | Retrieve audit log entry       |

## Running Tests

```bash
# From repo root — uses aiosqlite in-memory, Kafka is mocked
uv run pytest services/webhook/tests/ -v
```

## Cleanup

```bash
docker compose down webhook
```

## Further Reading

- [Architecture Overview](../../docs/04-architecture-overview.md)
- [Webhook Integration](../../docs/webhook-integration.md)
- [Webhook Debugging](../../docs/webhook-debugging.md)
