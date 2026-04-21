# System Requirements & Package Installation

This document lists all system-level packages required for **setup**, **daily development**, **database operations**, and **chaos testing**. Install these before running Data Zoo locally to avoid runtime surprises.

---

## Quick Install (macOS)

```bash
brew install postgresql redis mongodb-database-tools docker util-linux iproute2
```

## Quick Install (Ubuntu/Debian)

```bash
sudo apt-get install -y postgresql-client redis-tools mongodb-tools util-linux iproute2 docker.io docker-compose
```

## Quick Install (Fedora/RHEL)

```bash
sudo dnf install -y postgresql-contrib redis-tools mongodb-database-tools util-linux iproute2-utils docker docker-compose
```

---

## System Packages by Category

### Required for All Developers

| Package | macOS | Ubuntu/Debian | Fedora/RHEL | Purpose |
|---------|-------|---------------|------------|---------|
| **mkcert** | `mkcert` | `mkcert` | `mkcert` | Generate locally-trusted HTTPS certificates for local dev |
| **Docker** | `docker` or Docker Desktop | `docker.io` | `docker` | Container orchestration for all services |
| **Docker Compose** | incl. in Docker Desktop | `docker-compose` | `docker-compose` | Multi-service orchestration |
| **PostgreSQL Client** | `postgresql` | `postgresql-client` | `postgresql-libs` | `pg_dump`, `pg_restore`, `psql` (DB backup/restore/queries) |
| **Redis Tools** | `redis` | `redis-tools` | `redis` | `redis-cli` (cache inspection, cluster management) |
| **Python 3.14+** | `python@3.14` | `python3.14` | `python3.14` | Runtime for application |
| **uv** | `uv` | `uv` | `uv` | Fast Python package manager (local dev) |

### Required for Backup/Restore Operations

| Package | macOS | Ubuntu/Debian | Fedora/RHEL | Purpose | When Used |
|---------|-------|---------------|------------|---------|-----------|
| **PostgreSQL Client Tools** | `postgresql` | `postgresql-client` | `postgresql-libs` | `pg_dump`, `pg_restore` | [backup.sh](../infra/scripts/backup.sh), [restore.sh](../infra/scripts/restore.sh) |
| **MongoDB Tools** | `mongodb-database-tools` | `mongodb-tools` | `mongodb-tools` | `mongodump`, `mongorestore` | [backup.sh](../infra/scripts/backup.sh), [restore.sh](../infra/scripts/restore.sh) |
| **Gzip** | built-in | built-in | built-in | `gzip`, `zcat` | Backup compression (automatic) |

**Installation:**

**macOS:**

```bash
brew install postgresql mongodb-database-tools
```

**Ubuntu/Debian:**

```bash
sudo apt-get install -y postgresql-client mongodb-tools
```

**Fedora/RHEL:**

```bash
sudo dnf install -y postgresql-contrib mongodb-tools
```

### Required for Chaos Testing (`chaos.sh`)

| Package | macOS | Ubuntu/Debian | Fedora/RHEL | Purpose | When Used |
|---------|-------|---------------|------------|---------|-----------|
| **util-linux** | `util-linux` | `util-linux` | `util-linux` | `nsenter` (enter container network ns) | [chaos.sh](../infra/scripts/chaos.sh) network scenarios |
| **iproute2** | `iproute2` | `iproute2` | `iproute2-utils` | `tc` (traffic control, latency/packet loss) | [chaos.sh](../infra/scripts/chaos.sh) network chaos |

**Note:** `tc` is only used when chaos containers have `iproute2` installed. The chaos script will warn and fall back to graceful degradation if unavailable.

**Installation:**

**macOS:**

```bash
brew install util-linux iproute2
```

**Ubuntu/Debian:**

```bash
sudo apt-get install -y util-linux iproute2
```

**Fedora/RHEL:**

```bash
sudo dnf install -y util-linux iproute2-utils
```

### Optional: Performance & Debugging

| Package | macOS | Ubuntu/Debian | Fedora/RHEL | Purpose |
|---------|-------|---------------|------------|---------|
| **htop** | `htop` | `htop` | `htop` | System resource monitoring |
| **watch** | `watch` (GNU) | built-in | built-in | Command output polling (e.g., `watch 'docker ps'`) |
| **jq** | `jq` | `jq` | `jq` | JSON parsing (log inspection) |
| **curl** | built-in | built-in | built-in | HTTP testing (`curl http://localhost:8000/health`) |

