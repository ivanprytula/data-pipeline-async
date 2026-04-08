# Resource Management & Environment Profiles

Advanced resource constraint management for local development, testing, and production simulation.

---

## Overview

**Problem**: App works fine locally but fails in production under resource constraints (OOMKilled, throttled CPU).

**Solution**: Test locally under production-like resource constraints using `docker compose` environment profiles.

---

## Docker Compose Deployment Reference

Resources are defined in `deploy.resources` section of each service:

```yaml
services:
  app:
    deploy:
      # Restart policy (matches k8s restartPolicy)
      restart_policy:
        condition: on-failure      # Restart if container exits non-zero
        max_attempts: 5            # Max restart tries (0 = unlimited)
        delay: 5s                  # Delay before restart
        window: 120s               # Observation window for restart counting
      
      # Resource constraints (matches k8s requests/limits)
      resources:
        reservations:              # Minimum guaranteed (k8s requests)
          cpus: '0.25'             # 25% of one CPU core
          memory: '256M'           # 256 MB minimum
        limits:                    # Hard ceilings (k8s limits)
          cpus: '0.5'              # 50% of one CPU core
          memory: '512M'           # 512 MB maximum (OOMKilled if exceeded)
```

**Key distinction**:

- **`reservations`** = Kubernetes `requests` — Scheduler's minimum guarantee
- **`limits`** = Kubernetes `limits` — Hard ceiling (OOMKilled / CPU throttled if exceeded)

---

## K8s → Docker Compose Mapping

| Kubernetes | `docker compose` | Meaning |
|-----------|-----------------|---------|
| `requests.cpu: 500m` | `reservations.cpus: '0.5'` | Minimum guaranteed CPU (50% of core) |
| `limits.cpu: 1000m` | `limits.cpus: '1.0'` | Hard CPU limit |
| `requests.memory: 512Mi` | `reservations.memory: '512M'` | Minimum guaranteed memory |
| `limits.memory: 1Gi` | `limits.memory: '1G'` | Hard memory limit (OOMKilled if exceeded) |
| `restartPolicy: OnFailure` | `restart_policy.condition: on-failure` | Restart on crash |

---

## Environment Profiles

### Development (Loose Resources)

```bash
docker info | grep "Cgroup"

# Default — loose constraints for debugging
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Or use the helper script
bash scripts/compose.sh dev up
```

**Resource limits**:

- **DB**: 2 CPU, 2 GB memory — No pressure during development
- **App**: 2 CPU, 1 GB memory — Can grow during profiling/debugging

**When to use**:

- Local feature development
- Debugging with profilers (py-spy, Pyinstrument)
- First-time setup

---

### Production-Like (Tight Resources)

```bash
# Simulate production environment locally
docker compose -f docker-compose.yml -f docker-compose.prod-like.yml up

# Or use helper script
bash scripts/compose.sh prod-like up
```

**Resource limits**:

- **DB**: 1 CPU, 1 GB memory — Same as prod/staging
- **App**: 0.5 CPU, 512 MB memory — **Tight** (catches memory leaks)

**When to use**:

- Before committing code (catch memory leaks)
- Load testing (see if app saturates at expected throughput)
- Verifying graceful degradation under resource pressure

---

### Production (Base Config)

```bash
# Base configuration (no overrides)
docker compose -f docker-compose.yml up

# Or helper script
bash scripts/compose.sh prod up
```

**When to use**:

- CI/CD pipelines (GitHub Actions)
- Production deployments (after docker-compose is built)

---

## Helper Script: `bash scripts/compose.sh`

Wrapper that eliminates typing `-f` flags repeatedly:

```bash
# Development (default)
bash scripts/compose.sh dev up -d

# Production-like (test constraints)
bash scripts/compose.sh prod-like up -d

# Production (base config)
bash scripts/compose.sh prod up -d

# Any docker-compose command
bash scripts/compose.sh dev logs -f app
bash scripts/compose.sh prod-like ps
bash scripts/compose.sh prod down -v
```

---

## Monitor Resource Usage

### Real-Time Stats

```bash
# Watch CPU, memory, network usage
bash scripts/stats.sh

# Or native docker command
docker stats --no-stream
```

Output example:

```
CONTAINER ID     CPU %      MEM USAGE / LIMIT
abc123xyz        2.5%       185M / 512M        ← App using 36% of memory
def456uvw        5.2%       320M / 1G          ← DB using 32% of memory
```

