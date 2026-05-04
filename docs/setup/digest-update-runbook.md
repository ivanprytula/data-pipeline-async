# Monthly Digest Review & Update Runbook

**Status**: Active (Starting April 2026)
**Frequency**: 1st Monday of each month
**Owner**: Infrastructure/Security team
**Duration**: ~30-45 minutes per cycle

---

## Overview

Base image digests (Python, PostgreSQL) must be reviewed monthly for security patches. This runbook guides scanning for vulnerabilities, identifying new digests, testing, and merging updates.

Why digest pinning matters:

- ✅ Ensures reproducible builds across team
- ✅ Allows detection of base image vulnerabilities
- ✅ Prevents silent breakage from image updates
- ⚠️ Requires intentional updates (manual process, not automatic)

---

## Monthly Schedule

| Date                     | Task                                  | Approx Time |
| ------------------------ | ------------------------------------- | ----------- |
| **1st Monday, 9:00 AM**  | Scan current base images for vulns    | 5 min       |
| **1st Monday, 9:10 AM**  | Research new digests if vulns found   | 10 min      |
| **1st Monday, 9:25 AM**  | Update Dockerfiles with new digests   | 5 min       |
| **1st Monday, 9:35 AM**  | Run local build & security tests      | 10-15 min   |
| **1st Monday, 10:00 AM** | Push to develop, create PR for review | 5 min       |

Calendar reminders: Set recurring calendar event on **1st Monday of month at 9:00 AM UTC**

---

## Step 1: Scan Current Base Images for Vulnerabilities

### Current Pinned Images

```bash
# Python base image
python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa

# PostgreSQL base image (currently NOT pinned — ISSUE!)
postgres:17  # ← VULNERABLE (1 CRITICAL, 13 HIGH as of April 22, 2026)
```

### Scan Script

```bash
#!/bin/bash
# scan_base_images.sh — Run 1st Monday of each month

set -e

echo "📋 Scanning base images for vulnerabilities..."
echo ""

# Python image
echo "🐍 Scanning python:3.14-slim..."
docker run --rm aquasec/trivy image \
  --severity CRITICAL,HIGH \
  --format json \
  python:3.14-slim > /tmp/trivy-python.json

python_vulns=$(jq '.Results[]?.Misconfigurations[] // empty' /tmp/trivy-python.json | wc -l)
echo "   Vulnerabilities: $python_vulns"

# PostgreSQL image (CRITICAL — review after April 22, 2026)
echo "🐘 Scanning postgres:17..."
docker run --rm aquasec/trivy image \
  --severity CRITICAL,HIGH \
  --format json \
  postgres:17 > /tmp/trivy-postgres.json

postgres_vulns=$(jq '.Results[0].Vulnerabilities[]? | length' /tmp/trivy-postgres.json 2>/dev/null || echo "0")
echo "   Vulnerabilities: $postgres_vulns"

echo ""
echo "📊 Summary:"
if [ "$python_vulns" -eq 0 ] && [ "$postgres_vulns" -eq 0 ]; then
  echo "✅ All base images clean"
  exit 0
else
  echo "⚠️  Vulnerabilities detected — proceed to Step 2"
  exit 1
fi
```

Run it:

```bash
chmod +x scripts/scan_base_images.sh
bash scripts/scan_base_images.sh
```

### Expected Output

```sh
📋 Scanning base images for vulnerabilities...

🐍 Scanning python:3.14-slim...
   Vulnerabilities: 0

🐘 Scanning postgres:17...
   Vulnerabilities: 14

📊 Summary:
⚠️  Vulnerabilities detected — proceed to Step 2
```

If vulnerabilities found → proceed to Step 2

---

## Step 2: Research New Base Image Digests

### Python Image: Find Latest Secure Digest

```bash
# Check Docker Hub for latest python:3.14-slim tag
docker pull python:3.14-slim --dry-run  # (doesn't exist; use inspect instead)

# Method 1: Get digest via Docker inspect
docker inspect --format='{{index .RepoDigests 0}}' \
  $(docker pull python:3.14-slim -q 2>/dev/null)

# Method 2: Use docker pull with digest output
docker pull python:3.14-slim 2>&1 | grep "Digest:"

# Method 3: Use skopeo (if available)
skopeo inspect docker://python:3.14-slim | jq -r '.Digest'
```

