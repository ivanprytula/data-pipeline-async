# Index Optimization & Hotspot Analysis

## Overview

This document analyzes the indexing strategy for the data model, identifies potential hotspots, and provides recommendations for optimization.

---

## Current Index Strategy

### Records Table Indexes

| Index Name | Columns | Type | Purpose | Hotspot Risk |
|------------|---------|------|---------|--------------|
| `pk_records` | `id` | Primary Key | Unique row identification | ✅ Low (primary key lookups) |
| `ix_records_active_source` | `source` (partial: `deleted_at IS NULL`) | Btree | List records by source, excluding deleted | ⚠️ Medium (filters on 95% of rows) |
| `ix_records_timestamp` | `timestamp` | Btree | Range queries by timestamp | ✅ Low (used for time-series queries) |
| `ix_records_processed` | `processed` | Btree | Filter by processing status | ⚠️ High (low cardinality: 2 values) |
| `uq_records_source_timestamp` | `(source, timestamp)` | Unique | Prevent duplicate ingestion | ✅ Low (DML lookups only) |

#### Recommendations: Records Table

**1. Partial Index on `(source, processed)` is Low Value** ❌
- **Issue**: `ix_records_processed` on a boolean column has poor selectivity
  - 50/50 split: half rows are processed, half aren't
  - Index is often ignored by planner (sequential scan is cheaper)
- **Recommendation**: Remove or make composite
  - Consider: `ix_records_unprocessed` with `WHERE processed = false` (partial index)
  - This filters to ~5% of rows (faster for typical "get unprocessed" queries)

**2. Missing Composite Index for Common Query Pattern** 📌
- **Query Pattern**: "Get unprocessed records from source X in time range Y"
  ```python
  # Common query in CRUD layer
  records = await db.execute(
      select(Record)
      .where(
          (Record.deleted_at == None)
          & (Record.processed == False)
          & (Record.source == "api.example.com")
          & (Record.timestamp >= start_time)
          & (Record.timestamp <= end_time)
      )
      .order_by(Record.timestamp.desc())
      .limit(1000)
  )
  ```
- **Current Plan**: Uses partial index on `source` (deleted_at IS NULL) + sequential scan on processed/timestamp
  - Estimated 95K rows scanned before applying filters
- **Recommendation**: Add composite partial index:
  ```sql
  CREATE INDEX ix_records_unprocessed_by_source_timestamp
  ON records (source, timestamp DESC)
  WHERE deleted_at IS NULL AND processed = false;
  ```
  - Reduces full-table scan to ~5K rows (unprocessed only)
  - Index is ordered by timestamp DESC (useful for `ORDER BY timestamp DESC LIMIT N`)

**3. Archive Table Index Strategy** 🗂️
- **Current**: Basic timestamp index on each partition
- **Issue**: Partitions already segregate by month; timestamp index is redundant within a partition
- **Recommendation**: Prioritize `(source, timestamp)` composite index for lookups within a partition
  ```sql
  -- On each partition
  CREATE INDEX idx_records_archive_202604_source_ts
  ON records_archive_202604 (source, timestamp DESC)
  WHERE deleted_at IS NULL;
  ```

---

### Processed Events Table Indexes

| Index Name | Columns | Type | Purpose | Hotspot Risk |
|------------|---------|------|---------|--------------|
| `pk_processed_events` | `id` | Primary Key | Row identification | ✅ Low |
| `ix_events_idempotency_key` | `idempotency_key` | Unique | Idempotency deduplication | ✅ Low (DML lookup) |
| `ix_events_status` | `status` | Btree | Filter by processing status | ⚠️ Medium (low cardinality: ~4-5 values) |
| `ix_events_kafka_offset` | `kafka_offset` | Btree | Track Kafka consumer progress | ⚠️ Medium (mostly append-only) |
| `ix_events_dead_letter_queue` | `dead_letter_queue` | Btree | Find failed events | ✅ Low (sparse: <1% of rows) |

#### Recommendations: Processed Events

**1. Composite Index for Event Lookup** 📌
- **Query Pattern**: "Find all pending events for topic X created after time Y"
  ```sql
  SELECT * FROM processed_events
  WHERE kafka_topic = 'orders'
    AND status = 'pending'
    AND created_at > NOW() - INTERVAL '24 hours'
  ORDER BY created_at ASC;
  ```
- **Current Plan**: Full table scan (no compound index)
- **Recommendation**: Add partial composite index
  ```sql
  CREATE INDEX ix_events_pending_by_topic
  ON processed_events (kafka_topic, created_at)
  WHERE status = 'pending' AND deleted_at IS NULL;
  ```
  - Reduces rows to scan from 10M+ down to ~1K (pending events only)

