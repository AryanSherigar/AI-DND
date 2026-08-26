"""Turn Resolution Service Configuration module."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aidnd_db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    secret_key: str = "default-secret-key-change-in-production"
    environment: str = "development"


settings = Settings()