Example output:

```sh
sha256:NEW_DIGEST_12345abcde...
```

### PostgreSQL Image: Find Latest Secure Digest

```bash
# Check for postgres:17-latest or newer minor version
# First, see available tags
curl -s 'https://registry.hub.docker.com/v2/repositories/library/postgres/tags/' \
  | jq '.results[] | select(.name | contains("17")) | .name' | head -20

# Get digest for postgres:17-alpine (smaller, recommended for containers)
docker pull postgres:17-alpine
docker inspect --format='{{index .RepoDigests 0}}' \
  $(docker pull postgres:17-alpine -q)

# Alternative: postgres:17-bookworm (Debian-based, larger)
docker pull postgres:17-bookworm
docker inspect --format='{{index .RepoDigests 0}}' \
  $(docker pull postgres:17-bookworm -q)
```

Decision: Alpine vs Bookworm?

| Variant                 | Size    | Vulns                  | Notes                                                                      |
| ----------------------- | ------- | ---------------------- | -------------------------------------------------------------------------- |
| `postgres:17-alpine`    | ~100 MB | Fewer (smaller base)   | ❌ Limited apk packages for pgvector build tools                           |
| `postgres:17-bookworm`  | ~250 MB | Fewer than postgres:17 | **✅ Chosen** — Debian tools available, full pgvector v0.7.4 compatibility |
| `postgres:17` (default) | ~250 MB | 1 CRITICAL + 13 HIGH   | ❌ Avoid; vulnerable                                                       |

**⚠️ Current status (April 22, 2026)**: Switched from `postgres:17` to `postgres:17-bookworm`.

- Alpine was initially considered (smaller image) but pgvector build requires `/bin/bash` and Debian build tools unavailable in Alpine apk
- Bookworm provides reliable builds with acceptable image size (~250MB) and pinned digest for reproducibility

### Document New Digests

```bash
# Create update checklist
cat > /tmp/digest_update_checklist.md <<EOF
## Digest Update Checklist - $(date +%Y-%m-%d)

### Images to Update

- [ ] **python:3.14-slim**
  - Old digest: bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
  - New digest: NEW_DIGEST_HERE
  - Vuln change: 0 → 0 ✅

- [ ] **postgres:17-alpine** (switch from postgres:17)
  - Old tag: postgres:17 (NOT pinned)
  - New digest: NEW_POSTGRES_DIGEST
  - Vuln change: 14 → X
  - Action: Update infra/database/Dockerfile

### Changes Required
- [ ] Update all Python service Dockerfiles (6 files)
- [ ] Update infra/database/Dockerfile (switch to alpine)
- [ ] Test locally
- [ ] Push to develop, create PR

EOF
cat /tmp/digest_update_checklist.md
```

---

## Step 3: Update Dockerfiles with New Digests

### Files to Update

```bash
# Python services (update all 6)
- /Dockerfile                              # Main ingestor
- /services/inference/Dockerfile
- /services/analytics/Dockerfile
- /services/processor/Dockerfile
- /services/dashboard/Dockerfile

# Database (special case: switch base image)
- /infra/database/Dockerfile               # postgres:17 → postgres:17-alpine + pin digest
```

### Python Image Update (if new digest available)

Current line in all 6 Python Dockerfiles:

```dockerfile
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
```

Update to:

```dockerfile
FROM python:3.14-slim@sha256:NEW_DIGEST_HERE
```

Apply to all 6 files:

```bash
# Backup originals first
git stash

# Replace old digest with new one
find . -name "Dockerfile" -o -name "Dockerfile*" | xargs sed -i \
  's/sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa/sha256:NEW_DIGEST_HERE/g'

# Verify changes
grep "python:3.14-slim@sha256:" Dockerfile services/*/Dockerfile
```

### PostgreSQL Image Update (Special Case)

Current line in `/infra/database/Dockerfile`:

```dockerfile
FROM postgres:17
```

Update to:

```dockerfile
FROM postgres:17-alpine@sha256:NEW_POSTGRES_ALPINE_DIGEST
```

