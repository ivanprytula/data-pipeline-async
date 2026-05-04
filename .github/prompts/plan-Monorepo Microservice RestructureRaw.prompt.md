# Monorepo Microservice Restructure: services/ Consolidation

Scope note: This remains a monorepo with a single uv.lock, shared pyproject.toml dev tooling, and shared alembic/. The goal is organizational clarity so each service directory can eventually be owned by a separate team with minimal cross-service friction.

Phase 1 — Move ingestor under services/
This is the only service currently living outside services/, breaking the symmetry.

Rename the directory: ingestor/ → services/ingestor/

Update all Python imports (from ingestor.X → from services.ingestor.X / import ingestor.X → import services.ingestor.X). Affected files include:

All ~80 *.py files in ingestor/ itself (relative imports mostly fine, but absolute imports need updating)
All tests/**/*.py files (conftest, integration, unit, e2e — all import from ingestor)
alembic/env.py (imports ingestor.database and ingestor.models)
scripts/ci/check_service_boundaries.py SERVICE_ROOTS dict
Update root Dockerfile: change COPY ingestor/ ./ingestor/ → COPY services/ingestor/ ./services/ingestor/ and the CMD from ingestor.main:app → services.ingestor.main:app

Update docker-compose.yml ingestor service (no build-context change needed since context is already ., but develop.watch path changes)

Update pyproject.toml:

