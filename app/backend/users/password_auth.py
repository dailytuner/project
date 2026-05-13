"""Аутентификация по паролю для веб-интерфейса"""
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
import logging

from ..database.models import User
from .users_auth import AuthPlatform, get_user_by_platform

logger = logging.getLogger(__name__)

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    return pwd_context.verify(plain_password, hashed_password)


async def set_user_password(
        session: AsyncSession,
        user_id: int,
        password: str
) -> bool:
    """
    Установка или смена пароля пользователя

    Args:
        session: Сессия БД
        user_id: ID пользователя
        password: Новый пароль (min 6 символов)

    Returns:
        bool: Успешность операции
    """
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")

    hashed = hash_password(password)

    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(password_hash=hashed)
    )
    await session.commit()

    logger.info(f"Password set for user_id={user_id}")
    return True


async def verify_user_password(
        session: AsyncSession,
        user_id: int,
        password: str
) -> bool:
    """
    Проверка пароля пользователя

    Args:
        session: Сессия БД
        user_id: ID пользователя
        password: Пароль для проверки

    Returns:
        bool: Верный ли пароль
    """
    user = await session.get(User, user_id)
    if not user or not user.password_hash:
        return False

    return verify_password(password, user.password_hash)


async def authenticate_by_platform(
        session: AsyncSession,
        platform: AuthPlatform,
        platform_user_id: str,
        password: str
) -> Optional[int]:
    """
    Аутентификация пользователя по платформе и паролю

    Args:
        session: Сессия БД
        platform: Платформа (email/phone)
        platform_user_id: Email или телефон
        password: Пароль

    Returns:
        Optional[int]: ID пользователя или None
    """
    # Находим пользователя
    user = await get_user_by_platform(session, platform, platform_user_id)

    if not user:
        logger.warning(f"User not found: {platform}:{platform_user_id}")
        return None

    # Проверяем пароль
    if not user.password_hash:
        logger.warning(f"No password set for user_id={user.id}")
        return None

    if not verify_password(password, user.password_hash):
        logger.warning(f"Invalid password for user_id={user.id}")
        return None

    logger.info(f"User authenticated: user_id={user.id}, platform={platform}")
    return user.id


async def has_password(session: AsyncSession, user_id: int) -> bool:
    """Проверка, установлен ли пароль у пользователя"""
    user = await session.get(User, user_id)
    return user is not None and user.password_hash is not None


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Поиск пользователя по email (email_hash поле)"""
    result = await session.execute(
        select(User).where(User.email_hash == email)
    )
    return result.scalar_one_or_none()


async def get_user_by_phone(session: AsyncSession, phone: str) -> Optional[User]:
    """Поиск пользователя по телефону (phone_hash поле)"""
    # Очищаем телефон от форматирования
    clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if clean_phone.startswith('8'):
        clean_phone = '7' + clean_phone[1:]

    result = await session.execute(
        select(User).where(User.phone_hash == clean_phone)
    )
    return result.scalar_one_or_none()


__all__ = [
    'hash_password',
    'verify_password',
    'set_user_password',
    'verify_user_password',
    'authenticate_by_platform',
    'has_password',
    'get_user_by_email',
    'get_user_by_phone'
]