### One-Time Snapshot

```bash
docker stats --no-stream --format "{{.Names}}: {{.CPUPerc}} / {{.MemUsage}}"
```

---

## Workflow: Testing Resource Constraints

### 1. Run Under Production Constraints

```bash
# Start stack with production-like limits
bash scripts/compose.sh prod-like up -d

# In another terminal, monitor
bash scripts/stats.sh
```

### 2. Run Load Test

```bash
# Create 1000 records (should not hit memory limit)
uv run pytest tests/test_performance.py -v -s

# Or run for 5+ minutes (detect memory leaks)
bash scripts/compose.sh prod-like exec app \
  uv run pytest tests/test_under_constraints.py::test_memory_leak_detection -v -s
```

### 3. Check Results

If app runs 5 minutes without OOMKilled → ✅ Pass
If memory keeps growing → ❌ Memory leak detected

```bash
# View container logs (includes OOMKilled if it happened)
docker compose logs app
```

### 4. Debug & Iterate

If memory leak found:

```bash
# Run with loose resources to debug
bash scripts/compose.sh dev up -d

# Profile with py-spy
docker compose exec app py-spy record -o profile.svg -- \
  python -m pytest tests/test_under_constraints.py -v
```

---

## Restart Policy Examples

### Always Restart (Production)

```yaml
deploy:
  restart_policy:
    condition: any         # Restart on any exit
    max_attempts: 0        # Unlimited retries
```

### Restart on Failure (Default)

```yaml
deploy:
  restart_policy:
    condition: on-failure  # Restart only if non-zero exit
    max_attempts: 5        # Try 5 times max
    delay: 5s              # Wait 5s before retry
```

### Never Restart (Testing)

```yaml
deploy:
  restart_policy:
    condition: none        # Manual restart only
```

---

## CI/CD Integration

### GitHub Actions

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Start stack (production constraints)
        run: docker compose -f docker-compose.yml -f docker-compose.prod-like.yml up -d
      
      - name: Run tests
        run: docker compose exec -T app uv run pytest tests/ -v
      
      - name: Check resource stats
        if: failure()
        run: docker stats --no-stream
      
      - name: Clean up
        if: always()
        run: docker compose down -v
```

---

## Troubleshooting

### "Exit code 137" or "OOMKilled"

Memory limit was hit. Either:

1. **Increase limit** (if legitimate use case)
2. **Find memory leak** (if unexpected)

Check logs:

```bash
docker compose logs app | grep -i "oom\|killed"
```

### "CPU throttled" (app slow)

CPU limit is too tight. Check:

```bash
docker stats  # Watch CPU% approaching 100%
```

Increase `limits.cpus`:

```yaml
limits:
  cpus: '1.0'  # Was 0.5, bumped to 1.0
```

### Command Not Found: `bash scripts/compose.sh`

Make script executable:

```bash
chmod +x scripts/compose.sh
bash scripts/compose.sh dev up
```

---

## Best Practices

1. **Always test under prod-like constraints before shipping**

   ```bash
   bash scripts/compose.sh prod-like up -d
   uv run pytest tests/test_performance.py -v
   ```

2. **Monitor during load testing**

   ```bash
   # Terminal 1
   bash scripts/compose.sh prod-like up -d
   
   # Terminal 2
   bash scripts/stats.sh
   
   # Terminal 3
   uv run pytest tests/test_performance.py::test_memory_leak_detection -v -s
   ```

3. **Set reasonable defaults in base config**
   - `requests` = typical steady-state usage
   - `limits` = 2x requests (headroom for spikes)

4. **Document why limits are what they are**

   ```yaml
   # App needs 256M baseline, allow up to 512M for spikes
   # If hitting limit, investigate app (memory leak) not infra
   requests: { memory: '256M' }
   limits: { memory: '512M' }
   ```

---

## Next Steps

- [ ] Run `bash scripts/compose.sh prod-like up` and monitor with `bash scripts/stats.sh`
- [ ] Load test under prod constraints: `pytest tests/test_performance.py -v`
- [ ] If app survives 5-min stress test → ✅ Resource-safe
- [ ] Use prod-like profile in CI/CD before shipping

---

**Reference**: [Docker Compose deploy specification](https://docs.docker.com/reference/compose-file/deploy/)
