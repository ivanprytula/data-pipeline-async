# System Architecture — Data Zoo Platform

**Last Updated**: April 21, 2026
**Scope**: Phase 0 (Foundation) → Phase 8 (Production)
**Status**: In Design (Phase 1+ implementation pending)

---

## Monorepo Target Structure (Phases 0–8)

```text
data-pipeline-async/
├── app/                          (Phase 1+: Ingestor service)
│   ├── main.py
│   ├── crud.py                   (Ingestor-specific CRUD: Record operations)
│   ├── models.py
│   ├── schemas.py
│   ├── events.py                 (← Phase 1: Kafka producer singleton)
│   ├── routers/
│   ├── scrapers/                 (← Phase 2: Scraper implementations)
│   ├── storage/                  (← Platform-wide storage layer)
│   │   ├── __init__.py
│   │   ├── events.py             (← Phase 1: ProcessedEvent CRUD for event tracking)
│   │   └── mongo.py              (← Phase 2: MongoDB client)
│   └── core/circuit_breaker.py    (← Phase 4: Resilience patterns)
│
├── services/                      (← Phase 1+: New microservices)
│   ├── processor/                 (Phase 1: Kafka consumer)
│   ├── ai-gateway/               (Phase 3: Embeddings + Qdrant)
│   ├── query-api/                (Phase 5: Analytics + CQRS)
│   └── dashboard/                (Phase 6: HTMX + SSE frontend)
│
├── infra/
│   ├── terraform/                (← Phase 7: IaC for AWS)
│   ├── monitoring/               (← Phase 8: Prometheus + Grafana)
│   ├── scripts/
│   │   ├── backup.sh             (← Phase 8)
│   │   └── chaos.sh              (← Phase 8)
│   └── database/
│
├── docs/
│   ├── adr/                       (← Phase 0: ADR stubs)
│   │   ├── 001-kafka-vs-rabbitmq.md
│   │   ├── 002-qdrant-vs-pgvector.md
│   │   └── 003-htmx-vs-react.md
│   ├── architecture.md            (← This file, monorepo target structure)
│   ├── pillar-*.md               (Consolidated domain knowledge)
│   └── decisions.md              (Tech choice trade-off reasons)
│
├── learning_docs/
│   └── ACTION_PLAN.md            (← Phase 0: 8-week execution roadmap)
│
├── .github/
│   ├── instructions/             (8 phase guides + templates)
│   ├── prompts/
│   │   ├── plan-dataZooScaffolding.prompt.md
│   │   └── plan-dataZooPlatform.prompt.md
│   └── workflows/
│
├── docker-compose.yml            (← Evolves per phase)
├── pyproject.toml                (← Evolves per phase)
└── README.md
```

---

## Phase Progression

| Phase | Focus                | Services            | Components Added                                    |
| ----- | -------------------- | ------------------- | --------------------------------------------------- |
| **0** | Docs & Planning      | —                   | ADRs, architecture, ACTION_PLAN, monorepo structure |
| **1** | Event Streaming      | ingestor, processor | Redpanda, Kafka producer/consumer, fail-open events |
| **2** | Data Scraping        | + scrapers          | HTTP/HTML/browser scrapers, MongoDB client          |
| **3** | AI + Vector DB       | ai-gateway          | Qdrant, sentence-transformers, embeddings           |
| **4** | Resilience Patterns  | processor (updated) | Circuit breaker, DLQ, OpenTelemetry, Jaeger         |
| **5** | CQRS Read Layer      | query-api           | Materialized views, window functions, partitioning  |
| **6** | Dashboard            | dashboard           | HTMX, Jinja2, SSE, backend-rendered UI              |
| **7** | Cloud Deployment     | (all services)      | Terraform, AWS ECS Fargate, RDS, MSK, ElastiCache   |
| **8** | Production Hardening | (all services)      | Prometheus, Grafana, backups, chaos testing         |

---

## High-Level Data Flow (Phase 8 complete)

