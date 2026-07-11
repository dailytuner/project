# web/services/yandex_service.py
import os
import json
import logging
from typing import Dict, Optional
from urllib.parse import urlencode
import aiohttp
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class YandexOAuthService:
    """Сервис для авторизации через Яндекс OAuth"""

    def __init__(self):
        # Загружаем из файлов, указанных в переменных окружения
        self.client_id = self._load_secret_from_env("YANDEX_CLIENT_ID_FILE")
        self.client_secret = self._load_secret_from_env("YANDEX_CLIENT_SECRET_FILE")
        self.redirect_uri = self._load_secret_from_env("YANDEX_REDIRECT_URI_FILE")

        # Если не загрузилось, пробуем напрямую из переменных (для разработки)
        if not self.client_id:
            self.client_id = os.getenv("YANDEX_CLIENT_ID")
        if not self.client_secret:
            self.client_secret = os.getenv("YANDEX_CLIENT_SECRET")
        if not self.redirect_uri:
            self.redirect_uri = os.getenv("YANDEX_REDIRECT_URI", "https://dailytuner.ru/auth/yandex/callback")

        # Проверяем наличие credentials
        if not self.client_id or not self.client_secret:
            logger.warning(
                "Yandex OAuth credentials not configured. "
                "Set YANDEX_CLIENT_ID_FILE and YANDEX_CLIENT_SECRET_FILE environment variables "
                "or mount secrets to /run/secrets/"
            )

        self.auth_url = "https://oauth.yandex.ru/authorize"
        self.token_url = "https://oauth.yandex.ru/token"
        self.user_info_url = "https://login.yandex.ru/info"

    def _load_secret_from_env(self, env_var: str) -> Optional[str]:
        """Загрузка секрета из файла, указанного в переменной окружения"""
        file_path = os.getenv(env_var)
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    value = f.read().strip()
                    if value:
                        logger.info(f"Loaded secret from {file_path}")
                        return value
            except Exception as e:
                logger.error(f"Failed to load secret from {file_path}: {e}")
        return None

    def get_auth_url(self, state: str) -> str:
        """Генерация URL для редиректа на Яндекс"""
        if not self.client_id:
            raise HTTPException(
                status_code=500,
                detail="Yandex OAuth not configured: missing client_id"
            )

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "scope": "login:email login:info"  # Запрашиваем email и основные данные
        }
        return f"{self.auth_url}?{urlencode(params)}"

    async def get_token(self, code: str) -> str:
        """Обмен кода на access token"""
        if not self.client_id or not self.client_secret:
            raise HTTPException(
                status_code=500,
                detail="Yandex OAuth not configured"
            )

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    self.token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Yandex token error: {error_text}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to get token: {error_text}"
                    )

                result = await response.json()
                return result.get("access_token")

    async def get_user_info(self, token: str) -> Dict:
        """Получение информации о пользователе"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    self.user_info_url,
                    params={"format": "json"},
                    headers={"Authorization": f"OAuth {token}"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Yandex user info error: {error_text}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to get user info: {error_text}"
                    )

                return await response.json()

    async def authenticate(self, code: str) -> Dict:
        """Полный процесс аутентификации через Яндекс"""
        #logger.info("=" * 60)
        #logger.info("🔵 STEP 2.1: YANDEX AUTHENTICATE")
        #logger.info(f"📥 Code: {code}")

        try:
            # 1. Получаем токен
            #logger.info("🔄 Getting access token...")
            token = await self.get_token(code)
            #logger.info(f"✅ Access token received: {token[:20]}...")

            # 2. Получаем информацию о пользователе
            #logger.info("🔄 Getting user info...")
            user_data = await self.get_user_info(token)
            #logger.info(f"📦 Raw user_data: {user_data}")

            email = user_data.get("default_email")
            yandex_id = user_data.get("id")
            login = user_data.get("login")

            #logger.info(f"👤 User info extracted:")
            #logger.info(f"   - id: {yandex_id}")
            #logger.info(f"   - email: {email}")
            #logger.info(f"   - login: {login}")
            #logger.info(f"   - first_name: {user_data.get('first_name')}")
            #logger.info(f"   - last_name: {user_data.get('last_name')}")

            result = {
                "success": True,
                "yandex_id": yandex_id,
                "email": email,
                "login": login,
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
                "full_name": f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                "access_token": token,
                "refresh_token": None,
                "expires_in": 3600,
                "raw_data": user_data
            }

            #logger.info(f"✅ Return result: {result}")
            #logger.info("=" * 60)

            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Yandex authentication error: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Authentication failed: {str(e)}"
            )


# Глобальный экземпляр
yandex_service = YandexOAuthService()