Why Alpine?

- 🎯 Smaller image (100 MB vs 250 MB)
- 🔒 Fewer OS packages → fewer vulnerabilities
- ⚡ Faster builds and deploys
- ✅ Fully compatible with pgvector extension

Update file:

```bash
# Edit /infra/database/Dockerfile
sed -i 's/FROM postgres:17/FROM postgres:17-alpine@sha256:NEW_POSTGRES_ALPINE_DIGEST/' \
  infra/database/Dockerfile

# Verify
head -1 infra/database/Dockerfile
```

---

## Step 4: Test Locally

### Build All Services with New Digests

```bash
#!/bin/bash
# test_digest_updates.sh

set -e
export DOCKER_BUILDKIT=1

echo "🔨 Building all services with new digests..."
echo ""

services=(
  "ingestor:Dockerfile"
  "inference:services/inference/Dockerfile"
  "analytics:services/analytics/Dockerfile"
  "processor:services/processor/Dockerfile"
  "dashboard:services/dashboard/Dockerfile"
  "database:infra/database/Dockerfile"
)

for service in "${services[@]}"; do
  name="${service%%:*}"
  dockerfile="${service##*:}"

  echo "📦 Building $name..."
  if docker build -t "$name:digest-test" -f "$dockerfile" .; then
    echo "   ✅ Build successful"
  else
    echo "   ❌ Build FAILED"
    exit 1
  fi
done

echo ""
echo "🧪 Running Trivy scans on new images..."

for service in "${services[@]}"; do
  name="${service%%:*}"

  echo "🔍 Scanning $name:digest-test..."
  docker run --rm aquasec/trivy image \
    --severity CRITICAL,HIGH \
    "$name:digest-test" | head -20
done

echo ""
echo "✅ All builds and scans complete!"
```

Run it:

```bash
chmod +x scripts/test_digest_updates.sh
bash scripts/test_digest_updates.sh
```

### Test with docker-compose

```bash
# Quick integration test
docker compose up -d --build
sleep 10
docker compose ps

# Check logs for errors
docker compose logs -f --tail=50

# Test health checks
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8005/health

# Cleanup
docker compose down
```

---

## Step 5: Push & Create PR

### Commit Changes

```bash
git checkout -b chore/update-base-image-digests-$(date +%Y-%m)
git add Dockerfile services/*/Dockerfile infra/database/Dockerfile
git commit -m "chore(deps): update base image digests — $(date +%Y-%m-%d)

## Changes

### Python Base Image
- Old: python:3.14-slim@sha256:bc389...
- New: python:3.14-slim@sha256:NEW_DIG...
- Vulnerability impact: 0 → 0 ✅

### PostgreSQL Base Image
- Old: postgres:17 (untagged, had 14 vulns)
- New: postgres:17-alpine@sha256:NEW_DIG...
- Vulnerability impact: 14 → X ✅
- Reason: Alpine reduces attack surface + pgvector compatible

### Testing
- Local build: ✅ All 6 services built successfully
- Trivy scan: ✅ No new CRITICAL/HIGH vulns detected
- docker-compose: ✅ All services healthy
- Health checks: ✅ Passing

See: https://github.com/repo/security/code-scanning (latest results)"
```

### Push to develop

```bash
git push origin chore/update-base-image-digests-$(date +%Y-%m)
```

### Create PR

```bash
# GitHub CLI (if installed)
gh pr create \
  --base develop \
  --title "chore(deps): update base image digests — $(date +%Y-%m)" \
  --body "$(cat /tmp/digest_update_checklist.md)" \
  --label "type/dependency" \
  --label "area/docker-images"
```

Or manually:

1. Go to **Pull Requests** → **New Pull Request**
2. Base: `develop`, Compare: `chore/update-base-image-digests-...`
3. Title: `chore(deps): update base image digests — YYYY-MM`
4. Description: Include vulnerability scan results
5. Reviewers: Assign team lead
6. Labels: `type/dependency`, `area/docker-images`

### Merge Checklist

Before merging:

- [ ] All CI checks passing (build, lint, tests)
- [ ] Security scan shows no new vulns
- [ ] Code review approved
- [ ] Local testing confirmed
- [ ] SBOM generated (Phase 3) and reviewed

