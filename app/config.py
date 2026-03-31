"""App settings (async stack)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database — asyncpg DSN uses postgresql+asyncpg://
    # REQUIRED: Must be set via DATABASE_URL environment variable
    database_url: str

    sql_echo: bool = False
    debug: bool = False

    app_name: str = "Data Pipeline API (async)"
    app_version: str = "1.0.0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()  # type: ignore