```mermaid
graph TB
    Client["👤 API Client (HTTPS)"]
    ALB["⚡ AWS Application<br/>Load Balancer"]

    subgraph Compute["AWS ECS Fargate"]
        Ingestor["📝 Ingestor<br/>(app/)"]
        Scraper["🕷️ Scraper<br/>(Phase 2)"]
        Processor["⚙️ Processor<br/>(services/)"]
        AIGateway["🤖 AI Gateway<br/>(embeddings)"]
        QueryAPI["📊 Query API<br/>(analytics)"]
        Dashboard["🎨 Dashboard<br/>(HTMX)"]
    end

    subgraph Data["AWS Data Layer"]
        RDS["🗄️ PostgreSQL 17<br/>(RDS)"]
        MongoDB["📚 MongoDB<br/>(document store)"]
        Qdrant["🔍 Qdrant<br/>(vector DB)"]
        Redis["⚡ Redis<br/>(ElastiCache)"]
    end

    subgraph Messaging["AWS MSK<br/>(Kafka)"]
        Topics["📬 Topics<br/>records.events<br/>records.events.dlq"]
    end

    subgraph Observability["Observability"]
        Prometheus["📈 Prometheus"]
        Grafana["📊 Grafana"]
        Jaeger["🔍 Jaeger"]
    end

    Client -->|HTTPS| ALB
    ALB --> Ingestor
    ALB --> Dashboard
    Ingestor -->|publish| Topics
    Ingestor -->|write| RDS
    Ingestor -->|cache| Redis
    Topics -->|consume| Processor
    Processor -->|embed| AIGateway
    Processor -->|store| Qdrant
    Processor -->|log errors| Topics
    AIGateway -->|store| Qdrant
    QueryAPI -->|read analytics| RDS
    QueryAPI -->|listen| Topics
    Dashboard -->|query| QueryAPI
    Dashboard -->|search| AIGateway
    Ingestor -->|metrics| Prometheus
    Processor -->|metrics| Prometheus
    QueryAPI -->|metrics| Prometheus
    Prometheus -->|visualize| Grafana
    Ingestor -->|trace| Jaeger
    Processor -->|trace| Jaeger

    style Compute fill:#e3f2fd,stroke:#1976d2
    style Data fill:#fff3e0,stroke:#e65100
    style Messaging fill:#f3e5f5,stroke:#6a1b9a
    style Observability fill:#e8f5e9,stroke:#2e7d32
```

---

## Phase 0: Docs Consolidation (Foundation)

**Goal**: Establish single source of truth before any Phase 1 code.

### Architecture Goals

1. **Monorepo structure** — clearly separates services and shared code
2. **ADR-driven decisions** — all major choices documented with trade-offs
3. **Consolidated docs** — `docs/pillar-*.md` own one domain each; no duplication
4. **Execution roadmap** — `learning_docs/ACTION_PLAN.md` maps 8 phases to 16 weeks

### Key Files Created

- [ADR 001: Kafka vs RabbitMQ](adr/001-kafka-vs-rabbitmq.md) — Why Redpanda + Kafka API
- [ADR 002: Qdrant vs pgvector](adr/002-qdrant-vs-pgvector.md) — Why Qdrant primary, pgvector secondary
- [ADR 003: HTMX vs React](adr/003-htmx-vs-react.md) — Why HTMX + backend templates (Phase 6)
- This file: `docs/architecture.md` — Monorepo target + data flow diagrams

---

## Phase 1: Event-Driven Architecture (Current State)

```mermaid
graph TB
    Client["👤 API Client<br/>HTTP"]

    subgraph Ingestor["📝 Ingestor Service (app/)"]
        Router["🔀 Router<br/>/api/v1/records"]
        Validation["✔️ Pydantic v2"]
        CRUD["📦 Record CRUD<br/>app/crud.py"]
        Producer["📤 Kafka Producer<br/>app/events.py"]
    end

    subgraph Storage["🗄️ Platform Storage (app/storage/)"]
        EventsCRUD["📊 Event Storage<br/>app/storage/events.py<br/>(shared: ingestor + processor)"]
    end

    subgraph DB["🗄️ PostgreSQL 17"]
        Pool["🔌 AsyncSessionLocal<br/>asyncpg pool"]
        Tables["📋 records table"]
    end

    subgraph Cache["⚡ Redis Optional"]
        RedisNode["💾 Cache<br/>app/cache.py"]
    end

    subgraph Messaging["📬 Redpanda<br/>Kafka-compatible"]
        Topic1["📌 records.events"]
        Topic2["⚠️ records.events.dlq"]
    end

    subgraph ProcessorService["⚙️ Processor Service<br/>services/processor/"]
        Consumer["📥 AIOKafkaConsumer"]
        EventLogger["📝 Event Logger"]
    end

    Client -->|HTTP POST| Router
    Router --> Validation
    Validation --> CRUD
    CRUD -->|INSERT| Pool
    Pool -->|SQLAlchemy 2.0| Tables

    CRUD -->|cache check| RedisNode
    RedisNode -->|hit/miss| CRUD

    CRUD -->|after write| Producer
    Producer -->|publish| Topic1
    Producer -.->|fail-open:error| Topic2

    Topic1 -->|consume| Consumer
    Consumer -->|track idempotency| EventsCRUD
    EventsCRUD -->|store status| Pool
    Consumer --> EventLogger
    EventLogger -->|stdout JSON| Logs["📊 docker logs<br/>processor"]

    style Ingestor fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Storage fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style DB fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style Cache fill:#ffe0b2,stroke:#e65100,stroke-width:1px
    style Messaging fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
    style ProcessorService fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
```

