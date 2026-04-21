# Pillar 4: Observability

**Tier**: Middle (🟡) → Senior (🔴)
**Project**: Essential for debugging + production support

---

## Middle Tier (🟡)

### Structured Logging

**Requirements**:

- Every log entry is valid JSON
- Required fields: `timestamp`, `level`, `cid` (correlation ID), `event`, `context`
- Never log secrets or PII

**Example** (using `python-json-logger`):

```python
import logging
from pythonjsonlogger import jsonlogger

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)
logger.addHandler(handler)

# Log with context
logger.info("record_created", extra={
    "cid": request_id,
    "record_id": record.id,
    "source": record.source,
})
```

Output:

```json
{"timestamp": "2026-04-02T15:30:00Z", "level": "INFO", "event": "record_created", "cid": "abc123", "record_id": 42, "source": "api.example.com"}
```

---

### Metrics (Prometheus)

**Metric types**:

- `Counter`: always increases (requests_total)
- `Gauge`: up/down (active_connections)
- `Histogram`: distribution (request_duration_seconds)

**Example** (`prometheus-fastapi-instrumentator`):

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)

# Exposes /metrics endpoint
# Metrics: http_requests_total, http_request_duration_seconds, etc.
```

Then connect **Grafana** to Prometheus data source → build dashboard

---

### Request Lifecycle Logging

```python
# On request entry
logger.info("request_start", extra={
    "cid": request_id,
    "method": request.method,
    "path": request.url.path,
    "client_ip": request.client.host,
})

# On request exit
logger.info("request_end", extra={
    "cid": request_id,
    "status": response.status_code,
    "duration_ms": elapsed_ms,
})
```

---

## Senior (🔴)

### OpenTelemetry (Distributed Tracing)

**What it is**:

- Traces = request path across multiple services
- Spans = individual operation (DB query, HTTP call)
- Trace ID + Span ID link logs → traces → metrics

**Example**:

```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

tracer = trace.get_tracer(__name__)

@app.get("/records")
async def list_records():
    with tracer.start_as_current_span("list_records") as span:
        span.set_attribute("limit", 10)
        records = await db.query(...)
        span.set_attribute("rows_returned", len(records))
        return records
```

Spans appear in **Jaeger UI** with full trace graph

---

### Alerting + SLOs

**Alert rules** (Prometheus):

```yaml
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.01
  annotations:
    summary: "5% of requests are errors"
```

**SLOs**: Define acceptable error budget (e.g., 99.9% uptime = 43min downtime/month)

---

## You Should Be Able To

✅ Emit structured JSON logs with correlation IDs
✅ Instrument FastAPI with Prometheus metrics
✅ Build Grafana dashboard (error rate, latency P95)
✅ Trace requests across service boundaries with OpenTelemetry
✅ Write alerting rules for error rate + latency
✅ Explain why you log (debugging), metrics (SLOs), traces (dependencies)

---

## References

- [python-json-logger](https://github.com/madzak/python-json-logger)
- [Prometheus Docs](https://prometheus.io/docs/)
- [Grafana Dashboards](https://grafana.com/grafana/)
- [OpenTelemetry](https://opentelemetry.io/docs/instrumentation/python/)
- [Jaeger](https://www.jaegertracing.io/docs/)

---

## Checklist — Pillar 4: Observability

### Foundation 🟢

- [ ] Log structured JSON with `python-json-logger`: `event`, `level`, `cid`, context fields
  - [ ] Know the five log levels and when to use each: `DEBUG/INFO/WARNING/ERROR/CRITICAL`
- [ ] Explain the four golden signals: latency, traffic, errors, saturation
- [ ] Inject a correlation ID at request boundary and propagate it through the call chain
- [ ] Read Prometheus metrics output from `/metrics` endpoint

### Middle 🟡

- [ ] Know when to use `Counter` vs `Gauge` vs `Histogram` vs `Summary`
  - [ ] Counter: monotonically increasing (requests, errors)
  - [ ] Gauge: up and down (active connections, cache size)
  - [ ] Histogram: distribution (latency, request size)
- [ ] Write a Grafana query: `rate()`, `histogram_quantile(0.95, ...)`, `sum by (label)`
- [ ] Explain why P95/P99 latency matters more than average
  - [ ] Know that average hides tail latency impacting a fixed % of users
- [ ] Configure alert thresholds: error rate, latency SLO

### Senior 🔴

- [ ] Explain OpenTelemetry spans: parent/child relationships, `trace_id`, `span_id`
  - [ ] Know how `TraceContextPropagator` injects/extracts trace context across HTTP calls
- [ ] Explain cardinality explosion: why `user_id` as a Prometheus label is dangerous
- [ ] Link Prometheus exemplars to Jaeger traces
- [ ] Design SLI/SLO/SLA for the records API (latency, availability, error rate)
  - [ ] Know the difference: SLI = metric, SLO = target, SLA = contract

### Pre-Interview Refresh ✏️

- [ ] What is a correlation ID? Why inject it at middleware, not in each function?
- [ ] `Counter` vs `Gauge` — give a real example of each
- [ ] Why P95 latency over average? Give a scenario where average is misleading
- [ ] What is `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`?
- [ ] What is cardinality in Prometheus and why does high cardinality cause problems?
