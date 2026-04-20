# ADR #004: Scraper Architecture — Motor + Multi-Protocol Approach

**Date**: April 20, 2026
**Status**: ✅ Accepted (Phase 2 implementation complete)
**Context**: Need to ingest data from multiple sources (REST APIs, HTML, JS-rendered content) with resilience and observability.

---

## Problem

Data ingestion from heterogeneous sources presents three interconnected challenges:

1. **Protocol diversity**: Different sources require different approaches:
   - JSON APIs → async httpx/aiohttp
   - HTML pages → BeautifulSoup (no rendering needed)
   - JS-rendered content → Playwright/Selenium (expensive, slow)

2. **Concurrency limits**: Unbounded concurrency leads to:
   - Bans from rate-limited targets
   - Memory exhaustion (too many open connections)
   - Cascading failures (timeout storms)

3. **Failure isolation**: When downstream services fail (MongoDB unavailable, Kafka broker down), should we:
   - Crash the scraper? (fail-closed: safe but loses data)
   - Retry indefinitely? (fail-open: risky but resilient)
   - Queue locally? (hybrid: complex)

---

## Decision

Implement **Factory Pattern + Motor async client + Fail-Open Architecture**:

```python
# app/scrapers/__init__.py
class ScraperFactory:
    @staticmethod
    def get_scraper(source: str) -> Scraper:
        return {
            "jsonplaceholder": HTTPScraper(...),
            "hn": HTMLScraper(...),
            "playwright": BrowserScraper(...),
        }[source]

# Each scraper uses:
# - Semaphore(5) for concurrency (configurable)
# - Exponential backoff (3 retries max)
# - Timeout enforcement (10s default)
# - Pure async (no blocking calls)
```

**Storage**: Motor async MongoDB client, singleton pattern:

```python
# app/storage/mongo.py
async def store_scraped_docs(docs: list[dict]) -> int:
    """Insert or skip on duplicate. Return count inserted."""
    result = await _db[COLLECTION_SCRAPED].insert_many(docs, ordered=False)
    return len(result.inserted_ids)
```

**Failure mode**: Fail-open (endpoints always return 200, errors logged):

```python
# app/routers/scraper.py → scrape_source()
try:
    stored = await mongo.store_scraped_docs(scraped_items)
except Exception as e:
    logger.error("mongo_error", extra={"error": str(e)})
    stored = 0  # Don't crash; Kafka event still publishes

try:
    await events.publish_doc_scraped(source, stored)
except Exception as e:
    logger.error("kafka_error", extra={"error": str(e)})
    # Error logged; no retry (fire-and-forget)
```

---

## Rationale

### Why Factory Pattern?

- **Encapsulation**: Each scraper type hidden behind uniform interface
- **Type safety**: No string-based dispatch in endpoints
- **Extensibility**: Adding a 4th scraper (JSON-LD, RSS) requires 1 class + 1 dict entry
- **Testability**: Mock `ScraperFactory.get_scraper()` to test endpoint logic independently

**Alternative considered**: Inheritance hierarchy (`BaseScraper` → `HTTPScraper`, `HTMLScraper`, etc.)

- ✅ Pro: Explicit contracts via abstract methods
- ❌ Con: Over-engineered for 3 types; Factory + protocol is simpler

---

### Why Motor (not sync drivers)?

- **Non-blocking**: MongoClient is sync; would block event loop in async app
- **Async-native**: Motor is built for asyncio; integrates with lifespan hooks cleanly
- **Fits architecture**: Consistent with FastAPI async-first design (httpx, asyncpg, aiokafka all async)

**Alternative considered**: AsyncIO thread pool (`asyncio.to_thread(MongoClient.insert_many())`)

- ✅ Pro: Minimal code; use any sync driver
- ❌ Con: Still blocks thread pool; less observable; adds latency

---

### Why Semaphore(5) for concurrency?

- **Rate limiting**: Most public APIs allow 5–10 req/s; this keeps us conservative
- **Observability**: With 5 concurrent, easy to debug slow requests; with 50, connection pool exhaustion is hard to debug
- **Memory**: 5 connections @ ~100KB each = 500KB; 50 = 5MB; 100 = 10MB (adds up across instances)
- **Production safety**: Better to scrape slowly than get banned quickly

**Trade-off table** (100K URLs, 1 req/s baseline):

