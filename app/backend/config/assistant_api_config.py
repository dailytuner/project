import os
from typing import Dict, Any


class AssistantAPIConfig:
    """Конфигурация API для assistant"""

    # Настройки API
    API_TITLE = "Personal Assistant API"
    API_VERSION = "1.0.0"
    API_DESCRIPTION = "API для доступа к оптимальным активностям и рекомендациям"

    # Настройки сервера
    HOST = os.getenv("ASSISTANT_API_HOST", "0.0.0.0")
    PORT = int(os.getenv("ASSISTANT_API_PORT", "8000"))
    RELOAD = os.getenv("ASSISTANT_API_RELOAD", "False").lower() == "true"

    # Настройки CORS
    CORS_ORIGINS = os.getenv("ASSISTANT_API_CORS_ORIGINS", "*").split(",")

    # Настройки аутентификации
    API_KEYS = os.getenv("ASSISTANT_API_KEYS", "").split(",")

    # Настройки кэширования
    CACHE_TTL = int(os.getenv("ASSISTANT_API_CACHE_TTL", "300"))  # 5 минут

    # Настройки логирования
    LOG_LEVEL = os.getenv("ASSISTANT_API_LOG_LEVEL", "INFO")

    @classmethod
    def get_fastapi_config(cls) -> Dict[str, Any]:
        """Получение конфигурации для FastAPI"""
        return {
            "title": cls.API_TITLE,
            "description": cls.API_DESCRIPTION,
            "version": cls.API_VERSION,
            "docs_url": "/docs",
            "redoc_url": "/redoc"
        }


# Экспорт конфигурации
config = AssistantAPIConfig()