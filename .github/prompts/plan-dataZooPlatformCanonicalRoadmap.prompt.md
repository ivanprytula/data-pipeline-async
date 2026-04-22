# Plan: Data Zoo Platform — Canonical Roadmap

Executive summary

This document is the canonical, prioritized roadmap for the Data Zoo Platform. It consolidates the project pillars (stability, ingestion, background processing, observability, security, UI, notifications, and advanced ML features) into a single, scored plan with clear phases, milestones, and next actions. Use this file as the editable prompt for further refinement and to generate the persistent `docs/progress/roadmap.md`.

Scoring methodology

- Score range: 1 (low) — 10 (critical)
- Factors considered: user value, risk to shipping, cross-cutting dependencies, engineering effort, maintainability.
- Outcome: higher score = earlier implementation priority.

Prioritized pillars (scores & immediate steps)

1) Tests & CI Stabilization — Score: 10
- Why: Foundation for safe iteration; tests must be deterministic and fast in CI.
- Immediate tasks: ensure Alembic migrations run in test fixtures; preserve migrated schema (no destructive drop_all); truncate tables between tests; add CI job that runs full test matrix (unit + integration with PostgreSQL container).
- Owner: core maintainers / release engineer
- Timeframe: 0–14 days

2) Core Data Model & Migrations — Score: 9
- Why: Data model correctness and migration hygiene are prerequisites for all features.
- Immediate tasks: review models for index hotspots, data retention needs, and unique constraints; finalize Alembic scripts; add migration verification step in CI.
- Timeframe: 0–30 days

3) Reliable Ingestion & Scheduling — Score: 8
- Why: Ingestion is the product's primary function; must be robust and idempotent.
- Immediate tasks: add a lightweight scheduling abstraction (APScheduler or internal cron wrapper) for periodic jobs; implement idempotent ingestion tasks and backoff/retry policies; add health checks for ingestion pipelines.
- Longer: evaluate Celery/arq for long-running or heavy work.
- Timeframe: 14–60 days

4) Observability & Monitoring — Score: 8
- Why: Operability and SLO measurement depend on metrics, traces, and logs.
- Immediate tasks: integrate Prometheus metrics (request counters, latencies, job success/failure), structured JSON logging, OpenTelemetry traces for key flows, and Sentry error tracking; add dashboards for ingestion health and job backlog.
- Current status (April 23, 2026): baseline Sentry integration shipped.
- Implemented in repo:
  - Environment-gated Sentry SDK init (`SENTRY_ENABLED`, `SENTRY_DSN`)
  - FastAPI/SQLAlchemy/logging integrations for centralized exception capture
  - Release/environment tagging for faster production triage
- Timeframe: 14–45 days

5) Background Processing & Scaling — Score: 7
- Why: For scale and reliability (parallel workers, retries, visibility) a task broker may be needed.
- Immediate tasks: start with scheduled tasks + lightweight workers; evaluate Celery (Redis/RabbitMQ), `arq` (Redis), and serverless job approaches; prototype with one workflow (e.g., large batch ingest) to validate operational model.
- Current status (April 22, 2026): in-process worker queue prototype shipped behind feature flags.
- Implemented in repo:
  - Worker pool: `BackgroundWorkerPool` (asyncio queue + N workers)
  - Endpoints: `POST /api/v1/background/ingest/batch`, `GET /api/v1/background/tasks/{task_id}`, `GET /api/v1/background/workers/health`
  - Metrics: `pipeline_background_jobs_submitted_total`, `pipeline_background_jobs_processed_total`, `pipeline_background_jobs_in_queue`, `pipeline_background_jobs_active`
  - Tests: integration coverage with lifespan enabled and workers turned on
- Next: evaluate Celery/arq as drop-in execution backend while preserving the current API contract and observability labels.
- Timeframe: 45–120 days

6) Security, Auth, and RBAC — Score: 7
- Why: Product safety, multi-tenant readiness, and compliance.
- Immediate tasks: implement basic user model, role-based access control for API operations, rate-limiting (slowapi/fastapi middleware), and secret management patterns; add security headers and CI dependency scanning.
- Current status (April 23, 2026): baseline implementation shipped.
- Implemented in repo:
  - User model + migration: `users` table with role and active flags
  - RBAC dependencies: session/JWT role guards (`viewer`/`writer`/`admin`)
  - Role-protected API operations for secure archive/delete and JWT-protected writes
  - Security headers middleware on all responses
  - Production secret guardrails (startup fail-fast on weak defaults)
  - CI dependency scanning already active (`security-full.yml`: pip-audit + Trivy)
- Next: move session state to Redis, add persisted user auth endpoints, and expand RBAC coverage across more routes.
- Timeframe: 30–90 days

