# syntax=docker/dockerfile:1.4
# PostgreSQL 17 (Debian-based) with pgvector extension pre-installed
# Using postgres:17-bookworm instead of postgres:17-alpine because:
# - postgres:17 (untagged) has 1 CRITICAL + 13 HIGH vulns (as of 2026-04-22)
# - postgres:17-bookworm is still ~250MB (acceptable for database image)
# - Alpine's apk packages lack some PostgreSQL extension build tools
# - Bookworm ensures pgvector v0.7.4 builds reliably with full compatibility
# Digest pinning ensures reproducible builds; update monthly via docs/setup/digest-update-runbook.md

FROM postgres:17-bookworm@sha256:cf50a40bb0320a49a95725335bb1683cb627f9c70350100ca57c41f863d684f4
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install build dependencies required for pgvector compilation
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    build-essential \
    postgresql-server-dev-17 \
    git \
    && apt-get clean

# Clone and install pgvector
RUN git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git /tmp/pgvector && \
    cd /tmp/pgvector && \
    make && \
    make install && \
    rm -rf /tmp/pgvector

# Clean up to reduce image size
RUN apt-get remove -y build-essential git postgresql-server-dev-17 && \
    apt-get autoremove -y && \
    apt-get clean