**Phase 1 Flows:**

- **Ingest**: POST `/api/v1/records` → validate → store in PostgreSQL → publish Kafka event
- **Event**: Redpanda topic receives `{record_id, source}` payload
- **Consume**: Processor subscribes, logs each event to stdout
- **Fail-open**: If Kafka unavailable, request still succeeds (warning logged, event lost)
- **Cache** (optional): Redis for read-through caching
- **DLQ**: Failed messages route to dead letter queue for replay

## Components

### 🔀 FastAPI Application Layer

**Location**: \`app/main.py\`, \`app/routers/\`

**Responsibilities:**

- HTTP endpoint routing (\`/api/v1/records/*\`)
- Request validation via Pydantic v2
- Dependency injection (database sessions, logging)
- Error handling & HTTP exceptions
- Correlation ID propagation

### 📦 CRUD Layer

**Location**: \`app/crud.py\`

**Responsibilities:**

- Pure async database operations
- SQLAlchemy 2.0 ORM queries (\`select()\`, \`insert()\`, \`update()\`)
- Session lifecycle management
- Transaction handling (\`commit/rollback\`)

**Key Pattern:**
\`\`\`python
async def get_record(db: AsyncSession, record_id: int) -> Record | None:
    result = await db.execute(select(Record).where(Record.id == record_id))
    return result.scalar_one_or_none()
\`\`\`

### 🗄️ PostgreSQL + asyncpg

**Location**: \`app/database.py\`

**Configuration:**

- \`pool_size=5\`: Connections in pool
- \`max_overflow=10\`: Extra connections under load
- \`expire_on_commit=False\`: Keep ORM objects after commit (CRITICAL!)

### 🏷️ Correlation ID Tracing

**Location**: \`app/core/logging.py\`

Tracks requests end-to-end via ContextVar, injected into every log.

### 📤 Kafka Producer (Phase 1)

**Location**: `app/events.py`

**Responsibilities:**

- Singleton AIOKafkaProducer connected in `app/main.py` lifespan
- `publish_record_created(record_id, payload)` — publishes to `records.events` topic
- Fail-open: logs KafkaError but doesn't crash the request
- Generic type: `EventPayload[T]` for typed event payloads

**Key Pattern:**

```python
async def publish_record_created(record_id: int, payload: dict) -> None:
    """Publish record creation event to Kafka (fail-open)."""
    if _producer is None:
        return  # Not connected; silently skip
    try:
        value = json.dumps({"record_id": record_id, **payload}).encode()
        await _producer.send_and_wait("records.events", value=value)
    except KafkaError as exc:
        logger.warning("kafka_publish_failed", extra={"error": str(exc)})
        # Don't crash; events are best-effort observability
```

### 📊 Event Storage Layer (Platform-Wide) — Phase 1+

**Location**: `app/storage/events.py`

**Why it exists**: Processor needs to track consumed events with **industry-standard patterns**:

- **Idempotency**: Duplicate messages don't cause double-processing
- **Status tracking**: Event moves pending → processing → completed/failed/dead_letter
- **DLQ routing**: Failed events persist for later replay/inspection
- **Offset tracking**: Kafka offset stored for recovery after crashes
- **Batch efficiency**: Bulk-insert via INSERT...RETURNING (single round-trip)

**Shared by**: Both ingestor service and processor service (decoupled from `app/crud.py` which is ingestor-specific)

**Core Functions:**

```python
# Deduplication on consume
event, created = await create_processed_event(
    db,
    kafka_topic="records.events",
    kafka_partition=0,
    kafka_offset=1234,
    idempotency_key="uuid-of-event",  # Unique per event
    event_type="record.created",
    payload={"record_id": 42, "source": "api"}
)
# If same idempotency_key arrives twice: created=False (duplicate ignored)

