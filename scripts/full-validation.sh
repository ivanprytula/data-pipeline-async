#!/usr/bin/env bash
# Full end-to-end validation: setup → quality checks → cache verification.
# Only run after merging the Redis cache layer.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

OVERALL_SUCCESS=0

echo "=== PHASE 1: Code Quality Checks (lint, format, tests) ==="
if bash "$SCRIPT_DIR/quality-checks.sh"; then
  echo "✓ Quality checks passed"
else
  echo "✗ Quality checks failed"
  OVERALL_SUCCESS=1
fi
echo ""

echo "=== PHASE 2: Redis Cache Layer Verification ==="
if bash "$SCRIPT_DIR/verify-cache.sh"; then
  echo "✓ Cache verification passed"
else
  echo "✗ Cache verification failed"
  OVERALL_SUCCESS=1
fi
echo ""

echo "=== VALIDATION COMPLETE ==="
if [ $OVERALL_SUCCESS -eq 0 ]; then
  echo "✓ All phases passed!"
  echo ""
  echo "Next steps:"
  echo "  • Commit your changes"
  echo "  • Push to remote"
  echo "  • Deploy to staging/production"
  exit 0
else
  echo "✗ One or more phases failed (see above)"
  exit 1
fi
