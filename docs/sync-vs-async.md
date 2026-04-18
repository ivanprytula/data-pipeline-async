# Sync vs Async — Historical Reference

> **Archived**: This content was extracted from the main README when the project
> moved to async-only. See [../README.md](../README.md) for the current async setup.

Two self-contained, production-shaped implementations of the same data-pipeline API.
Pick one (or study both side-by-side to understand the difference).

```text
week1_data_pipeline/
├── sync/   ← pip + requirements.txt + SQLAlchemy sync + psycopg2
└── async/  ← uv + pyproject.toml  + SQLAlchemy async + asyncpg
```

Both use **Python 3.14**, **FastAPI**, **Pydantic v2**, and **python-json-logger**.

---

## Sync vs Async — What Changes and Why

| Concern               | sync/                                     | async/                                    |
| --------------------- | ----------------------------------------- | ----------------------------------------- |
| Dep management        | `pip` + `requirements.txt`                | `uv` + `pyproject.toml`                   |
| DB driver             | `psycopg2-binary` (C extension, blocking) | `asyncpg` (pure async, fastest PG driver) |
| SQLAlchemy session    | `Session` (thread-local)                  | `AsyncSession` (coroutine-safe)           |
| Route handlers        | `def`                                     | `async def`                               |
| CRUD calls            | direct `session.commit()`                 | `await session.commit()`                  |
| Test fixtures         | `pytest` fixtures, `TestClient`           | `pytest-asyncio`, `AsyncClient` (httpx)   |
| In-proc test DB       | `sqlite:///:memory:`                      | `sqlite+aiosqlite:///:memory:`            |
| Dockerfile base image | `python:3.14-slim`                        | `python:3.14-slim` + uv layer             |

**When to choose async**: Any production service that handles concurrent I/O (database
queries, external HTTP calls). FastAPI is async-first; `async def` routes process
multiple requests concurrently on a single thread without blocking the event loop.

**When sync is fine**: Early prototypes, scripts, CLIs, or when your team is unfamiliar
with asyncio and the performance headroom permits it.

---

## Quick Start — sync (archived)

```bash
cd sync

# 1. Create venv and install deps
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run tests (SQLite in-memory — no Docker needed)
pytest tests/ -v

# 3. Start the full stack (FastAPI + PostgreSQL)
cp .env.example .env
docker compose up --build

# 4. Open API docs
open http://localhost:8000/docs
```
