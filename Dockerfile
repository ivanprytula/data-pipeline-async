FROM python:3.14-slim AS builder
# uv — fast dependency installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install system dependencies for asyncpg/postgresql
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Install deps first (better layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen --no-install-project

# Stage 2: Final image — slim, no build tools, non-root user
FROM python:3.14-slim
WORKDIR /app

# Create non-root user for security
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

# Copy Python environment from builder
COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy source code
COPY --chown=appuser:appgroup app/ ./app/

USER appuser

# Port for FastAPI
EXPOSE 8000

# Single worker is fine for local development—lets you test without multi-process complexity
# Default asyncio is what you want anyway
# --workers 4 later if you want to test multi-worker performance in production-like conditions
# --loop uvloop (with uvloop installed) if you need extreme performance optimization
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
