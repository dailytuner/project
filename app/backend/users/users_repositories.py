# users_repositories.py
from sqlalchemy.ext.asyncio import AsyncSession
from ..database.models import User, UserProfile
from .users_auth import AuthPlatform

PLATFORM_FIELDS = {
    AuthPlatform.TELEGRAM: 'telegram_id',
    AuthPlatform.MAX: 'max_id',
    AuthPlatform.UDEMY: 'udemy_id',
    AuthPlatform.GOOGLE: 'google_id',
    AuthPlatform.APPLE: 'apple_id',
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

