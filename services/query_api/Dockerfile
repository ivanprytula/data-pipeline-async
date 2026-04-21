# Multi-stage build for query-api service
FROM python:3.14-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install Python dependencies via uv
COPY pyproject.toml uv.lock ./
RUN pip install -U pip && pip install uv && \
    uv pip install --system -e .

# Production stage
FROM python:3.14-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages

# Copy app and services
COPY app ./app
COPY services/query-api ./services/query-api

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8005/health', timeout=5).raise_for_status()" || exit 1

# Run query API
CMD ["uvicorn", "services.query_api.main:app", "--host", "0.0.0.0", "--port", "8005"]
