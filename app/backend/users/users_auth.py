# users_auth.py
from enum import Enum
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database.models import User
from ..database.core import logger


class AuthPlatform(str, Enum):
    TELEGRAM = 'telegram'
    MAX = 'max'
    UDEMY = 'udemy'
    GOOGLE = 'google'
    APPLE = 'apple'
    PHONE = 'phone'
    EMAIL = 'email'


class UserAuthService:
    """Сервис поиска пользователей по платформам авторизации"""

    @staticmethod
    async def get_user(
            session: AsyncSession,
            platform: AuthPlatform,
            platform_id: str
    ) -> Optional[User]:
        try:
            stmt = UserAuthService._build_user_query(platform, platform_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error finding user by {platform}: {e}")
            return None

    @staticmethod
    async def get_user_id(
            session: AsyncSession,
            platform: AuthPlatform,
            platform_id: str
    ) -> Optional[int]:
        try:
            stmt = UserAuthService._build_id_query(platform, platform_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user_id by {platform}: {e}")
            return None

    @staticmethod
    def _build_user_query(platform: AuthPlatform, platform_id: str):
        match platform:
            case AuthPlatform.TELEGRAM:
                try:
                    return select(User).where(User.telegram_id == int(platform_id))
                except ValueError:
                    raise ValueError(f"Invalid telegram_id: {platform_id}")
            case AuthPlatform.MAX:
                return select(User).where(User.max_id == platform_id)
            case AuthPlatform.UDEMY:
                return select(User).where(User.udemy_id == platform_id)
            case AuthPlatform.GOOGLE:
                return select(User).where(User.google_id == platform_id)
            case AuthPlatform.APPLE:
                return select(User).where(User.apple_id == platform_id)
            case AuthPlatform.PHONE:
                return select(User).where(User.phone_hash == platform_id)
            case AuthPlatform.EMAIL:
                return select(User).where(User.email_hash == platform_id)

    async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    def _build_id_query(platform: AuthPlatform, platform_id: str):
        match platform:
            case AuthPlatform.TELEGRAM:
                try:
                    return select(User.id).where(User.telegram_id == int(platform_id))
                except ValueError:
                    raise ValueError(f"Invalid telegram_id: {platform_id}")
            case AuthPlatform.MAX:
                return select(User.id).where(User.max_id == platform_id)
            case AuthPlatform.UDEMY:
                return select(User.id).where(User.udemy_id == platform_id)
            case AuthPlatform.GOOGLE:
                return select(User.id).where(User.google_id == platform_id)
            case AuthPlatform.APPLE:
                return select(User.id).where(User.apple_id == platform_id)
            case AuthPlatform.PHONE:
                return select(User.id).where(User.phone_hash == platform_id)
            case AuthPlatform.EMAIL:
                return select(User.id).where(User.email_hash == platform_id)


# Экспорт для удобства
get_user_by_platform = UserAuthService.get_user
get_user_id_by_platform = UserAuthService.get_user_id
get_user_by_id = UserAuthService.get_user_by_id
__all__ = ['AuthPlatform', 'UserAuthService', 'get_user_by_platform', 'get_user_id_by_platform', 'get_user_by_id']