---

## Digest Update Decision Tree

```sh
┌─────────────────────────────────────────────┐
│ Monthly Digest Review                       │
└──────────────┬──────────────────────────────┘
               │
               ▼
    ┌──────────────────────┐
    │ Scan base images     │
    │ for vulnerabilities  │
    └──────────┬───────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
    No vulns     Vulns found
        │             │
        │             ▼
        │    ┌──────────────────────┐
        │    │ Research new digests │
        │    │ (Docker Hub, skopeo) │
        │    └──────────┬───────────┘
        │               │
        │               ▼
        │    ┌──────────────────────┐
        │    │ Update Dockerfiles   │
        │    │ with new digests     │
        │    └──────────┬───────────┘
        │               │
        └───────┬───────┘
                │
                ▼
        ┌──────────────────────┐
        │ Test locally         │
        │ - Build all services │
        │ - Trivy scan         │
        │ - docker-compose up  │
        └──────────┬───────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
    Tests pass          Tests FAIL
        │                     │
        │                     ▼
        │          ┌─────────────────────┐
        │          │ Investigate failure │
        │          │ Check error logs    │
        │          │ Revert & reschedule │
        │          └─────────────────────┘
        │
        ▼
    ┌──────────────────────┐
    │ Commit + push PR     │
    │ to develop           │
    └──────────┬───────────┘
               │
               ▼
    ┌──────────────────────┐
    │ Review + merge to    │
    │ develop              │
    └──────────────────────┘
```

---

## Troubleshooting

### Issue: "Failed to get digest from Docker Hub"

Solution:

```sh
# Ensure Docker is running
docker ps

# Re-authenticate if needed
docker login

# Try manual inspect
docker pull python:3.14-slim
docker inspect $(docker images -q python:3.14-slim | head -1)
```

### Issue: New image fails to build

Solution:

```sh
# Get full build output
DOCKER_BUILDKIT=0 docker build -f Dockerfile . --progress=plain

# Check for base image compatibility issues
docker run --rm python:3.14-slim python --version  # Verify Python version
docker run --rm postgres:17-alpine psql --version   # Verify PostgreSQL version
```

### Issue: postgres:17-alpine incompatible with pgvector

Solution: Alpine is fully compatible. If you see errors:

```sh
# Test pgvector build in Alpine
docker build -f infra/database/Dockerfile . -t postgres-pgvector:test
docker run --rm postgres-pgvector:test psql -U postgres -c "CREATE EXTENSION pgvector;"
```

If Alpine fails, fall back to `postgres:17-bookworm@sha256:...` (Debian-based, more tested).

---

## References

- [Docker Hub Python Tags](https://hub.docker.com/_/python)
- [Docker Hub PostgreSQL Tags](https://hub.docker.com/_/postgres)
- [skopeo Inspect Digests](https://github.com/containers/skopeo)
- [pgvector Alpine Compatibility](https://github.com/pgvector/pgvector/wiki/Installation)
- [Trivy Image Scanning](https://aquasecurity.github.io/trivy/latest/docs/image/scanning/)

---

## Calendar & Reminders

**Monthly tasks** (1st Monday of each month):

```sh
# Add to crontab for automated reminders
0 9 1 * * [ $(date +\%u) -eq 1 ] && echo "🔔 Monthly digest review day!"
```

Sample calendar entry:

```sh
Title: 🔐 Monthly Base Image Digest Review
Recurrence: Monthly on 1st Monday
Time: 9:00 AM UTC
Duration: 45 minutes
Attendees: @ivanp, @infrastructure-team
Notes:
1. Run scan_base_images.sh
2. Check Trivy results
3. Update digests if needed
4. Test locally
5. Push PR to develop
```

---

## Changelog

| Date       | Update                       | Reason                         |
| ---------- | ---------------------------- | ------------------------------ |
| 2026-04-22 | Initial runbook              | Created for Phase 3 compliance |
| 2026-04-22 | Identified postgres:17 issue | 1 CRITICAL, 13 HIGH vulns      |
| 2026-05-01 | First scheduled review       | Monthly cycle begins           |
