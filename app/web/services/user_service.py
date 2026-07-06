# services/user_service.py

import logging
from typing import Dict, Any, Optional
from datetime import date

from ..web_client import web_client, AuthPlatform

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями"""

    def __init__(self):
        self.client = web_client

    async def validate_user(
            self,
            platform: str,
            platform_user_id: str,
            password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Проверка существования пользователя"""
        try:
            auth_platform = AuthPlatform(platform)
            result = await self.client.validate_user(
                auth_platform,
                platform_user_id,
                password
            )
            return result
        except ValueError as e:
            return {"success": False, "error": f"Invalid platform: {platform}"}
        except Exception as e:
            logger.error(f"Validate user error: {e}")
            return {"success": False, "error": str(e)}

    async def get_profile(
            self,
            platform: str,
            platform_user_id: str
    ) -> Dict[str, Any]:
        """Получение профиля пользователя"""
        try:
            auth_platform = AuthPlatform(platform)
            result = await self.client.get_user_profile(
                auth_platform,
                platform_user_id
            )
            return result
        except Exception as e:
            logger.error(f"Get profile error: {e}")
            return {"success": False, "error": str(e)}

    async def save_profile(
            self,
            platform: str,
            platform_user_id: str,
            profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Сохранение профиля"""
        try:
            auth_platform = AuthPlatform(platform)
            result = await self.client.save_user_profile(
                platform=auth_platform,
                platform_user_id=platform_user_id,
                **profile_data
            )
            return result
        except Exception as e:
            logger.error(f"Save profile error: {e}")
            return {"success": False, "error": str(e)}

    async def get_recommendations(
            self,
            platform: str,
            platform_user_id: str,
            target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Получение рекомендаций"""
        try:
            auth_platform = AuthPlatform(platform)
            result = await self.client.get_recommendations(
                platform=auth_platform,
                platform_user_id=platform_user_id,
                target_date=target_date
            )
            return result
        except Exception as e:
            logger.error(f"Get recommendations error: {e}")
            return {"success": False, "error": str(e)}

    async def set_password(
            self,
            platform: str,
            platform_user_id: str,
            password: str
    ) -> Dict[str, Any]:
        """Установка пароля"""
        try:
            auth_platform = AuthPlatform(platform)
            result = await self.client.set_password(
                platform=auth_platform,
                platform_user_id=platform_user_id,
                password=password
            )
            return result
        except Exception as e:
            logger.error(f"Set password error: {e}")
            return {"success": False, "error": str(e)}

    async def get_auth_status(
            self,
            platform: str,
            platform_user_id: str
    ) -> Dict[str, Any]:
        """Получение статуса аутентификации"""
        try:
            auth_platform = AuthPlatform(platform)
            result = await self.client.get_auth_status(
                platform=auth_platform,
                platform_user_id=platform_user_id
            )
            return result
        except Exception as e:
            logger.error(f"Get auth status error: {e}")
            return {"success": False, "error": str(e)}