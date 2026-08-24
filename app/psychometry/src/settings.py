# app/psychometry/src/settings.py

import os
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from tenacity import retry, stop_after_attempt, wait_exponential


class Settings(BaseSettings):
    """Application settings with validation."""

    # ========== Service ==========
    SERVICE_NAME: str = "psychometry"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "production"

    # ========== API ==========
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1/psych"
    ROOT_PATH: str = ""
    ALLOWED_ORIGINS: List[str] = ["*"]

    # ========== Database ==========
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:password@postgres:5432/personalassistant"
    )
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=100)
    DB_POOL_TIMEOUT: int = Field(default=30, ge=1)
    DB_POOL_RECYCLE: int = Field(default=3600, ge=60)

    # ========== JWT ==========
    JWT_SECRET_KEY: str = Field(min_length=32)
    JWT_SECRET_KEY_FILE: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_AUDIENCE: str = "psychometry"
    JWT_ISSUER: str = "personal-assistant"

    # ========== Astro Service ==========
    ASTRO_SERVICE_URL: Optional[str] = None
    ASTRO_FALLBACK_MODE: bool = True
    ASTRO_TIMEOUT: float = Field(default=3.0, ge=0.5, le=10.0)
    ASTRO_MAX_RETRIES: int = 2

    # ========== Data Lake (MinIO) ==========
    LAKE_ENDPOINT: str = "minio:9000"
    LAKE_BUCKET: str = "personal-assistant-lake"
    LAKE_ACCESS_KEY: str = "minioadmin"
    LAKE_SECRET_KEY: str = "minioadmin"
    LAKE_ACCESS_KEY_FILE: Optional[str] = None
    LAKE_SECRET_KEY_FILE: Optional[str] = None
    LAKE_USE_SSL: bool = False
    LAKE_REGION: str = "us-east-1"
    LAKE_UPLOAD_TIMEOUT: int = 30
    LAKE_MAX_RETRIES: int = 2

    # ========== Test Intervals ==========
    MMPI_INTERVAL_DAYS: int = Field(default=90, ge=1, le=365)
    IAT_INTERVAL_DAYS: int = Field(default=30, ge=1, le=365)

    # ========== Outbox ==========
    OUTBOX_POLL_INTERVAL: int = Field(default=30, ge=5)
    OUTBOX_MAX_RETRY: int = Field(default=5, ge=1, le=20)
    OUTBOX_STALE_MINUTES: int = Field(default=5, ge=1)
    OUTBOX_BATCH_SIZE: int = Field(default=100, ge=1, le=500)

    # ========== Rate Limiting ==========
    RATE_LIMIT_REQUESTS: int = Field(default=10, ge=1)
    RATE_LIMIT_PERIOD: int = Field(default=60, ge=1)

    # ========== MMPI Norms ==========
    MMPI_NORMS_PATH: str = "data/mmpi_norms.json"

    # ========== Metrics ==========
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090

    # ============================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================

    @classmethod
    def read_secret_file(cls, file_path: str) -> Optional[str]:
        """Read secret from file."""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return f.read().strip()
        except (IOError, OSError):
            pass
        return None

    # ============================================================
    # ВАЛИДАТОРЫ
    # ============================================================

    @field_validator("JWT_SECRET_KEY", mode="before")
    @classmethod
    def load_jwt_secret(cls, v, info) -> str:
        """Load JWT secret from file or environment."""
        # 1. Пробуем из файла
        jwt_file = os.environ.get("JWT_SECRET_KEY_FILE")
        if jwt_file:
            content = cls.read_secret_file(jwt_file)
            if content and len(content) >= 32:
                return content

        # 2. Пробуем из переменной окружения
        env_secret = os.environ.get("JWT_SECRET_KEY")
        if env_secret and len(env_secret) >= 32:
            return env_secret

        # 3. Используем переданное значение
        if v and len(v) >= 32:
            return v

        # 4. Ошибка (убрали development fallback)
        raise ValueError(
            "JWT_SECRET_KEY must be provided via JWT_SECRET_KEY_FILE, "
            "JWT_SECRET_KEY environment variable, or have min 32 chars"
        )

    @field_validator("LAKE_ACCESS_KEY", mode="before")
    @classmethod
    def load_lake_access_key(cls, v, info) -> str:
        """Load MinIO access key from file or environment."""
        # 1. Пробуем из файла
        key_file = os.environ.get("LAKE_ACCESS_KEY_FILE")
        if key_file:
            content = cls.read_secret_file(key_file)
            if content:
                return content

        # 2. Пробуем из переменной окружения
        env_key = os.environ.get("LAKE_ACCESS_KEY")
        if env_key:
            return env_key

        # 3. Используем переданное значение или fallback
        return v if v else "minioadmin"

    @field_validator("LAKE_SECRET_KEY", mode="before")
    @classmethod
    def load_lake_secret_key(cls, v, info) -> str:
        """Load MinIO secret key from file or environment."""
        # 1. Пробуем из файла
        key_file = os.environ.get("LAKE_SECRET_KEY_FILE")
        if key_file:
            content = cls.read_secret_file(key_file)
            if content:
                return content

        # 2. Пробуем из переменной окружения
        env_key = os.environ.get("LAKE_SECRET_KEY")
        if env_key:
            return env_key

        # 3. Используем переданное значение или fallback
        return v if v else "minioadmin"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v, info) -> str:
        """Load database URL from file or environment."""
        # 1. Пробуем из файла
        url_file = os.environ.get("DATABASE_URL_FILE")
        if url_file:
            content = cls.read_secret_file(url_file)
            if content:
                return content

        # 2. Пробуем из переменной окружения
        env_url = os.environ.get("DATABASE_URL")
        if env_url:
            return env_url

        # 3. Используем переданное значение
        if v:
            return v

        raise ValueError("DATABASE_URL must be provided")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()