---

## Platform-Specific Installation

### macOS (with Homebrew)

```bash
# Core development
brew install python@3.14 uv postgresql redis docker mkcert

# Database tools
brew install mongodb-database-tools

# Chaos testing & advanced
brew install util-linux iproute2

# Optional diagnostics
brew install htop jq watch
```

**Verify installation:**

```bash
pg_dump --version
redis-cli --version
mongodump --version
nsenter --version
tc --version
python3 --version
uv --version
docker --version
docker-compose --version
```

### Ubuntu/Debian 22.04+ (apt)

```bash
sudo apt-get update

# Core development
sudo apt-get install -y python3.14 python3.14-dev python3.14-venv curl git
sudo apt-get install -y postgresql-client redis-tools docker.io docker-compose mkcert libnss3-tools

# Python package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Database tools
sudo apt-get install -y mongodb-tools

# Chaos testing & advanced
sudo apt-get install -y util-linux iproute2

# Optional diagnostics
sudo apt-get install -y htop jq

# Enable Docker without sudo
sudo usermod -aG docker $USER
newgrp docker
```

**Verify installation:**

```bash
pg_dump --version
redis-cli --version
mongodump --version
nsenter --version
tc --version
python3 --version
~/.local/bin/uv --version
docker --version
docker-compose --version
```

### Fedora/RHEL 38+ (dnf)

```bash
sudo dnf update

# Core development
sudo dnf install -y python3.14 python3.14-devel curl git
sudo dnf install -y docker docker-compose postgresql mkcert nss-tools

# Python package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Database tools
sudo dnf install -y mongodb-tools redis

# Chaos testing & advanced
sudo dnf install -y util-linux iproute2-utils

# Optional diagnostics
sudo dnf install -y htop jq

# Enable Docker without sudo
sudo usermod -aG docker $USER
newgrp docker
```

**Verify installation:**

```bash
pg_dump --version
redis-cli --version
mongodump --version
nsenter --version
tc --version
python3 --version
~/.local/bin/uv --version
docker --version
docker-compose --version
```

---

## Script-by-Script Package Requirements

### `infra/scripts/backup.sh`

**PostgreSQL backup to file:**

```bash
# Required packages
pg_dump              # from: postgresql (macOS: postgresql, Ubuntu: postgresql-client)
gzip                 # built-in (all platforms)

# Optional (gracefully skipped if missing)
mongodump            # from: mongodb-tools (for MongoDB backup)
```

**Usage:**

```bash
bash infra/scripts/backup.sh
# Output: backups/postgres/pg_data_pipeline_YYYYMMDD_HHMMSS.sql.gz
#         backups/mongodb/mongo_data_zoo_YYYYMMDD_HHMMSS.archive.gz
```

### `infra/scripts/restore.sh`

**PostgreSQL restore from file:**

```bash
# Required packages
pg_restore           # from: postgresql (macOS: postgresql, Ubuntu: postgresql-client)
psql                 # from: postgresql
gzip / zcat          # built-in

# Optional (gracefully skipped if missing)
mongorestore         # from: mongodb-tools (for MongoDB restore)
```

**Usage:**

```bash
bash infra/scripts/restore.sh postgres backups/postgres/pg_data_pipeline_*.sql.gz
bash infra/scripts/restore.sh mongodb backups/mongodb/mongo_data_zoo_*.archive.gz
```

### `infra/scripts/chaos.sh`

**Service kill & network chaos:**

```bash
# Required packages
docker               # all scenarios
util-linux (nsenter) # network chaos scenarios
iproute2 / tc        # network latency/packet loss scenarios

# Optional (gracefully skipped if missing)
iproute2 in containers  # tc in container network namespace
```

**Usage:**

```bash
bash infra/scripts/chaos.sh kill              # kill random service
bash infra/scripts/chaos.sh network           # network latency + packet loss
bash infra/scripts/chaos.sh db                # PostgreSQL blackout
bash infra/scripts/chaos.sh kafka             # Redpanda outage
bash infra/scripts/chaos.sh gauntlet          # run all scenarios sequentially
```

---

## Verification Checklist

After installation, run the automated verification script:

```bash
bash scripts/verify-requirements.sh
```

Or manually verify all required tools are present:

