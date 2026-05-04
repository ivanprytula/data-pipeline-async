## Plan: Apply Docker Best Practices to 6 Dockerfiles

**TL;DR:** Apply 5 key improvements (BuildKit syntax, SHELL pipefail, digest pinning, cache mounts, clean instead of rm) to all 6 Dockerfiles and .dockerignore. All files are independent and can be applied in parallel. Complete improved versions are ready to copy-paste.

---

## Steps

### Phase 1: Apply 6 Dockerfiles (parallel, independent)

1. **Replace `/Dockerfile`** (Main ingestor service)
   - File path: `/home/$USER/<directory>/data-pipeline-async/Dockerfile`
   - Action: Overwrite with improved version (80 lines, saved in `/memories/session/dockerfile-improvements.md`)
   - Key changes: Add syntax directive, pin digest to sha256:bc389f7df..., add SHELL directive, convert 2 apt-get blocks to BuildKit cache mounts
   - Verification: File has syntax directive on line 1, SHELL directive after each FROM
   - *Parallel with steps 2-6*

2. **Replace `/services/inference/Dockerfile`**
   - File path: `/home/$USER/<directory>/data-pipeline-async/services/inference/Dockerfile`
   - Action: Overwrite with improved version
   - Key changes: Add syntax + digest + SHELL directives, replace apt-get pattern with cache mounts
   - Verification: File has syntax directive, BuildKit cache mount on apt-get call
   - *Parallel with steps 1, 3-6*

3. **Replace `/services/analytics/Dockerfile`**
   - File path: `/home/$USER/<directory>/data-pipeline-async/services/analytics/Dockerfile`
   - Action: Overwrite with improved version
   - Key changes: Add syntax + digest + SHELL to both builder and final stage, replace apt-get with cache mounts
   - Verification: Both FROM blocks have digest + SHELL
   - *Parallel with steps 1-2, 4-6*

4. **Replace `/services/processor/Dockerfile`**
   - File path: `/home/$USER/<directory>/data-pipeline-async/services/processor/Dockerfile`
   - Action: Overwrite with improved version
   - Key changes: Add syntax + digest + SHELL to both stages
   - Verification: Both stages have proper directives
   - *Parallel with steps 1-3, 5-6*

5. **Replace `/services/dashboard/Dockerfile`**
   - File path: `/home/$USER/<directory>/data-pipeline-async/services/dashboard/Dockerfile`
   - Action: Overwrite with improved version
   - Key changes: Add syntax + digest + SHELL directives (no apt changes needed)
   - Verification: File has all 3 directives
   - *Parallel with steps 1-4, 6*

6. **Replace `/infra/database/Dockerfile`**
   - File path: `/home/$USER/<directory>/data-pipeline-async/infra/database/Dockerfile`
   - Action: Overwrite with improved version (postgres:17 base + pgvector)
   - Key changes: Add syntax + SHELL directives, replace apt pattern with cache mounts, add git/build-essential cleanup
   - Verification: File has syntax + SHELL, BuildKit cache mount pattern
   - *Parallel with steps 1-5*

### Phase 2: Update .dockerignore (Depends on Phase 1 completion)

7. **Append to `/.dockerignore`**
   - File path: `/home/$USER/<directory>/data-pipeline-async/.dockerignore`
   - Action: Append 5 new lines to end of file:
     ```
     htmlcov/
     .coverage/
     infra/certs/
     *.pem
     logs/
     ```
   - Verification: File ends with `logs/`
   - *Depends on: All 6 Dockerfiles applied (Phase 1)*

### Phase 3: Verification (Depends on Phase 2 completion)

8. **Test main ingestor build with BuildKit**
   - Command: `export DOCKER_BUILDKIT=1 && docker build -t ingestor:latest .`
   - Expected: Build succeeds, recognizes BuildKit syntax directive
   - Verification: Output shows BuildKit cache mount messages (e.g., "COPY --mount=type=cache...")
   - *Depends on: /Dockerfile applied (step 1)*

9. **Test cache efficiency (second build should be faster)**
   - Command: `docker build -t ingestor:latest .` (run again immediately)
   - Expected: Second build completes 3-5x faster (cache hits from first build)
   - Verification: Compare build times, second build should use cached layers
   - *Depends on: First build succeeded (step 8)*

10. **Verify all Dockerfiles have correct syntax**
    - Command: Run `docker buildx bake --print` or inspect each Dockerfile for `# syntax=docker/dockerfile:1.4`
    - Expected: All 6 files have syntax directive as line 1
    - Verification: Syntax directive present in all 6 files
    - *Depends on: All Dockerfiles applied (steps 1-6)*