addopts = "--cov=ingestor ..." → "--cov=services/ingestor ..."
[tool.coverage.run] source = ["ingestor"] → ["services.ingestor"]
[[tool.ty.overrides]] include = ["ingestor", "tests"] → add "services"
Update CI workflow path filters in ci.yml (ingestor/** → services/ingestor/**)

Phase 2 — Fix Naming Inconsistencies
Two naming mismatches between Docker Compose and Python modules:

services/inference (compose build context path) vs services/inference (Python module) → standardize on inference (underscores) everywhere, including the compose develop.watch path and Dockerfile context
analytics (compose) vs analytics (Python) → same: standardize on analytics
This means renaming Docker Compose service keys inference → inference and analytics → analytics, and updating any references in nginx.conf, CI files, or scripts that reference the old hyphenated names.

Phase 3 — Per-Service Directory Structure (Team Separation)
Give each service in services/ the same skeleton so any team can onboard independently:

Code
services/
├── ingestor/
│   ├── README.md          # Team entry point: what this service does, how to run/test
│   ├── Dockerfile         # Moved from root Dockerfile
│   ├── pyproject.toml     # Service-local: declares its own [project] metadata (no version pinning yet)
│   └── tests/             # Service-local tests (moved from root tests/)
│       ├── unit/
│       └── integration/
├── inference/
│   ├── README.md
│   ├── Dockerfile         # Already exists
│   ├── pyproject.toml
│   └── tests/
├── analytics/
│   ├── README.md
│   ├── Dockerfile         # Already exists
│   ├── pyproject.toml
│   └── tests/
├── processor/
│   ├── README.md
│   ├── Dockerfile         # Already exists
│   ├── pyproject.toml
│   └── tests/
└── dashboard/
    ├── README.md
    ├── Dockerfile         # Already exists
    ├── pyproject.toml
    └── tests/
Sub-steps:

Add README.md per service — team name, service purpose, ports, env vars, how to run dev/test in isolation
Add pyproject.toml per service — [project] metadata only (name, version, description); no separate dependency resolution for now (deps still managed at root). Acts as a namespace marker and future extraction point
Migrate tests from root tests/{unit,integration,e2e}/<service>/ into services/<service>/tests/ — this is the biggest mechanical change after the import rename. Keep a stub tests/ at root for shared fixtures (conftest.py, shared/payloads.py) and cross-service e2e tests
Update pyproject.toml testpaths to include services/*/tests
Update check_service_boundaries.py — tests now co-located, script must not flag service-local test imports as boundary violations
Phase 4 — Monorepo Governance Layer
Add governance artifacts that make the team-per-service model explicit:

.github/CODEOWNERS — map each services/<name>/ to a team:

Code
services/ingestor/    @org/team-ingestor
services/inference/  @org/team-ai
services/analytics/   @org/team-query
services/processor/   @org/team-processor
services/dashboard/   @org/team-dashboard
libs/                 @org/platform-team
Update check_service_boundaries.py — reflect new services/ingestor path; add note about test co-location being allowed (tests may import their own service)

CI path-filter updates in ci.yml — per-service change detection already exists (ingestor_change, inference_change, etc.); update paths to match new layout. Consider adding per-service test jobs that only run the relevant service's tests on targeted changes

Document the monorepo trade-offs in a top-level docs/monorepo-structure.md:

Why one uv.lock (reproducibility, shared deps, simpler CI)
Why alembic/ stays at root (single schema owner = ingestor; other services are read-only)
How to add a new service (copy service skeleton)
Path to full extraction (when/if a service graduates to its own repo)
Migration Order & Risk
Step	Risk	Notes
Phase 1 (move ingestor)	High — many import sites	Do as a single atomic commit; run full test suite before merging
Phase 2 (fix naming)	Low	Mechanical find/replace; verify nginx/compose after
Phase 3 (per-service skeletons)	Medium — test relocation	Can be done incrementally per service
Phase 4 (governance)	Low	Documentation + CODEOWNERS only
What does NOT change:

Single uv.lock / shared dependency resolution
Root alembic/ (ingestor-owned migrations)
Root pyproject.toml as the dev tooling config hub (ruff, pytest, coverage)
libs/ stays at root (shared by all)
All services still in the same Git repository


## Q: Also, I'm thinking about services renaming, e.g. if/when I add API Gateway, there will be some confusion with 'inference'. Also, 'analytics' seems too generic name. What about system design pattern "service discovery" or 'service mesh' ? Do I need smth at current point of development?

Service Naming
The Problem with Current Names
Current name	Why it's problematic
inference	Collides with the well-known API Gateway pattern. When you add an API Gateway (nginx/Kong/AWS API GW sits in front of ALL services), "inference" sounds like the system entry point, not an AI-specific microservice.
analytics	Too generic — every HTTP service is a "query API" by that logic. Offers no domain signal.
Recommended Renames
Current	Suggested	Rationale
inference	embeddings-service or vector-service	Names what it actually does (text embedding + Qdrant search). No confusion with networking gateway patterns.
analytics	analytics-service	Reflects its domain: CQRS read-side, materialized views, window functions, analytics. Matches the existing router name analytics.py.
Other services are well-named already:

ingestor — clear write-side CQRS owner
processor — clear Kafka consumer worker
dashboard — clear UI service
If you add an API Gateway later, it unambiguously sits above all services with no name collision.

Service Discovery & Service Mesh — Do You Need Them Now?
Short answer: No. You have the right primitives already.

Here's why, mapped to your actual architecture:

Code
Current inter-service communication
────────────────────────────────────
  dashboard  ──HTTP──► ingestor   (INGESTOR_URL env var)
  dashboard  ──HTTP──► inference (INFERENCE_URL env var)
  ingestor   ──HTTP──► inference (INFERENCE_URL env var)
  analytics  ──SQL──►  postgres   (DATABASE_URL env var)
  processor  ──Kafka►  redpanda   (KAFKA_BROKER_URL env var)
What service discovery solves: dynamic location of services (IPs change at runtime, autoscaling creates/destroys instances, you can't hardcode URLs). Your services find each other via environment variables + Docker Compose DNS (http://ingestor:8000) — which IS a primitive form of service discovery (Compose's embedded DNS resolver).

What service mesh solves: mTLS between services, retries/circuit-breaking at the network layer, distributed tracing injection, canary traffic shifting — all without touching application code. You already implement circuit breaking and retry in ingestor/core/circuit_breaker.py and ingestor/core/retry.py at the application layer, and you have OTel tracing.

Decision Matrix for Your Current Stage
Capability	You need it?	You already have it via...
Service location (find peer services)	✅ Yes	Docker Compose DNS + env vars
Health checks	✅ Yes	/health + /readyz on every service
Circuit breaking	✅ Yes	libs/platform/circuit_breaker.py
Retry logic	✅ Yes	libs/platform/retry.py
Distributed tracing	✅ Yes	OTel + Jaeger
mTLS between services	❌ Not yet needed	No sensitive inter-service data in transit
Dynamic service registry	❌ Not needed	Services are static (5 known services, not 50)
Traffic shifting / canary	❌ Not needed	No multi-version deployments yet
When to Revisit
Trigger	Add...
Deploy to Kubernetes	K8s built-in DNS + Service objects replace Compose DNS. Still no mesh needed.
10+ services OR dynamic autoscaling	Consider Consul (service registry) or K8s native discovery
Need mTLS without code changes	Consider Istio or Linkerd sidecar mesh
Complex traffic routing (A/B, canary, fault injection)	Consider Istio or AWS App Mesh
Recommended Path
Code
Now (5 services, monorepo, Compose)
  └─► Env-var discovery + Compose DNS  ✅ already there

Next (K8s deployment)
  └─► K8s Service objects + CoreDNS    no mesh needed

Later (10+ services OR mTLS requirement)
  └─► Add Istio/Linkerd OR Consul
Bottom line: Add the renames (embeddings-service, analytics-service) now — they're zero-cost and prevent long-term confusion. Defer service discovery infrastructure until you hit Kubernetes with autoscaling or need mTLS.

## Q: continue planning efforts: 1) what if I add another but simpler AI integrations, i.e. AI chat or kinda "proxy prompting using my AI vendors paid subscription"? can I out them into new suggested "embeddings-service" ? 2) what if I want to add more 'processors"-like services? should I add new features only to current "processor" or I'm free to create new services just to sure they act as events consumers?

Question 1: AI Chat / Proxy Prompting — Where Does It Belong?
The previous rename recommendation (inference → embeddings-service) was deliberately narrow: name it after what it does (embed text → store/query vectors). Adding chat and proxy prompting adds a second responsibility. Whether to co-locate or split depends on how you model the bounded context:

Option A — Rename to ai-service (recommended for now)
Widen the scope of the single service to cover all AI vendor interactions:

Code
ai-service
  ├── /embed          ← POST text → embedding vector (existing)
  ├── /search         ← POST query → Qdrant nearest-neighbours (existing)
  ├── /chat           ← POST messages → LLM response (new)
  └── /prompt         ← POST prompt → proxied vendor response (new)
Rationale: All four endpoints share the same cross-cutting concerns — vendor API keys, rate limits, retry/circuit-breaker against external APIs, OpenTelemetry spans for AI latency. One service, one set of secrets, one deployment unit. This is the "AI vendor adapter" bounded context.

When it breaks down: if chat becomes stateful (conversation history in DB), or if you need separate scaling (embeddings are CPU-bound, chat is I/O-bound), split then.

Option B — Keep embeddings-service + add llm-service
Code
embeddings-service   ← vector ops only
llm-service          ← chat, proxy prompting
When to choose this: if LLM usage needs separate billing tracking, different team ownership, or you anticipate chat growing into a full conversation management system (with session storage, RAG pipeline, etc.).

Decision Rule
Signal	Do this
Simple proxy, same vendor keys, same retry logic	Option A: ai-service
Chat needs session/history storage (new DB dependency)	Option B: split
Different team owns AI infra vs. AI chat	Option B: split
Just starting, uncertain	Option A: start merged, split later when you feel the pain
Question 2: Multiple Processor-Like Services
Yes — create new services freely. This is exactly what Kafka's consumer group model is designed for.

How Kafka Consumer Groups Enable This
Code
redpanda topic: pipeline.records
        │
        ├──► consumer-group: processor          ← existing service
        │       └─ enriches records, writes to Postgres
        │
        ├──► consumer-group: notifier           ← hypothetical new service
        │       └─ sends webhook/email on certain record types
        │
        └──► consumer-group: archiver           ← hypothetical new service
                └─ writes cold storage (S3/GCS)
Each consumer group gets its own independent offset — they all read from the same topic at their own pace. Adding a new consumer never touches the producer or the existing processor.

When to Extend Existing processor vs. Create a New Service
Situation	Recommendation
New logic is in the same domain (e.g., enrich record in a different way)	Extend processor (add a new handler/strategy)
New logic has a different scaling profile (e.g., slow I/O, GPU work)	New service with its own consumer group
New logic has different failure tolerance (e.g., archival can lag, notifications must be fast)	New service — independent lag/backpressure
New logic needs different dependencies (S3 SDK, email provider)	New service — don't bloat processor's requirements.txt
New logic would make processor do two unrelated things	New service — SRP applies to services too
Naming Convention for New Consumers
Keep names verb-or-role based, not generic:

Code
processor      ← enriches + persists (existing)
notifier       ← alerts/webhooks
archiver       ← cold storage
scorer         ← ML scoring pipeline
auditor        ← compliance/audit log writer
Avoid names like processor-2 or worker-new — name it after what it does to the event.

Practical Next Steps
Code
Short term (you're here)
  └─► Rename inference → ai-service
  └─► Add /chat and /prompt endpoints to ai-service
  └─► Keep processor focused on enrichment + Postgres writes

Medium term (as you add consumers)
  └─► Create notifier service (new consumer group, same topic)
  └─► Each new consumer is a standalone Docker Compose service
  └─► No changes to ingestor, no changes to processor
