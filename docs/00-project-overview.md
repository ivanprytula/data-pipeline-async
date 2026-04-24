# Project Overview — Data Zoo Platform

> **Start here.** This document explains what this project is, why it exists, and how to navigate the documentation.

---

## What is Data Zoo?

Data Zoo is a **production-grade async data pipeline platform** built with modern Python, demonstrating how to design, build, test, deploy, and operate a **real-world event streaming and ingestion system** at scale.

This is a **learning-focused project**—every component choice, architecture decision, and operational pattern reflects lessons from distributed systems, performance optimization, and production reliability. The codebase is an **interview preparation resource**: code examples, decision rationale, and operational playbooks that teach scalable backend patterns.

### Core Mission

- **Learn by doing**: Build a complete system from REST API to Kubernetes deployment
- **Production patterns**: Every layer follows industry best practices
- **Interview-ready**: Design decisions and trade-offs documented throughout the codebase
- **Measurable outcomes**: Concrete performance metrics, test coverage, and production readiness checklists

---

## Hiring Audience Fast Path (Recruiters + Interviewers)

Use this when evaluating candidate fit quickly:

1. [CV](../CV.md) for role positioning and production impact history.
2. [Architecture Overview](04-architecture-overview.md) for system decomposition and trade-offs.
3. [Backend Concepts and Patterns](09-backend-concepts-and-patterns.md) for technical depth and reasoning style.
4. [Interview Prep](10-interview-prep-middle-plus.md) for communication quality in interview-like scenarios.

Expected takeaway: this repository is not a toy demo. It is a structured portfolio showing practical backend engineering decisions, reliability patterns, and evidence of production-oriented thinking.

---

## Pillar 6 Status: Security, Auth, and RBAC

Current state (implemented baseline):

- Basic user data model exists (`users` table + Alembic migration).
- RBAC role guards are implemented for session and JWT flows (`viewer`, `writer`, `admin`).
- Role-protected API operations are live for secure archive/delete and JWT-protected writes.
- Security headers are attached to all HTTP responses.
- Production startup includes fail-fast checks for weak default secrets.
- CI security scanning is active (`pip-audit` and Trivy image scans).

Next planned hardening:

- Move session state from in-memory to Redis-backed persistent store.
- Add persisted user auth endpoints (registration/login/logout/role management).
- Expand RBAC checks across additional API operations.

---

## Pillar 7 Status: Admin UI and User Workflows

Current state (implemented baseline):

- Dashboard admin page is live at `/admin` (HTMX + Jinja2).
- Worker health workflow is wired to background worker health API.
- Task lookup workflow is wired to task status API by task ID.
- Manual rerun workflow submits one-record background batches.
- Role-aware session bootstrap workflow is available from admin UI.
- Dashboard integration tests cover admin page and all admin partial workflows.

Next planned hardening:

- Add persisted user CRUD/auth endpoints in ingestor.
- Replace bootstrap-only session helper with real user management operations.
- Add audit/event views in admin UI for operational traceability.

---

## 8-Phase Roadmap

Data Zoo progresses through **8 phases**, each adding one architectural layer:

| Phase | Focus                | Status                 | Interview Q                                          |
| ----- | -------------------- | ---------------------- | ---------------------------------------------------- |
| **1** | Event Streaming      | ✅ Done                | Real-time ETL for 1000+ events/sec                   |
| **2** | Data Scraping        | ✅ Done                | Design scraper for 100K URLs without ban             |
| **3** | AI + Vector DB       | ✅ Done                | Semantic search over 100K docs                       |
| **4** | Resilience Patterns  | ✅ Done                | Circuit breaker + DLQ for failures                   |
| **5** | CQRS + Analytics     | 🚀 Active              | Read-optimized DB for 10M queries/day                |
| **6** | Dashboard            | ✅ Implemented baseline| Server-rendered dashboard with SSE + admin workflows |
| **7** | Cloud IaC            | ✅ Done                | Multi-env Terraform (dev/prod)                       |
| **8** | Production Hardening | ⏹️ Queued              | Backup/chaos/observability strategy                  |

---

## Tech Stack Summary

