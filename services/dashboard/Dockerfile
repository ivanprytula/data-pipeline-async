# syntax=docker/dockerfile:1.4

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa AS builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ARG UV_EXCLUDE_NEWER
ENV UV_EXCLUDE_NEWER=$UV_EXCLUDE_NEWER \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY services/dashboard/pyproject.toml ./
RUN uv sync --package dashboard --no-dev --no-install-project

# ── Stage 2: final ────────────────────────────────────────────────────────────
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appgroup services/dashboard ./services/dashboard

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8003/health', timeout=5)"

EXPOSE 8003

CMD ["/app/.venv/bin/uvicorn", "services.dashboard.main:app", "--host", "0.0.0.0", "--port", "8003"]
