# Portfolio Item Template

Save to: `docs/portfolio-phase-{N}-{title}.md`

---

## Format

```markdown
# Phase N — {Title}

### What I Built
- {Feature 1}: {metric}
- {Feature 2}: {metric}
- {Feature 3 (optional)}: {metric}

### Interview Questions Prepared
- [ ] **Core Q**: "{question}"
  *Answer*: {1-2 sentence sketch}

- [ ] **Follow-up**: "{question}"
  *Answer*: {1-2 sentence sketch}

- [ ] **Design Scenario**: "{scenario}"
  *Answer*: {How would you approach?}

### Key Learning

{1-2 sentence insight OR mistake avoided}

### Code

[data-pipeline-async/path/to/code](https://github.com/ivanp/data-pipeline-async/tree/main/path)

---

## Why This Matters

{Optional: 1 sentence explaining why this phase matters for production systems}
```

---

## Examples

### Phase 1 — Event Streaming

```markdown
# Phase 1 — Event Streaming with Redpanda

### What I Built
- Redpanda topic (`records.events`): 10 partitions by source_id, 10M+ events/day
- Celery producer: app/events.py with 3-retry exponential backoff, publishes on record.created
- Consumer: services/processor pulls async, processes events, routes failures to DLQ
- Failure mode: Kafka unavailable → fail-open (log + continue, no service crash)

### Interview Questions Prepared

- [ ] **Core Q**: "Design real-time ETL for 1000+ events/sec"
  *Typical answer*: Topic partitioning by entity ID, consumer groups for scale, exactly-once semantics via idempotency keys

- [ ] **Follow-up**: "What's consumer lag? Why monitor it?"
  *Typical answer*: Lag = messages behind. Monitor to detect slow consumers (processor stalled), then trigger alerts or auto-scale

- [ ] **Design Scenario**: "Your event processor is 2 hours behind. What happened and how diagnose?"
  *Approach*: Check consumer lag metric → check processor logs for errors → check DLQ for poison pills → restart processor vs increase parallelism

### Key Learning

Offset management is invisible but critical. Get partition assignment strategy wrong and you either iterate slowly (rebalancing thrashing) or lose messages. Consumer group rebalancing is the second hidden complexity—worth understanding deeply.

### Code

[app/events.py](https://github.com/ivanp/data-pipeline-async/blob/main/app/events.py)
[services/processor/main.py](https://github.com/ivanp/data-pipeline-async/blob/main/services/processor/main.py)

---

## Why This Matters

Event-driven systems decouple services and enable real-time analytics. Redpanda is Kafka-compatible but simpler for local development. Understanding event ordering, idempotency, and consumer lag is essential for any distributed system at scale.
```

### Phase 5 — Database Optimization

```markdown
# Phase 5 — Database Query Optimization

### What I Built
- EXPLAIN ANALYZE walkthrough: identified seq scan, proposed composite index
- Composite index on (pipeline_id, created_at): 5s → 50ms latency for analytics query
- Window function rewrite: replaced subquery with PARTITION BY + LAG, further 10% improvement
- Keyset pagination: replaced LIMIT/OFFSET for consistent ordering at 10K+ pages

### Interview Questions Prepared

- [ ] **Core Q**: "This query is slow (5s). Fix."
  *Typical answer*: Run EXPLAIN ANALYZE → identify bottleneck (seq scan? join?) → add index or rewrite query

- [ ] **Follow-up**: "How read EXPLAIN ANALYZE output?"
  *Typical answer*: Look for "Seq Scan" (bad), "Index Scan" (good). Check actual rows vs estimated rows (planner misalignment). Check planning time vs execution time.

- [ ] **Design Scenario**: "You add a composite index and query still slow. What's next?"
  *Approach*: Check if index is actually used (maybe planner ignores due to stats outdated) → run ANALYZE → rewrite query to avoid subquery → consider window function

### Key Learning

EXPLAIN ANALYZE is your debugging tool. Many slow queries aren't about indices—they're about query structure (N+1, subqueries, wrong join order). Window functions are underused; they're often faster than subqueries because they avoid joins.

### Code

[docs/pillar-2-database.md#query-optimization](https://github.com/ivanp/data-pipeline-async/blob/main/docs/pillar-2-database.md)
(Examples embedded in test fixtures)

---

## Why This Matters

Query optimization is 80% of production performance gains. Learn EXPLAIN ANALYZE deeply. It teaches you about index structures, join algorithms, and query planning. Most developers never get good at this—it's a differentiator.
```

---

## Tips

- **Metrics matter**: "10M events/day" is better than "event streaming works"
- **Answer arc**: Each interview Q should have a 2-3 sentence answer ready
- **Key learning = insight**: Don't just list technical facts; explain what surprised you or what you'd do differently
- **Code links**: Working examples > documentation
- **Optional section**: "Why this matters" helps non-experts understand relevance
