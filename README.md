# Data Zoo — Backend Platform (8 Phases)

Async FastAPI + SQLAlchemy 2.0 data pipeline. An 8-phase learning program covering
event streaming, scraping, CI/CD, AI/vectors, testing, database optimization, security,
and infrastructure as code.

---

## Quick Start

```bash
cp .env.example .env          # configure local values
uv sync                       # install dependencies
docker compose up -d db redis # start core services
uv run alembic upgrade head   # apply migrations
uv run uvicorn app.main:app --reload
open http://localhost:8000/docs
```

See [docs/setup/environment-setup.md](docs/setup/environment-setup.md) for full setup and
[docs/dev/commands.md](docs/dev/commands.md) for all dev commands.

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| API | FastAPI + Pydantic v2 |
| ORM | SQLAlchemy 2.0 async (`AsyncSession`, `mapped_column`) |
| DB | PostgreSQL 17 + Alembic migrations |
| Cache | Redis (fail-open; `fakeredis` in tests) |
| Streaming | Redpanda (Kafka-compatible) + aiokafka |
| Testing | pytest + aiosqlite (no Postgres required in CI) |
| Linting | Ruff + ty type checker |

---

## 8-Phase Overview

| Phase | Focus | Core Interview Q | Status |
|-------|-------|-----------------|--------|
| **1** | Event Streaming | Design real-time ETL for 1000+ events/sec | ✅ Done |
| **2** | Data Scraping | Design scraper for 100K URLs without ban | ✅ Done |
| **3** | AI + Vector DB | Design semantic search over 100K docs | ✅ Done |
| **4** | Resilience Patterns | Design circuit breaker + DLQ for failures | ✅ Done |
| **5** | CQRS + Analytics | Design read-optimized DB for 10M queries/day | 🚀 Active |
| **6** | Dashboard | Design server-rendered dashboard with SSE | ⏹️ Queued |
| **7** | Cloud IaC | Design multi-env Terraform (dev/staging/prod) | ✅ Done |
| **8** | Production Hardening | Design backup/chaos/observability strategy | ⏹️ Queued |

---

## Docs

### Setup & Tech Stack

| File | Purpose |
|------|---------|
| [docs/setup/environment-setup.md](docs/setup/environment-setup.md) | Local setup, `.env` config, Docker services |
| [docs/setup/pgvector-setup-guide.md](docs/setup/pgvector-setup-guide.md) | pgvector extension setup |
| [docs/setup/references.md](docs/setup/references.md) | External docs and learning resources |

### Daily Dev

| File | Purpose |
|------|---------|
| [docs/dev/commands.md](docs/dev/commands.md) | All dev, test, migration and load-test commands |
| [docs/dev/gotchas.md](docs/dev/gotchas.md) | Known pitfalls and non-obvious behaviours |

### System Design & Architecture

| File | Purpose |
|------|---------|
| [docs/cloud-deployment.md](docs/cloud-deployment.md) | Phase 7: AWS Fargate deployment, Terraform setup, secrets management |
| [docs/design/architecture.md](docs/design/architecture.md) | System overview and component diagram (Phases 0–7) |
| [docs/design/decisions.md](docs/design/decisions.md) | Key design decisions with rationale (infrastructure, databases, CI/CD) |
| [docs/design/be-learning-knowledge-base.md](docs/design/be-learning-knowledge-base.md) | Backend patterns knowledge base |
| [docs/design/adr/](docs/design/adr/) | Architecture Decision Records (ADR 001–003) |

### Pillars, Portfolio & Weekly Progress

| File | Purpose |
|------|---------|
| [docs/progress/MIDDLE-TIER-GRIND-OUTPUT-GUIDE.md](docs/progress/MIDDLE-TIER-GRIND-OUTPUT-GUIDE.md) | Interview prep system and output format guide |
| [docs/progress/phase-1-portfolio-item.md](docs/progress/phase-1-portfolio-item.md) | Phase 1 — Event streaming portfolio item |
| [docs/progress/phase-5-advanced-sql-cqrs.md](docs/progress/phase-5-advanced-sql-cqrs.md) | Phase 5 — Advanced SQL + CQRS reference |
| [docs/progress/pillar-1-core-backend.md](docs/progress/pillar-1-core-backend.md) | Pillar 1: Core backend patterns |
| [docs/progress/pillar-2-database.md](docs/progress/pillar-2-database.md) | Pillar 2: Database |
| [docs/progress/pillar-3-ops-infrastructure.md](docs/progress/pillar-3-ops-infrastructure.md) | Pillar 3: Ops & infrastructure |
| [docs/progress/pillar-4-observability.md](docs/progress/pillar-4-observability.md) | Pillar 4: Observability |
| [docs/progress/pillar-5-security.md](docs/progress/pillar-5-security.md) | Pillar 5: Security |
| [docs/progress/pillar-6-ai-llm.md](docs/progress/pillar-6-ai-llm.md) | Pillar 6: AI / LLM |
| [docs/progress/pillar-7-data-etl.md](docs/progress/pillar-7-data-etl.md) | Pillar 7: Data / ETL |
| [docs/progress/portfolio-phase-2-scrapers.md](docs/progress/portfolio-phase-2-scrapers.md) | Phase 2 portfolio item |
| [docs/progress/portfolio-phase-3-ai-gateway.md](docs/progress/portfolio-phase-3-ai-gateway.md) | Phase 3 portfolio item |
| [docs/progress/portfolio-phase-4-resilience.md](docs/progress/portfolio-phase-4-resilience.md) | Phase 4 portfolio item |
| [docs/progress/portfolio-phase-7-cloud-iac.md](docs/progress/portfolio-phase-7-cloud-iac.md) | Phase 7 portfolio item — Infrastructure as Code, Terraform, ECS Fargate |
| [docs/progress/weekly-progress-phase-2.md](docs/progress/weekly-progress-phase-2.md) | Weekly progress — Phase 2 |
| [docs/progress/weekly-progress-phase-3.md](docs/progress/weekly-progress-phase-3.md) | Weekly progress — Phase 3 |
| [docs/progress/weekly-progress-phase-4.md](docs/progress/weekly-progress-phase-4.md) | Weekly progress — Phase 4 |
| [docs/templates/](docs/templates/) | LinkedIn, portfolio, and commit templates |