# Track processing state
await mark_event_processing(db, event.id)   # pending → processing
await mark_event_completed(db, event.id)     # processing → completed ✓
await mark_event_failed(db, event.id, "timeout error", {"stack": "..."})  # → failed
await mark_event_dlq(db, event.id, "max retries exceeded")  # → dead_letter (human inspection)
```

**ORM Model**: `app/models.py::ProcessedEvent` with fields:

- `kafka_topic`, `kafka_partition`, `kafka_offset` — Kafka metadata
- `idempotency_key` — unique per event (prevents double-processing)
- `status` — pending | processing | completed | failed | dead_letter
- `payload` — JSON event data
- `error_message`, `error_details` — full context if failed
- `dead_letter_queue` — boolean flag for DLQ routing
- `processing_attempts` — retry count
- `processed_at` — completion timestamp (via TimestampMixin)

### 📥 Kafka Consumer (Phase 1)

**Location**: `services/processor/main.py`

**Responsibilities:**

- Runs as standalone service in Docker
- Subscribes to `records.events` topic with group `processor-group`
- Retry loop on startup (waits for Redpanda leader election)
- Logs each event as JSON to stdout
- Handles malformed messages gracefully

**Execution:**

```bash
docker compose up processor
# or
cd services/processor && python main.py
```

### 📊 Environment-Aware Logging

**Development:**
\`\`\`
2026-04-16 11:18:05 | INFO | app/routers/records.py:45:create_record | [cid-123] record created
\`\`\`

**Production:**
\`\`\`json
{"message": "record_created", "user_id": 42, "cid": "cid-123"}
\`\`\`

### 🧪 Testing Pyramid

- **Unit**: Isolated functions (5+ tests)
- **Integration**: Components together with aiosqlite (20 tests)
- **E2E**: Full HTTP roundtrip with AsyncClient (20 tests)

## How to Update This Diagram

1. Edit this file (\`docs/architecture.md\`)
2. Modify Mermaid syntax
3. Commit & push:
   \`\`\`bash
   git add docs/architecture.md
   git commit -m "docs: update architecture"
   git push origin main
   \`\`\`
4. GitHub auto-renders the diagram
5. Team reviews in PR before merging

## Phase 1 Design Patterns

### Observer Pattern — Event Publishing

When a record is created, the ingestor publishes an event without coupling to the processor:

```text
Record created → Kafka event → Processor consumes asynchronously
↑
No tight dependency between ingestor and processor
```

**Benefits:**

- Processor can be down; ingestor still works (fail-open)
- Multiple consumers can process same event (add more services later)
- Decoupled: ingestor doesn't care if processor succeeds/fails

### TypeVar + Generic — Typed Event Payloads

```python
from typing import Generic, TypeVar

T = TypeVar('T')

class EventPayload(Generic[T]):
    """Future: extend for strongly-typed event schemas."""
    record_id: int
    data: T  # Can be any type: dict, RecordData, etc.
```

This prepares for Phase 2+ when we add scrapers with different payload types.

---

## Phase 2: Data Scraping with Multi-Protocol Support (Current Implementation)

**Status**: ✅ Complete — Scrapers + MongoDB + Kafka event integration
**Timeline**: Week 3–4 (April 2026)

### Architecture

```mermaid
graph TB
    Client["👤 API Client<br/>HTTP"]

    subgraph Ingestor["📝 Ingestor (app/)"]
        RecordsRouter["🔀 Records Router<br/>/api/v1/records"]
    end

    subgraph Scrapers["🕷️ Scraper Service (app/routers/scraper.py)"]
        ScraperRouter["POST /api/v1/scrape/{source}"]
        Factory["🏭 ScraperFactory"]
        HTTPScraper["HTTPScraper<br/>(httpx)"]
        HTMLScraper["HTMLScraper<br/>(BeautifulSoup)"]
        BrowserScraper["BrowserScraper<br/>(Playwright)"]
    end

    subgraph Storage["🗄️ Storage Layer (app/storage/)"]
        Mongo["📚 Motor Async<br/>MongoDB client"]
        Cache["💾 Redis Optional"]
    end

    subgraph Events["📤 Event Publishing (app/events.py)"]
        KafkaProducer["Kafka Producer<br/>publish_doc_scraped()"]
    end

    subgraph Data["Data Persistence"]
        MongoDB_DB["🗄️ MongoDB<br/>(Document store)"]
        RDS["🗄️ PostgreSQL<br/>(Structured data)"]
        Kafka["📬 Redpanda<br/>(Event stream)"]
    end

    Client -->|POST /api/v1/scrape/...| ScraperRouter
    ScraperRouter --> Factory
    Factory -->|REST API| HTTPScraper
    Factory -->|HTML Parse| HTMLScraper
    Factory -->|Browser| BrowserScraper

    HTTPScraper -->|Semaphore(5)<br/>Exponential backoff| Cache
    HTMLScraper -->|Parse HTML| Cache
    BrowserScraper -->|JS rendering| Cache

    HTTPScraper -->|Fail-open| Mongo
    HTMLScraper -->|Fail-open| Mongo
    BrowserScraper -->|Fail-open| Mongo

    Mongo -->|insert_many| MongoDB_DB
    KafkaProducer -->|Async<br/>Fire-and-forget| Kafka
    ScraperRouter -->|Always 200| KafkaProducer

    RDS -.->|Optional analytics| ScraperRouter

    style Scrapers fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style Storage fill:#ffe0b2,stroke:#e65100,stroke-width:2px
    style Data fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