**2. Kafka Offset Index for Consumer Tracking** ✅
- **Current**: Simple B-tree on `kafka_offset`
- **Issue**: Offset is mostly monotonically increasing (poor for B-tree)
- **Alternative**: Consider removing if queries typically use `ORDER BY created_at` instead
  - Benchmark: Compare query plan with/without index
  - If kafka_offset is rarely filtered directly, remove it

---

## Hotspot Analysis

### Write Hotspots

#### 1. Records Table (High Volume Insert)
- **Risk**: Concurrent inserts into `records` table (indexed on `source`, `timestamp`)
- **Symptom**: Lock contention on B-tree leaf pages
- **Mitigation**:
  - Use list partitioning by source (e.g., partition by source hash modulo)
  - Spreads writes across multiple table partitions
  - Requires schema change and backfill (post-v1.0)

#### 2. Idempotency Key Index (UQ Constraint)
- **Risk**: Unique index on `idempotency_key` becomes bottleneck for high-velocity event processing
- **Symptom**: Lock waits during concurrent event deduplication
- **Mitigation**:
  - Use UNIQUE with NULLS DISTINCT (PostgreSQL 15+) for sparse columns
  - Consider sharded idempotency keys (prefix by kafka_partition)

### Read Hotspots

#### 1. Records by Source (Common Query)
- **Risk**: All queries filtered by `source` cause contention on `ix_records_active_source`
- **Symptom**: Cache pressure on B-tree root pages
- **Mitigation**:
  - Monitored via `pg_stat_user_indexes` (see Query Performance section)
  - Consider list partitioning if reads exceed 10K/sec per source

#### 2. Unprocessed Records (Batch Jobs)
- **Risk**: Batch processing jobs scan `WHERE processed = false` multiple times per day
- **Symptom**: Redundant scans of ~50% of table even with index on `processed`
- **Mitigation**:
  - Implement recommended `ix_records_unprocessed_by_source_timestamp` index
  - Add caching layer (Redis) for frequently accessed unprocessed batches

---

## Performance Baselines

### Query Performance Targets

| Query | Target P95 | Current (Est.) | Gap |
|-------|-----------|--------|-----|
| Get unprocessed records from source (1K limit) | <50ms | 200–500ms | ❌ 5–10x slower |
| Range query by timestamp (24h, 10K rows) | <100ms | 100–150ms | ✅ Acceptable |
| Check idempotency before insert | <5ms | 5–10ms | ⚠️ At risk under load |
| List all processed events by status | <200ms | 200–300ms | ⚠️ At risk (low selectivity) |

### Index Usage Monitoring Query

```sql
-- Top 10 slowest index scans (requires pg_stat_statements)
SELECT
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
WHERE query LIKE '%records%' OR query LIKE '%processed_events%'
ORDER BY total_time DESC
LIMIT 10;

-- Index bloat analysis
SELECT
    schemaname,
    tablename,
    indexname,
    idx_blk_read,
    idx_blk_hit,
    ROUND(
        (idx_blk_hit::NUMERIC / (idx_blk_hit + idx_blk_read)) * 100,
        2
    ) AS cache_hit_ratio
FROM pg_statio_user_indexes
WHERE schemaname = 'public'
ORDER BY (idx_blk_hit + idx_blk_read) DESC;
```

---

## Implementation Checklist

### Phase 1: Hotspot Mitigation (Immediate)
- [ ] Add partial index `ix_records_unprocessed_by_source_timestamp` (reduces scan from 95K to 5K rows)
- [ ] Monitor `ix_records_processed` usage; remove if not used by planner
- [ ] Add composite index `ix_events_pending_by_topic` for event processing queries

### Phase 2: Performance Validation (Week 1–2)
- [ ] Run query benchmarks before/after index changes
- [ ] Collect `pg_stat_statements` data for 48 hours
- [ ] Compare P95 latencies for common query patterns
- [ ] Verify no regressions in insert performance (check `INSERT` contention)

### Phase 3: Long-Term Optimization (Post-v1.0)
- [ ] Implement list partitioning on records table (by source hash)
- [ ] Consider sharded idempotency keys for event deduplication
- [ ] Archive old partitions to cold storage (integrate with data retention job)
- [ ] Monitor and react to new hotspots via continuous profiling

---

## References

- [PostgreSQL Index Types](https://www.postgresql.org/docs/current/indexes.html)
- [Partial Indexes](https://www.postgresql.org/docs/current/indexes-partial.html)
- [Query Planning & EXPLAIN ANALYZE](https://www.postgresql.org/docs/current/sql-explain.html)
- [Index Statistics](https://www.postgresql.org/docs/current/monitoring-stats.html)
