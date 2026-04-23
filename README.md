# Data Zoo — Backend Platform

Production-grade async data pipeline in Python. Learn scalable backend patterns through a real codebase: event streaming, scraping, AI, resilience, observability, and cloud deployment.

**8-phase learning program**: Build a complete system from REST API to Kubernetes deployment, covering every layer of a production backend.

## For Recruiters and Technical Interviewers

If you have 10 minutes, use this evaluation path:

1. [CV](CV.md): Candidate scope, impact stories, role level.
2. [Architecture Overview](docs/04-architecture-overview.md): System thinking, design depth, trade-offs.
3. [Backend Concepts and Patterns](docs/09-backend-concepts-and-patterns.md): Technical reasoning quality.
4. [Interview Prep](docs/10-interview-prep-middle-plus.md): Communication clarity under interview-style questions.

### What This Repository Demonstrates

- Real backend production patterns: async I/O, resilience, idempotency, CQRS, observability.
- Measurable engineering outcomes: reliability improvements, latency optimization, throughput-oriented design.
- Engineering maturity: tests, CI/CD, documentation quality, and explicit design decisions (ADRs).
- Security baseline delivery: role-based auth guards, protected operations, response security headers, and CI vulnerability scans.
- Admin workflow baseline: HTMX/Jinja2 admin UI for job health, task lookup, manual reruns, and role-aware session bootstrap.
- Practical scope fit: strong middle/middle+ backend profile with realistic boundaries around platform depth.

### Evidence Map

| Capability                         | Evidence                                                                                                                                                                                             |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| System design and architecture     | [docs/04-architecture-overview.md](docs/04-architecture-overview.md), [docs/design/decisions.md](docs/design/decisions.md)                                                                           |
| Database and performance reasoning | [docs/09-backend-concepts-and-patterns.md](docs/09-backend-concepts-and-patterns.md), [docs/progress/phase-5-advanced-sql-cqrs.md](docs/progress/phase-5-advanced-sql-cqrs.md)                       |
| Reliability and resilience         | [docs/04-architecture-overview.md](docs/04-architecture-overview.md), [docs/progress/portfolio-phase-4-resilience.md](docs/progress/portfolio-phase-4-resilience.md)                                 |
| Security, auth, and RBAC           | [docs/04-architecture-overview.md](docs/04-architecture-overview.md), [docs/progress/pillar-5-security.md](docs/progress/pillar-5-security.md), [docs/progress/roadmap.md](docs/progress/roadmap.md) |
| Admin UI and user workflows        | [docs/04-architecture-overview.md](docs/04-architecture-overview.md), [docs/03-daily-development.md](docs/03-daily-development.md), [docs/progress/roadmap.md](docs/progress/roadmap.md)             |
| Communication quality              | [CV.md](CV.md), [docs/10-interview-prep-middle-plus.md](docs/10-interview-prep-middle-plus.md)                                                                                                       |
| Delivery workflow quality          | [docs/dev/commands.md](docs/dev/commands.md), [docs/cloud-deployment.md](docs/cloud-deployment.md), [docs/adr/README.md](docs/adr/README.md)                                                         |

---

## Quick Start (One Command)

```bash
bash scripts/setup/01-bootstrap-dev-environment.sh
```

This automatically:

- Installs `uv` (Python package manager)
- Syncs Python dependencies
- Generates local HTTPS certificates
- Starts all services (PostgreSQL, Redis, Kafka, etc.)
- Creates database schema

Then access:

- **API**: `https://localhost/api/docs` (Swagger UI)
- **Metrics**: `http://localhost:9090` (Prometheus)
- **Tracing**: `http://localhost:16686` (Jaeger)

---

## Documentation

📖 **Quick Navigation** (numbered for clarity):

### Table of Contents

