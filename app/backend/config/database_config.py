import os
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class DatabaseConfig:
    """Конфигурация базы данных - иммутабельная и безопасная"""
    
    # Классовые константы (всегда доступны)
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 10
    POOL_TIMEOUT: int = 30
    
    @property
    def DATABASE_URL(self) -> str:
        """Ленивая загрузка URL из секрета/переменной"""
        url_file = os.getenv('DATABASE_URL_FILE')
        if url_file and Path(url_file).exists():
            with open(url_file, 'r') as f:
                return f.read().strip()
        return os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres@postgres:5432/personalassistant"
        )
    
    @property
    def POOL_PRE_PING(self) -> bool:
        return os.getenv("DB_POOL_PRE_PING", "True").lower() == "true"
    
    @property
    def POOL_RECYCLE(self) -> int:
        return int(os.getenv("DB_POOL_RECYCLE", "300"))
    
    @property
    def ECHO(self) -> bool:
        return os.getenv("DB_ECHO", "False").lower() == "true"
        
    @property
    def SERVER_SETTINGS(self) -> dict:
        """📊 Для Grafana метрик"""
        return {
            "application_name": "personal-assistant-api",
            "timezone": "Europe/Moscow",
            "log_min_duration_statement": "1000"  # >1s в логи
        }
        
        
    
    def safe_db_url(self, max_length: int = 40) -> str:
        """Безопасное логирование URL БД"""
        url = self.DATABASE_URL
        return f"{url[:max_length]}..." if len(url) > max_length else url

