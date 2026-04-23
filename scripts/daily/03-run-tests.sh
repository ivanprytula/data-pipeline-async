#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"

echo "==> Installing uv (if missing)"
command -v uv >/dev/null 2>&1 || pip install uv

echo "==> Syncing dependencies"
uv sync

case "$MODE" in
	all)
		echo "==> Running full test suite"
		uv run pytest tests/ -v
		;;
	unit)
		echo "==> Running unit tests only"
		uv run pytest -x -q -m "unit" --cov=ingestor --cov-report=term-missing --cov-report=html tests/
		;;
	integration)
		echo "==> Running integration tests only"
		uv run pytest -x -q -m "integration" tests/
		;;
	*)
		echo "Usage: bash scripts/daily/03-run-tests.sh [all|unit|integration]" >&2
		exit 1
		;;
esac

echo "==> Done. Now, you can start the app with Docker:"
echo "    docker compose up --build"
