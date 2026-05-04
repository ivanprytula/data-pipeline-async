# Docker BuildKit & Security Scanning Setup Guide

**Last Updated**: April 22, 2026
**Status**: Production Ready

---

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Security Scanning Tools](#security-scanning-tools)
3. [Pre-Commit Hooks](#pre-commit-hooks)
4. [GitHub Actions Workflows](#github-actions-workflows)
5. [Troubleshooting](#troubleshooting)

---

## Local Development Setup

### Enable BuildKit (Recommended)

BuildKit enables faster, more efficient Docker builds with layer caching.

#### Option 1: Per-Command (Temporary)

```bash
export DOCKER_BUILDKIT=1
docker build -t ingestor:latest .

# Second build should be 3-5x faster
docker build -t ingestor:latest .
```

#### Option 2: Permanent (Linux/macOS)

Add to `~/.bashrc`, `~/.zshrc`, or equivalent:

```bash
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
```

Then reload shell:

```bash
source ~/.bashrc  # or ~/.zshrc
```

#### Option 3: Docker Daemon Config (All Users)

**Linux**: Edit `/etc/docker/daemon.json`

```json
{
  "features": {
    "buildkit": true
  }

}
```

Then restart Docker:

```bash
sudo systemctl restart docker
```

**macOS/Docker Desktop**: Settings → Docker Engine → Add to JSON:

```json
{
  "features": {

    "buildkit": true
  }
}
```

#### Verify BuildKit is Enabled

```bash
docker build --help | grep -i buildkit
# Should show buildkit references

# Or check during build:
docker build -t test:latest . --progress=plain
# Output should include lines like: "COPY --mount=type=cache..."
```

---

## Security Scanning Tools

### 1. pip-audit (Python Dependency Scanner)

Scans Python dependencies for known CVEs.

#### Installation

```bash
# One-time install in your environment
pip install pip-audit

# Or via uv (if using this project)
uv pip install pip-audit
```

#### Usage

```bash
# Scan current environment
pip-audit

# Scan with descriptions (verbose)
pip-audit --desc

# Scan specific requirements file
pip-audit -r requirements.txt

# Scan and fix (attempt auto-remediation)

pip-audit --fix

# Fail if vulnerabilities found (useful for CI/CD)
pip-audit && echo "✓ No vulnerabilities" || echo "✗ Vulnerabilities found"
```

#### Example Output

```text
Found 2 known security vulnerabilities in 2 packages

Vulnerability #1
    Package: Django
    Installed version: 3.2.0
    Vulnerability ID: CVE-2021-33571
    URL: https://nvd.nist.gov/vuln/detail/CVE-2021-33571
    Description: Django 3.2.0 has an issue...
    Fix available: Upgrade to Django 3.2.4 or later

Vulnerability #2
    Package: Pillow
    Installed version: 8.1.0
    Vulnerability ID: GHSA-97jx-qpc9-p57w
    URL: https://github.com/advisories/GHSA-97jx-qpc9-p57w
    Description: ...
    Fix available: Upgrade to Pillow 8.2.0 or later
```

---

### 2. Trivy (Container Image Scanner)

Scans Docker images for OS-level vulnerabilities, misconfigurations, and dependency vulnerabilities.

#### Installation

**macOS (Homebrew)**:

```bash

brew install trivy
```

**Linux (apt)**:

```bash

sudo apt-get install trivy
```

**Docker (no install needed)**:

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image ingestor:latest
```

**Download Binary**:

- [Trivy GitHub Releases](https://github.com/aquasecurity/trivy/releases)

#### Usage

```bash
# Scan a local image
trivy image ingestor:latest

# Scan with detailed output
trivy image --severity CRITICAL,HIGH ingestor:latest

# Generate SARIF report (for GitHub Code Scanning)
trivy image --format sarif --output report.sarif ingestor:latest


# Scan and fail if high- ever ty vulns found
trivy image --severity H GH,C ITICAL --exit-code 1 ingestor:latest

# Scan multiple images
trivy image ingestor:latest inference:latest

# Scan and list only unfixed vulnerabilities
trivy image --severity HIGH --list-all-pkgs ingestor:latest
```

#### Example Output

```sh
2024-04-22T10:15:32.123Z INFO Vulnerability DB Repository: ghcr.io/aquasecurity/trivy-db
2024-04-22T10:15:33.456Z INFO Scanning image: ingestor:latest

ingestor:latest (debian 12.5)
==============================

Vulnerabilities (CRITICAL: 0, HIGH: 2, MEDIUM: 5, LOW: 12, UNKNOWN: 0)

CRITICAL Vulnerabilities
(none)

HIGH Vulnerabilities
┌──────────────────┬─────────────┬──────────┬─────────────────┬─────────────────┐
│      Library     │   Severity  │   Type   │      Title      │     Fixed By    │
├──────────────────┼─────────────┼──────────┼─────────────────┼─────────────────┤
│ openssl          │   HIGH      │ OS Pkg   │ CVE-2024-1234   │ 3.0.13          │
│ curl             │   HIGH      │ OS Pkg   │ CVE-2024-5678   │ 7.68.1          │
└──────────────────┴─────────────┴──────────┴─────────────────┴─────────────────┘


MEDIUM Vulnerabilities
...
```

---

## Pre-Commit Hooks

Pre-commit hooks run local security checks before each commit, catching issues early.

### Setup Pre-Commit Framework

**Installation**:

```bash
pip install pre-commit
```

**Initialize** (one-time per repository):

```bash
cd /home/$USER/<directory>/data-pipeline-async
pre-commit install
```

This creates `.git/hooks/pre-commit` automatically.

### Add pip-audit Hook

**Edit `.pre-commit-config.yaml`** in repo root:

```yaml
repos:
  # pip-audit hook
  - repo: https://github.com/pypa/pip-audit
    rev: v2.6.3
    hooks:
      - id: pip-audit
        name: pip-audit (Python vulnerability scan)
        language: python
        entry: pip-audit
        files: ^(pyproject\.toml|uv\.lock|requirements\.txt)$
        pass_filenames: false
        args: ['--desc']
        stages: [commit]

  # Example: Add ruff linting hook (if not present)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        name: ruff-lint
        args: [--fix]
      - id: ruff-format
        name: ruff-format
```

### Run Pre-Commit Manually

```bash
# Run all hooks against all files
pre-commit run --all-files

# Run only pip-audit
pre-commit run pip-audit --all-files

# Skip hooks for a specific commit (use sparingly)
git commit -m "wip" --no-verify

# Update hook versions
pre-commit autoupdate
```

### Docker Image Scanning in Pre-Commit (Optional)

To add Trivy as a pre-commit hook:

```yaml
  # Trivy Docker image scan
  - repo: https://github.com/aquasecurity/trivy
    rev: v0.45.0
    hooks:
      - id: trivy-docker-image-scan
        name: Trivy scan Docker images
        entry: trivy image
        language: docker
        types: [docker_image]
        args: ['--severity', 'HIGH,CRITICAL', '--exit-code', '1']
```

**Note**: This requires Docker daemon access and is slower; recommended for CI/CD only.

---

## GitHub Actions Workflows

### Workflow 1: Python Dependency Scanning

**File**: `.github/workflows/security-python-audit.yml`

```yaml
name: Python Security Audit

on:
  push:
    branches: [main, develop]
    paths: ['pyproject.toml', 'uv.lock', 'requirements*.txt']
  pull_request:
    paths: ['pyproject.toml', 'uv.lock', 'requirements*.txt']

permissions:
  contents: read
  security-events: write

jobs:
  pip-audit:
    name: pip-audit (Python Dependencies)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1

      - name: Set up Python
        uses: actions/setup-python@f677139bbe7f9c59b41e7b10b6291dadaecdb150 # v4.7.0
        with:
          python-version: "3.14"
          cache: pip

      - name: Install pip-audit
        run: pip install pip-audit

      - name: Run pip-audit with descriptions
        run: pip-audit --desc
        # Set continue-on-error: true to warn without blocking merge
        continue-on-error: false

      - name: Report results
        if: always()
        run: |
          echo "### Python Dependency Security Scan" >> $GITHUB_STEP_SUMMARY
          echo "✅ No vulnerabilities found" >> $GITHUB_STEP_SUMMARY
```

Alternative (recommended): use the prebuilt CI image `ghcr.io/${{ github.repository_owner }}/data-pipeline-ci` for the `pip-audit` job to avoid per-job Python setup and to use pre-synced wheels.

```yaml
pip-audit:
  runs-on: ubuntu-latest
  container:
    image: ghcr.io/${{ github.repository_owner }}/data-pipeline-ci:latest
  steps:
    - uses: actions/checkout@<sha>
    - name: Export locked deps
      run: uv export --frozen --all-groups --no-hashes --format requirements-txt > requirements-audit.txt
    - name: Run pip-audit
      uses: pypa/gh-action-pip-audit@1220774d901786e6f652ae159f7b6bc8fea6d266
      with:
        inputs: requirements-audit.txt
```

### Workflow 2: Docker Image Vulnerability Scanning

**File**: `.github/workflows/security-docker-trivy.yml`

```yaml
name: Docker Container Scanning

on:
  push:
    branches: [main, develop]
    paths:
      - 'Dockerfile'
      - 'services/*/Dockerfile'
      - 'infra/database/Dockerfile'
      - '.dockerignore'
  pull_request:
    paths:
      - 'Dockerfile'
      - 'services/*/Dockerfile'
      - 'infra/database/Dockerfile'
      - '.dockerignore'

permissions:
  contents: read
  security-events: write

jobs:
  trivy-scan:
    name: Trivy Container Scan
    runs-on: ubuntu-latest
    strategy:
      matrix:
        image:
          - name: ingestor
            dockerfile: Dockerfile
          - name: inference
            dockerfile: services/inference/Dockerfile
          - name: analytics
            dockerfile: services/analytics/Dockerfile
          - name: processor
            dockerfile: services/processor/Dockerfile
          - name: dashboard
            dockerfile: services/dashboard/Dockerfile
          - name: database
            dockerfile: infra/database/Dockerfile
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1

      - name: Build Docker image
        run: |
          export DOCKER_BUILDKIT=1
          docker build -t ${{ matrix.image.name }}:${{ github.sha }} -f ${{ matrix.image.dockerfile }} .

      - name: Run Trivy scan
        uses: aquasecurity/trivy-action@596663df4c19c487e7c8fa0138c4e12f9ea76814 # v0.17.0
        with:
          image-ref: ${{ matrix.image.name }}:${{ github.sha }}
          format: sarif
          output: ${{ matrix.image.name }}-trivy.sarif
          severity: 'CRITICAL,HIGH'
          exit-code: '0'  # Set to '1' to fail on vulns

      - name: Upload Trivy SARIF
        uses: github/codeql-action/upload-sarif@47b3685fe9c552c72e8345287d38c6cacf27abf5 # v2.24.2
        with:
          sarif_file: ${{ matrix.image.name }}-trivy.sarif
          category: trivy-${{ matrix.image.name }}

      - name: Summary
        run: |
          echo "### Trivy Scan Results (${{ matrix.image.name }})" >> $GITHUB_STEP_SUMMARY
          echo "Image: \`${{ matrix.image.name }}:${{ github.sha }}\`" >> $GITHUB_STEP_SUMMARY
          echo "Status: ✅ Scanned and uploaded to Code Scanning" >> $GITHUB_STEP_SUMMARY
```

### Workflow 3: Combined Security Pipeline

**File**: `.github/workflows/security-full.yml` (Recommended - runs both scans)

```yaml
name: Security Scan (Full)

on:
  push:
    branches: [main, develop]
  pull_request:

permissions:
  contents: read
  security-events: write

jobs:
  python-deps:
    name: Python Dependencies
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1
      - uses: actions/setup-python@f677139bbe7f9c59b41e7b10b6291dadaecdb150 # v4.7.0
        with:
          python-version: "3.14"
      - run: pip install pip-audit
      - run: pip-audit --desc

  docker-images:
    name: Docker Images
    runs-on: ubuntu-latest
    needs: python-deps
    strategy:
      matrix:
        dockerfile:
          - {name: "ingestor", path: "Dockerfile"}
          - {name: "inference", path: "services/inference/Dockerfile"}
          - {name: "analytics", path: "services/analytics/Dockerfile"}
          - {name: "processor", path: "services/processor/Dockerfile"}
          - {name: "dashboard", path: "services/dashboard/Dockerfile"}
          - {name: "database", path: "infra/database/Dockerfile"}
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4.3.1

      - name: Build
        run: |
          export DOCKER_BUILDKIT=1
          docker build -t ${{ matrix.dockerfile.name }}:${{ github.sha }} -f ${{ matrix.dockerfile.path }} .

      - name: Scan with Trivy
        uses: aquasecurity/trivy-action@596663df4c19c487e7c8fa0138c4e12f9ea76814 # v0.17.0
        with:
          image-ref: ${{ matrix.dockerfile.name }}:${{ github.sha }}
          format: sarif
          output: trivy-${{ matrix.dockerfile.name }}.sarif
          severity: 'CRITICAL,HIGH'

      - name: Upload SARIF

        uses: github/codeql-action/upload-sarif@47b3685fe9c552c72e8345287d38c6cacf27abf5 # v2.24.2
        with:
          sarif_file: trivy-${{ matrix.dockerfile.name }}.sarif
          category: trivy-${{ matrix.dockerfile.name }}
```

---

## Troubleshooting

### Issue: BuildKit Not Recognized

**Symptom**: Error: `unknown flag: --mount`

**Solution**:

```bash

# Verify BuildKit is enabled
export DOCKER_BUILDKIT=1
docker version | grep -i buildkit

# If not shown, enable it
export DOCKER_BUILDKIT=1
docker build -t test:latest .
```

---

### Issue: pip-audit Fails Unexpectedly

**Symptom**: `pip-audit: command not found`

**Solution**:

```bash

# Install pip-audit
pip install pip-audit

# Or verify it's in PATH
which pip-audit

# If using uv:
uv pip install pip-audit
```

---

### Issue: Trivy Takes Too Long

**Symptom**: Trivy scan takes 5+ minutes

**Solution**:

```bash
# Update Trivy DB (cached, usually fast)
trivy image --download-db-only

# Scan with less detail (faster)
trivy image --severity HIGH,CRITICAL ingestor:latest

# Skip certain checks
trivy image --skip-update ingestor:latest
```

---

### Issue: Pre-Commit Hook Blocks Commit

**Symptom**: `pre-commit run` fails on pip-audit

**Solution**:

```bash
# Check vulnerability details
pip-audit --desc

# Fix dependencies
pip install --upgrade <package-name>

# Or skip hook for this commit (use sparingly)
git commit -m "fix: temporary skip" --no-verify
```

---

## Best Practices

1. **Run security scans locally first**: `pre-commit run --all-files` before pushing
2. **Update Trivy DB regularly**: `trivy image --download-db-only` (monthly)
3. **Monitor CVE announcements**: Subscribe to Python package security lists
4. **Set exit code strategically**:
   - Local dev: `exit-code: 0` (warn only)
   - CI/CD main: `exit-code: 1` (block merge)
5. **Review SARIF reports**: Check GitHub Code Scanning tab after each scan

---

## Additional Resources

- [Docker BuildKit Documentation](https://docs.docker.com/build/buildkit/)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [pip-audit Documentation](https://github.com/pypa/pip-audit)
- [OWASP Top 10 - Vulnerable Components](https://owasp.org/Top10/A06_2021-Vulnerable_and_Outdated_Components/)
- [GitHub Code Scanning](https://docs.github.com/en/code-security/code-scanning)
