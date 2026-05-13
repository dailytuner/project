import logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncAttrs
from sqlalchemy.orm import sessionmaker, declarative_base

from ..config.database_config import DatabaseConfig

logger = logging.getLogger(__name__)
config = DatabaseConfig()

async_engine = create_async_engine(
    config.DATABASE_URL,
    echo=config.ECHO,
    pool_pre_ping=config.POOL_PRE_PING,
    pool_recycle=config.POOL_RECYCLE,
    pool_size=config.POOL_SIZE,
    max_overflow=config.MAX_OVERFLOW,
    pool_timeout=config.POOL_TIMEOUT,
    connect_args={
        "command_timeout": 60,
        "server_settings": config.SERVER_SETTINGS
    },
    future=True
)

async_session = sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession
)

Base = declarative_base(cls=AsyncAttrs)

@asynccontextmanager
async def get_db():
    """Совместим с текущим использованием: async for session in get_db()"""
    session = async_session()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

async def close_db():
    try:
        await async_engine.dispose()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Failed to close database connections: {e}")
        raise

__all__ = ['async_engine', 'async_session', 'Base', 'get_db', 'close_db']
