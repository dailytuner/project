"""
Settings configuration for Psychometry Service.
"""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings."""

    # Service
    SERVICE_NAME: str = "psychometry"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:pass@localhost:5432/db",
        description="Async PostgreSQL connection URL"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600  # 1 hour

    # Astro Service
    ASTRO_SERVICE_URL: Optional[str] = None
    ASTRO_FALLBACK_MODE: bool = True
    ASTRO_TIMEOUT: float = 5.0

    # Data Lake (MinIO)
    LAKE_BUCKET: str = "personal-assistant-lake"
    LAKE_ENDPOINT: str = "minio:9000"
    LAKE_ACCESS_KEY: str = "minioadmin"
    LAKE_SECRET_KEY: str = "minioadmin"
    LAKE_USE_SSL: bool = False
    LAKE_REGION: str = "us-east-1"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1/psych"

    # Test Intervals (in days)
    MMPI_INTERVAL_DAYS: int = 90
    IAT_INTERVAL_DAYS: int = 30

    # Outbox Worker
    OUTBOX_POLL_INTERVAL: int = 30  # seconds
    OUTBOX_MAX_RETRY: int = 5
    OUTBOX_STALE_MINUTES: int = 5
    OUTBOX_BATCH_SIZE: int = 100

    # JWT
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 10
    RATE_LIMIT_PERIOD: int = 60  # seconds

    # MMPI Norms
    MMPI_NORMS_PATH: str = "data/mmpi_norms.json"

    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v):
        """Ensure database URL uses asyncpg driver."""
        if v and "postgresql+asyncpg" not in v:
            # Replace postgresql:// with postgresql+asyncpg://
            if v.startswith("postgresql://"):
                v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


# Global settings instance
settings = Settings()