| Layer               | Technology                                                      |
| ------------------- | --------------------------------------------------------------- |
| **API**             | FastAPI + Pydantic v2                                           |
| **Database**        | PostgreSQL 17 + SQLAlchemy 2.0 (async)                          |
| **Cache**           | Redis                                                           |
| **Streaming**       | Redpanda (Kafka-compatible)                                     |
| **Background Jobs** | APScheduler + in-process worker queue                           |
| **Admin UI**        | HTMX + Jinja2 dashboard workflows                               |
| **Observability**   | Prometheus + OpenTelemetry + Sentry + structured JSON logging   |
| **Security/Auth**   | HTTP Basic (docs), v1 bearer/session auth, v2 JWT + RBAC guards |
| **Testing**         | pytest + aiosqlite (in-memory for fast unit tests)              |
| **CI/CD**           | GitHub Actions (split unit/integration workflows)               |
| **IaC**             | Terraform (AWS Fargate + managed services)                      |
| **Local Dev**       | Docker Compose + uv package manager                             |

---

## Documentation Navigation

This project is documented in **numbered reading order**. Start at **00** and progress:

### Quick Path (First-Time Setup)

1. **[01 — System Setup](01-system-setup.md)** — Install system packages and local dependencies
2. **[02 — First-Time Project Setup](02-first-time-setup.md)** — Initialize project, generate HTTPS certs, start services
3. **[03 — Daily Development](03-daily-development.md)** — Common commands for local development

### Deep Dive (Architecture & Decisions)

1. **[04 — Architecture Overview](04-architecture-overview.md)** — System design, components, phase-by-phase details
2. **[Cloud Deployment](cloud-deployment.md)** — Production deployment, Kubernetes, infrastructure guidance
3. **[11 — Online/Cloud Services and Accounts](11-online-cloud-services-and-accounts.md)** — Long-term services, ownership, and budget checklist
4. **[Dev Commands](dev/commands.md)** — Test and CI-related daily workflows

### Reference

1. **[Design Decisions](design/decisions.md)** — Key decisions with rationale across all layers
2. **[Knowledge Base](design/be-learning-knowledge-base.md)** — Patterns, anti-patterns, learning resources

---

## Quick Start (30 seconds)

Canonical quick-start commands live in **[README.md](../README.md)**.

For step-by-step setup and troubleshooting, follow:

1. **[01 — System Setup](01-system-setup.md)**
2. **[02 — First-Time Project Setup](02-first-time-setup.md)**
3. **[03 — Daily Development](03-daily-development.md)**

---

## Project Layout

Use the canonical structure summary in **[README.md](../README.md#project-layout)**.

For component-level architecture and data flow, see **[04 — Architecture Overview](04-architecture-overview.md)**.

---

## Why This Structure?

**Top-to-bottom organization**: Start with high-level concepts, progressively dive deeper into implementation details.

**No duplication**: Information lives in one place. Links connect related docs.

**Workflows in scripts**: Bash scripts capture repeatable workflows. Markdown documents explain the *why*, not the *how*.

**Numbered docs**: Reading order is explicit. `00` → `01` → `02` makes navigation clear.

---

## What's Next?

- **New to the project?** Start with **[01 — System Setup](01-system-setup.md)**
- **Setting up locally for first time?** Follow **[02 — First-Time Project Setup](02-first-time-setup.md)**
- **Want to understand the architecture?** Jump to **[04 — Architecture Overview](04-architecture-overview.md)**
- **Contributing code?** See **[03 — Daily Development](03-daily-development.md)** for workflow commands

---

## Key Resources

- **GitHub:** [github.com/ivanp/data-pipeline-async](https://github.com/ivanp/data-pipeline-async)
- **API Docs:** Automatically generated at `/api/docs` (Swagger UI) when server is running
- **Metrics Dashboard:** Prometheus at `http://localhost:9090` (if running locally)
- **Tracing:** Jaeger UI at `http://localhost:16686` (if running locally)
- **Error Tracking:** Sentry (when `SENTRY_ENABLED=true` and `SENTRY_DSN` configured)

---

## Contact & Contributing

This is a personal learning project. For issues, improvements, or feedback, open a GitHub issue.
