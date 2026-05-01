# syntax=docker/dockerfile:1.4
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa AS builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# uv — fast dependency installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system dependencies for asyncpg/postgresql
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG UV_EXCLUDE_NEWER
ENV UV_EXCLUDE_NEWER=$UV_EXCLUDE_NEWER \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install deps first (better layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# Stage 2: Final image — slim, no build tools, non-root user
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /app

# Install system deps for asyncpq/pgvector + Playwright browser execution
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    libpq5 \
    libnss3 \
    libxss1 \
    libx11-6 \
    libxcb1 \
    libxrandr2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libdbus-1-3 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    fonts-noto \
    && rm -rf /var/lib/apt/lists/*

# Copy Python environment from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install Playwright browsers as root (required for appuser to use them)
RUN playwright install chromium && \
    playwright install-deps chromium

# Create non-root user for security (after Playwright setup)
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

# Set ownership of app directory to non-root user
RUN chown -R appuser:appgroup /app

# Copy source code and migration files
COPY --chown=appuser:appgroup ingestor/ ./ingestor/
COPY --chown=appuser:appgroup alembic/ ./alembic/
COPY --chown=appuser:appgroup alembic.ini ./

USER appuser

# Port for FastAPI
EXPOSE 8000

CMD ["uvicorn", "ingestor.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
