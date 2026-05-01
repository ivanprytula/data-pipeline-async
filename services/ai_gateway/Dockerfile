# syntax=docker/dockerfile:1.4

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa AS builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Build-time deps: compiler toolchain + BLAS headers for sentence-transformers
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

ARG UV_EXCLUDE_NEWER
ENV UV_EXCLUDE_NEWER=$UV_EXCLUDE_NEWER \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Workspace root + lock file needed for uv sync --package
COPY pyproject.toml uv.lock ./
COPY services/ai_gateway/pyproject.toml ./services/ai_gateway/pyproject.toml
RUN uv sync --package ai-gateway --no-dev --no-install-project

# ── Stage 2: final ────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Runtime BLAS library only (~20 MB vs ~300 MB build toolchain)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appgroup services/ai_gateway/embeddings.py \
                               services/ai_gateway/vector_store.py \
                               services/ai_gateway/main.py ./

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=5)"

EXPOSE 8001

CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
