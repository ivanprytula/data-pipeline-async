# syntax=docker/dockerfile:1.4
FROM python:3.14-slim@sha256:bc389f7dfcb21413e72a28f491985326994795e34d2b86c8ae2f417b4e7818aa
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /app

# Dependencies for numpy and sentence-transformers
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    build-essential \
    libopenblas-dev \
    && apt-get clean

# Install Python packages
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    sentence-transformers==2.2.2 \
    qdrant-client==2.7.0

# Copy app code
COPY embeddings.py vector_store.py main.py ./

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health').read()"

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
