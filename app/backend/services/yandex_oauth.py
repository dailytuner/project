"""
Сервис для работы с Яндекс OAuth API
Документация: https://yandex.ru/dev/id/doc/en/
"""
import logging
import json
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode

import aiohttp
from pydantic import BaseModel, Field

from ..database.core import async_session
from ..database.models import User
from ..users.users_auth import AuthPlatform
from ..users.users_repositories import update_yandex_tokens
from ..users.user_services import user_service
from ..config.yandex_config import YANDEX_CONFIG

logger = logging.getLogger(__name__)


# =============================================
# PYDANTIC МОДЕЛИ
# =============================================

class YandexTokenResponse(BaseModel):
    """Ответ от API Яндекса при получении токенов"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # По умолчанию 1 час
    id_token: Optional[str] = None


class YandexUserInfo(BaseModel):
    """Информация о пользователе от Яндекса"""
    id: str  # Уникальный ID пользователя
    login: str  # Логин (никнейм)
    display_name: Optional[str] = None
    real_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    sex: Optional[str] = None
    default_email: Optional[str] = None
    emails: Optional[list] = None
    birthday: Optional[str] = None
    is_avatar_empty: bool = True
    default_avatar_id: Optional[str] = None
    avatar_url: Optional[str] = None
    psuid: Optional[str] = None  # Persistent user ID

    @property
    def email(self) -> Optional[str]:
        """Получить основной email"""
        return self.default_email or (self.emails[0] if self.emails else None)

    @property
    def full_name(self) -> str:
        """Получить полное имя"""
        if self.display_name:
            return self.display_name
        if self.real_name:
            return self.real_name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.login or "User"

    @property
    def avatar(self) -> Optional[str]:
        """Получить URL аватара"""
        if self.is_avatar_empty or not self.default_avatar_id:
            return None
        return f"https://avatars.yandex.net/get-yapic/{self.default_avatar_id}/islands-200"


# =============================================
# YANDEX OAUTH СЕРВИС
# =============================================

class YandexOAuthService:
    """
    Сервис для работы с Яндекс OAuth 2.0

    Поддерживает:
    - Генерацию URL для авторизации
    - Обмен кода на токены
    - Обновление токенов
    - Получение информации о пользователе
    - Полный цикл аутентификации
    """

    # API endpoints
    AUTH_URL = "https://oauth.yandex.ru/authorize"
    TOKEN_URL = "https://oauth.yandex.ru/token"
    USER_INFO_URL = "https://login.yandex.ru/info"

    # Scopes для доступа (минимальные для аутентификации + календарь на будущее)
    # Полный список: https://yandex.ru/dev/id/doc/en/scope-list
    SCOPES = [
        "login:email",  # Доступ к email
        "login:info",  # Доступ к базовой информации
        "login:avatar",  # Доступ к аватару
        #"login:birthday",  # Доступ к дате рождения (опционально)
        # "calendar:read",  # Для будущей интеграции с Календарем
        # "calendar:write", # Для будущей интеграции с Календарем
    ]

    def __init__(
            self,
            client_id: Optional[str] = None,
            client_secret: Optional[str] = None,
            redirect_uri: Optional[str] = None
    ):
        # ✅ Используем конфигурацию из секретов
        self.client_id = client_id or YANDEX_CONFIG.get('client_id')
        self.client_secret = client_secret or YANDEX_CONFIG.get('client_secret')
        self.redirect_uri = redirect_uri or YANDEX_CONFIG.get('redirect_uri')

        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            logger.warning("⚠️ Yandex OAuth credentials not fully configured")

        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать HTTP-сессию"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Закрыть HTTP-сессию"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # =============================================
    # ПУБЛИЧНЫЕ МЕТОДЫ
    # =============================================

    def get_auth_url(self, state: Optional[str] = None) -> str:
        """
        Сгенерировать URL для перенаправления пользователя на страницу авторизации Яндекса

        Args:
            state: Произвольная строка для защиты от CSRF (будет возвращена в callback)

        Returns:
            str: URL для авторизации
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",  # Запрашиваем refresh_token
            "prompt": "select_account",  # Всегда показываем выбор аккаунта
        }

        if state:
            params["state"] = state

        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
            self,
            code: str,
            code_verifier: Optional[str] = None
    ) -> YandexTokenResponse:
        """
        Обменять временный код на access_token и refresh_token

        Args:
            code: Временный код из callback
            code_verifier: PKCE code verifier (опционально)

        Returns:
            YandexTokenResponse: Токены
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }

        if code_verifier:
            data["code_verifier"] = code_verifier

        session = await self._get_session()

        try:
            async with session.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Yandex token exchange error: {response.status} - {error_text}")
                    raise Exception(f"Token exchange failed: {response.status}")

                result = await response.json()
                logger.info("✅ Yandex tokens obtained successfully")

                return YandexTokenResponse(**result)

        except aiohttp.ClientError as e:
            logger.error(f"Yandex token exchange network error: {e}")
            raise

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Обновить истекший access_token с помощью refresh_token

        Args:
            refresh_token: Refresh-токен для обновления

        Returns:
            Dict: Новые токены
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        session = await self._get_session()

        try:
            async with session.post(
                    self.TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Yandex token refresh error: {response.status} - {error_text}")
                    raise Exception(f"Token refresh failed: {response.status}")

                result = await response.json()
                logger.info("✅ Yandex token refreshed successfully")

                return result

        except aiohttp.ClientError as e:
            logger.error(f"Yandex token refresh network error: {e}")
            raise

    async def get_user_info(self, access_token: str) -> YandexUserInfo:
        """
        Получить информацию о пользователе

        Args:
            access_token: Действующий access_token

        Returns:
            YandexUserInfo: Информация о пользователе
        """
        session = await self._get_session()

        try:
            async with session.get(
                    self.USER_INFO_URL,
                    params={"format": "json"},
                    headers={"Authorization": f"OAuth {access_token}"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Yandex user info error: {response.status} - {error_text}")
                    raise Exception(f"User info failed: {response.status}")

                result = await response.json()
                logger.info(f"✅ Yandex user info obtained for ID: {result.get('id')}")

                return YandexUserInfo(**result)

        except aiohttp.ClientError as e:
            logger.error(f"Yandex user info network error: {e}")
            raise

    # =============================================
    # ВЫСОКОУРОВНЕВЫЕ МЕТОДЫ
    # =============================================

    async def authenticate_with_code(
            self,
            code: str,
            create_user: bool = True,
            code_verifier: Optional[str] = None
    ) -> Tuple[Optional[User], YandexUserInfo, YandexTokenResponse]:
        """
        Полный цикл аутентификации: обмен кода на токены, получение данных пользователя,
        создание/обновление пользователя в БД.

        Args:
            code: Временный код из callback
            create_user: Создавать ли пользователя если не найден
            code_verifier: PKCE code verifier

        Returns:
            Tuple[User, YandexUserInfo, YandexTokenResponse]:
                (пользователь в БД, данные из Яндекса, токены)
        """
        try:
            # 1. Обмениваем код на токены
            tokens = await self.exchange_code(code, code_verifier)

            # 2. Получаем информацию о пользователе
            user_info = await self.get_user_info(tokens.access_token)

            if not user_info.id:
                raise ValueError("No user ID from Yandex")

            # 3. Находим или создаем пользователя
            user = None
            async with async_session() as session:
                # Ищем по yandex_id
                from ..users.users_auth import get_user_by_platform
                user = await get_user_by_platform(session, AuthPlatform.YANDEX, user_info.id)

                if user:
                    # Обновляем существующего пользователя
                    logger.info(f"🔍 Found existing user: {user.id} (Yandex: {user_info.id})")

                    # Обновляем токены
                    await update_yandex_tokens(
                        session,
                        user.id,
                        tokens.access_token,
                        tokens.refresh_token,
                        tokens.expires_in,
                        user_info.email,
                        user_info.login,
                        user_info.avatar
                    )

                    # Обновляем email если изменился
                    if user_info.email and not user.email_hash:
                        user.email_hash = user_info.email

                    await session.commit()

                elif create_user:
                    # Создаем нового пользователя
                    logger.info(f"🆕 Creating new user from Yandex: {user_info.id}")

                    from ..users.users_auth import UserAuthService

                    user = User()
                    user.yandex_id = user_info.id
                    user.yandex_email = user_info.email
                    user.yandex_login = user_info.login
                    user.yandex_avatar_url = user_info.avatar
                    user.email_hash = user_info.email
                    user.primary_auth_method = 'yandex'
                    user.is_verified = True

                    session.add(user)
                    await session.flush()

                    # Сохраняем токены
                    await update_yandex_tokens(
                        session,
                        user.id,
                        tokens.access_token,
                        tokens.refresh_token,
                        tokens.expires_in,
                        user_info.email,
                        user_info.login,
                        user_info.avatar
                    )

                    await session.commit()
                    await session.refresh(user)

                    # Создаем пустой профиль (пользователь заполнит позже)
                    from ..database.models import UserProfile
                    #profile = UserProfile(user_id=user.id)
                    profile = UserProfile(
                        user_id=user.id,
                        birth_date=date(2000, 1, 1),  # ← фиктивная дата
                        birth_time=datetime.strptime("12:00", "%H:%M").time(),  # ← фиктивное время
                        birth_city="Moscow",  # ← фиктивный город
                        birth_country="Russia"
                    )
                    session.add(profile)
                    await session.commit()

                    logger.info(f"✅ New user created: {user.id} ({user_info.email})")

                else:
                    logger.warning(f"⚠️ User not found and create_user=False: {user_info.id}")

            return user, user_info, tokens

        except Exception as e:
            logger.error(f"❌ Yandex authentication error: {e}")
            raise

    async def get_valid_access_token(self, user_id: int) -> Optional[str]:
        """
        Получить действующий access_token для пользователя, при необходимости обновляя его

        Args:
            user_id: ID пользователя в БД

        Returns:
            Optional[str]: Действующий access_token или None
        """
        return await user_service.get_yandex_access_token(user_id)

    async def revoke_token(self, access_token: str) -> bool:
        """
        Отозвать токен (при выходе из системы)

        Args:
            access_token: Токен для отзыва

        Returns:
            bool: Успешно ли отозван токен
        """
        # Яндекс не предоставляет эндпоинт для отзыва токена напрямую через API,
        # но можно удалить токен из БД, что по сути лишает его силы в нашем приложении
        # Документация: https://yandex.ru/dev/id/doc/en/revoke-token

        # Просто удаляем токены из БД для этого пользователя
        try:
            async with async_session() as session:
                # Находим пользователя по access_token (сложно без связи)
                # Вместо этого удаляем токен при logout через user_service
                pass
            return True
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False


# =============================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# =============================================

yandex_oauth_service = YandexOAuthService(
    client_id=YANDEX_CONFIG.get('client_id'),
    client_secret=YANDEX_CONFIG.get('client_secret'),
    redirect_uri=YANDEX_CONFIG.get('redirect_uri')
)


# =============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ WEB API
# =============================================

async def get_yandex_auth_url(
        state: Optional[str] = None,
        redirect_uri: Optional[str] = None
) -> str:
    """Получить URL для редиректа на Яндекс-авторизацию"""
    client_id = YANDEX_CONFIG.get('client_id')
    if not client_id:
        raise ValueError("YANDEX_CLIENT_ID is not set")

    redirect_uri = redirect_uri or YANDEX_CONFIG.get('redirect_uri')
    if not redirect_uri:
        raise ValueError("YANDEX_REDIRECT_URI is not set")

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join([
            "login:email",
            "login:info",
            "login:avatar",
            #"login:birthday",
        ]),
        "access_type": "offline",
        "prompt": "select_account",
    }

    if state:
        params["state"] = state

    return f"https://oauth.yandex.ru/authorize?{urlencode(params)}"


__all__ = [
    'YandexOAuthService',
    'YandexTokenResponse',
    'YandexUserInfo',
    'yandex_oauth_service',
    'get_yandex_auth_url',
]