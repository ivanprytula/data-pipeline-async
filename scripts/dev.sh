#!/bin/bash
# scripts/dev.sh

# Start DB
docker compose up -d db

# Wait for DB to be healthy
docker compose exec db pg_isready -U postgres || sleep 2

# Start app
uv run uvicorn app.main:app --reload
