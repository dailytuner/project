"""Веб-клиент для взаимодействия с backend API (через email/phone)"""
import aiohttp
import os
import logging
from typing import Dict, Any, Optional
from datetime import date
from enum import Enum

logger = logging.getLogger(__name__)


class AuthPlatform(str, Enum):
    """Платформы авторизации (совпадает с backend)"""
    TELEGRAM = 'telegram'
    MAX = 'max'
    UDEMY = 'udemy'
    GOOGLE = 'google'
    APPLE = 'apple'
    PHONE = 'phone'
    EMAIL = 'email'
    YANDEX = 'yandex'


class WebAPIClient:
    """Клиент для веб-интерфейса (поддержка email/phone)"""

    def __init__(self):
        #self.base_url = os.getenv("BACKEND_API_URL", "http://backend-api:8000/api")
        self.base_url = os.getenv("BACKEND_API_URL", "http://backend-api:8000/api/v1")
        self.api_key_file = os.getenv("API_KEY_FILE", "/run/secrets/backend-api-key")
        self.api_key = self._load_api_key()
        self._session = None

    def _load_api_key(self) -> str:
        """Загрузка API ключа"""
        if os.path.exists(self.api_key_file):
            try:
                with open(self.api_key_file, 'r') as f:
                    return f.read().strip()
            except Exception as e:
                logger.error(f"Failed to read API key: {e}")
        return os.getenv("BACKEND_API_KEY", "")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получение сессии"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json"
                }
            )
        return self._session

    # ========== МЕТОДЫ ДЛЯ ПАРОЛЬНОЙ АУТЕНТИФИКАЦИИ ==========

    async def set_password(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            password: str
    ) -> Dict[str, Any]:
        """Установка пароля для пользователя"""
        session = await self._get_session()

        payload = {
            "platform": platform.value,
            "platform_user_id": platform_user_id,
            "password": password
        }

        # ✅ Убираем /api/v1, так как base_url уже содержит его
        async with session.post(
                f"{self.base_url}/auth/set-password",  # ← /api/v1 уже в base_url
                json=payload
        ) as response:
            return await response.json()

    async def login(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            password: str
    ) -> Dict[str, Any]:
        """Вход с паролем"""
        session = await self._get_session()

        payload = {
            "platform": platform.value,
            "platform_user_id": platform_user_id,
            "password": password
        }

        async with session.post(
                f"{self.base_url}/auth/login",  # ← /api/v1 уже в base_url
                json=payload
        ) as response:
            return await response.json()

    async def get_auth_status(
            self,
            platform: AuthPlatform,
            platform_user_id: str
    ) -> Dict[str, Any]:
        """Проверка статуса аутентификации (есть ли пароль)"""
        session = await self._get_session()

        async with session.get(
                f"{self.base_url}/auth/status",  # ← /api/v1 уже в base_url
                params={
                    "platform": platform.value,
                    "platform_user_id": platform_user_id
                }
        ) as response:
            return await response.json()

    # ========== ОСНОВНЫЕ МЕТОДЫ ==========

    async def save_user_profile(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            **profile_data
    ) -> Dict[str, Any]:
        """Сохранение профиля пользователя"""
        session = await self._get_session()

        payload = {
            "request": {
                "platform": platform.value,
                "platform_user_id": platform_user_id
            },
            "profile": {k: str(v) for k, v in profile_data.items() if v}
        }

        logger.info(f"Saving profile for {platform.value}: {platform_user_id}")

        async with session.post(
                f"{self.base_url}/user/profile",  # ← /api/v1 уже в base_url
                json=payload
        ) as response:
            return await response.json()

    async def validate_user(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            password: Optional[str] = None
    ) -> Dict[str, Any]:
        """Проверка профиля пользователя (опционально с паролем)"""
        session = await self._get_session()

        params = {
            "platform": platform.value,
            "platform_user_id": platform_user_id
        }

        if password:
            params["password"] = password

        async with session.get(
                f"{self.base_url}/user/validate",  # ← /api/v1 уже в base_url
                params=params
        ) as response:
            return await response.json()

    async def get_user_profile(
            self,
            platform: AuthPlatform,
            platform_user_id: str
    ) -> Dict[str, Any]:
        """Получение профиля пользователя"""
        session = await self._get_session()

        params = {
            "platform": platform.value,
            "platform_user_id": platform_user_id
        }

        async with session.get(
                f"{self.base_url}/user/profile",  # ← /api/v1 уже в base_url
                params=params
        ) as response:
            return await response.json()

    async def get_optimal_activities(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Получение оптимальных активностей"""
        session = await self._get_session()

        payload = {
            "platform": platform.value,
            "platform_user_id": platform_user_id
        }
        if target_date:
            payload["date"] = target_date.isoformat()

        async with session.post(
                f"{self.base_url}/optimal-activities",  # ← /api/v1 уже в base_url
                json=payload
        ) as response:
            return await response.json()

    async def get_recommendations(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Получение рекомендаций (через новый forecast API)"""
        session = await self._get_session()

        params = {
            "platform": platform.value,
            "platform_user_id": platform_user_id
        }
        if target_date:
            params["forecast_date"] = target_date.isoformat()

        async with session.get(
                f"{self.base_url}/forecast",  # ← /api/v1 уже в base_url
                params=params
        ) as response:
            result = await response.json()

        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }

        # Получаем оси
        axes = result.get("axes", [])

        # Находим уровень энергии (ось energy_will)
        energy_level = 0.5
        for axis in axes:
            if isinstance(axis, dict):
                axis_name = axis.get("name")
                daily_val = axis.get("daily_value", 0.5)
            else:
                axis_name = getattr(axis, "name", None)
                daily_val = getattr(axis, "daily_value", 0.5)

            if axis_name == "energy_will":
                energy_level = daily_val
                break

        # Формируем рекомендации
        recommendations = []

        # Основной совет
        top_advice = result.get("top_advice", "")
        if top_advice:
            recommendations.append(f"⭐ {top_advice}")

        # Предупреждения
        caution_advice = result.get("caution_advice", "")
        if caution_advice and caution_advice != "✅ Особых предостережений нет":
            recommendations.append(f"⚠️ {caution_advice}")

        # Сводка
        summary = result.get("summary", "")
        if summary and summary != "➡️ Нейтральный день":
            recommendations.append(f"📌 {summary}")

        # Финансовые рекомендации
        financial_advice = result.get("financial_advice", {})

        if financial_advice and isinstance(financial_advice, dict):
            has_finance = any([
                financial_advice.get("advice"),
                financial_advice.get("index") is not None,
                financial_advice.get("favorable_actions"),
                financial_advice.get("avoid_actions"),
                financial_advice.get("best_time")
            ])

            if has_finance:
                recommendations.append("")
                recommendations.append("💎 ФИНАНСОВЫЙ ПРОГНОЗ:")

                index_val = financial_advice.get("index")
                if index_val is not None:
                    score_emoji = "🟢" if index_val >= 70 else "🟡" if index_val >= 40 else "🔴"
                    recommendations.append(
                        f"{score_emoji} Индекс: {index_val}% ({financial_advice.get('level', 'medium')})")

                advice_text = financial_advice.get("advice", "")
                if advice_text:
                    recommendations.append(f"📊 {advice_text}")

                best_time_finance = financial_advice.get("best_time", "")
                if best_time_finance:
                    recommendations.append(f"🕐 {best_time_finance}")

                favorable = financial_advice.get("favorable_actions", [])
                if favorable:
                    rec_line = "✅ Благоприятно: " + ", ".join(favorable[:3])
                    recommendations.append(rec_line)

                avoid = financial_advice.get("avoid_actions", [])
                if avoid:
                    rec_line = "❌ Избегай: " + ", ".join(avoid[:3])
                    recommendations.append(rec_line)

                invest_hint = financial_advice.get("investment_hint", "")
                if invest_hint:
                    recommendations.append(f"💡 {invest_hint}")

        activities_text = "\n".join(recommendations) if recommendations else "Нет рекомендаций на этот день"

        # Форматируем дату
        forecast_date = result.get("forecast_date")
        if forecast_date:
            date_obj = date.fromisoformat(forecast_date) if isinstance(forecast_date, str) else forecast_date
            date_formatted = date_obj.strftime("%d.%m.%Y")
        else:
            date_formatted = (target_date or date.today()).strftime("%d.%m.%Y")

        return {
            "success": True,
            "energy_level": energy_level,
            "date": (target_date or date.today()).isoformat(),
            "date_formatted": date_formatted,
            "recommendations_text": activities_text,
            "energy_percent": round(energy_level * 100),
            "summary": summary,
            "warnings": caution_advice,
            "financial_advice": financial_advice
        }

    async def create_yandex_user(
            self,
            yandex_id: str,
            email: str,
            login: str,
            access_token: str,
            expires_at: str,
            refresh_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создание или получение пользователя через Яндекс OAuth."""
        #logger.info("=" * 60)
        #logger.info("🔵 STEP 3.1: WEB_CLIENT CREATE YANDEX USER")
        #logger.info(f"📤 Payload to backend:")
        #logger.info(f"   - platform: {AuthPlatform.YANDEX.value}")
        #logger.info(f"   - platform_user_id: {yandex_id}")
        #logger.info(f"   - email: {email}")
        #logger.info(f"   - login: {login}")
        #logger.info(f"   - access_token: {access_token[:20]}...")
        #logger.info(f"   - expires_at: {expires_at}")
        #logger.info(f"   - refresh_token: {refresh_token}")
        #logger.info(f"📤 URL: {self.base_url}/user/yandex")

        session = await self._get_session()

        payload = {
            "platform": AuthPlatform.YANDEX.value,
            "platform_user_id": yandex_id,
            "email": email,
            "login": login,
            "access_token": access_token,
            "expires_at": expires_at
        }

        if refresh_token:
            payload["refresh_token"] = refresh_token
            logger.info(f"   - refresh_token included: {refresh_token}")

        logger.info(f"📦 Full payload: {payload}")

        async with session.post(
                f"{self.base_url}/user/yandex",
                json=payload
        ) as response:
            result = await response.json()
            logger.info(f"📥 Backend response status: {response.status}")
            logger.info(f"📥 Backend response body: {result}")
            logger.info("=" * 60)

            if result.get("success"):
                logger.info(f"✅ Yandex user processed: ID={result.get('user_id')}")
            else:
                logger.error(f"❌ Failed to process yandex user: {result}")

            return result



    async def close(self):
        """Закрытие сессии"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


# Глобальный экземпляр
web_client = WebAPIClient()
