"""Core API Configuration module."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "default-secret-key-change-in-production"
MIN_PRODUCTION_SECRET_KEY_LENGTH = 32


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
    jwt_access_expire_minutes: int = 15
    jwt_refresh_expire_days: int = 7
    firebase_project_id: str = "ai-dnd-47eb0"
    firebase_credentials_path: str = ""
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    environment: str = "development"
    frontend_base_url: str = "http://localhost:5173"
    log_level: str = "INFO"
    log_format: str = "json"
    gcs_bucket_name: str = ""
    core_api_public_url: str = "http://localhost:8000"
    local_upload_dir: str = "uploads"
    gemini_api_key: str = ""
    imagen_model_name: str = "imagen-3.0-generate-002"
    imagen_timeout_seconds: int = 30
    lyria_model_name: str = "lyria-002"
    lyria_timeout_seconds: int = 60
    # Memory layer (apps/memory-layer) -- unconsumed by memory_client.py
    # until it stops being a mock (see its own module docstring, "Phase 4"),
    # but declared here now so the real client has settings to read.
    memory_service_url: str = "http://localhost:8002"
    memory_service_api_key: str = ""
    memory_query_timeout_seconds: int = 3
    memory_ingest_timeout_seconds: int = 5
    # NEW-MED-02 fix: 10s was consistently too short for a scenario with
    # substantial lore -- memory-layer's template ingest runs sequential
    # Gemini extraction calls plus embedding generation, which routinely
    # exceeds it, surfacing as a false "publish failed" to the user while
    # memory-layer keeps working in the background regardless.
    memory_template_timeout_seconds: int = 60
    memory_clone_timeout_seconds: int = 5

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
