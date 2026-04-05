#!/bin/bash
# scripts/stats.sh — Monitor container resource usage in real-time
# Usage: bash scripts/stats.sh

set -e

echo "📊 Container Resource Usage (press Ctrl+C to stop)"
echo ""
echo "Format: NAME | CPU% | MEM USAGE / LIMIT | NET I/O"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

docker stats \
  --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
  --no-trunc
