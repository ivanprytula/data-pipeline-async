#!/bin/bash
# scripts/compose.sh — Wrapper around docker-compose with environment profiles
# Usage: bash scripts/compose.sh dev up        (loose resources)
#        bash scripts/compose.sh prod-like up  (tight resources, test prod constraints)
#        bash scripts/compose.sh prod up       (production, use in CI/CD)

set -e

PROFILE="${1:-dev}"
shift || true

case "$PROFILE" in
  dev)
    echo "🚀 Development (loose resources for debugging)"
    docker compose -f docker-compose.yml -f docker-compose.dev.yml "$@"
    ;;
  prod-like)
    echo "📦 Production-like (tight resources — test for memory leaks, CPU exhaustion)"
    docker compose -f docker-compose.yml -f docker-compose.prod-like.yml "$@"
    ;;
  prod)
    echo "⚠️  Production (no overrides — use in CI/CD only)"
    docker compose -f docker-compose.yml "$@"
    ;;
  *)
    echo "❌ Unknown profile: $PROFILE"
    echo ""
    echo "Available profiles:"
    echo "  dev         — Loose resources for debugging (default)"
    echo "  prod-like   — Tight resources matching staging/prod (test locally)"
    echo "  prod        — Base config only (use in CI/CD)"
    echo ""
    echo "Usage: bash scripts/compose.sh <profile> <command>"
    echo "Examples:"
    echo "  bash scripts/compose.sh dev up"
    echo "  bash scripts/compose.sh prod-like up -d"
    echo "  bash scripts/compose.sh prod-like logs app"
    echo "  bash scripts/compose.sh prod up"
    exit 1
    ;;
esac
