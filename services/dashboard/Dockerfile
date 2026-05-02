# syntax=docker/dockerfile:1.4

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:5b3879b6f3cb77e712644d50262d05a7c146b7312d784a18eff7ff5462e77033 AS builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY services/dashboard/pyproject.toml ./services/dashboard/pyproject.toml
RUN uv sync --package dashboard --no-dev --no-install-project

# ── Stage 2: final ────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:5b3879b6f3cb77e712644d50262d05a7c146b7312d784a18eff7ff5462e77033
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appgroup libs/ ./libs/
COPY --chown=appuser:appgroup services/dashboard ./services/dashboard

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/health', timeout=5)"

EXPOSE 8003

CMD ["/app/.venv/bin/uvicorn", "services.dashboard.main:app", "--host", "0.0.0.0", "--port", "8003"]