| N   | Time | Ban Risk | Observability |
| --- | ---- | -------- | ------------- |
| 1   | 27h  | Minimal  | Best          |
| 5   | 5.5h | Low      | Good          |
| 20  | 1.5h | Medium   | Fair          |
| 100 | 3m   | High     | Poor          |

**Decision**: Default to 5; overridable per-source via config (`app/config.py` → `SEMAPHORE_LIMITS`)

---

### Why Fail-Open?

- **System resilience**: MongoDB restart shouldn't crash scraper endpoint
- **Data preservation**: Even if storage fails, we log error and user gets feedback
- **Kafka async**: Even if Kafka broker down 30 seconds, scraper completes (event queued on recovery)
- **Production reality**: Perfection is enemy of ship

**Alternative considered**: Fail-closed (crash on MongoDB unavailable)

- ✅ Pro: Forces operator to notice
- ❌ Con: Cascading failure; user gets 500; X-Ray traces fill with timeout errors

**Middle ground** (not chosen): Queue locally to disk, retry on recovery

- ✅ Pro: No data loss
- ❌ Con: 2x complexity; need cleanup; replay logic; not needed for Phase 2

---

## Consequences

### Positive

- ✅ **Decoupled storage**: Scraper works even if MongoDB/Kafka briefly fails
- ✅ **Observable failures**: All errors logged with context (source, count, duration)
- ✅ **Extensible**: Adding new scraper type takes 15 minutes (1 module + Factory entry)
- ✅ **Testable**: Mock `ScraperFactory.get_scraper()` for unit tests; no real HTTP calls needed

### Negative

- ⚠️ **Data loss potential**: If MongoDB AND Kafka both fail, scraped data lost (mitigated: log error, on-call can re-run)
- ⚠️ **Lag visibility**: User doesn't know if MongoDB insert failed (mitigated: Kafka event includes count; processor can monitor)
- ⚠️ **Configuration complexity**: Semaphore limits now per-source; must tune for each target

---

## Decisions Impacted / Impacting

**Upstream** (already decided):

- ADR #001 (Kafka vs RabbitMQ): Chose Kafka; Phase 2 confirms good fit for event stream
- Pydantic v2 validation: ScrapeResponse schema validates request params

**Downstream** (affects future phases):

- **Phase 3 (AI)**: Playwright scraper output (HTML → markdown) fed to embeddings model
- **Phase 4 (Resilience)**: Circuit breaker pattern applied to scraper timeouts (if >30% fail, auto-disable source)
- **Phase 5 (CQRS)**: Materialized view in PostgreSQL: `materialized_view_scraped_docs_by_source` for analytics

---

## Implementation Checklist

- [x] ScraperFactory (app/scrapers/**init**.py) with 3 types
- [x] HTTPScraper (httpx + exponential backoff)
- [x] HTMLScraper (BeautifulSoup)
- [x] BrowserScraper (Playwright)
- [x] Motor async client (app/storage/mongo.py)
- [x] Semaphore concurrency (default 5)
- [x] ScrapeResponse schema
- [x] POST /api/v1/scrape/{source} endpoint
- [x] Fail-open error handling (no exception propagates)
- [x] Kafka event: publish_doc_scraped()
- [x] Lifespan wiring: Motor connect/disconnect
- [x] Config: MONGO_URL, MONGO_DB_NAME
- [x] Logging: All errors with context
- [ ] Distributed tracing (OpenTelemetry, Phase 4)
- [ ] Circuit breaker (Phase 4)
- [ ] Per-source timeout config (Phase 3+)

---

## Open Questions / Future Work

1. **Playwright browser pool**: Currently starts fresh for each request. At scale, consider pooling (BrowserManager singleton).
2. **Retry strategy**: Currently 3 retries on timeout. Should we retry on 429/503 with longer backoff?
3. **Proxy support**: For large-scale scraping, integrate residential proxy pool (Bright Data, Crawlbase).
4. **Rate limit observability**: Add endpoint returning `{source: lag_seconds}` for monitoring scraper lag.
5. **Scraper scheduling**: Celery Beat to re-scrape sources on schedule (daily, hourly, weekly).

---

## References

- [Motor documentation](https://motor.readthedocs.io/)
- [httpx async client](https://www.python-httpx.org/)
- [Playwright async API](https://playwright.dev/python/docs/async-api)
- [Factory Pattern in Python](https://refactoring.guru/design-patterns/factory-method)
- [Fail-open vs fail-closed](https://en.wikipedia.org/wiki/Fail-open) (system security principle applicable to resilience)
