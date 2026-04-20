# data-pipeline-async — Project Copilot Context

AI memory and working notes for this project. Complements `project-config.yaml`.

---

## What This Project Is

**Purpose**: Teach distributed systems design to mid/senior engineers via reproducible,
locally-runnable Docker Compose scenarios. Every scenario is designed to _break_ under load and
_fix_ via a known architecture pattern.

**Learning Loop**: Baseline (unoptimized) → Breaking Point (k6 load test) → Fix (pattern applied)

**Domain so far**: E-commerce (orders, users, inventory)

---

## Active Scenarios

See `docs/` for scenario definitions and runnable examples. Add new scenarios under `docs/` and link any supporting code or scripts from the checklist.

---

## Stack (This Project)

| Layer        | Choice               | Why                                           |
| ------------ | -------------------- | --------------------------------------------- |
| Language     | Python 3.14          | Modern async, type hints, familiar            |
| Framework    | FastAPI + Uvicorn    | Async-native, Pydantic v2, OpenAPI free       |
| Database     | PostgreSQL 17        | Industry standard, rich features for teaching |
| ORM          | SQLAlchemy 2.0 async | asyncpg driver, connection pool control       |
| Cache        | Redis                | Scenario 2+ (not yet built)                   |
| Load Testing | k6 (JS)              | Readable scripts, Prometheus integration      |
| Monitoring   | Prometheus + Grafana | Visual proof of bottlenecks                   |
| Container    | Docker Compose       | Full local env, no cloud required             |
| Package Mgr  | uv                   | Fast, reproducible                            |
| Linter       | Ruff                 | Fast, replaces flake8 + isort + black         |
| Type Checker | ty                   | Astral's new checker (replaces mypy)          |

---

## Key Architecture Decisions

| Decision           | Choice                                                | Date       |
| ------------------ | ----------------------------------------------------- | ---------- |
| Container naming   | `scenario-{N}-{name}-{service}`                       | 2026-03-23 |
| Instruction split  | Design patterns extracted from python.instructions.md | 2026-03    |
| Global Copilot dir | `~/.copilot/` as source-of-truth for shared assets    | 2026-03-23 |
| Templates          | Language-agnostic in copilot-config.yaml              | 2026-03-23 |

---

## Daily AI Session Checklist

Start of session:

- [ ] Review `memories/repo/data-pipeline-async.md` for last known state
- [ ] Confirm active scenario / task
- [ ] Run `docker ps | grep scenario-` to see what's running
- [ ] Check for any failing tests or lint errors

End of session:

- [ ] Mark completed items in scenario checklist above
- [ ] Push any new/improved skills or instructions: `./scripts/migrate-to-global.sh`
- [ ] Update `memories/repo/data-pipeline-async.md` with new decisions

---

## Copilot Configuration Files

| File                              | Purpose                               |
| --------------------------------- | ------------------------------------- |
| `.github/copilot-instructions.md` | Main project instructions for Copilot |
| `.copilot/project-config.yaml`    | Stack, skills, conventions override   |
| `.copilot/README.md`              | This file — working context           |
| `~/.copilot/copilot-config.yaml`  | Global defaults + templates           |
| `~/.copilot/README.md`            | Global ecosystem guide                |
