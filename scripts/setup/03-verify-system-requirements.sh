#!/usr/bin/env bash
set -euo pipefail

# ─── Configuration ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

# ─── Helper functions ─────────────────────────────────────────────────────────
check_command() {
    if command -v "$1" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1 ${RED}NOT FOUND${NC} (install: $2)"
        return 1
    fi
}

check_docker_compose() {
    if command -v docker-compose &>/dev/null; then
        echo -e "${GREEN}✓${NC} docker-compose (v1)"
        return 0
    elif docker compose version &>/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} docker compose (v2 - bundled with Docker)"
        return 0
    else
        echo -e "${RED}✗${NC} docker-compose ${RED}NOT FOUND${NC} (install: docker-compose)"
        return 1
    fi
}

check_command_warning() {
    if command -v "$1" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${YELLOW}⚠${NC} $1 not found (optional: $2)"
        return 1
    fi
}

# ─── Main ──────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "System Requirements Verification"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

FAILED=0

echo "Core Development Tools:"
check_command "docker" "docker" || ((FAILED++))
check_docker_compose || ((FAILED++))
check_command "python3" "python3.14" || ((FAILED++))
check_command "uv" "uv" || ((FAILED++))
check_command "curl" "curl" || ((FAILED++))

echo ""
echo "Database Backup/Restore:"
check_command "pg_dump" "postgresql" || ((FAILED++))
check_command "pg_restore" "postgresql" || ((FAILED++))
check_command "psql" "postgresql" || ((FAILED++))
check_command_warning "mongodump" "mongodb-tools" || true
check_command_warning "mongorestore" "mongodb-tools" || true

echo ""
echo "Chaos Testing (Optional but recommended):"
check_command_warning "nsenter" "util-linux" || true
check_command_warning "tc" "iproute2" || true

echo ""
echo "Optional Diagnostics:"
check_command_warning "jq" "jq" || true
check_command_warning "htop" "htop" || true

echo ""
echo "════════════════════════════════════════════════════════════════════════════"
echo "Version Information:"
echo "════════════════════════════════════════════════════════════════════════════"
echo ""

if command -v python3 &>/dev/null; then
    echo "Python:          $(python3 --version)"
fi

if command -v uv &>/dev/null; then
    echo "uv:              $(uv --version)"
fi

if command -v docker &>/dev/null; then
    echo "Docker:          $(docker --version)"
fi

if command -v docker-compose &>/dev/null; then
    echo "Docker Compose:  $(docker-compose --version)"
elif docker compose version &>/dev/null 2>&1; then
    echo "Docker Compose:  $(docker compose version)"
fi

if command -v pg_dump &>/dev/null; then
    echo "PostgreSQL:      $(pg_dump --version)"
fi

echo ""

if [[ "${FAILED}" -eq 0 ]]; then
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✓ All required packages installed! Ready for development.${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. cp .env.example .env"
    echo "  2. bash scripts/daily/01-start-dev-services.sh"
    echo "  3. uv run pytest tests/ -v"
    echo "  4. bash infra/scripts/backup.sh"
    exit 0
else
    echo -e "${RED}════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}✗ ${FAILED} required package(s) missing. See docs/setup/system-requirements.md${NC}"
    echo -e "${RED}════════════════════════════════════════════════════════════════════════════${NC}"
    exit 1
fi
