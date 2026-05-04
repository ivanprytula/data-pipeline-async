# Weekly Progress Report — Phase 4: Resilience Patterns

**Week**: 7–8 of 16 (Phase 4: Circuit Breakers, DLQ, OpenTelemetry)
**Date Range**: April 20–21, 2026
**Status**: ✅ Phase Complete

---

## What Is This Document?

**Why it matters**: Mid-tier → senior progression requires demonstrating production-grade distributed systems thinking. This phase proves resilience engineering competence: circuit breakers, DLQ, distributed tracing, and Prometheus observability.

---

## Phase 4 Goal

> "System handles downstream failures gracefully: Circuit breaker, Dead Letter Queue, OpenTelemetry distributed tracing"

**What I Built**: Industry-standard resilience patterns protecting Kafka producer and MongoDB writes, DLQ routing in processor, full end-to-end trace visibility via Jaeger, and Prometheus metrics for circuit state.

---

## Weekly Metrics

| Metric                       | Goal  | Actual       | Status |
| ---------------------------- | ----- | ------------ | ------ |
| Core Q answered cold         | 1/1   | ✅ 1/1        | ✅      |
| Follow-ups prepared          | 2/2   | ✅ 2/2        | ✅      |
| Code committed               | 10–15 | ✅ 13         | ✅      |
| Tests passing                | 100%  | ✅ 307 (100%) | ✅      |
| Circuit breaker tests        | 10+   | ✅ 10         | ✅      |
| Portfolio item written       | 1     | ✅ 1          | ✅      |
| Architecture diagram updated | 1     | ✅ 1          | ✅      |
| Pre-commit hooks             | All   | ✅ All pass   | ✅      |

---

## Interview Readiness

### Core Question: "Design a circuit breaker for microservices calling external APIs"

**Cold Answer** (practiced, ~3 min):

> "Circuit breaker prevents cascading failures when downstream services are flaky. Three states:
>
> **1. CLOSED** (normal): Requests pass through. Track consecutive failures.
>
> **2. OPEN** (failing): After N consecutive failures (e.g., 5), reject all requests immediately for T seconds (e.g., 30s). This gives the downstream service time to recover without being hammered.
>
> **3. HALF_OPEN** (probe): After timeout, allow 1 probe request. If it succeeds → CLOSED. If it fails → re-open.
>
> **Concurrency safety**: Use async locks to prevent race conditions. Without locks, two concurrent failures could both increment the counter and open the circuit twice.
>
> **Observability**: Export circuit state to Prometheus (0=CLOSED, 1=OPEN, 2=HALF_OPEN) and log all state transitions with context (circuit name, failure count).
>
> **Implementation**: I built this in `app/core/circuit_breaker.py` as a decorator factory:
>
> ```python
> @circuit_breaker(failure_threshold=5, recovery_timeout=30.0)
> async def _send_to_kafka(topic: str, value: bytes) -> None:
>     await _producer.send_and_wait(topic, value=value)
> ```
>
> **Applied to**: Kafka producer (`app/events.py`) and MongoDB writes (`app/storage/mongo.py`). When Kafka goes down, circuit opens → ingestor continues serving requests (fail-open). Circuit state exported to `/metrics` endpoint.
>
> **Test coverage**: 10 unit tests covering all state transitions, concurrent access, and edge cases."

**Why this works in interview**:

- ✅ Shows understanding of the **why** (prevent cascading failures)
- ✅ Explains all 3 states clearly
- ✅ Addresses concurrency (async locks)
- ✅ Mentions observability (Prometheus metrics)
- ✅ References working code (can point to GitHub)
- ✅ Demonstrates production thinking (fail-open, test coverage)

---

### Follow-up Q1: "How does DLQ prevent poison pill messages from blocking the queue?"

**Cold Answer** (2 min):