- [Data Zoo — Backend Platform](#data-zoo--backend-platform)
  - [For Recruiters and Technical Interviewers](#for-recruiters-and-technical-interviewers)
    - [What This Repository Demonstrates](#what-this-repository-demonstrates)
    - [Evidence Map](#evidence-map)
  - [Quick Start (One Command)](#quick-start-one-command)
  - [Documentation](#documentation)
    - [Table of Contents](#table-of-contents)
    - [Core Learning Path (for developers)](#core-learning-path-for-developers)
    - [Job Search \& Career Path](#job-search--career-path)
    - [Additional Reference Docs](#additional-reference-docs)
  - [Tech Stack](#tech-stack)
  - [8-Phase Roadmap](#8-phase-roadmap)
  - [Project Layout](#project-layout)
    - [Architecture Records](#architecture-records)
    - [Pillars, Portfolio \& Weekly Progress](#pillars-portfolio--weekly-progress)

### Core Learning Path (for developers)

| Doc                                                                              | Purpose                                          |
| -------------------------------------------------------------------------------- | ------------------------------------------------ |
| **[00 — Project Overview](docs/00-project-overview.md)**                         | What this project is, how to navigate            |
| **[01 — System Setup](docs/01-system-setup.md)**                                 | Install system packages (5–10 min)               |
| **[02 — First-Time Setup](docs/02-first-time-setup.md)**                         | Initialize project locally                       |
| **[03 — Daily Development](docs/03-daily-development.md)**                       | Common workflows & commands                      |
| **[04 — Architecture](docs/04-architecture-overview.md)**                        | System design & components                       |
| **[09 — Backend Concepts & Patterns](docs/09-backend-concepts-and-patterns.md)** | Theory/mental models for strong middle engineers |

### Job Search & Career Path

| Doc                                                              | Purpose                                            |
| ---------------------------------------------------------------- | -------------------------------------------------- |
| **[CV.md](CV.md)**                                               | Recruiter-focused narrative + Data Zoo positioning |
| **[10 — Interview Prep](docs/10-interview-prep-middle-plus.md)** | Practical Q&A for middle/middle+ roles             |

### Additional Reference Docs

| Doc                                                                                     | Purpose                                                  |
| --------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **[Dev Commands](docs/dev/commands.md)**                                                | Day-to-day command reference                             |
| **[Cloud Deployment](docs/cloud-deployment.md)**                                        | Deployment architecture and operational guidance         |
| **[Online/Cloud Services and Accounts](docs/11-online-cloud-services-and-accounts.md)** | Long-term account, service, and cost ownership checklist |
| **[Design Decisions](docs/design/decisions.md)**                                        | Architectural decisions and trade-offs                   |
| **[Knowledge Base](docs/design/be-learning-knowledge-base.md)**                         | Backend learning patterns and references                 |
| **[ADR Index](docs/adr/README.md)**                                                     | Architecture Decision Records index                      |

---

## Tech Stack

| Layer               | Technology                                         |
| ------------------- | -------------------------------------------------- |
| **API**             | FastAPI + Pydantic v2                              |
| **Database**        | PostgreSQL 17 + SQLAlchemy 2.0 (async)             |
| **Cache**           | Redis                                              |
| **Streaming**       | Redpanda (Kafka)                                   |
| **Background Jobs** | APScheduler + in-process workers                   |
| **Observability**   | Prometheus + OpenTelemetry + Sentry + JSON logging |
| **Testing**         | pytest + aiosqlite                                 |
| **CI/CD**           | GitHub Actions                                     |
| **IaC**             | Terraform (AWS)                                    |

---

## 8-Phase Roadmap

| Phase | Focus           | Status  | Interview Q                                    |
| ----- | --------------- | ------- | ---------------------------------------------- |
| **1** | Event Streaming | ✅      | Real-time ETL for 1000+ events/sec             |
| **2** | Data Scraping   | ✅      | Scraper for 100K URLs without ban              |
| **3** | AI + Vectors    | ✅      | Semantic search over 100K docs                 |
| **4** | Resilience      | ✅      | Circuit breaker + DLQ                          |
| **5** | CQRS            | 🚀      | Read-optimized DB for 10M queries/day          |
| **6** | Dashboard       | ✅      | Server-rendered SSE dashboard + admin workflows|
| **7** | Cloud IaC       | ✅      | Multi-env Terraform                            |
| **8** | Hardening       | ⏹️      | Backup/chaos/observability                     |

---

## Project Layout

```text
ingestor/              # Main application
docs/                  # Documentation (canonical docs + references)
scripts/               # Automation & workflows
tests/                 # Test suite (unit + integration)
infra/                 # Infrastructure-as-Code (Terraform)
docker-compose.yml     # Local dev services
pyproject.toml         # Python dependencies
```

### Architecture Records

- [ADR Index](docs/adr/README.md)
- [Legacy ADR Folder](docs/design/adr/)

### Pillars, Portfolio & Weekly Progress

| File                                                                                                 | Purpose                                                                 |
| ---------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| [docs/progress/MIDDLE-TIER-GRIND-OUTPUT-GUIDE.md](docs/progress/MIDDLE-TIER-GRIND-OUTPUT-GUIDE.md)   | Interview prep system and output format guide                           |
| [docs/progress/phase-1-portfolio-item.md](docs/progress/phase-1-portfolio-item.md)                   | Phase 1 — Event streaming portfolio item                                |
| [docs/progress/phase-5-advanced-sql-cqrs.md](docs/progress/phase-5-advanced-sql-cqrs.md)             | Phase 5 — Advanced SQL + CQRS reference                                 |
| [docs/progress/pillar-1-core-backend.md](docs/progress/pillar-1-core-backend.md)                     | Pillar 1: Core backend patterns                                         |
| [docs/progress/pillar-2-database.md](docs/progress/pillar-2-database.md)                             | Pillar 2: Database                                                      |
| [docs/progress/pillar-3-ops-infrastructure.md](docs/progress/pillar-3-ops-infrastructure.md)         | Pillar 3: Ops & infrastructure                                          |
| [docs/progress/pillar-4-observability.md](docs/progress/pillar-4-observability.md)                   | Pillar 4: Observability                                                 |
| [docs/progress/pillar-5-security.md](docs/progress/pillar-5-security.md)                             | Pillar 5: Security                                                      |
| [docs/progress/pillar-6-ai-llm.md](docs/progress/pillar-6-ai-llm.md)                                 | Pillar 6: AI / LLM                                                      |
| [docs/progress/pillar-7-data-etl.md](docs/progress/pillar-7-data-etl.md)                             | Pillar 7: Data / ETL                                                    |
| [docs/progress/pillar-8-notifications-emailing.md](docs/progress/pillar-8-notifications-emailing.md) | Pillar 8: Notifications / Emailing                                      |
| [docs/progress/portfolio-phase-2-scrapers.md](docs/progress/portfolio-phase-2-scrapers.md)           | Phase 2 portfolio item                                                  |
| [docs/progress/portfolio-phase-3-ai-gateway.md](docs/progress/portfolio-phase-3-ai-gateway.md)       | Phase 3 portfolio item                                                  |
| [docs/progress/portfolio-phase-4-resilience.md](docs/progress/portfolio-phase-4-resilience.md)       | Phase 4 portfolio item                                                  |
| [docs/progress/portfolio-phase-7-cloud-iac.md](docs/progress/portfolio-phase-7-cloud-iac.md)         | Phase 7 portfolio item — Infrastructure as Code, Terraform, ECS Fargate |
| [docs/progress/weekly-progress-phase-2.md](docs/progress/weekly-progress-phase-2.md)                 | Weekly progress — Phase 2                                               |
| [docs/progress/weekly-progress-phase-3.md](docs/progress/weekly-progress-phase-3.md)                 | Weekly progress — Phase 3                                               |
| [docs/progress/weekly-progress-phase-4.md](docs/progress/weekly-progress-phase-4.md)                 | Weekly progress — Phase 4                                               |
| [docs/templates/](docs/templates/)                                                                   | LinkedIn, portfolio, and commit templates                               |
