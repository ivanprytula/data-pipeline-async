#!/usr/bin/env bash
# Run from async/ directory
set -euo pipefail

echo "==> Installing uv (if missing)"
command -v uv >/dev/null 2>&1 || pip install uv

echo "==> Syncing dependencies"
uv sync

echo "==> Running tests (aiosqlite in-memory — no Postgres needed)"
uv run pytest tests/ -v

echo "==> Done. Start the app with Docker:"
echo "    docker compose up --build"
