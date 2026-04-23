# LinkedIn Post Template (Technical Tone, 280 chars max)

## Format

Week N: {Feature implementation}. Technical detail (metrics, patterns, trade-offs).
GitHub: [link].

{category} #{skill}

---

## Examples (Copy & Adapt)

### Phase 1 — Event Streaming

```text
Week 2: Implemented event-driven architecture with Redpanda. Topic partitioning by source_id, consumer groups, DLQ for poison pills. 10M events/day throughput. GitHub: [link]. #backend #event-streaming
```

### Phase 2 — Scrapers

```text
Week 4: Built scraper for 100K URLs using async semaphore (concurrency=50) + exponential backoff. Pydantic validation as ETL gate. 3 backends: HTTP, HTML, browser. GitHub: [link]. #backend #data-engineering
```

### Docker+CI — GitHub Actions

```text
Week 6: Automated CI/CD pipeline: test → ruff → multi-stage Docker build → ECR push. 80% image size reduction via builder pattern. GitHub: [link]. #backend #devops
```

### Phase 3 — AI+Vector Search

```text
Week 8: Semantic search over 100K documents using Qdrant + embeddings. LRU cache reduces re-encoding by 70%, API latency <500ms. GitHub: [link]. #backend #ai
```

### Phase 4 — Testing Deep Dive

```text
Week 10: Production-grade pytest patterns: async fixtures, Celery mocking, time travel (freezegun), parametrization. 100% test coverage maintained. GitHub: [link]. #backend #testing
```

### Phase 5 — Database Optimization

```text
Week 12: Query optimization via composite index + window function rewrite. 5s → 50ms latency on analytics queries. EXPLAIN ANALYZE read fluently. GitHub: [link]. #backend #database
```

### Phase 6 — Security & Auth

```text
Week 14: JWT implementation: short-lived access + long-lived refresh tokens, rate limiting on /login (5 attempts/min), HMAC webhook validation. GitHub: [link]. #backend #security
```

### Phase 7 — Infrastructure as Code

```text
Week 16: Terraform multi-env (dev/staging/prod) with RDS + Fargate + ElastiCache. Automatic backups, secrets rotation via AWS Secrets Manager. GitHub: [link]. #backend #devops
```

---

## Tips

- **Be specific**: Metrics beat adjectives ("50% latency reduction" not "much faster")
- **Technical language**: Assume your audience knows the domain
- **Always include GitHub link**: Proof of work
- **2 hashtags max**: #backend + 1 topic
- **Aim for 200-260 chars** (leaves room for link preview)
