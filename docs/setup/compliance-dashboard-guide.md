# Compliance Dashboard Guide

**Status**: Production Ready (Phase 3.2)
**Last Updated**: April 22, 2026
**Scope**: SBOM tracking, vulnerability audit trail, compliance reporting

---

## Overview

The Compliance Dashboard is a GitHub Actions-based system that automatically generates and archives Software Bill of Materials (SBOMs) and compliance records for all container images. It provides:

- **SBOM Generation**: CycloneDX format for each service (standardized component manifest)
- **Scan History**: Timestamped records of every security scan
- **Audit Trail**: 365-day retention for compliance investigations
- **Traceability**: Link vulnerabilities to specific commits and branches

---

## Quick Start

### Step 1: Trigger a Scan

Push changes to `main` or `develop` branch:

```bash
git add docs/
git commit -m "docs: update compliance guide"
git push origin main
```

The `Security Scan (Full Pipeline)` workflow automatically runs.

### Step 2: Access SBOM & Compliance Reports

1. Go to **GitHub** → **Actions** tab
2. Select **Security Scan (Full Pipeline)**
3. Click latest run (green ✅ checkmark)
4. Scroll to **Artifacts** section
5. Download:
   - **sbom-cyclonedx/** - All service SBOMs
   - **compliance-reports/** - Compliance records

---

## Understanding SBOMs (Software Bill of Materials)

### What is a SBOM?

A SBOM is a machine-readable inventory of all components (libraries, packages, dependencies) in a container image. Used for:

- **License Compliance**: Identify open-source licenses (MIT, GPL, Apache, etc.)
- **Vulnerability Tracking**: Link CVEs to specific component versions
- **Supply Chain Security**: Detect unexpected or compromised dependencies
- **Compliance Audits**: SOC2, ISO27001, HIPAA requirements

### SBOM Format: CycloneDX

Standard format used by industry (NTIA, CISA endorsed). Structure:

```json
{
  "bomFormat": "CycloneDX",
  "specVersion": "1.4",
  "serialNumber": "urn:uuid:...",
  "version": 1,
  "components": [
    {
      "type": "library",
      "name": "openssl",
      "version": "3.0.7",
      "purl": "pkg:deb/debian/openssl@3.0.7?arch=amd64",
      "licenses": [
        { "license": { "name": "Apache-2.0" } }
      ]
    },
    {
      "type": "application",
      "name": "python-fastapi",
      "version": "0.109.0",
      "purl": "pkg:pypi/fastapi@0.109.0"
    }
  ]
}
```

### Fields Explained

| Field | Meaning |
|-------|---------|
| `type` | `library` (OS package) or `application` (Python package) |
| `name` | Component name |
| `version` | Pinned version |
| `purl` | Package URL (unique identifier for dependency tools) |
| `licenses` | License(s) under which component is distributed |

---

## Using SBOMs for Security

### Example 1: Find All Python Packages

```bash
# Extract only Python packages from ingestor SBOM
jq '.components[] | select(.type == "application") | {name, version}' \
  sbom-ingestor.json
```

**Output**:
```json
{
  "name": "fastapi",
  "version": "0.109.0"
}
{
  "name": "sqlalchemy",
  "version": "2.0.23"
}
```

### Example 2: Check for GPL License

```bash
# Find components with GPL license
jq '.components[] | select(.licenses[]?.license.name | contains("GPL"))' \
  sbom-*.json
```

If GPL packages found → must review for compliance implications.

### Example 3: Audit OS Packages

```bash
# List all Debian packages (from base image)
jq '.components[] | select(.type == "library" and .purl | contains("pkg:deb"))' \
  sbom-database.json
```

Useful for checking if critical OS packages (openssl, libc, curl) are present.

---

## Compliance Dashboard Artifacts

### Artifact: sbom-cyclonedx/

Contains one JSON file per service:
- `sbom-ingestor.json` - FastAPI REST API
- `sbom-ai_gateway.json` - Embedding service
- `sbom-query_api.json` - Query service
- `sbom-processor.json` - Background worker
- `sbom-dashboard.json` - Dashboard UI
- `sbom-database.json` - PostgreSQL + pgvector

**Retention**: 90 days (downloadable for compliance review)

### Artifact: compliance-reports/

Contains JSON records of every scan:
- Format: `compliance-{commit_sha}.json`
- **Retention**: 365 days (1-year audit trail)

**Example record**:
```json
{
  "timestamp": "2026-04-22T14:32:10Z",
  "commit_sha": "abc123def456abc123def456abc123def456abc1",
  "branch": "main",
  "workflow_run_id": 8901234567,
  "sbom_generated": true,
  "sbom_format": "CycloneDX",
  "python_deps_status": "success",
  "docker_images_status": "success",
  "images_scanned": 6,
  "sbom_artifacts": [...]
}
```

---

## Compliance Workflows

### Workflow 1: Pre-Release Security Audit

**Goal**: Verify all components before production deployment

```bash
# 1. Download latest SBOM from Actions → compliance-reports
# 2. Check last compliance-*.json timestamp matches your release commit
timestamp=$(jq -r '.timestamp' compliance-reports/compliance-*.json | sort | tail -1)
echo "Last security scan: $timestamp"

# 3. Verify no failures
failed=$(jq '.[] | select(.python_deps_status == "failure" or .docker_images_status == "failure")' \
  compliance-reports/*.json)
if [ -z "$failed" ]; then
  echo "✅ All recent scans passed - safe to release"
else
  echo "❌ Recent scan failures detected - fix before release"
  echo "$failed"
fi

# 4. Extract SBOMs for license review
unzip sbom-cyclonedx.zip -d sbom-review/
```

### Workflow 2: Monthly Compliance Report

**Goal**: Track compliance trends and document audit trail

```bash
# Generate compliance summary (run monthly)
cat > compliance-summary-$(date +%Y-%m).md <<EOF
# Compliance Summary - $(date +"%B %Y")

## Scan Metrics
EOF

# Count successful scans this month
success_count=$(jq '[.[] | select(.python_deps_status == "success")]' \
  compliance-reports/*.json | jq 'length')
echo "- Total scans: $success_count" >> compliance-summary-$(date +%Y-%m).md

# List detected vulnerabilities (if any)
vulns=$(jq '.[] | select(.python_deps_status == "failure")' \
  compliance-reports/*.json)
if [ -z "$vulns" ]; then
  echo "- Vulnerabilities detected: 0" >> compliance-summary-$(date +%Y-%m).md
else
  echo "- Vulnerabilities detected: $(echo "$vulns" | jq 'length')" >> compliance-summary-$(date +%Y-%m).md
fi
```

### Workflow 3: License Compliance Check

**Goal**: Ensure no prohibited licenses in dependencies

```bash
# Scan all SBOMs for GPL (may require approval)
prohibited_licenses=("GPL" "AGPL" "SSPL")

for sbom in sbom-*.json; do
  echo "Checking $sbom..."
  for license in "${prohibited_licenses[@]}"; do
    jq ".components[] | select(.licenses[]?.license.name | contains(\"$license\")) | {name, license: .licenses[0].license.name}" \
      "$sbom" && echo "⚠️  Found $license license"
  done
done
```

---

## GitHub UI Access

### View Latest Scan Results

1. **Go to Actions**:
   - Click **Actions** tab in repository
   - Click **Security Scan (Full Pipeline)**

2. **Select Run**:
   - Most recent run at top
   - Green ✅ = all checks passed
   - Red ❌ = vulnerabilities detected

3. **View Summary**:
   - Scroll down to "Python Dependency Security Scan" section
   - Review status: ✅ Passed or ❌ Failed

4. **Download Artifacts**:
   - Click **Artifacts** section
   - Download `sbom-cyclonedx` (latest SBOMs)
   - Download `compliance-reports` (historical records)

### Track Scan History

1. **Click workflow run list** (left sidebar → Security Scan)
2. **Filter by branch**: `main` or `develop`
3. **Sort by date**: Latest runs first
4. **Review trends**:
   - Consistent ✅ = healthy supply chain
   - Increasing ❌ = vulnerabilities introduced
   - Check git log at timestamp of failure

---

## Compliance Retention Policy

| Artifact | Retention | Purpose |
|----------|-----------|---------|
| SBOM (CycloneDX) | 90 days | Active vulnerability monitoring |
| Compliance Report | 365 days | Audit trail for compliance investigations |
| GitHub Code Scanning | 90 days | PR/commit-level vulnerability display |

**Why 365 days for compliance reports?**
- SOC2 Type II requires 12-month audit trail
- Regulatory investigations may need 1-year history
- Cheap to store (JSON artifacts are small, ~2-5 KB each)

---

## Troubleshooting

### Issue: SBOM artifacts not available

**Cause**: Workflow skipped on pull requests (only runs on `main`/`develop` push)

**Solution**:
```bash
# Verify workflow triggers by checking .github/workflows/security-full.yml
git push origin main  # Triggers workflow
# Wait 2-3 minutes for workflow to complete
```

### Issue: Compliance reports empty

**Cause**: First run - no historical data yet

**Solution**:
- Run 2-3 scans over time (successive commits)
- Reports accumulate over days/weeks
- Historical trends emerge after ~30 days

### Issue: SBOM parsing fails

**Cause**: Outdated `jq` version or malformed JSON

**Solution**:
```bash
# Validate SBOM JSON
jq . sbom-ingestor.json > /dev/null && echo "✅ Valid" || echo "❌ Invalid"

# Update jq if needed
brew install jq  # macOS
apt-get install jq  # Ubuntu/Debian
```

---

## Integrations

### Export SBOMs to External Systems

**Snyk** (optional, future Phase 3.3):
```bash
# Upload SBOM to Snyk for continuous monitoring
snyk sbom --json > sbom-report.json
```

**CycloneDX Dashboard**:
- Use online tool: https://cyclonedx.org/
- Upload any `sbom-*.json` file
- View interactive component graph

**Dependency-check** (OWASP):
```bash
# Generate HTML report from CycloneDX
dependency-check --data /opt/dc-data \
  --scan sbom-ingestor.json \
  --format HTML \
  --out ./reports/
```

---

## Best Practices

### ✅ DO

- Review SBOM after major dependency updates
- Check license compliance quarterly
- Archive compliance reports for audit purposes
- Include SBOM in release notes (link to artifacts)
- Monitor compliance dashboard for trends

### ❌ DON'T

- Ignore failed security scans
- Deploy code with `python_deps_status: failure`
- Delete compliance reports before 365 days (retention policy)
- Commit SBOMs to git (they're large and generated dynamically)
- Assume SBOMs are security guarantees (they're inventory, not vulnerability reports)

---

## References

- [CycloneDX Standard](https://cyclonedx.org/)
- [SBOM Spec (NTIA/CISA)](https://www.cisa.gov/sites/default/files/pdf/sbom-minimum-elements-en.pdf)
- [Trivy SBOM Generation](https://aquasecurity.github.io/trivy/latest/docs/supply-chain/sbom/)
- [OWASP Dependency-Check](https://owasp.org/www-project-dependency-check/)
