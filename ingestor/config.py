"""App settings (async stack)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ingestor.constants import (
    BACKGROUND_MAX_TRACKED_TASKS_DEFAULT,
    BACKGROUND_WORKER_COUNT_DEFAULT,
    BACKGROUND_WORKER_QUEUE_SIZE_DEFAULT,
)


class Settings(BaseSettings):
    """Application configuration.

    Reads from .env (local dev) or environment variables (CI/prod).
    Order of precedence: environment > .env > defaults
    """

    # Database — asyncpg DSN uses postgresql+asyncpg://
    # REQUIRED: Must be set via DATABASE_URL environment variable
    # ============ Database ============
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/data_pipeline",
        description="PostgreSQL connection string (asyncpg driver)",
    )

    # Connection pool settings
    # Adjust based on expected load and PostgreSQL max_connections
    # Formula: (max_connections / instances) to avoid "too many connections" errors
    db_pool_size: int = 5  # Number of connections to keep open
    db_max_overflow: int = 10  # Extra connections beyond pool_size when demand spikes
    db_pool_timeout: int = 30  # Seconds to wait for available connection before raising an error  # noqa: E501
    db_pool_recycle: int = 1800  # Recycle connections after 30 min (avoid stale)

    # Echo SQL statements for debugging (disable in production)
    db_echo: bool = Field(
        default=False,
        description="Enable SQL query logging",
    )

    # ============ App ============
    app_name: str = Field(
        default="Data Pipeline API (async)",
        description="Application name",
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application version",
    )
    environment: str = Field(
        default="development",
        description="Execution environment: development, testing, staging, production",
    )

    log_level: str = Field(
        default="INFO",
        description="Global logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    # Dependency library logging levels (reduce noise from verbose libs)
    log_sqlalchemy_level: str | None = Field(
        default=None,
        description="SQLAlchemy logging level (default: WARNING if not set)",
    )

    log_httpx_level: str | None = Field(
        default=None,
        description="HTTPX logging level (default: WARNING if not set)",
    )

    log_asyncio_level: str | None = Field(
        default=None,
        description="Asyncio logging level (default: WARNING if not set)",
    )

    # ============ Documentation Auth ============
    docs_username: str | None = Field(
        default=None,
        description="Username for docs authentication. If None, docs are public. Set to enable.",
    )

    docs_password: str | None = Field(
        default=None,
        description="Password for docs authentication. If None, docs are public. Set to enable.",
    )

    # ============ API Auth — v1 (Token + Session) ============
    api_v1_bearer_token: str | None = Field(
        default=None,
        description="Simple bearer token for v1 endpoints. "
        " If set, endpoints require Authorization: Bearer <token>",
    )

    token_expiry_hours: int = Field(
        default=24,
        description="Token expiration time in hours (for session tokens)",
    )

    # ============ API Auth — v2 (JWT) ============
    jwt_secret: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for JWT signing (MUST be >32 chars in production)",
    )

    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm (HS256, RS256, etc.)",
    )

    jwt_expiry_minutes: int = Field(
        default=60,
        description="JWT token expiration in minutes",
    )

    # ============ Redis Caching ============
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching layer",
    )

    redis_enabled: bool = Field(
        default=False,
        description="Enable Redis caching. Disabled by default (tests use fakeredis)",
    )

    # ============ Kafka / Redpanda ============
    kafka_broker_url: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers (comma-separated). Override with KAFKA_BROKER_URL.",
    )

    kafka_enabled: bool = Field(
        default=False,
        description="Enable Kafka event publishing. Disabled by default (safe for tests w/o broker).",  # noqa: E501
    )

    # ============ MongoDB ============
    mongo_url: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URL",
    )

    mongo_db_name: str = Field(
        default="datazoo",
        description="MongoDB database name",
    )

    mongo_enabled: bool = Field(
        default=False,
        description="Enable MongoDB storage. Disabled by default (safe for tests w/o MongoDB).",
    )

    # ============ OpenTelemetry ============
    otel_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry distributed tracing. Disabled by default.",
    )

    otel_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP gRPC endpoint for trace export (e.g., http://jaeger:4317).",
    )

    otel_service_name: str = Field(
        default="ingestor",
        description="Service name shown in Jaeger / OTel collector UI.",
    )

    # ============ Background workers (Pillar 5) ============
    background_workers_enabled: bool = Field(
        default=False,
        description="Enable in-process background worker queue for large batch ingestion.",
    )

    background_worker_count: int = Field(
        default=BACKGROUND_WORKER_COUNT_DEFAULT,
        ge=1,
        le=32,
        description="Number of async worker tasks consuming the in-process queue.",
    )

    background_worker_queue_size: int = Field(
        default=BACKGROUND_WORKER_QUEUE_SIZE_DEFAULT,
        ge=1,
        le=10000,
        description="Maximum number of queued background jobs before rejecting new submissions.",
    )

    background_max_tracked_tasks: int = Field(
        default=BACKGROUND_MAX_TRACKED_TASKS_DEFAULT,
        ge=10,
        le=50000,
        description="Maximum completed task statuses kept in memory for status lookups.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env (local dev)
        env_file_encoding="utf-8",
        case_sensitive=False,  # DATABASE_URL and database_url both work
        extra="ignore",  # Ignore unknown env vars
    )


# Singleton instance
settings = Settings()
