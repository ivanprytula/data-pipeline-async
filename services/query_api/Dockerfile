# syntax=docker/dockerfile:1.4
# Multi-stage build for query-api service
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa AS builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /app

# Install system dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean

# Copy pyproject.toml and install Python dependencies via uv
COPY pyproject.toml uv.lock ./
RUN pip install -U pip && pip install uv && \
    uv pip install --system -e .

# Production stage
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages

# Copy only query_api source to keep service image independent
COPY services/query_api ./services/query_api

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8005/health', timeout=5).raise_for_status()" || exit 1

# Run query API
CMD ["uvicorn", "services.query_api.main:app", "--host", "0.0.0.0", "--port", "8005"]
