FROM python:3.14-slim

# Layer 1: System dependencies (cached longest — rarely changes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Layer 2: Pip and uv tools (cached — only changes on version bump)
ARG PIP_VERSION=26.0
ARG UV_VERSION=0.11.7
RUN python -m pip install --upgrade pip==${PIP_VERSION} \
    && python -m pip install uv==${UV_VERSION}

# Layer 3: Workspace setup (cached — changes only if lockfile/pyproject changes)
WORKDIR /workspace
COPY uv.lock pyproject.toml .python-version ./

# Layer 4: Install dependencies (cached — reused if lockfile unchanged)
# Even if only code changes, this layer is skipped
RUN uv sync --frozen || true

# Layer 5: Default entrypoint (cached until entrypoint changes)
ENTRYPOINT ["sh", "-lc", "python --version && pip --version && uv --version"]
