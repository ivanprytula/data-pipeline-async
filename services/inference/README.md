# inference

AI vendor adapter. Generates embeddings and serves vector search results backed by Qdrant.

## Quick Start

### Prerequisites

- Docker, Docker Compose

### Spin Up

```bash
docker compose up inference qdrant
```

### Check Health

```bash
curl http://localhost:8001/health
```

## Port

| Environment    | Port   |
| -------------- | ------ |
| Docker Compose | `8001` |
| Local dev      | `8001` |

## Key Environment Variables

| Variable          | Default              | Notes                       |
| ----------------- | -------------------- | --------------------------- |
| `QDRANT_URL`      | `http://qdrant:6333` | Vector store endpoint       |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2`   | sentence-transformers model |
| `LOG_LEVEL`       | `INFO`               | Logging verbosity           |

## Architecture

```text
FastAPI routes (routers/)
  └─ Embedding pipeline (embeddings.py)
       └─ sentence-transformers → vector
  └─ Vector store (vector_store.py)
       └─ Qdrant client → similarity search
```

## API Endpoints

| Method | Path      | Description                           |
| ------ | --------- | ------------------------------------- |
| GET    | `/health` | Liveness probe                        |
| POST   | `/embed`  | Generate embedding for a text payload |
| POST   | `/search` | Nearest-neighbour vector search       |

## Running Tests

```bash
# From repo root
uv run pytest services/inference/tests/ -v
```

## Cleanup

```bash
docker compose down inference qdrant
```

## Further Reading

- [Architecture Overview](../../docs/04-architecture-overview.md)
