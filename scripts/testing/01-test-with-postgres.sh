#!/usr/bin/env bash
# Run concurrent tests against PostgreSQL in Docker container.
#
# Usage: ./scripts/testing/01-test-with-postgres.sh
# Or:    ./scripts/testing/01-test-with-postgres.sh tests/integration/records/test_concurrency.py -v
#
# This script:
# 1. Starts PostgreSQL test container (if not running)
# 2. Waits for PostgreSQL to be ready
# 3. Runs pytest with DATABASE_URL_TEST pointing to the container
# 4. Cleans up if needed

set -e

# Cleanup function: always stop the test container on exit
cleanup() {
    echo "🛑 Stopping PostgreSQL test container..."
    docker compose --profile test down || echo "⚠️  Failed to stop test container"
}

trap cleanup EXIT

PORT=5433
HOST=localhost
USER=postgres
PASSWORD=postgres
DB=test_database

DB_URL="postgresql+asyncpg://${USER}:${PASSWORD}@${HOST}:${PORT}/${DB}"

echo "🐘 Starting PostgreSQL test database..."
docker compose --profile test up -d db-test

echo "⏳ Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker exec data-pipeline-db-test pg_isready -U $USER >/dev/null 2>&1; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ PostgreSQL failed to start after $max_attempts seconds"
    exit 1
fi

# Run pytest with PostgreSQL connection
echo ""
echo " Running tests with PostgreSQL..."
echo "   DATABASE_URL_TEST=$DB_URL"
echo ""

DATABASE_URL_TEST="$DB_URL" uv run pytest "${@:-.}" tests/integration/records/test_concurrency.py

echo ""
echo "✅ Tests complete!"
echo ""
echo "📝 To manually run with PostgreSQL:"
echo "   export DATABASE_URL_TEST='$DB_URL'"
echo "   pytest tests/integration/records/test_concurrency.py -v"
echo ""
echo "🛑 To stop the container:"
echo "   docker compose --profile test down"