```bash
#!/usr/bin/env bash
set -e

echo "✓ Checking system requirements..."

# Core
command -v docker           &>/dev/null || echo "❌ docker not found"
command -v docker-compose   &>/dev/null || echo "❌ docker-compose not found"
command -v python3          &>/dev/null || echo "❌ python3 not found"
command -v uv               &>/dev/null || echo "❌ uv not found"
command -v curl             &>/dev/null || echo "❌ curl not found"
command -v mkcert           &>/dev/null || echo "❌ mkcert not found (for HTTPS)"

# Database backup/restore
command -v pg_dump          &>/dev/null || echo "❌ pg_dump not found (install: postgresql)"
command -v pg_restore       &>/dev/null || echo "❌ pg_restore not found (install: postgresql)"
command -v mongodump        &>/dev/null || echo "⚠ mongodump not found (optional: mongodb-tools)"
command -v mongorestore     &>/dev/null || echo "⚠ mongorestore not found (optional: mongodb-tools)"

# Chaos testing
command -v nsenter          &>/dev/null || echo "⚠ nsenter not found (install: util-linux)"
command -v tc               &>/dev/null || echo "⚠ tc not found (install: iproute2)"

echo ""
echo "Verifications:"
python3 --version
docker --version
docker-compose --version
pg_dump --version 2>&1 | head -1
echo ""
echo "All checks passed! Ready for development."
```

Save as `scripts/verify-requirements.sh` and run:

```bash
bash scripts/verify-requirements.sh
```

---

## Troubleshooting

### PostgreSQL client not found

**Error:** `pg_dump: command not found`

**Solution:**

- **macOS:** `brew install postgresql`
- **Ubuntu:** `sudo apt-get install postgresql-client`
- **Fedora:** `sudo dnf install postgresql`

### MongoDB tools not found

**Error:** `mongodump: command not found` or `mongorestore: command not found`

**Solution:**

- **macOS:** `brew install mongodb-database-tools`
- **Ubuntu:** `sudo apt-get install mongodb-tools`
- **Fedora:** `sudo dnf install mongodb-tools`

### `nsenter` or `tc` not found (chaos testing)

**Error:** `nsenter: command not found` or `tc: not found`

**These are optional** — the chaos script will gracefully degrade. To enable network chaos:

- **macOS:** `brew install util-linux iproute2`
- **Ubuntu:** `sudo apt-get install util-linux iproute2`
- **Fedora:** `sudo dnf install util-linux iproute2-utils`

### Docker permission denied

**Error:** `docker: permission denied while trying to connect to the Docker daemon`

**Solution (Linux only):**

```bash
sudo usermod -aG docker $USER
newgrp docker
docker ps  # should work now
```

---

## Container Image Sizes

These images are pulled when you first run `docker compose up`:

| Service | Image | Size | Installed Packages |
|---------|-------|------|-------------------|
| PostgreSQL | `postgres:17-alpine` | ~153MB | pg_dump, pg_restore (built-in) |
| Redis | `redis:7-alpine` | ~40MB | redis-cli (built-in) |
| MongoDB | `mongodb:7` | ~700MB | mongodump, mongorestore (built-in) |
| Redpanda | `redpanda/redpanda:latest` | ~1.2GB | Kafka-compatible broker |
| Nginx | `nginx:1.27-alpine` | ~42MB | Reverse proxy, static files |
| Prometheus | `prom/prometheus:v2.52.0` | ~300MB | Metrics scraping, alerting |
| Grafana | `grafana/grafana:10.4.0` | ~300MB | Dashboard, visualization |

**Total local development footprint:** ~2.8GB (first download only, reused for subsequent runs)

---

## CI/CD (GitHub Actions)

**GitHub Actions runners** (Ubuntu 22.04) come pre-installed with:

- PostgreSQL client tools ✓
- Docker ✓
- Python 3.8–3.13 ✓

**No additional setup required for CI.** Tests run in containers with their own dependencies.

---

## Next Steps

1. **Install all packages** using the quick install commands above for your platform
2. **Verify installation** with `scripts/verify-requirements.sh`
3. **Start local environment** with `bash scripts/dev-services.sh`
4. **Try backup/restore** with `bash infra/scripts/backup.sh` and `bash infra/scripts/restore.sh`
5. **Try chaos testing** with `bash infra/scripts/chaos.sh gauntlet`

See [docs/setup/environment-setup.md](environment-setup.md) for `.env` configuration.
See [docs/dev/commands.md](../dev/commands.md) for all daily development commands.
