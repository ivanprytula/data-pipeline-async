-- PostgreSQL database initialization script for data-pipeline-async
-- This script runs automatically when the PostgreSQL container starts
-- (mounted to /docker-entrypoint-initdb.d/)
-- Create pgvector extension (Phase 5: vector similarity for embeddings)
-- Used for comparison with Qdrant; enables vector column types and similarity operators
CREATE EXTENSION IF NOT EXISTS vector;

-- Optional: Create pgcrypto for UUID generation and encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Optional: Create uuid-ossp for UUID v1/v4 generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set default PostgreSQL parameters for async connection pooling
-- These are recommendations for use with asyncpg + SQLAlchemy
-- Note: These can also be set in postgresql.conf
SET max_connections = 200;

SET shared_buffers = '256MB';

SET effective_cache_size = '1GB';

SET work_mem = '4MB';

SET maintenance_work_mem = '64MB';
