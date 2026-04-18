FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1

COPY pyproject.toml ./
RUN uv pip install --system "aiokafka>=0.11"

# Stage 2: Final image — slim, non-root user
FROM python:3.14-slim
WORKDIR /app

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid appgroup --shell /bin/false --no-create-home appuser

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --chown=appuser:appgroup main.py .

USER appuser

CMD ["python", "main.py"]
