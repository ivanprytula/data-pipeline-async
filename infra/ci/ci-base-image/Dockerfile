FROM python:3.14-slim

# Install system deps: curl for health checks, postgresql-client for migrations
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install pinned pip and uv as root so dependencies can be installed during build
ARG PIP_VERSION=26.0
ARG UV_VERSION=0.11.7
RUN python -m pip install --upgrade pip==${PIP_VERSION} \
    && python -m pip install uv==${UV_VERSION}

# Prepare workspace for uv to read lockfile and install pinned wheels
WORKDIR /workspace
COPY uv.lock pyproject.toml .python-version ./

# Sync pinned dependencies into the image to speed CI jobs (may be large)
RUN uv sync --frozen || true

# Keep root user for GitHub Actions to write to temp dirs (CI-only image)

# Default entrypoint: print versions
ENTRYPOINT ["sh", "-lc", "python --version && pip --version && uv --version"]
