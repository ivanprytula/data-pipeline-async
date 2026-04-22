#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing uv (if missing)"
command -v uv >/dev/null 2>&1 || pip install uv

echo "==> Syncing dependencies"
uv sync

echo "==> Running tests (aiosqlite in-memory — no Postgres needed). Skipping e2e by default."
# fast unit tests first (run serially to avoid DB migration races), then slower integration tests
uv run pytest -x -q -m "unit" --cov=ingestor --cov-report=term-missing --cov-report=html tests/
# uv run pytest -x -q -m "integration" --cov=. --cov-report=term-missing --cov-report=html tests/

echo "==> Done. Now, you can start the app with Docker:"
echo "    docker compose up --build"
