from .core import async_session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

async def check_db_connection():
    """Проверка подключения к базе данных"""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        logger.info("✅ Подключение к БД успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return False
