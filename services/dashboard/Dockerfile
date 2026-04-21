FROM python:3.14-slim

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
