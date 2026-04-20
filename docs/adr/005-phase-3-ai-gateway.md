# ADR 005: Phase 3 — AI Gateway Architecture with Semantic Search

**Status**: Accepted
**Date**: April 20, 2026
**Part of**: [Architecture — Data Zoo Platform](../architecture.md)
**Related ADRs**: [ADR 002: Qdrant vs pgvector](002-qdrant-vs-pgvector.md)
**Context**: Phase 3 introduces semantic search capabilities via a dedicated AI Gateway service. This ADR documents the architectural decisions and learning patterns.

---

## Decision

**Implement AI Gateway as a separate FastAPI service that:**

1. Provides embeddings API (`/embed`, `/embed-batch`)
2. Indexes documents to Qdrant (`/index`)
3. Performs semantic similarity search (`/search`)
4. Uses lazy-loaded sentence transformers with LRU caching
5. Communicates with app via HTTP (not direct Qdrant client)

---

## Options Considered

### Option A: Direct Qdrant from App (Monolithic)

- **Pros:**
  - Simpler: fewer services
  - Lower latency (no HTTP overhead)
  - Easier to debug (single process)
- **Cons:**
  - App becomes coupled to vector store
  - Embedding model (380M parameters) slows down main service
  - Harder to scale embeddings independently
  - Not production-realistic (tech giants like Anthropic, OpenAI separate this layer)

### Option B: AI Gateway as Dedicated Service ✅

- **Pros:**
  - Clear separation of concerns (API vs AI)
  - Embeddings service can scale independently
  - Reusable by multiple consumers (batch indexing, admin tools, etc.)
  - Mirrors real-world architecture (embedding APIs are commoditized)
  - Each service has a single reason to change
- **Cons:**
  - One additional Docker container
  - Network latency between app ↔ gateway
  - Requires circuit breakers for resilience

### Option C: Async Workers + Qdrant

- **Pros:**
  - Async flexibility
  - Could leverage parallel embeddings (batch processing)
- **Cons:**
  - Over-engineered for Phase 3 (no queue backlog problems yet)
  - Still needs gateway-like abstraction

---

## Rationale

### 1. Single Responsibility Principle (SRP)

- **API svc**: Route handling, auth, business logic
- **AI Gateway**: Embeddings, vector indexing, semantic search
- **Qdrant**: Persisted vector index

Each has one reason to change. If embeddings logic changes (e.g., switch models), only AI Gateway updates.

### 2. Scaling & Performance

- Embedding model uses CPU (50M parameters). Without isolation:
  - Loading model on every app restart wastes time
  - During high search load, embeddings block API routes
- Separate service allows:
  - Independent horizontal scaling (`docker-compose up -d --scale ai-gateway=2`)
  - Load balancer distributes embedding requests
  - App remains snappy for business logic

### 3. Architectural Realism

**Real-world pattern** (OpenAI, Anthropic, Cohere):

```text
App Tier
  ├─ Route handler (FastAPI)
  ├─ Auth middleware
  └─ HTTP calls to Embeddings API

Embedding Tier (independent)
  ├─ Sentence-transformers model
  ├─ LRU cache
  └─ Batch processing logic

Vector DB Tier
  └─ Qdrant (persistence)
```

**What we're learning**:

- Tier separation and resilience patterns
- How external APIs are consumed (HTTP, error handling, timeouts)
- Trade-offs of HTTP vs direct client (latency vs isolation)

### 4. Async Patterns in FastAPI

AI Gateway shows:

- `asyncio.run()` isolated to lifespan (model loading)
- LRU caching with `functools` in async context
- Batch operations more efficient than individual calls
- Dependency injection for vector store

---

## Architecture Diagram

```text
┌─────────────────────────────────────────────────────────┐
│ App Service (Port 8000)                                 │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ FastAPI Routes (business logic)                     │ │
│ └────────────────────┬────────────────────────────────┘ │
│                      │ HTTP POST /search                 │
│                      │ {"query": "..."}                  │
│                      ▼                                    │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Search Integration Layer                            │ │
│ │ ┌──────────────────────────────────┐                │ │
│ │ │ from services.search import ...  │                │ │
│ │ └──────────────────────────────────┘                │ │
│ └──────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────┘
                      │
      ┌───────────────┼───────────────┐
      │ HTTP          │ HTTP          │ HTTP
      ▼               ▼               ▼
┌─────────────────────────────────────────────────────────┐
│ AI Gateway Service (Port 8001)                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ POST /embed       — Single text embedding          │ │
│ │ POST /embed-batch — Multiple texts                 │ │
│ │ POST /index       — Upsert to Qdrant               │ │
│ │ POST /search      — Similarity search + filters    │ │
│ │ GET /health       — Liveness probe                 │ │
│ └────────────────┬────────────────────────────────────┘ │
│                  │                                       │
│                  ▼                                       │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Embeddings Module                                   │ │
│ │ ┌─────────────────────────────────────────────────┐ │ │
│ │ │ SentenceTransformer (all-MiniLM-L6-v2)        │ │ │
│ │ │ • Lazy-loaded on first use                    │ │ │
│ │ │ • LRU cache: 1000 max entries                 │ │ │
│ │ │ • Output: 384-dim vectors                     │ │ │
│ │ └─────────────────────────────────────────────────┘ │ │
│ └─────────────────────┬────────────────────────────────┘ │
│                       │ Vector endpoints                  │
│                       ▼                                    │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Vector Store Module (Qdrant client)                │ │
│ │ • Upsert points with metadata                      │ │
│ │ • Search with HNSW indexes                         │ │
│ │ • Optional metadata filtering                      │ │
│ └──────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────┘
                      │
      ┌───────────────┴───────────────┐
      │ gRPC                          │
      ▼                               ▼
┌──────────────────────┐  ┌──────────────────────┐
│ Qdrant Service       │  │ Qdrant Web UI        │
│ (Port 6333)          │  │ (Port 6334)          │
│ • Collections        │  │ • Explore data       │
│ • HNSW indexes       │  │ • Debug queries      │
│ • Persistence       │  │ • Collection stats   │
└──────────────────────┘  └──────────────────────┘
```

