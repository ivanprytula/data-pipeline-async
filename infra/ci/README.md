# CI Image — Maintainer Quick Commands

This file documents common commands for maintainers to build, test, push, and pin the `data-pipeline-ci` image used by CI.

Replace `${OWNER}` with your GitHub organization or username when running commands locally.

Build locally (single-arch, load into Docker):

```bash
docker buildx build -f infra/ci/ci-base-image/Dockerfile \
 -t ghcr.io/${OWNER}/data-pipeline-ci:sha-$(git rev-parse --short HEAD) \
 --load .
```

Push to GHCR (requires GHCR auth / GITHUB_TOKEN):

```bash
docker push ghcr.io/${OWNER}/data-pipeline-ci:sha-$(git rev-parse --short HEAD)
```

Get the image digest to pin in workflows:

```bash
docker pull ghcr.io/${OWNER}/data-pipeline-ci:sha-$(git rev-parse --short HEAD)
docker inspect --format='{{index .RepoDigests 0}}' ghcr.io/${OWNER}/data-pipeline-ci:sha-$(git rev-parse --short HEAD)
# Result: ghcr.io/${OWNER}/data-pipeline-ci@sha256:<digest>
```

Quick local smoke test (run prechecks inside the image):

```bash
docker run --rm -v "$PWD":/work -w /work ghcr.io/${OWNER}/data-pipeline-ci:sha-<short_sha> \
 sh -c "uv run ruff check . && uv run ty check"
```

Pin the image in workflows (immutable):

```yaml
container:
 image: ghcr.io/${{ github.repository_owner }}/data-pipeline-ci@sha256:<digest>
```

Rollback options

- Update the workflow to reference the previous image digest and commit the change.
- (Less preferred) re-tag a previous image as `latest` in GHCR and update `:latest` in workflows.

Notes

- The repository builds/publishes the image via `.github/workflows/build-ci-image.yml`.
- Validate the image locally before pushing to GHCR.
- Keep `infra/ci/ci-base-image/Dockerfile` minimal and rebuild only when runtime deps change.

## Two Separate Images

**This image (CI toolbox)**: Ephemeral, reusable runtime for GitHub Actions jobs.

- Contains: Python 3.14, uv, build tools (ruff, pytest, ty, etc.), system deps.
- Does NOT contain: project code (mounted at runtime via `Checkout` action).
- Rebuilt only when `uv.lock`, `pyproject.toml`, or system deps change (rarely).
- Used by: prechecks, unit, integration, e2e, migrations, dependency-audit, docs-quality jobs.

**App image** (separate): Production package for services.

- Located: `Dockerfile` in repo root (or `infra/docker/app.Dockerfile` if refactored).
- Contains: FastAPI service code + optimized runtime (smaller base, no test/lint deps).
- Rebuilt on every code change.
- Purpose: Deploy to ECS/K8s, not run CI tools.

Why separate? CI image is reusable across builds; app image must be rebuilt per release.

## Commands

Replace `${OWNER}` with your GitHub organization or username when running commands locally.
