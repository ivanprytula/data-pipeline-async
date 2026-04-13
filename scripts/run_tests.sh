#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing uv (if missing)"
command -v uv >/dev/null 2>&1 || pip install uv

echo "==> Syncing dependencies"
uv sync

echo "==> Running tests (aiosqlite in-memory — no Postgres needed). Skipping e2e by default."
uv run pytest -q -m "not e2e" tests/

echo "==> Done. Now, you can start the app with Docker:"
echo "    docker compose up --build"
