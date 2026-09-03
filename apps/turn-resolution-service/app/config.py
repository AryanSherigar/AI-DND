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
    jwt_algorithm: str = "HS256"
    cors_origins: list[str] = ["http://localhost:5173"]
    environment: str = "development"

    gemini_api_key: str = ""
    gemini_model_name: str = "gemini-3.5-flash-lite"
    gemini_temperature: float = 0.7
    gemini_max_output_tokens: int = 200
    gemini_top_p: float = 0.95
    gemini_timeout_seconds: int = 30
    gemini_max_retries: int = 2
    turn_history_window_size: int = 10
    play_count_increment_turn_threshold: int = 10
    state_write_max_retries: int = 2
    memory_batch_turn_interval: int = 5
    tool_call_max_round_trips: int = 5
    log_level: str = "INFO"
    log_format: str = "json"


settings = Settings()
