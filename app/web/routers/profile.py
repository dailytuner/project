# routers/profile.py

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import logging

from ..services.user_service import UserService
from ..models.user import ProfileRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["profile"])
user_service = UserService()


@router.post("/profile")
async def save_profile(request: Request):
    """Сохранение профиля"""
    try:
        data = await request.json()
        req_data = data.get("request", {})
        profile_data = data.get("profile", {})

        platform = req_data.get("platform")
        platform_user_id = req_data.get("platform_user_id")

        if not platform or not platform_user_id:
            return JSONResponse({
                "success": False,
                "error": "platform and platform_user_id required"
            })

        result = await user_service.save_profile(
            platform=platform,
            platform_user_id=platform_user_id,
            profile_data=profile_data
        )
        return JSONResponse(result)

    except Exception as e:
        logger.error(f"Save profile error: {e}")
        return JSONResponse({"success": False, "error": str(e)})


@router.get("/profile")
async def get_profile(platform: str, platform_user_id: str):
    """Получение профиля"""
    result = await user_service.get_profile(platform, platform_user_id)
    return JSONResponse(result)