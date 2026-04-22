# syntax=docker/dockerfile:1.4
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY services/dashboard/pyproject.toml .
RUN uv sync --no-dev --no-install-project

COPY services/dashboard ./services/dashboard

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8003

CMD ["uv", "run", "uvicorn", "services.dashboard.main:app", "--host", "0.0.0.0", "--port", "8003"]
