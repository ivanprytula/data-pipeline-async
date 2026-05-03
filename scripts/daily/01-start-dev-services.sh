#!/bin/bash
# Start core development services.

set -e

echo "🚀 Starting development services..."
echo ""

docker compose up -d db redis redpanda mongodb jaeger

echo ""
echo "⏳ Waiting for services to be healthy..."
docker compose ps

echo ""
echo "✅ All services ready!"
echo ""
echo "Available services:"
echo "  PostgreSQL (main):   localhost:5432  (DATABASE_URL)"
echo "  PostgreSQL (tests):  auto-provisioned via testcontainers when needed"
echo "  Redis:               localhost:6379"
echo "  Kafka (Redpanda):    localhost:9092"
echo "  MongoDB:             localhost:27017"
echo "  Jaeger UI:           http://localhost:16686"
echo ""
echo "Run tests with: uv run pytest tests/ -v"
echo "Stop services with: docker compose down"