```

### Components

**🏭 ScraperFactory** (`app/scrapers/__init__.py`)

- Dispatches requests to appropriate scraper type
- Pattern: Uniform interface, 3 implementations
- `get_scraper(source: str) -> Scraper`

📡 HTTPScraper

- Uses `httpx.AsyncClient` for REST APIs
- Example: JSONPlaceholder (demo API)
- Features: Exponential backoff (3 retries), timeout (10s), async concurrency

🔍 HTMLScraper

- Uses BeautifulSoup + httpx for HTML parsing
- Example: Hacker News front page
- Features: CSS selector queries, lightweight

🌐 BrowserScraper

- Uses Playwright for JS-rendered content
- Example: Pages requiring browser automation
- Features: Full browser automation, JavaScript execution, cookies/auth

📚 Motor Async MongoDB

- Singleton pattern (app/storage/mongo.py)
- Collection: `scraped` — immutable log of scraped documents
- Fail-open: Errors logged, endpoint still returns 200
- Documents: `{url, title, content, source, created_at, updated_at}`

**📊 ScrapeResponse** (`app/schemas.py`)

```python
class ScrapeResponse(BaseModel):
    source: str
    items_scraped: int       # Documents fetched
    items_stored: int        # Successfully persisted to MongoDB
    duration_ms: int         # Total time (scrape + storage)
    event_published: bool    # Kafka event published?
```

**📤 Kafka Event: `doc.scraped`**

- Published after **every** scrape (success or partial failure)
- Payload: `{source, count, timestamp}`
- Downstream: Processor can track scrape lag, trigger indexing, etc.
- Async fire-and-forget (errors logged, doesn't block response)

### Design Principles (Phase 2)

1. Fail-Open Architecture
   - If MongoDB unavailable → endpoint returns 200 (items_stored=0, error logged)
   - If Kafka unavailable → endpoint returns 200 (event_published=false, error logged)
   - Rationale: Don't cascade failures; user gets feedback; data can be replayed from logs
2. Concurrency Safety with Semaphore
   - `Semaphore(5)` by default (configurable per source)
   - Prevents: Bot bans, rate limiting, connection exhaustion
   - Improves: Observability (easier to debug with 5 vs 100 concurrent)
3. Configurable Resilience

    ```python
    # app/config.py
    SCRAPER_TIMEOUTS = {
        "jsonplaceholder": 10,
        "hn": 15,
        "playwright": 30  # Browser slower
    }
    SEMAPHORE_LIMITS = {
        "jsonplaceholder": 10,  # More aggressive safe
        "hn": 5,                # Conservative
        "playwright": 3         # Heavy on resources
    }
    ```

4. Observable Failures

  ```python
  logger.error("scrape_failed, extra={
      "source": source,
      "duration_ms": duration,
      "error_type": type(e).__name__,
      "count_attempted": len(items),
      "count_stored": stored_count
    })
  ```

### Data Flows

**Happy Path:**

```text
POST /api/v1/scrape/hn?limit=50
  ↓
  ScraperFactory.get_scraper("hn") → HTMLScraper
  ↓
  HTTPScraper.fetch() → [Item, Item, ...]
  ↓
  Motor.insert_many() → MongoDB (created_at assigned)
  ↓
  publish_doc_scraped("hn", 50) → Kafka (async)
  ↓
  Return ScrapeResponse {source: "hn", items_scraped: 50, items_stored: 50, event_published: true}
