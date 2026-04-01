"""App settings (async stack)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Logging verbosity. Override with LOG_LEVEL env var. 
    
    Accepts: DEBUG, INFO, WARNING, ERROR, CRITICAL."""
    # Database — asyncpg DSN uses postgresql+asyncpg://
    # REQUIRED: Must be set via DATABASE_URL environment variable
    database_url: str

    sql_echo: bool = False
    log_level: str = "INFO"

    app_name: str = "Data Pipeline API (async)"
    app_version: str = "1.0.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()  # type: ignore
