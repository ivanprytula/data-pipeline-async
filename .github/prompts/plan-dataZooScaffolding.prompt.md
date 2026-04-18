# Scaffolding Phase: 12-File Blueprint Before Phase 1 Code

## TL;DR

Create 12 reference files (8 phase guides + 3 templates + 1 tracking root) in `.github/instructions/` and `docs/templates/`. These are pure execution blueprints—no code changes. Once created, you have a complete roadmap for all 8 phases + weekly tracking checklist.

---

## What Gets Created (Batch Approach)

### Batch 1 (Root Scaffolding) — ~30 min

1. `.github/instructions/middle-tier-grind-tracking.md` — Weekly checklist (SQL patterns 40, pytest fixtures 10, async gotchas 5, interview Q per phase)
2. `docs/templates/linkedin-post-template.md` — 280-char post format with examples
3. `docs/templates/portfolio-item-template.md` — GitHub link + learning insight format
4. `docs/templates/github-commit-template.md` — Structured commit messages with interview prep section

### Batch 2 (Phase Guides) — ~2–3 hours, parallel

5. `.github/instructions/phase-1-events.md` — Redpanda + Celery toy (consumer lag, partitioning, exactly-once)
6. `.github/instructions/phase-2-scrapers.md` — GraphQL toy (rate limiting, async semaphore)
7. `.github/instructions/docker-ci-guide.md` — WebSocket toy (GitHub Actions, ECR, multi-stage Docker)
8. `.github/instructions/phase-3-ai-qdrant.md` — gRPC toy (embeddings, vector DB, caching)
9. `.github/instructions/phase-4-testing.md` — Pytest fixtures + Celery mocking (10 patterns, 5 async gotchas)
10. `.github/instructions/phase-5-database.md` — SQL mastery (40 patterns, EXPLAIN ANALYZE, indexes)
11. `.github/instructions/phase-6-security.md` — JWT + refresh tokens, rate limiting, input validation
12. `.github/instructions/phase-7-terraform.md` — Terraform modules, multi-env (dev/staging/prod), Fargate, CD

---

## Each Phase Guide Contains

| Section | What It Holds | Example |
|---------|--------------|---------|
| Overview | What phase unlocks | "Event streaming enables decoupled services" |
| Core Interview Q | The main question you'll face | "Design real-time ETL for 1000+ events/sec" |
| Suggested Answer Arc | 3–4 bullet points you should cover | Topic partitioning by entity ID, consumer groups for scale |
| Follow-up Questions | Gotchas interviewers ask | Consumer lag definition, exactly-once idempotency |
| Toy Example | Concrete feature to build | Celery background job publishing to Kafka |
| Code Checklist | Step-by-step (from existing plan) | Add Redpanda to docker-compose, create app/events.py |
| Interview Prep | Specific talking points | Partition assignment strategies, offset management |
| Artifacts | Portfolio items to create | LinkedIn post, portfolio-phase-N.md, 8–15 commits |
| Success Criteria | How to know you're done | Processor receives events, tests 100% pass, Docker ports healthy |

---

## File Structure

```
.github/instructions/
├── middle-tier-grind-tracking.md          (ROOT — weekly checklist)
├── phase-1-events.md
├── phase-2-scrapers.md
├── docker-ci-guide.md
├── phase-3-ai-qdrant.md
├── phase-4-testing.md
├── phase-5-database.md
├── phase-6-security.md
└── phase-7-terraform.md                   (Infrastructure as Code)

docs/templates/
├── linkedin-post-template.md
├── portfolio-item-template.md
└── github-commit-template.md
```

---

## Integration with Existing Files

