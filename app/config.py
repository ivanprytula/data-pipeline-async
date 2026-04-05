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
    sql_echo: bool = Field(
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
        description="Logging verbosity. Accepts: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    model_config = SettingsConfigDict(
        env_file=".env",  # Load from .env (local dev)
        env_file_encoding="utf-8",
        case_sensitive=False,  # DATABASE_URL and database_url both work
        extra="ignore",  # Ignore unknown env vars
    )


# Singleton instance
settings = Settings()
