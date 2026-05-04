# Services

Multi-service directory for Data Zoo Platform microservices.

## Directory Structure

```text
services/
├── processor/       (Phase 1: Kafka consumer, processes events)
├── ai_gateway/      (Phase 3: Embeddings + vector search)
├── query_api/       (Phase 5: Analytics + CQRS read model)
└── dashboard/       (Phase 6: HTMX + SSE frontend)
```

## Phase Timeline

Each service is added in a specific phase of the 8-phase roadmap:

| Service        | Phase | Purpose                                                                                | Status    |
| -------------- | ----- | -------------------------------------------------------------------------------------- | --------- |
| **processor**  | 1     | Consumes events from Kafka topic; transforms/validates; writes to PostgreSQL           | ⏳ Queued |
| **ai_gateway** | 3     | Embeddings service; calls OpenAI/Ollama; stores vectors in Qdrant; semantic search API | ⏳ Queued |
| **query_api**  | 5     | Read-only analytics service; materialized views; window functions; CQRS pattern        | ⏳ Queued |
| **dashboard**  | 6     | Backend-rendered HTML (HTMX + Jinja2); data explorer; semantic search UI; live metrics | ⏳ Queued |

## Development

Each service:

- Has its own `main.py` (FastAPI or similar)
- Has its own `Dockerfile` (multi-stage build)
- Shares `pyproject.toml` dependencies (deps added to root `pyproject.toml`, services optionally override)
- Can be run locally via `docker compose` or standalone
- Has integration tests in `tests/` at the root level

### Running Locally

```bash
# All services + local dependencies
docker compose up --build

# Specific service
docker compose up processor
```

## Testing

Services are tested as part of the main test suite:

```bash
uv run pytest tests/ -v
```

Integration tests verify inter-service communication (Kafka, HTTP calls, database writes, etc.).

## Deployment

Each service is deployed independently:

- **Docker**: Multi-stage Dockerfile per service
- **AWS ECS Fargate**: Task definition per service (Phase 7)
- **Local**: `docker-compose` orchestration

---

**Related:** See [Architecture — Data Zoo Platform](../docs/design/architecture.md) for the full system design.
