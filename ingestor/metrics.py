"""Custom Prometheus metrics for the data pipeline.

This module defines all application-level counters and histograms.
It is imported once at startup and kept as module-level singletons —
prometheus_client enforces that metric names are globally unique within
a process, so registering the same name twice raises a ValueError.

Metric naming convention (Prometheus best practice):
  <namespace>_<subsystem>_<unit>_<suffix>
  e.g. pipeline_records_created_total

Exposed on: GET /metrics (text/plain; version=0.0.4)

Pillars:
  Pillar 4 — Observability (entry point)
  Next step: connect Grafana dashboard (Week 5)
"""

from prometheus_client import Counter, Gauge, Histogram


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

records_created_total = Counter(
    name="pipeline_records_created_total",
    documentation="Number of records successfully inserted (all endpoints combined).",
    labelnames=["endpoint"],
)
"""Incremented on every successful record INSERT.

Labels:
  endpoint: "single" | "batch" | "upsert"

Usage::

    from ingestor.metrics import records_created_total
    records_created_total.labels(endpoint="single").inc()
"""

records_upsert_conflicts_total = Counter(
    name="pipeline_records_upsert_conflicts_total",
    documentation="Number of upsert requests that hit an existing record (conflict resolved).",
    labelnames=["mode"],
)
"""Incremented when upsert detects a (source, timestamp) conflict.

Labels:
  mode: "idempotent" | "strict"
"""


# ---------------------------------------------------------------------------
# Gauges
# ---------------------------------------------------------------------------

circuit_breaker_state = Gauge(
    name="pipeline_circuit_breaker_state",
    documentation="Circuit breaker state (0=CLOSED, 1=OPEN, 2=HALF_OPEN).",
    labelnames=["circuit"],
)
"""Circuit breaker state indicator.

Labels:
  circuit: Function qualified name (e.g. "_send_to_kafka", "_mongo_insert_one")

Values:
  0 = CLOSED (normal operation)
  1 = OPEN (failures >= threshold, calls rejected)
  2 = HALF_OPEN (recovery timeout elapsed, probe allowed)

Usage::

    from ingestor.metrics import circuit_breaker_state
    circuit_breaker_state.labels(circuit="my_function").set(1)  # OPEN
"""

# ---------------------------------------------------------------------------
# Histograms
# ---------------------------------------------------------------------------

batch_size_histogram = Histogram(
    name="pipeline_batch_insert_size",
    documentation="Distribution of batch insert sizes (number of records per /batch request).",
    buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
)
"""Observe the batch size on every POST /api/v1/records/batch call.

Usage::

    from ingestor.metrics import batch_size_histogram
    batch_size_histogram.observe(len(records))
"""

enrich_duration_seconds = Histogram(
    name="pipeline_enrich_duration_seconds",
    documentation="Wall-clock time (seconds) for a full /enrich fan-out request.",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)
"""Observe total enrichment wall time per /enrich call."""


# ---------------------------------------------------------------------------
# Cache metrics
# ---------------------------------------------------------------------------

cache_hits_total = Counter(
    name="pipeline_cache_hits_total",
    documentation="Number of successful cache hits (record retrieved from cache).",
    labelnames=["operation"],
)
"""Incremented when cache.get_record() returns a cached value.

Labels:
  operation: "get" | "list" (currently only "get" in use)
"""

cache_misses_total = Counter(
    name="pipeline_cache_misses_total",
    documentation="Number of cache misses (record not in cache, fetched from DB).",
    labelnames=["operation"],
)
"""Incremented when cache.get_record() returns None (cache miss).

Labels:
  operation: "get" | "list" (currently only "get" in use)
"""

cache_errors_total = Counter(
    name="pipeline_cache_errors_total",
    documentation="Number of cache operation errors (Redis connection, serialization).",
    labelnames=["operation"],
)
"""Incremented when cache operations fail (fail-open, logged as warning).

Labels:
  operation: "get" | "set" | "invalidate"
"""
