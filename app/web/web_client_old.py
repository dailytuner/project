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


class WebAPIClient:
    """Клиент для веб-интерфейса (поддержка email/phone)"""

    def __init__(self):
        self.base_url = os.getenv("BACKEND_API_URL", "http://backend-api:8000")
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

    # ========== НОВЫЕ МЕТОДЫ ДЛЯ ПАРОЛЬНОЙ АУТЕНТИФИКАЦИИ ==========

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

        async with session.post(
                f"{self.base_url}/api/v1/auth/set-password",
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
                f"{self.base_url}/api/v1/auth/login",
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
                f"{self.base_url}/api/v1/auth/status",
                params={
                    "platform": platform.value,
                    "platform_user_id": platform_user_id
                }
        ) as response:
            return await response.json()

    # ========== СУЩЕСТВУЮЩИЕ МЕТОДЫ (с небольшими изменениями) ==========

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
                f"{self.base_url}/api/v1/user/profile",
                json=payload
        ) as response:
            return await response.json()

    async def validate_user(
            self,
            platform: AuthPlatform,
            platform_user_id: str,
            password: Optional[str] = None  # ✅ НОВЫЙ параметр
    ) -> Dict[str, Any]:
        """Проверка профиля пользователя (опционально с паролем)"""
        session = await self._get_session()

        params = {
            "platform": platform.value,
            "platform_user_id": platform_user_id
        }

        # ✅ Добавляем пароль, если передан
        if password:
            params["password"] = password

        async with session.get(
                f"{self.base_url}/api/v1/user/validate",
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
                f"{self.base_url}/api/v1/user/profile",
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
                f"{self.base_url}/api/v1/optimal-activities",
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
                f"{self.base_url}/api/v1/forecast",
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

        # ========== ФИНАНСОВЫЕ РЕКОМЕНДАЦИИ (исправлено) ==========
        financial_advice = result.get("financial_advice", {})

        if financial_advice and isinstance(financial_advice, dict):
            # Проверяем наличие данных
            has_finance = any([
                financial_advice.get("advice"),
                financial_advice.get("index") is not None,
                financial_advice.get("favorable_actions"),
                financial_advice.get("avoid_actions"),
                financial_advice.get("best_time")
            ])

            if has_finance:
                recommendations.append("")  # пустая строка для отступа
                recommendations.append("💎 ФИНАНСОВЫЙ ПРОГНОЗ:")

                # Индекс
                index_val = financial_advice.get("index")
                if index_val is not None:
                    score_emoji = "🟢" if index_val >= 70 else "🟡" if index_val >= 40 else "🔴"
                    recommendations.append(
                        f"{score_emoji} Индекс: {index_val}% ({financial_advice.get('level', 'medium')})")

                # Основной совет
                advice_text = financial_advice.get("advice", "")
                if advice_text:
                    recommendations.append(f"📊 {advice_text}")

                # Лучшее время
                best_time_finance = financial_advice.get("best_time", "")
                if best_time_finance:
                    recommendations.append(f"🕐 {best_time_finance}")

                # Благоприятные действия
                favorable = financial_advice.get("favorable_actions", [])
                if favorable:
                    rec_line = "✅ Благоприятно: " + ", ".join(favorable[:3])
                    recommendations.append(rec_line)

                # Действия которых стоит избегать
                avoid = financial_advice.get("avoid_actions", [])
                if avoid:
                    rec_line = "❌ Избегай: " + ", ".join(avoid[:3])
                    recommendations.append(rec_line)

                # Подсказка по инвестициям
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

    # =============================================
    # YANDEX OAUTH МЕТОДЫ
    # =============================================

    async def get_yandex_login_url(self) -> Dict[str, Any]:
        """Получить URL для авторизации через Яндекс"""
        session = await self._get_session()

        async with session.get(
                f"{self.base_url}/api/v1/auth/yandex/login"
        ) as response:
            return await response.json()

    async def handle_yandex_callback(self, code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Обработать callback от Яндекса"""
        session = await self._get_session()

        params = {"code": code}
        if state:
            params["state"] = state

        async with session.get(
                f"{self.base_url}/api/v1/auth/yandex/callback",
                params=params
        ) as response:
            return await response.json()

    async def yandex_logout(self, user_id: int) -> Dict[str, Any]:
        """Выйти из Яндекс аккаунта"""
        session = await self._get_session()

        async with session.post(
                f"{self.base_url}/api/v1/auth/yandex/logout",
                params={"user_id": user_id}
        ) as response:
            return await response.json()

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
