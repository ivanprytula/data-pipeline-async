#!/usr/bin/env bash
set -euo pipefail

echo "==> Stopping any test profile services"
docker compose --profile test down || true

echo "==> Locating test volume (suffix: _pg_test_data)"
VOLUME_NAME=$(docker volume ls --format '{{.Name}}' | grep '_pg_test_data$' | head -n1 || true)

if [ -n "$VOLUME_NAME" ]; then
  echo "Found volume: $VOLUME_NAME — removing it"
  docker volume rm "$VOLUME_NAME"
else
  echo "No test volume found — nothing to remove"
fi

echo "==> Starting fresh db-test service"
docker compose --profile test up -d db-test

echo "==> Waiting for Postgres to accept connections"
until docker compose --profile test exec -T db-test pg_isready -U postgres >/dev/null 2>&1; do
  sleep 1
  echo "Waiting for postgres..."
done

echo "Test database is ready. Run your tests now."
