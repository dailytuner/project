# user_serices.py
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from .users_auth import AuthPlatform, get_user_by_platform
from .users_repositories import PLATFORM_FIELDS
from .users_queries import get_user_data_for_profile

from ..database.core import async_session
from ..database.models import User, UserProfile
from ..calculators.geocoder import AsyncCityGeocoder

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для управления пользователями с полным циклом"""

    def __init__(self, geocoder: Optional[AsyncCityGeocoder] = None):
        self.geocoder = geocoder

    @asynccontextmanager
    async def _get_session(self, external_session: Optional[AsyncSession] = None):
        """Контекстный менеджер для сессий"""
        if external_session:
            yield external_session
        else:
            session = async_session()
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_or_create_user(
            self,
            platform: AuthPlatform,  # ✅ Изменено на AuthPlatform
            platform_user_id: str,
            session: Optional[AsyncSession] = None
    ) -> User:
        """
        Получить существующего или создать нового пользователя
        """
        async with self._get_session(session) as db_session:
            # Ищем по платформе
            user = await get_user_by_platform(db_session, platform, platform_user_id)
            if user:
                return user

            # ✅ УПРОЩЕНО через PLATFORM_FIELDS
            user = User()
            field_name = PLATFORM_FIELDS[platform]

            # Telegram требует int, остальные str
            if platform == AuthPlatform.TELEGRAM:
                setattr(user, field_name, int(platform_user_id))
            else:
                setattr(user, field_name, platform_user_id)

            user.primary_auth_method = platform.value
            db_session.add(user)
            await db_session.flush()  # Получаем user.id
            await db_session.refresh(user)

            logger.info(f"🆕 Создан новый пользователь: {platform}:{platform_user_id}")
            return user

    async def create_or_update_full_profile(
            self,
            platform: AuthPlatform,  # ✅ AuthPlatform
            platform_user_id: str,
            birth_date: str,
            birth_time: str,
            birth_city: str,
            birth_country: str = "Russia",
            profession: Optional[str] = None,
            current_city: Optional[str] = None,
            job_position: Optional[str] = None,
            session: Optional[AsyncSession] = None
    ) -> Tuple[bool, User, UserProfile]:
        """Полное создание или обновление профиля"""
        async with self._get_session(session) as db_session:
            # Парсим даты
            birth_date_obj = datetime.strptime(birth_date, "%Y-%m-%d").date()
            birth_time_obj = datetime.strptime(birth_time, "%H:%M").time()

            # Получаем или создаем пользователя
            user = await self.get_or_create_user(platform, platform_user_id, db_session)

            # Получаем или создаем профиль
            result = await db_session.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            profile = result.scalar_one_or_none()

            if profile:
                # Обновляем существующий
                profile.birth_date = birth_date_obj
                profile.birth_time = birth_time_obj
                profile.birth_city = birth_city
                profile.birth_country = birth_country
                profile.profession = profession or profile.profession
                profile.current_city = current_city or profile.current_city
                profile.job_position = job_position or profile.job_position
                #profile.updated_at = datetime.utcnow()
                profile.updated_at = datetime.now(timezone.utc)
                created = False
            else:
                # Создаем новый
                profile = UserProfile(
                    user_id=user.id,
                    birth_date=birth_date_obj,
                    birth_time=birth_time_obj,
                    birth_city=birth_city,
                    birth_country=birth_country,
                    profession=profession,
                    current_city=current_city,
                    job_position=job_position
                )
                db_session.add(profile)
                created = True

            # Геокодирование
            if created or not profile.birth_lat:
                await self._geocode_and_update_profile(profile, db_session)

            logger.info(f"{'🆕 Создан' if created else '📝 Обновлен'} профиль {platform}:{platform_user_id}")
            await db_session.commit()
            return (created, user, profile)

    async def _geocode_and_update_profile(
        self,
        profile: UserProfile,
        session: AsyncSession
    ):
        """Геокодирование города и обновление координат"""
        try:
            if not profile.birth_city or not self.geocoder:
                return
            
            coords = await self.geocoder.geocode(
                profile.birth_city,
                country_code=profile.birth_country_code
            )
            
            if coords:
                profile.birth_lat = float(coords.lat) if coords.lat else None
                profile.birth_lng = float(coords.lon) if coords.lon else None
                profile.birth_timezone = coords.timezone
                profile.birth_country_code = coords.country_code
                
                logger.info(
                    f"Геокодирован город {profile.birth_city}: "
                    f"lat={profile.birth_lat}, lng={profile.birth_lng}"
                )
            else:
                logger.warning(f"Не удалось геокодировать город: {profile.birth_city}")
                
        except Exception as e:
            logger.error(f"Ошибка геокодирования для {profile.birth_city}: {e}")

    async def validate_user_profile(
        self,
        platform: AuthPlatform,
        platform_user_id: str
    ) -> Dict[str, Any]:
        """
        Валидация полноты данных пользователя.
        """
        try:
            async with async_session() as session:
                user = await get_user_by_platform(session, platform, platform_user_id)

                if not user:
                    return {
                        'platform': platform,
                        'platform_user_id': platform_user_id,
                        'exists': False,
                        'has_complete_data': False,
                        'missing_fields': ['user_not_found'],
                        'can_calculate': False
                    }

                # Загружаем профиль
                result = await session.execute(
                    select(UserProfile).where(UserProfile.user_id == user.id)
                )
                profile = result.scalar_one_or_none()

                if not profile:
                    return {
                        'user_id': user.id,
                        'exists': True,
                        'has_complete_data': False,
                        'missing_fields': ['profile_not_found'],
                        'can_calculate': False
                    }

                # Проверяем обязательные поля
                required_fields = [
                    ('birth_date', profile.birth_date),
                    ('birth_time', profile.birth_time),
                    ('birth_city', profile.birth_city),
                    ('profession', profile.profession)
                ]

                missing = [field for field, value in required_fields if not value]

                return {
                    'user_id': user.id,
                    'exists': True,
                    'has_complete_data': len(missing) == 0,
                    'missing_fields': missing,
                    'can_calculate': len(missing) == 0
                }

        except Exception as e:
            logger.error(f"❌ Ошибка валидации {platform}:{platform_user_id}: {e}")
            return {
                'exists': False,
                'has_complete_data': False,
                'missing_fields': ['validation_error'],
                'can_calculate': False
            }

    async def get_complete_user_data(
        self,
        platform: str,
        platform_user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Получение всех данных пользователя в одном запросе"""
        try:
            async with async_session() as session:
                user = await get_user_by_platform(session, platform, platform_user_id)
                
                if not user:
                    return None
                
                # Используем готовый запрос из queries
                return await get_user_data_for_profile(session, user.id)
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения данных {platform}:{platform_user_id}: {e}")
            return None

    async def get_user_profile_by_id(
            self,
            user_id: int,
            include_extended: bool = False,
            session: Optional[AsyncSession] = None
    ) -> Optional[Dict[str, Any]]:
        """Получение профиля пользователя по user_id (без platform)"""
        async with self._get_session(session) as db_session:
            try:
                # Получаем пользователя по ID
                user = await db_session.get(User, user_id)
                if not user:
                    logger.warning(f"Пользователь user_id={user_id} не найден")
                    return None

                # Получаем профиль
                result = await db_session.execute(
                    select(UserProfile).where(UserProfile.user_id == user.id)
                )
                profile = result.scalar_one_or_none()
                if not profile:
                    return None

                # Базовые поля
                data = {
                    'user_id': user.id,
                    'birth_date': profile.birth_date,
                    'birth_time': profile.birth_time.strftime("%H:%M") if profile.birth_time else None,
                    'birth_city': profile.birth_city,
                    'birth_country': profile.birth_country,
                    'profession': profile.profession,
                    'current_city': profile.current_city,
                    'job_position': profile.job_position,
                    'created_at': profile.created_at.isoformat() if profile.created_at else None,
                    'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
                    'has_geodata': bool(profile.birth_lat and profile.birth_lng)
                }

                # Расширенные поля
                if include_extended:
                    data.update({
                        'birth_lat': float(profile.birth_lat) if profile.birth_lat else None,
                        'birth_lng': float(profile.birth_lng) if profile.birth_lng else None,
                        'birth_timezone': profile.birth_timezone,
                        'birth_country_code': profile.birth_country_code,
                        'system_language': profile.system_language,
                        'current_lat': float(profile.current_lat) if profile.current_lat else None,
                        'current_lng': float(profile.current_lng) if profile.current_lng else None,
                    })

                return data

            except Exception as e:
                logger.error(f"Ошибка получения профиля user_id={user_id}: {e}")
                return None

    async def validate_user_profile_by_id(
            self,
            user_id: int
    ) -> Dict[str, Any]:
        """Валидация профиля по user_id"""
        try:
            async with async_session() as session:
                user = await session.get(User, user_id)
                if not user:
                    return {
                        'user_id': user_id,
                        'exists': False,
                        'has_complete_data': False,
                        'missing_fields': ['user_not_found'],
                        'can_calculate': False
                    }

                # Загружаем профиль
                result = await session.execute(
                    select(UserProfile).where(UserProfile.user_id == user.id)
                )
                profile = result.scalar_one_or_none()

                if not profile:
                    return {
                        'user_id': user.id,
                        'exists': True,
                        'has_complete_data': False,
                        'missing_fields': ['profile_not_found'],
                        'can_calculate': False
                    }

                # Проверяем обязательные поля
                required_fields = [
                    ('birth_date', profile.birth_date),
                    ('birth_time', profile.birth_time),
                    ('birth_city', profile.birth_city),
                    ('profession', profile.profession)
                ]

                missing = [field for field, value in required_fields if not value]

                return {
                    'user_id': user.id,
                    'exists': True,
                    'has_complete_data': len(missing) == 0,
                    'missing_fields': missing,
                    'can_calculate': len(missing) == 0
                }

        except Exception as e:
            logger.error(f"❌ Ошибка валидации user_id={user_id}: {e}")
            return {
                'user_id': user_id,
                'exists': False,
                'has_complete_data': False,
                'missing_fields': ['validation_error'],
                'can_calculate': False
            }

    async def get_user_by_id(
            self,
            user_id: int,
            session: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """Получение пользователя по ID"""
        async with self._get_session(session) as db_session:
            return await db_session.get(User, user_id)

    async def get_user_profile(
        self,
        platform: AuthPlatform,
        platform_user_id: str,
        include_extended: bool = False,
        session: Optional[AsyncSession] = None
    ) -> Optional[Dict[str, Any]]:
        """Получение полного профиля пользователя"""
        async with self._get_session(session) as db_session:
            try:
                user = await get_user_by_platform(db_session, platform, platform_user_id)

                if not user:
                    return None

                # Загружаем профиль
                result = await db_session.execute(
                    select(UserProfile).where(UserProfile.user_id == user.id)
                )
                profile = result.scalar_one_or_none()

                if not profile:
                    return None

                # Базовые поля
                data = {
                    'user_id': user.id,
                    'platform': platform,
                    'platform_user_id': platform_user_id,
                    'birth_date': profile.birth_date,
                    'birth_time': profile.birth_time.strftime("%H:%M") if profile.birth_time else None,
                    'birth_city': profile.birth_city,
                    'birth_country': profile.birth_country,
                    'profession': profile.profession,
                    'current_city': profile.current_city,
                    'job_position': profile.job_position,
                    'created_at': profile.created_at.isoformat() if profile.created_at else None,
                    'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
                    'has_geodata': bool(profile.birth_lat and profile.birth_lng)
                }

                # Расширенные поля (геоданные)
                if include_extended:
                    data.update({
                        'birth_lat': float(profile.birth_lat) if profile.birth_lat else None,
                        'birth_lng': float(profile.birth_lng) if profile.birth_lng else None,
                        'birth_timezone': profile.birth_timezone,
                        'birth_country_code': profile.birth_country_code,
                        'system_language': profile.system_language,
                        'current_lat': float(profile.current_lat) if profile.current_lat else None,
                        'current_lng': float(profile.current_lng) if profile.current_lng else None,
                    })

                return data

            except Exception as e:
                logger.error(f"Ошибка получения профиля {platform}:{platform_user_id}: {e}")
                return None

    async def has_password(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            session: Optional[AsyncSession] = None
    ) -> bool:
        """Проверка, установлен ли пароль у пользователя"""
        from .password_auth import has_password

        async with self._get_session(session) as db_session:
            user = await get_user_by_platform(db_session, platform, platform_user_id)
            if not user:
                return False
            return await has_password(db_session, user.id)

    async def set_password(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            password: str,
            session: Optional[AsyncSession] = None
    ) -> bool:
        """Установка пароля для пользователя"""
        from .password_auth import set_user_password

        async with self._get_session(session) as db_session:
            user = await get_user_by_platform(db_session, platform, platform_user_id)
            if not user:
                raise ValueError(f"User not found: {platform}:{platform_user_id}")

            return await set_user_password(db_session, user.id, password)

    async def authenticate(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            password: str,
            session: Optional[AsyncSession] = None
    ) -> Optional[int]:
        """Аутентификация пользователя по паролю"""
        from .password_auth import authenticate_by_platform

        async with self._get_session(session) as db_session:
            return await authenticate_by_platform(
                db_session, platform, platform_user_id, password
            )


    async def get_user_by_email(
            self,
            email: str,
            session: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """Поиск пользователя по email"""
        from .password_auth import get_user_by_email

        async with self._get_session(session) as db_session:
            return await get_user_by_email(db_session, email)

    async def get_user_by_phone(
            self,
            phone: str,
            session: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """Поиск пользователя по телефону"""
        from .password_auth import get_user_by_phone

        async with self._get_session(session) as db_session:
            return await get_user_by_phone(db_session, phone)


# Синглтон для удобства использования
user_service = UserService(geocoder=AsyncCityGeocoder())