> "**Poison pill problem**: A malformed message (e.g., invalid JSON) crashes the consumer. Consumer retries infinitely, blocking all subsequent messages in the queue (head-of-line blocking).
>
> **DLQ solution**: After N retries (e.g., 3), forward the bad message to a separate Dead Letter Queue topic. Continue processing the next message. Human inspects DLQ later.
>
> **My implementation** (`services/processor/main.py`):
>
> - Track per-message retry count: `retry_counts[(partition, offset)] = attempt`
> - After 3 failures, call `_send_to_dlq(producer, raw_value, reason, partition, offset)`
> - DLQ payload includes full context: source topic/partition/offset + error reason + original bytes
> - Timeout protection: `asyncio.wait_for(..., timeout=5.0)` prevents hang if DLQ topic down
> - Clear retry counter after success OR DLQ send (prevents memory leak)
>
> **Result**: Poison pill messages don't block the queue. They're routed to DLQ for later inspection."

**Why this works**:

- ✅ Explains the problem (head-of-line blocking)
- ✅ Shows the solution (DLQ routing)
- ✅ Mentions practical details (retry tracking, timeout, memory)
- ✅ Demonstrates production thinking (traceability via partition/offset)

---

### Follow-up Q2: "How implement distributed tracing across async microservices?"

**Cold Answer** (3 min):

> "Distributed tracing tracks requests across multiple services. Key components:
>
> **1. Trace context propagation**: Pass trace ID + span ID across service boundaries (HTTP headers or Kafka message metadata).
>
> **2. Instrumentation**:
>
> - **Auto-instrumentation**: FastAPI requests automatically create spans
> - **Manual spans**: Background workers (Kafka consumers) create spans manually
>
> **3. Correlation**: Inject trace ID into logs so log lines can be linked to traces in Jaeger UI.
>
> **4. Storage**: Send spans to OTLP collector (Jaeger, Tempo, etc.).
>
> **My implementation**:
>
> - **OTel setup** (`app/core/tracing.py`): TracerProvider + OTLP gRPC exporter → Jaeger (port 4317)
> - **Auto-instrument FastAPI**: `FastAPIInstrumentor.instrument_app(app)` creates HTTP spans
> - **Manual consumer span** (`services/processor/main.py`):
>
>   ```python
>   with tracer.start_as_current_span("kafka.consume", attributes={...}):
>       await _process_message(event)
>   ```
>
> - **Trace ID in logs** (`app/core/logging.py`):
>   - Dev: `[trace:abc12345] record_created`
>   - Prod JSON: `{\"trace_id\": \"abc12345...\", \"message\": \"record_created\"}`
>
> **Result**: Full request trace in Jaeger UI:
>
> - Span 1: POST /records (ingestor, 50ms)
> - Span 2: kafka.publish (ingestor, 5ms)
> - Span 3: kafka.consume (processor, 200ms)
>
> All linked by trace ID. Logs filterable by trace ID for debugging."

**Why this works**:

- ✅ Explains the **what** (trace context propagation)
- ✅ Distinguishes auto vs manual instrumentation
- ✅ Shows log correlation (trace ID in structured logs)
- ✅ Demonstrates end-to-end understanding (ingestor → Kafka → processor)
- ✅ References working implementation

---

### Design Scenario: "Service A calls Service B; Service B is flaky (50% failure). Design resilience."

**Cold Answer** (4 min walkthrough):

> **Problem**: Service B is flaky (50% error rate). Service A crashes or degrades when B is down.
>
> **Solution layers**:
>
> **1. Circuit breaker** (primary defense):
>
> - After 5 consecutive failures, open circuit for 30s
> - Service A stops hammering Service B
> - Service A returns cached/default response instead of failing
>
> **2. Retry with exponential backoff** (transient failures):
>
> - On 503/timeout, retry 3 times: 100ms → 200ms → 400ms
> - Don't retry on 4xx (client errors are permanent)
>
> **3. Timeout** (prevent indefinite hangs):
>
> - Hard timeout on Service B calls (e.g., 5s)
> - Use `asyncio.wait_for(call_service_b(), timeout=5.0)`
>
> **4. Observability**:
>
> - Log all failures with trace IDs
> - Alert on error rate > 10%
> - Export circuit state to Prometheus
>
> **5. Fallback/degradation**:
>
> - Return stale cached data
> - Return partial results (e.g., skip optional fields)
> - Return placeholder ("Service temporarily unavailable")
>
> **My implementation** (Phase 4):
>
> - Service A = ingestor, Service B = Kafka
> - Circuit breaker on `_send_to_kafka()` (5 failures → open 30s)
> - Fail-open: ingestor continues serving requests even if Kafka down
> - Observability: `pipeline_circuit_breaker_state` metric exported
> - Graceful degradation: events are best-effort, not critical path
>
> **Result**: Kafka downtime doesn't crash ingestor; circuit state visible in Grafana."

