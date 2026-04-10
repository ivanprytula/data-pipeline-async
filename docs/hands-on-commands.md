# Hands-On Commands

## Configuration Precedence

### The Mature Solution: Layer Your Configuration

Priority (highest first):

1. Container/k8s environment variables (production)
2. CI/CD job env vars (GitHub Actions, GitLab CI)
3. .env file (local development)
4. Settings defaults (fallback)

Example:
DATABASE_URL = k8s secret > CI env > .env > default

Alternative representation: bottom to top direction:

```text
Development (local)
    ↓
Testing (CI — secrets injected)
    ↓
Staging (k8s env vars)
    ↓
Production (secrets manager + k8s)
```

### Testing Different Environments Locally

```bash
# Development (uses .env)
docker compose up

# Testing (uses isolated DB)
ENV_FILE=.env.testing docker compose up

# Staging simulation
ENV_FILE=.env.staging docker compose up
```
