# users_repositories.py
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ..database.models import User, UserProfile
from .users_auth import AuthPlatform
import logging

logger = logging.getLogger(__name__)

PLATFORM_FIELDS = {
    AuthPlatform.TELEGRAM: 'telegram_id',
    AuthPlatform.MAX: 'max_id',
    AuthPlatform.UDEMY: 'udemy_id',
    AuthPlatform.GOOGLE: 'google_id',
    AuthPlatform.APPLE: 'apple_id',
    AuthPlatform.YANDEX: 'yandex_id',
    AuthPlatform.PHONE: 'phone_hash',
    AuthPlatform.EMAIL: 'email_hash',
}


async def create_user_with_profile(
        session: AsyncSession,
        platform: AuthPlatform,
        platform_id: str,
        **profile_data
) -> User:
    from .users_auth import get_user_by_platform

    # Проверяем существование
    if await get_user_by_platform(session, platform, platform_id):
        raise ValueError(f"User already exists for {platform}:{platform_id}")

    # Создаем пользователя
    user = User()
    field_name = PLATFORM_FIELDS[platform]
    if platform == AuthPlatform.TELEGRAM:
        setattr(user, field_name, int(platform_id))
    else:
        setattr(user, field_name, platform_id)

    user.primary_auth_method = platform.value
    session.add(user)
    await session.flush()

    # Создаем профиль
    profile = UserProfile(user_id=user.id, **profile_data)
    session.add(profile)

    await session.commit()
    return user


async def update_yandex_tokens(
        session: AsyncSession,
        user_id: int,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        yandex_email: Optional[str] = None,
        yandex_login: Optional[str] = None,
        yandex_avatar_url: Optional[str] = None
) -> bool:
    """
    Обновляет токены и данные Яндекса для пользователя
    """
    from datetime import datetime, timezone, timedelta

    user = await session.get(User, user_id)
    if not user:
        logger.warning(f"User {user_id} not found for Yandex token update")
        return False

    # Обновляем токены
    user.yandex_access_token = access_token
    user.yandex_refresh_token = refresh_token
    user.yandex_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Обновляем данные пользователя
    if yandex_email:
        user.yandex_email = yandex_email
        # Если email не был установлен ранее, обновляем email_hash
        if not user.email_hash:
            user.email_hash = yandex_email

    if yandex_login:
        user.yandex_login = yandex_login

    if yandex_avatar_url:
        user.yandex_avatar_url = yandex_avatar_url

    await session.commit()
    logger.info(f"✅ Yandex tokens updated for user {user_id}")
    return True


__all__ = ['PLATFORM_FIELDS', 'create_user_with_profile', 'update_yandex_tokens']