```

**Degraded (MongoDB down):**

```text
POST /api/v1/scrape/hn
  ↓
  Scrape succeeds → [Item, Item, ...]
  ↓
  Motor.insert_many() → ❌ ConnectionError
  ↓
  logger.error("mongo_error") → [logged]
  ↓
  Kafka event still publishes (items_stored=0)
  ↓
  Return ScrapeResponse {items_scraped: 50, items_stored: 0, event_published: true}
     ⬆️ User sees what happened; can retry; on-call can replay
```

**Cascading Failure (both MongoDB + Kafka down):**

```text
Scrape succeeds → MongoDB fails → Kafka fails
  ↓
  Both errors logged with context
  ↓
  Endpoint still returns 200
  ⬆️ Data lost but logged; replay possible from error logs
```

### Configuration in docker-compose

```yaml
# docker-compose.yml
services:
  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

  app:
    environment:
      MONGO_URL: "mongodb://mongodb:27017"
      MONGO_DB_NAME: "datazoo"
```

### ADR

See [ADR #004: Scraper Architecture](adr/004-scraper-architecture.md) for detailed decision rationale.

---

### Fail-Open Principle

If Kafka is unavailable:

1. `publish_record_created()` logs warning, returns silently
2. POST /api/v1/records still returns 201
3. Request completes; event is lost (telemetry only, not critical data)

This is the opposite of fail-closed (crash on error). For observability, fail-open is acceptable.

---

## Phase 4: Resilience Patterns — Circuit Breaker, DLQ, OpenTelemetry (Current Implementation)

**Status**: ✅ Complete — Circuit breakers + DLQ routing + distributed tracing
**Timeline**: Week 7–8 (April 2026)

### Architecture

```mermaid
graph TB
    Client["👤 API Client<br/>HTTP"]

    subgraph Ingestor["📝 Ingestor (app/)"]
        RecordsRouter["🔀 Records Router<br/>/api/v1/records"]
        EventsPub["📤 Events Publisher<br/>app/events.py"]
        CircuitBreaker1["⚡ Circuit Breaker<br/>@circuit_breaker"]
    end

    subgraph Kafka["📬 Redpanda (Kafka)"]
        TopicMain["Topic: records.events"]
        TopicDLQ["Topic: records.events.dlq"]
    end

    subgraph Processor["⚙️ Processor (services/processor/)"]
        Consumer["Kafka Consumer<br/>MAX_RETRIES=3"]
        DLQRouter["❌ DLQ Router<br/>_send_to_dlq()"]
        OTelSpan["🔍 OTel Span<br/>kafka.consume"]
    end

    subgraph Storage["🗄️ Storage Layer"]
        MongoDB["📚 MongoDB<br/>(scraped docs)"]
        CircuitBreaker2["⚡ Circuit Breaker<br/>@circuit_breaker"]
    end

    subgraph Observability["🔭 Observability"]
        Jaeger["🔍 Jaeger<br/>(OTLP gRPC :4317)"]
        Prometheus["📊 Prometheus<br/>(/metrics)"]
    end

    Client -->|POST /records| RecordsRouter
    RecordsRouter -->|Publish| EventsPub
    EventsPub --> CircuitBreaker1
    CircuitBreaker1 -->|State: CLOSED/OPEN/HALF_OPEN| TopicMain
    CircuitBreaker1 -.->|Metrics| Prometheus

    TopicMain --> Consumer
    Consumer -->|Success| OTelSpan
    Consumer -->|Failure (3x)| DLQRouter
    DLQRouter -->|asyncio.wait_for(5s)| TopicDLQ

    Consumer -->|Embed/Index| MongoDB
    MongoDB --> CircuitBreaker2
    CircuitBreaker2 -.->|Metrics| Prometheus

    EventsPub -.->|Trace| Jaeger
    Consumer -.->|Trace| Jaeger
    OTelSpan -.->|trace_id| Jaeger

    style Ingestor fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    style Processor fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style Observability fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style Kafka fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
