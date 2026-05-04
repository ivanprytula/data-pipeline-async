# dashboard

Server-side rendered UI. Jinja2 templates served by FastAPI with a real-time
metrics stream via Server-Sent Events (SSE), proxied from the ingestor and
Prometheus.

## Quick Start

### Prerequisites

- Docker, Docker Compose

### Spin Up

```bash
docker compose up dashboard ingestor
```

### Open in Browser

```text
http://localhost:8003
```

## Port

| Environment    | Port   |
| -------------- | ------ |
| Docker Compose | `8003` |
| Local dev      | `8003` |

## Key Environment Variables

| Variable         | Default                  | Notes                         |
| ---------------- | ------------------------ | ----------------------------- |
| `INGESTOR_URL`   | `http://ingestor:8000`   | Upstream ingestor API         |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Metrics source for SSE stream |
| `LOG_LEVEL`      | `INFO`                   | Logging verbosity             |

## Architecture

```text
FastAPI routes (routers/)
  ├─ pages.py   — Jinja2 HTML page rendering
  ├─ ops.py     — JSON API proxying ingestor endpoints
  └─ sse.py     — Server-Sent Events metric stream
       └─ httpx AsyncClient → Prometheus /metrics
```

## Running Tests

```bash
# From repo root — no upstream services needed (httpx is mocked)
uv run pytest services/dashboard/tests/ -v
```

## Cleanup

```bash
docker compose down dashboard
```

## Further Reading

- [Architecture Overview](../../docs/04-architecture-overview.md)