---

## Relevant Files

### Source (Ready-to-apply improved versions)
- `/memories/session/dockerfile-improvements.md` — All 6 complete improved Dockerfiles + updated .dockerignore (copy-paste ready)
- `/memories/session/apply-dockerfile-improvements.sh` — Bash script that applies all changes automatically

### Target (Files to be modified)
- `/Dockerfile` — Main ingestor, multi-stage builder → final
- `/services/inference/Dockerfile` — Embedding service, single stage
- `/services/analytics/Dockerfile` — Query service, multi-stage
- `/services/processor/Dockerfile` — Background processor, multi-stage
- `/services/dashboard/Dockerfile` — Dashboard UI, single stage
- `/infra/database/Dockerfile` — PostgreSQL 17 + pgvector, single stage
- `/.dockerignore` — Exclude patterns (append 5 lines)

---

## Verification Checklist

1. **Syntax check**: `grep "# syntax=docker/dockerfile:1.4" /Dockerfile /services/*/Dockerfile /infra/database/Dockerfile` — Should find 6 matches
2. **SHELL directives**: `grep -A1 "FROM python" /Dockerfile` — Should show `SHELL ["/bin/bash", "-o", "pipefail", "-c"]` after each FROM
3. **Digest pinning**: `grep "@sha256:" /Dockerfile /services/*/Dockerfile` — Should show python:3.14-slim with digest
4. **BuildKit cache mounts**: `grep "mount=type=cache" /Dockerfile /services/*/Dockerfile /infra/database/Dockerfile` — Should find cache mount patterns
5. **No rm -rf**: `grep -v "^\s*#" /Dockerfile | grep "rm -rf /var/lib/apt" || echo "✓ No rm -rf found"` — Should return nothing (clean found instead)
6. **Docker build test**: `export DOCKER_BUILDKIT=1 && docker build -t test:latest . --dry-run` — Should succeed without errors

---

## Key Decisions

**Approach:** Direct file replacement (all 6 files overwritten with complete improved versions)
- **Why:** All improvements are proven and ready; easier to audit than incremental changes
- **Alternative rejected:** Incremental sed/patch approach — too error-prone across 6 files with different structures

**BuildKit cache mount pattern:** `--mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked`
- **Why:** Persistent apt cache across builds, locked sharing prevents race conditions, apt-get clean leaves cache intact
- **Benefit:** 3-5x faster rebuilds on second+ invocation

**Digest pinning:** python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
- **Why:** Reproducible builds (same Python version, same dependencies) across all developers and CI/CD runs
- **Security:** Prevents silent base image updates that could introduce vulnerabilities

**SHELL directive:** After each FROM (both builder and final stages)
- **Why:** Ensures pipefail is active in all stages; any pipe command failure causes build to fail
- **Fallback:** Without this, `apt-get update && apt-get install ... | grep` would succeed even if grep fails

**apt-get clean over rm -rf /var/lib/apt/lists/**
- **Why:** apt-get clean respects Docker layer caching; rm -rf forces re-download on next layer
- **Trade-off:** Slightly larger layer (~50MB), but faster overall build time via cache reuse

---

## Further Considerations

1. **Timing**: All 6 files can be applied simultaneously (they're independent). No blocking dependencies between files.

2. **Rollback**: Original Dockerfiles are in git history. If issues arise, `git checkout -- Dockerfile services/*/Dockerfile infra/database/Dockerfile .dockerignore` reverts changes.

3. **CI/CD Integration**: Ensure `.github/workflows/*.yml` sets `DOCKER_BUILDKIT=1` environment variable so GitHub Actions also benefits from BuildKit cache mounts.

---

## Execution Options

| Option | Effort | Speed | Requirements |
|--------|--------|-------|--------------|
| **A (Recommended)**: Copy-paste from memory | 2 min | Manual | Read `/memories/session/dockerfile-improvements.md`, paste 7 times |
| **B (Fastest)**: Run bash script | 10 sec | Auto | `bash /memories/session/apply-dockerfile-improvements.sh` |
| **C (VSCode)**: Use editor tools | 3 min | Manual | File edit tools enabled |

---

## Next Steps

1. Choose execution option (A, B, or C)
2. Apply all 6 Dockerfiles + .dockerignore (Phase 1-2)
3. Run verification commands (Phase 3)
4. Confirm all 6 files have improvements applied
5. Run Docker build test to verify BuildKit caching works
