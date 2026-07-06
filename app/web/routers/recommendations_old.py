# routers/recommendations.py

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import date
import logging

from ..services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["recommendations"])
user_service = UserService()

@router.get("/validate")
async def validate_user(platform: str, platform_user_id: str, password: str = None):
    """Проверка пользователя"""
    result = await user_service.validate_user(platform, platform_user_id, password)
    return JSONResponse(result)

@router.get("/recommendations")
async def get_recommendations(platform: str, platform_user_id: str, date: str = None):
    """Получение рекомендаций"""
    try:
        target_date = date.fromisoformat(date) if date else None
        result = await user_service.get_recommendations(
            platform=platform,
            platform_user_id=platform_user_id,
            target_date=target_date
        )
        return JSONResponse(result)
    except ValueError:
        return JSONResponse({"success": False, "error": "Invalid date format"})
    except Exception as e:
        logger.error(f"Get recommendations error: {e}")
        return JSONResponse({"success": False, "error": str(e)})

@router.get("/forecast")
async def get_forecast(
    platform: str,
    platform_user_id: str,
    forecast_date: str = None,
    force_recalculate: bool = False
):
    """Получение прогноза"""
    try:
        target_date = date.fromisoformat(forecast_date) if forecast_date else None
        result = await user_service.get_recommendations(
            platform=platform,
            platform_user_id=platform_user_id,
            target_date=target_date
        )
        return JSONResponse(result)
    except ValueError:
        return JSONResponse({"success": False, "error": "Invalid date format"})
    except Exception as e:
        logger.error(f"Get forecast error: {e}")
        return JSONResponse({"success": False, "error": str(e)})
