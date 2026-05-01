# syntax=docker/dockerfile:1.4
FROM python:3.14-slim@sha256:5b3879b6f3cb77e712644d50262d05a7c146b7312d784a18eff7ff5462e77033 AS builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ARG UV_EXCLUDE_NEWER
ENV UV_EXCLUDE_NEWER=$UV_EXCLUDE_NEWER \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY services/processor/pyproject.toml ./services/processor/pyproject.toml
RUN uv sync --package processor --no-dev --no-install-project

# Stage 2: Final image — slim, non-root user
FROM python:3.14-slim@sha256:5b3879b6f3cb77e712644d50262d05a7c146b7312d784a18eff7ff5462e77033
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
WORKDIR /app

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

# Copy Python dependencies from builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appgroup services/processor/main.py .

USER appuser

CMD ["python", "main.py"]
