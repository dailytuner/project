# web/routers/recommendations.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import datetime, date
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
        target_date = None
        if date:
            #  конвертации
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                return JSONResponse({
                    "success": False,
                    "error": "Invalid date format. Use YYYY-MM-DD"
                })

        result = await user_service.get_recommendations(
            platform=platform,
            platform_user_id=platform_user_id,
            target_date=target_date
        )
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Get recommendations error: {e}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        })


@router.get("/forecast")
async def get_forecast(
        platform: str,
        platform_user_id: str,
        forecast_date: str = None,
        force_recalculate: bool = False
):
    """Получение прогноза"""
    try:
        target_date = None
        if forecast_date:
            try:
                target_date = datetime.strptime(forecast_date, "%Y-%m-%d").date()
            except ValueError:
                return JSONResponse({
                    "success": False,
                    "error": "Invalid date format. Use YYYY-MM-DD"
                })

        result = await user_service.get_recommendations(
            platform=platform,
            platform_user_id=platform_user_id,
            target_date=target_date
        )
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Get forecast error: {e}", exc_info=True)
        return JSONResponse({
            "success": False,
            "error": str(e)
        })