**Why this works in interview**:

- ✅ Multi-layered resilience (circuit breaker + retry + timeout + fallback)
- ✅ Shows trade-off awareness (don't retry 4xx)
- ✅ Mentions observability (metrics, logs, alerts)
- ✅ Demonstrates production thinking (graceful degradation)
- ✅ References actual implementation

---

## Implementation Milestones

### Week 7 (April 14–20)

**Monday–Tuesday**: Circuit breaker foundation

- ✅ Designed 3-state machine (CLOSED → OPEN → HALF_OPEN)
- ✅ Implemented `app/core/circuit_breaker.py` with `asyncio.Lock` for concurrency safety
- ✅ Added `@circuit_breaker` decorator factory
- ✅ Tested state transitions manually

**Wednesday**: Applied circuit breaker to services

- ✅ Wrapped `app/events.py::_send_to_kafka` with circuit breaker
- ✅ Wrapped `app/storage/mongo.py::_mongo_insert_one` with circuit breaker
- ✅ Fixed test isolation issue (guard logic outside circuit)
- ✅ All 297 tests passing

**Thursday**: OpenTelemetry tracing

- ✅ Added OTel deps to `pyproject.toml`
- ✅ Implemented `app/core/tracing.py` (setup + trace ID extraction)
- ✅ Added Jaeger all-in-one service to `docker-compose.yml`
- ✅ Wired OTel into `app/main.py` lifespan
- ✅ Injected trace IDs into structured logs

**Friday**: DLQ routing in processor

- ✅ Rewrote `services/processor/main.py` with retry tracking
- ✅ Implemented `_send_to_dlq()` with 5s timeout
- ✅ Added OTel manual span for consumer
- ✅ Tested: malformed messages → DLQ after 3 retries

### Week 8 (April 21)

**Monday**: Production hardening

- ✅ Added Prometheus `circuit_breaker_state` gauge
- ✅ Integrated metrics into circuit breaker state transitions
- ✅ Moved OTel setup before first log (trace IDs in all logs)
- ✅ Added timeout to DLQ send (`asyncio.wait_for`)
- ✅ Fixed type error (`ty` type checker)

**Tuesday**: Test coverage + documentation

- ✅ Created `tests/unit/core/test_circuit_breaker.py` (10 comprehensive tests)
- ✅ All tests passing (307 total, 19 skipped)
- ✅ Pre-commit hooks passing (ty, ruff, bandit, pip-audit)
- ✅ Written portfolio item (`docs/portfolio-phase-4-resilience.md`)
- ✅ Updated architecture diagram
- ✅ Code review: all PRs merged, production-ready

---

## Key Learnings

### 1. Circuit Breaker Concurrency Safety Is Non-Negotiable

**Problem**: Without locks, race conditions during state transitions:

- Two failures both increment counter → circuit opens twice (incorrect state)
- HALF_OPEN probe + normal request concurrent → both pass through (breaks probe logic)

**Solution**: `asyncio.Lock` for all state reads/writes:

```python
async with lock:
    self._maybe_transition_to_half_open()
    if self._state == CircuitState.OPEN:
        raise CircuitOpenError(...)
```

**Test**: `test_concurrent_calls_thread_safe` validates lock behavior with 20 concurrent calls.

---

### 2. DLQ Retry Counter Memory Management

**Problem**: Unbounded memory growth if retry counter not cleared after DLQ send.

**Solution**: Always `pop()` after success or DLQ:

```python
if attempt >= MAX_RETRIES:
    await _send_to_dlq(...)
    retry_counts.pop(msg_key, None)  # ✅ Clear counter
else:
    retry_counts[msg_key] = attempt  # Track retry
```

**Lesson**: In-memory state tracking requires careful lifecycle management.

---

### 3. OTel Setup Order Matters

**Problem**: First log line missing trace ID if OTel initialized after logging starts.

**Solution**: Move `setup_tracing()` to **before** `logger.info("startup", ...)`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # OTel first (trace_id available for all logs)
    if settings.otel_enabled:
        setup_tracing(app, ...)

    logger.info("startup", ...)  # ✅ Now has trace_id
```

**Lesson**: Initialization order matters for cross-cutting concerns like tracing.

---

### 4. Circuit Breaker Guard vs Business Logic Separation

**Problem**: If circuit wraps "not connected" check + I/O, test skips count as failures and open circuit.

**Solution**: Separate guard (outside) from I/O (inside circuit):

```python
@circuit_breaker(...)
async def _mongo_insert_one(doc: dict):
    if _db is None:
        raise RuntimeError("MongoDB not connected")  # Inside circuit
    await _db.scraped.insert_one(doc)

async def insert_scraped_doc(doc: dict):
    if _db is None:
        raise RuntimeError("MongoDB not connected")  # Outside circuit (guard)
    await _mongo_insert_one(doc)
```

**Lesson**: Circuit breaker should wrap only the actual I/O operation, not precondition checks.

---

## Production Readiness Checklist

| Item                           | Status          | Evidence                                            |
| ------------------------------ | --------------- | --------------------------------------------------- |
| Circuit breaker implementation | ✅ Complete      | `app/core/circuit_breaker.py` (181 lines)           |
| Circuit breaker tests          | ✅ 10 tests      | All edge cases covered                              |
| DLQ routing                    | ✅ Complete      | `services/processor/main.py` with 3-retry threshold |
| DLQ timeout protection         | ✅ 5s timeout    | `asyncio.wait_for()`                                |
| OpenTelemetry tracing          | ✅ Complete      | Jaeger backend, FastAPI auto-instrumentation        |
| Trace ID in logs               | ✅ 100% coverage | Dev + prod formatters                               |
| Prometheus metrics             | ✅ Circuit state | `pipeline_circuit_breaker_state` gauge              |
| Type safety                    | ✅ No errors     | `ty` type checker pass                              |
| Security scan                  | ✅ Clean         | Bandit pass                                         |
| Dependency audit               | ✅ Clean         | pip-audit pass                                      |
| Full test suite                | ✅ 307 passed    | 0 failures                                          |

---

## Next Phase Preview

**Phase 5: Advanced SQL + CQRS Read Side** (Weeks 9–10)

**Goal**: Materialized views, window functions, table partitioning, CTEs. CQRS: analytics as decoupled read service.

**Deliverables**:

- `services/analytics/` FastAPI service (read-only)
- Alembic migration: `records_hourly_stats` materialized view
- Analytics endpoints with CTEs, `PERCENT_RANK()`, `RANK() OVER (PARTITION BY ...)`
- CQRS: analytics subscribes to `records.events` Kafka topic for read-optimized projections

**Interview prep**: "Design a CQRS read model for real-time analytics"

---

## Reflection

What went well:

- ✅ Circuit breaker pattern clean and reusable (decorator factory)
- ✅ DLQ routing prevents head-of-line blocking
- ✅ Full end-to-end trace visibility (Jaeger UI)
- ✅ Comprehensive test coverage (10 circuit breaker tests)
- ✅ Prometheus metrics for production observability

What was hard:

- ⚠️ OTel type annotations (manual span creation + graceful degradation)
- ⚠️ Circuit breaker test isolation (guard vs I/O separation)
- ⚠️ DLQ retry counter lifecycle management

What I'd do differently:

- Start with circuit breaker tests first (TDD approach)
- Design DLQ payload structure earlier (less refactoring)

Phase 4 complete — production-ready resilience patterns ✅
