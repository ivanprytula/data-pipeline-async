#!/bin/bash
# scripts/ops/02-compose-profile.sh — Wrapper around docker-compose with environment profiles
# Usage: bash scripts/ops/02-compose-profile.sh dev up        (loose resources)
#        bash scripts/ops/02-compose-profile.sh prod-like up  (tight resources, test prod constraints)
#        bash scripts/ops/02-compose-profile.sh prod up       (production, use in CI/CD)

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
    echo "  prod-like   — Tight resources matching prod (test locally)"
    echo "  prod        — Base config only (use in CI/CD)"
    echo ""
    echo "Usage: bash scripts/ops/02-compose-profile.sh <profile> <command>"
    echo "Examples:"
    echo "  bash scripts/ops/02-compose-profile.sh dev up"
    echo "  bash scripts/ops/02-compose-profile.sh prod-like up -d"
    echo "  bash scripts/ops/02-compose-profile.sh prod-like logs app"
    echo "  bash scripts/ops/02-compose-profile.sh prod up"
    exit 1
    ;;
esac