```

### Components

**⚡ Circuit Breaker** (`app/core/circuit_breaker.py`)

- Three-state machine: CLOSED → OPEN → HALF_OPEN
- Failure threshold: 5 consecutive failures → circuit opens
- Recovery timeout: 30 seconds before transitioning to HALF_OPEN
- Concurrency safety: `asyncio.Lock` for state transitions
- Applied to:
  - `app/events.py::_send_to_kafka` — protects Kafka producer
  - `app/storage/mongo.py::_mongo_insert_one` — protects MongoDB writes

```python
@circuit_breaker(failure_threshold=5, recovery_timeout=30.0)
async def _send_to_kafka(topic: str, value: bytes) -> None:
    """Kafka publish wrapped with circuit breaker."""
    if _producer is None:
        raise RuntimeError("Producer not connected")
    await _producer.send_and_wait(topic, value=value)
```

**State machine**:

```text
CLOSED ──(failures >= 5)──► OPEN
  ▲                           │
  │                           │ (30s elapsed)
  │                        HALF_OPEN
  │                           │
  └────(next call succeeds)───┘
```

**❌ Dead Letter Queue (DLQ)** (`services/processor/main.py`)

- Retry tracking: `retry_counts[(partition, offset)] = attempt`
- Max retries: 3 (configurable via `MAX_RETRIES`)
- After 3 failures: route to `records.events.dlq` topic
- Timeout protection: `asyncio.wait_for(..., timeout=5.0)` prevents hang
- DLQ payload structure:

```json
{
  "source_topic": "records.events",
  "source_partition": 0,
  "source_offset": 1234,
  "reason": "json.JSONDecodeError: Expecting value: line 1 column 1",
  "original": "{malformed json..."
}
```

**Why DLQ prevents head-of-line blocking**: Poison pill messages (malformed JSON, invalid schema) are forwarded to DLQ after 3 retries. Processor continues processing next message instead of blocking entire queue.

**🔍 OpenTelemetry Distributed Tracing** (`app/core/tracing.py`)

- TracerProvider with OTLP gRPC exporter → Jaeger backend (port 4317)
- FastAPI auto-instrumentation: `FastAPIInstrumentor.instrument_app(app)`
- Manual consumer spans: `tracer.start_as_current_span("kafka.consume", attributes={...})`
- Trace ID injection into logs:
  - Dev format: `[trace:abc12345] record_created`
  - Prod JSON: `{"trace_id": "abc12345...", "message": "record_created"}`

**End-to-end trace example**:

```text
Jaeger UI → Trace abc12345 →
  Span 1: POST /api/v1/records (ingestor, 50ms)
  Span 2: kafka.publish (ingestor, 5ms)
  Span 3: kafka.consume (processor, 200ms)
    → All linked by trace_id
```

**📊 Prometheus Metrics** (`app/metrics.py`)

- Circuit breaker state: `pipeline_circuit_breaker_state` (Gauge, 0=CLOSED, 1=OPEN, 2=HALF_OPEN)
  - Labels: `circuit` (e.g., `_send_to_kafka`, `_mongo_insert_one`)
  - Exported at `/metrics` endpoint
- State transitions update metric:

```python
# In circuit_breaker.py
if _METRICS_AVAILABLE:
    from app.metrics import circuit_breaker_state
    circuit_breaker_state.labels(circuit=self.name).set(1)  # OPEN
```

### Design Principles (Phase 4)

1. **Fail-Open with Circuit Breaker**
   - Kafka down → circuit opens after 5 failures → ingestor continues serving requests
   - MongoDB down → circuit opens → scraper continues serving requests (items_stored=0)
   - Rationale: Prevent cascading failures; system degrades gracefully
2. **Poison Pill Isolation with DLQ**
   - Malformed message → retry 3x → forward to DLQ → continue processing
   - Rationale: One bad message doesn't block entire queue (head-of-line blocking)
3. **End-to-End Observability**
   - Every request traced: ingestor → Kafka → processor
   - Trace ID in all logs → correlate logs with traces in Jaeger UI
   - Circuit state exported to Prometheus → alert on prolonged OPEN state
4. **Concurrency Safety in Circuit Breaker**
   - `asyncio.Lock` prevents race conditions during state transitions
   - Test coverage: `test_concurrent_calls_thread_safe` validates lock behavior
5. **Graceful Degradation**
   - OTel tracer unavailable → logs warning, continues without tracing
   - DLQ send timeout → logs error, continues processing next message
   - Circuit open → immediate failure, no hammering downstream service

### Data Flows

**Happy Path (with tracing):**

```text
POST /api/v1/records
  ↓
  OTel: Start span "POST /api/v1/records" (trace_id=abc12345)
  ↓
  Circuit breaker: State = CLOSED
  ↓
  Publish to Kafka (trace_id propagated in message metadata)
  ↓
  Processor: Start span "kafka.consume" (parent_span_id=abc12345)
  ↓
  Process message → Success
  ↓
  Jaeger UI: Full trace (ingestor → Kafka → processor)