These new files **reference** (don't duplicate):
- `docs/decisions.md` — Tech choice rationale (Redpanda vs Kafka, Qdrant vs pgvector)
- `docs/commands.md` — CLI tools (docker-compose, pytest, commands)
- `docs/pillar-5-security.md` — Auth mechanisms (HTTP Basic, Bearer, Sessions)
- `docs/pillar-2-database.md` — SQL fundamentals (foundation for Phase 5)

---

## File Contents (Detailed)

### 1. `.github/instructions/middle-tier-grind-tracking.md` (ROOT)

**Purpose:** Single source of truth for weekly tracking, checklists, measurements.

**Sections:**
- Phase timeline table (weeks 1–16, core Q, toys)
- **SQL Patterns Checklist (40)**
  - Basic 10: SELECT, JOIN, GROUP BY, subqueries, UNION, DISTINCT, CASE, CAST, COALESCE, CROSS JOIN
  - Mid 15: Composite index, PARTIAL INDEX, BRIN, GIN, EXPLAIN ANALYZE, CTE, recursive, window functions, PARTITION BY, LATERAL, keyset pagination, self-join, UPDATE/DELETE with JOIN, transaction isolation
  - Advanced 15: Materialized view, constraints, triggers, PL/pgSQL, JSON ops, array ops, range types, full-text search, exclusion, pooling, VACUUM/ANALYZE/REINDEX, prepared statements, cursor
  - Format: `[ ]` checkbox per pattern + description
- **Pytest Fixtures (10)**
  - async_session, client, mock_external_api, cleanup, parametrized, scope, tmp_file, time_travel, caplog, db_transaction_rollback
  - Format: `[ ]` + one-liner use case
- **Async Gotchas (5)**
  - Greenlet without event loop → `expire_on_commit=False`
  - Sync code in async → `asyncio.to_thread()`
  - Task not awaited → always `await`
  - Cancellation not propagated → check `current_task().cancel()`
  - Event loop closed → use `asyncio_mode = "auto"`
  - Format: Issue → Fix table
- **Weekly Interview Q Checklist** (8 rows + 1 new Phase 8)
  - Phase 1: "Consumer lag and partitioning" | `[ ] Explain | [ ] Design scenario`
  - Phase 2: "Scraper design and rate limiting" | `[ ] Explain | [ ] Design scenario`
  - Phase 3 (Docker+CI): "Dev → prod pipeline" | `[ ] Explain | [ ] Design scenario`
  - Phase 4: "Test external API call" | `[ ] Explain | [ ] Design scenario`
  - Phase 5: "Slow query (5s). Fix." | `[ ] Explain | [ ] Design scenario`
  - Phase 6: "Design JWT auth for multi-service" | `[ ] Explain | [ ] Design scenario`
  - Phase 7: "Terraform for multi-env" | `[ ] Explain | [ ] Design scenario`
  - Phase 8: "State locked 2 hours. Recovery?" | `[ ] Explain | [ ] Design scenario`
- **Success Metrics Table**
  - Interview Q cold: 4/5 per week ✓
  - Commits/phase: 8–15 ✓
  - Tests: 100% ✓
  - LinkedIn posts: 1/phase ✓
  - Portfolio items: 1/phase ✓
- **Final CV One-Liner** (from memory)

**Usage:** Print weekly; check off patterns as learned; audit interview Q readiness before each phase.

---

### 2–8. Phase Guides (`.github/instructions/phase-{1,2,3,4,5,6,7}-*.md`)

**Template structure (copy for each):**

```markdown
# Phase {N} — {Title}

## Overview
{What this phase unlocks; why it matters for interviews/CV}

## Core Interview Question
**Q:** {The main question interviewers ask}

**Suggested Answer Arc:**
- {Point 1}
- {Point 2}
- {Point 3}

**Follow-Up Questions You Might Face:**
- {Q1}
- {Q2}

## Toy Example: {Feature Name}
{Concrete feature to build, 2–3 sentences}

**Files to Create:**
- {file 1}
- {file 2}

**Steps:**
1. {Step 1}
2. {Step 2}
3. ...

## Code Checklist
- [ ] Step 1: {description}
- [ ] Step 2: {description}
- [ ] ...

## Interview Prep
**Talking Points:**
- {Concept 1}: {brief explanation}
- {Concept 2}: {brief explanation}

## Artifacts
**LinkedIn Post:**
{Example post in 280 chars}

**Portfolio Item:**
File: `docs/portfolio-phase-{N}-{title}.md`
Include: What built, interview Q, key learning, GitHub link

**Commits:**
Aim for 8–15 commits over 2 weeks

## Success Criteria
- [ ] {Criterion 1}
- [ ] {Criterion 2}
- [ ] Tests still 100%
```

**Per-Phase Details:**

#### Phase 1: Events (Redpanda + Celery)
- Toy: Production-ready Celery background job (retry, timeout, DLQ) publishing to Redpanda topic with partitioning by source_id
- Interview Q: "Design real-time ETL for 1000+ events/sec"
- Follow-ups: "What's consumer lag? Why monitor?", "Exactly-once vs at-least-once?"
- Talking points: Consumer lag, topic partitioning, exactly-once vs at-least-once, offset management
- Success: Processor receives events reliably, Kafka unavailability doesn't crash service (fail-open), tests verify event delivery

#### Phase 2: Scrapers (GraphQL + Playwright)
- Toy: GraphQL endpoint `query { scraperStatus { source, urlsQueued, successRate } }`
- Interview Q: "Design scraper for 100K URLs without ban"
- Talking points: Rate limiting, exponential backoff, Pydantic validation as ETL filter
- Success: 3 scraper types (REST, HTML, browser), Motor async client, events published

#### Docker+CI: WebSocket + GitHub Actions
- Toy: WebSocket `/ws/scraper-status/{source}` streams live stats
- Interview Q: "Walk me through dev → prod pipeline"
- Talking points: CI/CD stages, Docker multi-stage, image registry, artifact push
- Success: GitHub Actions workflow (test → ruff → build → ECR push), multi-stage Dockerfile -80% size

#### Phase 3: AI+Qdrant (gRPC + Embeddings)
- Toy: gRPC service `EmbeddingService.EmbedText() → embedding: [float]`
- Interview Q: "Design semantic search over 100K docs"
- Talking points: Embedding models, vector DB trade-offs, LRU caching, cosine similarity
- Success: Qdrant running, API endpoint returns top-10 by similarity in <500ms

#### Phase 4: Testing (Pytest + Celery Mocking)
- Toy: Parametrized test for Celery retry logic + mock external API
- Interview Q: "How do you test function calling external API?"
- Talking points: 10 pytest patterns, async testing, freezegun for time travel
- Success: All 5 async gotchas documented with examples, 10 fixtures demonstrated

#### Phase 5: Database (SQL Mastery)
- Toy: EXPLAIN ANALYZE walkthrough; create index that cuts query from 5s → 50ms
- Interview Q: "This query is slow (5s). Fix it."
- Talking points: Query plans, index strategies, materialized views, window functions
- Success: 40 SQL patterns checklist complete, all basic + mid tier demonstrated in code

#### Phase 6: Security (JWT + Rate Limiting)
- Toy: JWT refresh token flow + rate limit on /login endpoint
- Interview Q: "Design JWT auth for multi-service"
- Talking points: JWT structure (not encrypted), refresh token strategy, rate limiting, input validation
- Success: Bearer token auth working, HMAC webhook validation, 3rd service can verify JWT

#### Phase 7: Terraform (IaC + Multi-Env)
- Toy: Terraform modules (PostgreSQL RDS, Fargate, ElastiCache, Secret Manager)
- Interview Q: "Walk me through code → production"
- Talking points: Terraform state, multi-env variables, secrets management, rollback strategy
- Success: `terraform plan` shows multi-env setup, GitHub Actions applies plan on merge

---

### 9–11. Templates (`docs/templates/`)

#### `linkedin-post-template.md`
```markdown
# LinkedIn Post Template (280 chars max)

## Format

🚀 Week N: {Feature}. {Why impact matters}.
GitHub: [link].
#{category} #{skill}

## Examples

### Phase 1
🚀 Week 2: Event streaming with Redpanda. Shipped /scraper → publishes events. Processor consumes async, zero coupling. 10M events/day. GitHub: [link]. #backend #distributed-systems

### Phase 3
🚀 Week 8: AI-ready backend. Semantic search over 100K+ docs using Qdrant + embeddings. 500ms latency. GitHub: [link]. #backend #ai

### Phase 7
🚀 Week 16: Infrastructure as code. Multi-service backend via Terraform to AWS Fargate. Prod in <5min. GitHub: [link]. #backend #devops
```

#### `portfolio-item-template.md`
```markdown
# Portfolio Item Template

## Format

# Phase N — {Title}

### What I Built
- {Feature 1}
- {Feature 2}: {metric}

### Interview Questions Prepared
- [ ] Core Q: {question}
- [ ] Follow-up: {question}
- [ ] Design scenario: {scenario}

### Key Learning
{1-2 sentence insight}

### Code
[GitHub link](path)

## Examples

### Phase 1 — Event Streaming
**What I Built**
- Redpanda topic: 10M+ events/day, 10 partitions by source_id
- Celery task: 3-retry exponential backoff, publishes to Kafka
- Consumer: offset management + DLQ for poison pills

**Interview Questions Prepared**
- [ ] Core Q: "Design real-time ETL for 1000+ events/sec"
- [ ] Follow-up: "What's consumer lag? Why monitor it?"
- [ ] Design scenario: "Event processor 2 hours behind. Diagnosis?"

**Key Learning**
Offset management is invisible but crucial—get partition assignment wrong and you iterate slowly or lose data.

**Code**
[data-pipeline-async/app/events.py](path)

### Phase 7 — Infrastructure as Code
**What I Built**
- Terraform modules: PostgreSQL RDS → Fargate → CloudWatch
- Multi-env: dev/staging/prod with tfvars inheritance
- Secrets rotation via AWS Secrets Manager

**Interview Questions Prepared**
- [ ] Core Q: "Provision production PostgreSQL RDS with Terraform"
- [ ] Follow-up: "How handle secrets in IaC?"
- [ ] Design scenario: "Spin staging replica of production. How Terraform helps?"

**Key Learning**
Terraform state is source of truth—manual AWS console changes invalidate state. Now I always `terraform plan` before deploy.

**Code**
[data-pipeline-async/infra/terraform/](path)
```

#### `github-commit-template.md`
```markdown
# GitHub Commit Message Template

## Format

feat(phaseN): {short title}

- {detail 1}
- {detail 2}

Prepared for interviews:
- {Interview skill 1}
- {Interview skill 2}

## Examples

### Phase 1
feat(phase1): event-driven architecture foundation

- Redpanda topic: records.events (10 partitions by source_id)
- Producer: app/events.py publishes record.created post-commit
- Consumer: services/processor pulls async, logs event, no blocking
- Failure mode: Kafka unavailable → fail-open (log + continue)
- Throughput: 100K events/sec (tested with k6)

Prepared for interviews:
- Explain consumer lag and partition rebalancing
- Design topic partitioning strategy
- Describe exactly-once vs at-least-once + idempotency

### Phase 3
feat(phase3): AI-ready vector search infrastructure

- Qdrant vector DB: 100K+ embeddings with metadata
- gRPC service: EmbeddingService.EmbedText() for internal calls
- Cache: LRU cache to avoid re-encoding same text
- API: POST /search?q=query → top 10 by cosine similarity
- Latency: 500ms for 100K docs

Prepared for interviews:
- Explain embedding model selection trade-offs
- Walk through semantic search design vs keyword search
- Discuss vector DB indexing (IVF/HNSW) impact on latency

### Phase 7
feat(phase7): infrastructure-as-code deployment

- Terraform modules: PostgreSQL RDS, Fargate ECS, ElastiCache
- Multi-env: dev/staging/prod with tfvars inheritance
- Secrets: AWS Secrets Manager integration, auto-rotation
- CD pipeline: GitHub Actions (plan review → auto apply)
- Rollback: terraform destroy previous version + pull old image

Prepared for interviews:
- Design multi-environment Terraform structure
- Explain state management best practices
- Walk through secrets rotation in IaC
```

---

## Creation Checklist

### Batch 1 (Immediate)
- [ ] Create `.github/instructions/middle-tier-grind-tracking.md`
- [ ] Create `docs/templates/linkedin-post-template.md`
- [ ] Create `docs/templates/portfolio-item-template.md`
- [ ] Create `docs/templates/github-commit-template.md`

### Batch 2 (After Batch 1)
- [ ] Create `.github/instructions/phase-1-events.md`
- [ ] Create `.github/instructions/phase-2-scrapers.md`
- [ ] Create `.github/instructions/docker-ci-guide.md`
- [ ] Create `.github/instructions/phase-3-ai-qdrant.md`
- [ ] Create `.github/instructions/phase-4-testing.md`
- [ ] Create `.github/instructions/phase-5-database.md`
- [ ] Create `.github/instructions/phase-6-security.md`
- [ ] Create `.github/instructions/phase-7-terraform.md`

---

## Verification After Creation

- ✅ 11 files exist with ~2,500 lines total
- ✅ Tracking file: 40 SQL patterns, 10 pytest fixtures, 5 async gotchas, 8 interview Q rows
- ✅ Each phase guide: overview, core Q + arc, toy, checklist, interview prep, artifacts section
- ✅ All file paths match project structure
- ✅ Example code blocks realistic, copy-paste ready
- ✅ No typos in interview questions

---

---

## Execution Order: Which Plan First? ✓ ANSWERED

**Run `plan-dataZooPlatform.prompt.md` FIRST (16-week roadmap: WHAT + WHY)**
**Then run `plan-dataZooScaffolding.prompt.md` (scaffolding files: HOW + WHEN)**
**Execute dataZooPlatform in 2-week chunks per phase** ✓

Refinements Applied:
- ✅ Phase 5 simplified: 15 practical SQL patterns (not 40)
- ✅ Interview Q with follow-ups on every phase
- ✅ Toy examples marked as "production-ready" (not minimal)
- ✅ LinkedIn posts in technical/measured tone (not celebratory)
- ✅ No README.md for `.github/instructions/`

---

## Next Steps

1. **Approve this scaffolding plan** (ready to execute)
2. **Create all 11 files** in parallel (Batch 1 = 30 min, Batch 2 = 2–3 hours)
3. **Push to GitHub** with commit: `docs(phase0): create scaffolding for 8-phase Data Zoo`
4. **Start Phase 1** using `.github/instructions/phase-1-events.md` as implementation blueprint
