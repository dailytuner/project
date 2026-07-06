# routers/auth.py

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

from ..services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
user_service = UserService()

class PasswordRequest(BaseModel):
    platform: str
    platform_user_id: str
    password: str

@router.post("/set-password")
async def set_password(request_data: PasswordRequest):
    """Установка пароля"""
    result = await user_service.set_password(
        platform=request_data.platform,
        platform_user_id=request_data.platform_user_id,
        password=request_data.password
    )
    return JSONResponse(result)

@router.post("/login")
async def login(request_data: PasswordRequest):
    """Вход с паролем"""
    # Используем validate_user с паролем
    result = await user_service.validate_user(
        platform=request_data.platform,
        platform_user_id=request_data.platform_user_id,
        password=request_data.password
    )
    return JSONResponse(result)

@router.get("/status")
async def auth_status(platform: str, platform_user_id: str):
    """Статус аутентификации"""
    result = await user_service.get_auth_status(platform, platform_user_id)
    return JSONResponse(result)