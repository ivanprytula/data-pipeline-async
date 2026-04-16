"""App settings (async stack)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env (local dev)
        env_file_encoding="utf-8",
        case_sensitive=False,  # DATABASE_URL and database_url both work
        extra="ignore",  # Ignore unknown env vars
    )


# Singleton instance
settings = Settings()