```

**Degraded (Circuit open):**

```text
POST /api/v1/records
  ↓
  Circuit breaker: State = OPEN (5 consecutive failures)
  ↓
  Raise CircuitOpenError("Circuit _send_to_kafka is OPEN")
  ↓
  Log warning: "event_publish_failed circuit=_send_to_kafka"
  ↓
  Request still returns 201 (event lost, logged)
  ↓
  After 30s: Circuit → HALF_OPEN (1 probe allowed)
```

**Poison Pill (DLQ routing):**

```text
Kafka message: {malformed json...}
  ↓
  Processor: json.JSONDecodeError
  ↓
  retry_counts[(partition, offset)] = 1
  ↓
  Retry #2: json.JSONDecodeError
  ↓
  retry_counts[(partition, offset)] = 2
  ↓
  Retry #3: json.JSONDecodeError
  ↓
  retry_counts[(partition, offset)] = 3 (>= MAX_RETRIES)
  ↓
  _send_to_dlq(producer, raw_value, reason, partition, offset)
  ↓
  DLQ topic: records.events.dlq (with full context)
  ↓
  retry_counts.pop((partition, offset))  # Clear counter
  ↓
  Continue processing next message
```

### Configuration

```yaml
# docker-compose.yml
services:
  jaeger:
    image: jaegertracing/all-in-one:1.56
    ports:
      - "4317:4317" # OTLP gRPC
      - "16686:16686" # Jaeger UI
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  ingestor:
    environment:
      - OTEL_ENABLED=true
      - OTEL_ENDPOINT=http://jaeger:4317
      - OTEL_SERVICE_NAME=ingestor
```

```python
# app/config.py
otel_enabled: bool = True
otel_endpoint: str = "http://localhost:4317"
otel_service_name: str = "ingestor"
```

### Key Learnings (Phase 4)

1. **Circuit breaker state transitions must be lock-safe**: Without `asyncio.Lock`, concurrent failures cause race conditions (e.g., two failures both increment counter to 5).
2. **DLQ retry counter must be cleared after send**: Without `retry_counts.pop()`, memory grows unbounded.
3. **OTel setup must run before first log**: If logging starts before OTel initialized, first log line missing trace ID.
4. **Circuit breaker guard vs business logic separation**: If circuit wraps "not connected" check + I/O, test skips count as failures and open circuit. Solution: Separate guard (outside) from I/O (inside circuit).

### ADR

See [ADR #005: Circuit Breaker Pattern](adr/005-circuit-breaker-pattern.md) for detailed decision rationale.

---

## Key Design Decisions

| Decision                      | Rationale                                                                  |
| ----------------------------- | -------------------------------------------------------------------------- |
| Async/Await                   | Non-blocking I/O → handle 100s concurrent requests                         |
| SQLAlchemy 2.0                | Type-safe ORM with modern Python syntax                                    |
| Pydantic v2                   | Validation + serialization in one place                                    |
| Environment-aware logging     | Dev: readable; Prod: structured JSON                                       |
| In-memory aiosqlite tests     | Fast, no infrastructure needed                                             |
| Redpanda (not Kafka)          | Simpler Docker setup, no Zookeeper, Kafka-compatible API                   |
| Fail-open events              | Kafka unavailability doesn't block ingestor; events are observability only |
| Processor as separate service | Enables independent scaling, deployment, and development (Phase 2+)        |
| Single topic `records.events` | Start simple; add `records.events.dlq` in Phase 4 for error handling       |
| Circuit breaker pattern       | Protect downstream services from cascading failures (Phase 4)              |
| DLQ routing                   | Prevent poison pill messages from blocking queue (Phase 4)                 |
| OpenTelemetry tracing         | End-to-end observability across microservices (Phase 4)                    |

## Related Documents

- [API Routes](../app/routers/records.py)
- [Database Models](../app/models.py)
- [Performance Benchmarks](../tests/integration/records/test_performance.py)
- [6-Week Action Plan](../learning_docs/ACTION_PLAN.md)

**Questions?** Open a GitHub issue or PR against this document.
