# GitHub Commit Template

Save to: `docs/templates/github-commit-template.md`

---

## Format

```text
{type}({scope}): {description}

{body}

{interview prep section}
```

---

## Rules

1. **Type**: `feat`, `fix`, `docs`, `refactor`, `test`, `infra`, `perf`
2. **Scope**: Phase or component (e.g., `events`, `database`, `testing`, `ci`)
3. **Description**: Lowercase, present tense, <50 chars, actionable
4. **Body**: Why + what, 1-3 lines. Link to issue if exists.
5. **Interview Prep** (OPTIONAL): Post-commit self-check to prep for follow-up Qs

---

## Examples

### Phase 1: Event Streaming

```text
feat(events): add Redpanda producer with exponential backoff

Added Celery producer in app/events.py. Records trigger event emission
on creation. Producer handles Redpanda unavailability with 3-retry
exponential backoff. DLQ consumer in services/processor/main.py.

INTERVIEW CHECKLIST:
- [ ] "Why exponential backoff?" → Prevents thundering herd on retry
- [ ] "What if producer fails?" → Event is logged, processed async, retried
- [ ] "Exactly-once semantics?" → Idempotency key in payload, consumer dedupes
```

### Phase 2: ETL with Async Semaphore

```text
feat(scrapers): implement GraphQL scraper with rate limiting

Scraper for pricing data via GraphQL. Async semaphore limits to 10
concurrent requests. Playwright handles JS-heavy pages. Exponential
backoff on 429s. Results cached in Redis for 1 hour.

Resolves: #42

INTERVIEW CHECKLIST:
- [ ] "Why semaphore?" → Prevent overwhelming target, respect rate limits
- [ ] "How handle rate limits?" → Check X-RateLimit headers, backoff on 429
- [ ] "Async vs threads?" → I/O-bound (network), so async better. CPU-bound would use ProcessPoolExecutor
```

### Docker + CI: Multi-Stage Build

```text
infra(ci): add GitHub Actions workflow with multi-stage Docker builds

Workflow (ci.yml): linting → unit tests → integration tests → docker build.
Docker: builder stage compiles deps, runtime stage ~50MB slimmed image.
Push to ECR on main branch. Includes GitHub Status checks for PRs.

INTERVIEW CHECKLIST:
- [ ] "Why multi-stage?" → Separate compile environment from runtime, smaller image
- [ ] "ECR vs DockerHub?" → ECR integrates with ECS/Fargate (AWS native), simpler secret mgmt
- [ ] "How cache dependencies?" → RUN statement layer caching. If requirements.txt unchanged, skip pip install
```

### Phase 3: Vector DB + LRU Cache

```text
feat(ai): add LRU cache decorator for embedding API calls

Implemented app/cache.py with @lru_cache_async decorator. Embedding calls
(gRPC to Qdrant) now cached by text hash. Cache size 1000, TTL 24h.
Memcached alternative considered but overkill—in-process cache sufficient.

INTERVIEW CHECKLIST:
- [ ] "Redis vs in-process cache?" → Redis if multi-process/distributed. Single process → in-process is faster
- [ ] "Cache hit ratio target?" → Aim for 60%+. Monitor via prometheus metric cache_hits / cache_total
- [ ] "Stale embedding scenario?" → Accept staleness (vectors don't change frequently). TTL prevents forever-stale
```

### Phase 4: Pytest Fixtures + Mocking

```text
test(testing): refactor fixtures to support async Celery mocking

Reorganized conftest.py with: async_db_session (SQLite in-mem), mocked_celery
(task.apply_async mocked to immediate exec), client (AsyncClient), parametrized fixtures.
All tests now run in ~8s (down from 22s with real Celery).

INTERVIEW CHECKLIST:
- [ ] "Fixture scope: function vs module?" → function (isolation) unless expensive setup. DB session always function.
- [ ] "How mock Celery?" → dependency_overrides pattern + mock.patch('celery.app.task'). Or celery.current_app.conf.task_always_eager=True
- [ ] "Parametrize vs for loop?" → Parametrize for matrix expansion (test_payload[0], test_payload[1], etc). Shows better in pytest report.
```

### Phase 5: Database Index + Window Function

```text
perf(database): add composite index on (pipeline_id, created_at), rewrite analytics query

Analytics query was seq scan (5s). Added composite index on (pipeline_id, created_at).
Query now index scan (50ms). Bonus: rewritten subquery → window function PARTITION BY,
additional 10% gain.

Query plan before/after added to commit as comment.

INTERVIEW CHECKLIST:
- [ ] "How read EXPLAIN ANALYZE?" → "Seq Scan" = bad. "Index Scan" = good. Check actual vs estimated rows.
- [ ] "Composite index ordering?" → WHERE conditions first, then high-cardinality ORDER BY. Prefix subsets usable (a,b index scans a alone).
- [ ] "Window functions vs subquery?" → Window functions execute once per partition, no join. Subquery executes per row. Window typically faster.
```

### Phase 6: JWT Token Rotation

```text
feat(security): implement JWT refresh token rotation with rate limiting

Added refresh_token endpoint in app/auth.py. Returns new access + refresh token.
Old refresh token invalidated in Redis. Rate limit 5 refreshes/hour per user.
Refresh token expires 30d, access token 15min.

INTERVIEW CHECKLIST:
- [ ] "Why rotate refresh?" → Mitigates stolen tokens. If refresh leaked, attacker limited to 30d window not 90d
- [ ] "Rate limit strategy?" → Token bucket in Redis. decay = current_time - last_refresh. If decay < 12min, reject (5/hour = 1 per 12min).
- [ ] "Single-use refresh?' → Optional (more secure but breaks multi-tab scenario). Documented tradeoff in docs/api-auth-production-guide.md
```

### Phase 7: Terraform Multi-Environment

```text
infra(terraform): add multi-environment support (dev, prod)

Terraform modules: networking, RDS, ECS cluster, ALB. Variables.tf defines env inputs.
Workspaces separate tfstate (dev, prod). Secrets fetched from AWS Secrets Manager.
Terraform plan gated by GitHub Actions (manual approval for prod).

INTERVIEW CHECKLIST:
- [ ] "State lock?" → DynamoDB table (terraform init -backend-config). Prevents concurrent applies, corrupted state
- [ ] "Rotate secrets?" → AWS Secrets Manager + rotation Lambda. Terraform reads current secret, applies it. Rotation transparent.
- [ ] "ECS vs Fargate?" → Fargate (simpler, per-task billing). ECS EC2 (cheaper at scale, more control). Started Fargate, can migrate to ECS EC2 later.
```

---

## Commit Checklist

Before pushing:

- [ ] Commit is **atomic** (one logical change)
- [ ] Tests pass (`pytest`, linting `ruff`)
- [ ] Commit message follows template above
- [ ] Interview checklist filled in (if applicable)
- [ ] GitHub issue linked (if exists, use `Resolves: #123`)
- [ ] Branch name is phase-aware (`phase-1-{feature}`, `phase-2-{feature}`, etc.)

---

## Why Commit Quality Matters

Interview prep happens during commits: Stop, articulate the "why," fill in the checklist. This forces you to:

1. **Understand decisions** (exponential backoff, semaphore, caching, indexing)
2. **Prepare follow-ups** (cache hit ratio? state lock? token rotation?)
3. **Teach others** (future self reading this commit in 6 months)

8–15 commits per phase × 7 phases = 56–105 commits over 16 weeks. That's 56–105 opportunities to solidify understanding and document reasoning. Use them.
