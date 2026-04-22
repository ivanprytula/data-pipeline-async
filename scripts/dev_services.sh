#!/bin/bash
# Start all services needed for development and testing
# This includes both runtime services (db, redis, kafka, mongodb, jaeger)
# and test-specific services (db-test for PostgreSQL concurrent tests)

set -e

echo "🚀 Starting all development & test services..."
echo ""

# Start all core services + test profile
docker compose --profile test up -d db db-test redis redpanda mongodb jaeger

echo ""
echo "⏳ Waiting for services to be healthy..."
docker compose ps

echo ""
echo "✅ All services ready!"
echo ""
echo "Available services:"
echo "  PostgreSQL (main):   localhost:5432  (DATABASE_URL)"
echo "  PostgreSQL (test):   localhost:5433  (DATABASE_URL_TEST for concurrent tests)"
echo "  Redis:               localhost:6379"
echo "  Kafka (Redpanda):    localhost:9092"
echo "  MongoDB:             localhost:27017"
echo "  Jaeger UI:           http://localhost:16686"
echo ""
echo "Run tests with: uv run pytest tests/ -v"
echo "Stop services with: docker compose --profile test down"
