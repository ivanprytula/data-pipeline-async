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

# Set UV behavior to avoid hardlink/symlink issues in CI and Docker filesystems
# UV_LINK_MODE=copy forces uv to copy files instead of hardlinking/symlinking
# UV_COMPILE_BYTECODE=1 pre-compiles bytecode for slightly faster startup
ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

# Layer 3: Workspace setup (cached — changes only if lockfile/pyproject changes)
WORKDIR /workspace
COPY uv.lock pyproject.toml .python-version ./
COPY services/ai_gateway/pyproject.toml services/ai_gateway/pyproject.toml
COPY services/dashboard/pyproject.toml services/dashboard/pyproject.toml
COPY services/processor/pyproject.toml services/processor/pyproject.toml
COPY services/query_api/pyproject.toml services/query_api/pyproject.toml
COPY services/webhook/pyproject.toml services/webhook/pyproject.toml

# Layer 4: Install dependencies (cached — reused if lockfile unchanged)
# Even if only code changes, this layer is skipped
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --all-extras

# Layer 5: Default entrypoint (cached until entrypoint changes)
ENTRYPOINT ["sh", "-lc", "python --version && pip --version && uv --version"]