7) Admin UI & User Workflows — Score: 6
- Why: Admin tooling reduces friction (job control, user management, visibility).
- Immediate tasks: implement a minimal admin UI (static React or server-side templates) for job status, manual re-run, and user management; iterate after API stabilization.
- Current status (April 23, 2026): baseline dashboard admin workflows shipped.
- Implemented in repo:
  - Dashboard admin page: `GET /admin` (HTMX + Jinja2)
  - Worker health workflow: `GET /api/v1/background/workers/health`
  - Task lookup workflow: `GET /api/v1/background/tasks/{task_id}`
  - Manual rerun workflow: `POST /api/v1/background/ingest/batch` (single-record admin batch)
  - Session bootstrap workflow: `POST /api/v1/records/auth/login` (role-aware)
  - Integration tests for admin page and admin partial workflows
- Next: add persisted user CRUD/auth endpoints and expose real user management in admin UI.
- Timeframe: 60–180 days

8) Notifications & Emailing — Score: 5
- Why: Operational convenience (alerts, processed notifications) — not critical to core ingestion.
- Immediate tasks: add notification abstraction and a transactional email provider integration for alerts and user notifications.
- Current status (April 23, 2026): baseline implementation shipped.
- Implemented in repo:
  - Notification abstraction supporting Slack, Telegram, webhook, and email (Resend)
  - Background worker failure alerts wired to notification dispatch
  - Manual dispatch endpoint: `POST /api/v1/notifications/test`
  - Env-based configuration for providers (no hardcoded secrets)
  - Unit/integration tests for dispatch and endpoint behavior
- Next: add Jira issue automation for critical alerts and user-level notification preferences.
- Timeframe: 60–150 days

9) Embeddings & LLM Features (Vector Search) — Score: 4
- Why: Strategic differentiation but high effort, dependent on data shape and query patterns.
- Immediate tasks: define use cases, prototype small PoC with pgvector or Qdrant; defer large investment until core product stabilizes.
- Timeframe: 120+ days (after stabilization)

Phases & milestones

Phase 0 — Stabilize (0–30 days)
- Runbook: Tests & CI stabilization, Alembic + migrations, core model reviews, limited observability (basic metrics + logging).
- Milestone: Green CI across unit and integration suites; reproducible local dev environment; documented test lifecycle.

Phase 1 — Foundation (30–90 days)
- Runbook: scheduling abstraction, idempotent ingestion jobs, role-based auth, richer observability dashboards, small admin UI.
- Milestone: Scheduled jobs running in production-like environment; onboarding doc for new jobs; basic RBAC in API.

Phase 2 — Scale & Reliability (90–180 days)
- Runbook: background worker architecture (broker selection + runbook), alerting/SLIs, horizontal scaling of ingestion, admin UX polish.
- Milestone: Successful load test at expected traffic; worker autoscaling policy defined and tested.

Phase 3 — Productization & Advanced Capabilities (180+ days)
- Runbook: notification workflows, ML/LLM features (vector search, similarity), marketplace integrations, hardened security controls for production tenants.
- Milestone: Public-facing admin UI and stable LLM POC in production sandbox.

30/60/90-day tactical plan

- 0–30 days (30-day focus):
  - Ensure tests and CI are stable (Alembic in tests, truncate-only cleanup).
  - Add CI job for migrations verification and PostgreSQL integration tests.
  - Integrate basic Prometheus metrics and structured logging.
  - Complete core model review and index recommendations.

- 30–60 days (60-day focus):
  - Add scheduling abstraction and migrate one periodic job to it.
  - Implement basic RBAC and rate-limiting middleware.
  - Build minimal admin endpoints (job status, manual rerun).
  - Add Grafana dashboards for ingestion and job health.

- 60–90 days (90-day focus):
  - Evaluate broker-backed worker approach (Celery/arq/proc model) and compare against current in-process baseline.
  - Implement worker runbook and disaster-recovery steps for failed jobs.
  - Add automated alerting for job failures and high-latency requests.

Risks & mitigations

- Risk: Premature broker adoption (complexity & ops burden)
  - Mitigation: Start with internal scheduler + lightweight workers; only adopt broker if load and operational needs require it.

- Risk: Test flakiness due to environmental mismatch (SQLite vs PostgreSQL)
  - Mitigation: Standardize on Alembic migrations for tests; ensure CI runs full PostgreSQL integration matrix.

- Risk: Data model changes cause downtime or long migrations
  - Mitigation: Use online-safe migration patterns, zero-downtime migration docs, and migration previews in CI.

Next actions (immediate)

1. Persist this plan: create `docs/progress/roadmap.md` (this file is an editable prompt — convert to repo doc once confirmed).
2. Create PR with the roadmap and link relevant pillar docs for traceability.
3. Tag owners and schedule a short planning review to align 30/60/90-day commitments.
4. Add CI job(s): migrations verification and PostgreSQL integration tests.
5. Iterate this prompt/file with stakeholders and lock the canonical roadmap in `docs/progress/roadmap.md`.

Notes

- This plan is intentionally pragmatic: fix the test & DB foundations first, then incrementally add scheduling and observability before investing in brokers or ML.
- For each pillar, create 2–3 tickets that are small, testable, and shippable — prefer incremental rollouts.

---

End of plan (editable).
