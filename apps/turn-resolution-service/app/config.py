"""Turn Resolution Service Configuration module."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "default-secret-key-change-in-production"
MIN_PRODUCTION_SECRET_KEY_LENGTH = 32
SECONDS_PER_DAY = 86400


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
    secret_key: str = DEFAULT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    cors_origins: list[str] = ["http://localhost:5173"]
    environment: str = "development"

    gemini_api_key: str = ""
    gemini_model_name: str = "gemini-3.5-flash-lite"
    gemini_temperature: float = 0.75
    gemini_max_output_tokens: int = 350
    gemini_top_p: float = 0.95
    gemini_timeout_seconds: int = 30
    gemini_max_retries: int = 2
    turn_history_window_size: int = 6
    play_count_increment_turn_threshold: int = 10
    state_write_max_retries: int = 2
    memory_batch_turn_interval: int = 5
    memory_service_url: str = "http://localhost:8002"
    memory_service_api_key: str = ""
    memory_query_timeout_seconds: int = 3
    memory_ingest_timeout_seconds: int = 5
    tool_call_max_round_trips: int = 5
    minigame_iframe_handshake_timeout_seconds: int = 20
    log_level: str = "INFO"
    log_format: str = "json"
    sse_ping_interval_seconds: int = 15
    is_rate_limit_enabled: bool = True
    rate_limit_requests_per_window: int = 30
    rate_limit_window_seconds: int = 60
    rate_limit_daily_requests: int = 1000
    rate_limit_daily_window_seconds: int = SECONDS_PER_DAY
    image_generation_model_name: str = "gemini-3.1-flash-image"
    image_generation_timeout_seconds: int = 30
    gcs_bucket_name: str = ""
    local_upload_dir: str = "uploads"
    firebase_credentials_path: str = ""

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Refuse to boot in production with the default or a weak secret_key."""
        if self.environment == "production" and (
            self.secret_key == DEFAULT_SECRET_KEY
            or len(self.secret_key) < MIN_PRODUCTION_SECRET_KEY_LENGTH
        ):
            raise ValueError(
                "FATAL: Insecure SECRET_KEY configured in production environment!"
            )
        return self


settings = Settings()