---

## Implementation Details

### Service Composition (docker-compose.yml)

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - '6333:6333'  # REST + gRPC
    healthcheck: [curl http://localhost:6333/health]

  ai-gateway:
    build: services/ai-gateway/Dockerfile
    environment:
      - QDRANT_URL=http://qdrant:6333
    ports:
      - '8001:8001'
    depends_on:
      - qdrant
    healthcheck: [curl http://localhost:8001/health]

  app:
    environment:
      - AI_GATEWAY_URL=http://ai-gateway:8001
    depends_on:
      - ai-gateway
```

### API Contract

**Embed Request/Response:**

```json
POST /embed
{
  "text": "semantic search example"
}

→ {
  "embedding": [0.123, -0.456, ...],  // 384 dims
  "dimension": 384
}
```

**Search Request/Response:**

```json
POST /search
{
  "query": "find documents about caching",
  "top_k": 5,
  "collection": "documents",
  "filters": {"source": "blog"}  // optional
}

→ {
  "results": [
    {
      "id": 42,
      "score": 0.89,
      "metadata": {"source": "blog", "title": "..."}
    }
  ],
  "count": 1,
  "query": "..."
}
```

---

## Embedding Model Choice: all-MiniLM-L6-v2

| Aspect | Rationale |
|--------|-----------|
| **Model Name** | all-MiniLM-L6-v2 (HuggingFace) |
| **Size** | ~50M parameters, 384-dim output |
| **Speed** | ~1000 docs/sec on CPU |
| **Quality** | Good trade-off for semantic search (MTEB rank #11) |
| **License** | Apache 2.0 (commercial-friendly) |
| **Why NOT GPT/Claude** | Overkill for embeddings (too slow, too expensive) |
| **Why NOT word2vec** | Outdated (doesn't understand phrases) |

---

## Resilience & Failure Modes

### Scenario 1: AI Gateway Down

**Current behavior** (Phase 3):

- Search requests to app fail with 503
- App's `/search` endpoint returns error

**Phase 4 improvement**:

- Cache last 100 queries in Redis
- Return stale results with `"stale": true` flag
- Implement circuit breaker (stop calling after 5 failures)

### Scenario 2: Qdrant Down

**Current**: AI Gateway lifespan fails, service won't start (healthy design)

**Options for Phase 4**:

- Spring gracefully, allow indexing to queue (Redis)
- Serve stale results from cache
- Switch to pgvector backup automatically

### Scenario 3: High Latency

**Current**: HTTP overhead ~5-10ms per embedding

**Optimization (Phase 4)**:

- Batch embedding requests (amortize transport)
- Implement request pooling in app
- Monitor via Prometheus: `ai_gateway_latency_p99`

---

## Testing Strategy

### Unit Tests (Phase 3)

- Mock `SentenceTransformer` (don't load real model)
- Test LRU cache: verify cache hits/misses
- Mock Qdrant client: test upsert/search logic

### Integration Tests (Phase 4)

- Docker Compose stack with all services
- Load AI Gateway with 100 embedding requests
- Verify Qdrant points persisted
- Mock app → gateway → qdrant round-trip

### Load Testing (Phase 5)

- k6 script: concurrent search requests
- Measure P99 latency, throughput
- Identify bottleneck (embeddings vs Qdrant vs network)

---

## Consequences

### Positive

✅ Clear separation: API logic ↔ AI logic ↔ Vector DB
✅ Teaches realistic multi-service architecture
✅ Embedding service independently scalable
✅ Prepares for LLM integration (Phase 6)
✅ Each service has one reason to change

### Negative

❌ Additional deployment complexity
❌ Network round-trips (app → gateway → qdrant)
❌ Harder to debug than monolithic
❌ Eventual consistency between app's cache + Qdrant

### Mitigations

- Health checks on all services (fail fast)
- Circuit breakers for app → gateway (Phase 4)
- Structured logging with correlation IDs
- Metrics: latency, errors, cache hit rates

---

## Future Work

**Phase 4: Caching & Optimization**

- Redis caching for frequent queries
- Circuit breaker pattern
- Batch embedding pooling

**Phase 5: Comparison & Trade-offs**

- Add pgvector implementation (ADR 002)
- Load test: Qdrant vs pgvector latency
- Document when to use each

**Phase 6: LLM Integration**

- Add `/rerank` endpoint (LLM-based snippet reranking)
- Combine semantic search + LLM for RAG

**Phase 7: Multi-modal**

- Add image embeddings (CLIP model)
- `/embed-image` endpoint

---

## References

- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Sentence Transformers](https://www.sbert.net/) — embedding models
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) — model rankings
- [Locality Sensitive Hashing](https://en.wikipedia.org/wiki/Locality-sensitive_hashing) — approximate NN theory
- [FastAPI Best Practices](https://fastapi.tiangolo.com/deployment/concepts/#high-availability)

---

**Decision Maker**: Team
**Agreed Upon**: Phase 3 (April 20, 2026)
**Supersedes**: None
**Superseded By**: [ADR 006 (Future)](./006-phase-4-caching.md) (if created)
