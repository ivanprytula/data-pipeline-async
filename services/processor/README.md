# processor

Kafka enrichment consumer. Reads pipeline events from a Redpanda topic,
enriches them, and emits results downstream with OpenTelemetry tracing.

## Quick Start

### Prerequisites

- Docker, Docker Compose

### Spin Up

```bash
docker compose up processor redpanda
```

### Check Health

```bash
curl http://localhost:8002/health
```

## Port

| Environment    | Port   |
| -------------- | ------ |
| Docker Compose | `8002` |
| Local dev      | `8002` |

## Key Environment Variables

| Variable                      | Default              | Notes                      |
| ----------------------------- | -------------------- | -------------------------- |
| `KAFKA_BOOTSTRAP_SERVERS`     | `redpanda:9092`      | Redpanda/Kafka broker list |
| `KAFKA_TOPIC`                 | `pipeline-events`    | Input topic                |
| `KAFKA_GROUP_ID`              | `processor-group`    | Consumer group             |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://jaeger:4317` | Trace exporter             |
| `LOG_LEVEL`                   | `INFO`               | Logging verbosity          |

## Architecture

```text
Kafka consumer (consumer.py)
  └─ aiokafka AsyncConsumer
       └─ Message enrichment (routers/)
            └─ OpenTelemetry tracing (otel.py)
```

## Running Tests

```bash
# From repo root
uv run pytest services/processor/tests/ -v
```

## Cleanup

```bash
docker compose down processor redpanda
```

## Further Reading

- [Architecture Overview](../../docs/04-architecture-overview.md)
