# PostgreSQL 17 with pgvector extension pre-installed
# This image extends the official postgres:17 and adds the pgvector extension
# which is required for Phase 5 (vector similarity + Qdrant comparison)

FROM postgres:17

# Install build dependencies required for pgvector compilation
RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-server-dev-17 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone and install pgvector
RUN git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git /tmp/pgvector && \
    cd /tmp/pgvector && \
    make && \
    make install && \
    rm -rf /tmp/pgvector

# Clean up to reduce image size
RUN apt-get remove -y build-essential git postgresql-server-dev-17 && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*
