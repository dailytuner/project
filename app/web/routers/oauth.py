# web/routers/oauth.py
import secrets
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

from ..services.yandex_service import yandex_service
from ..services.user_service import UserService
from ..web_client import AuthPlatform

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["oauth"])
user_service = UserService()

# Простое хранилище для state (в проде использовать Redis)
STATE_STORE = {}

@router.get("/yandex")
async def yandex_login(request: Request):
    """Начало авторизации через Яндекс"""
    try:
        # Генерируем state для защиты от CSRF
        state = secrets.token_urlsafe(32)
        
        # Сохраняем state
        STATE_STORE[state] = {"created_at": secrets.token_urlsafe(8)}
        
        # Получаем URL для редиректа
        auth_url = yandex_service.get_auth_url(state)
        
        return RedirectResponse(auth_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Yandex login error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/yandex/callback")
async def yandex_callback(
        request: Request,
        response: Response,
        code: str,
        state: str = None
):
    """Callback после авторизации в Яндексе"""
    try:
        # Проверяем state
        if not state or state not in STATE_STORE:
            logger.warning(f"Invalid OAuth state: {state}")
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        # Удаляем использованный state
        del STATE_STORE[state]

        # Получаем данные пользователя от Яндекса
        user_info = await yandex_service.authenticate(code)

        if not user_info["success"]:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        yandex_id = user_info.get("yandex_id")
        email = user_info.get("email")
        login = user_info.get("login")
        name = user_info.get("full_name") or user_info.get("login")

        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Yandex")

        logger.info(f"Yandex auth for: {email} (ID: {yandex_id})")

        # Получаем токены
        access_token = user_info.get("access_token")
        refresh_token = user_info.get("refresh_token")
        expires_in = user_info.get("expires_in", 3600)
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

        # Создаем пользователя через backend
        from ..web_client import web_client

        result = await web_client.create_yandex_user(
            yandex_id=yandex_id,
            email=email,
            login=login,
            access_token=access_token,
            expires_at=expires_at,
            refresh_token=refresh_token
        )

        if not result.get("success"):
            logger.error(f"Failed to create yandex user: {result}")
            raise HTTPException(status_code=400, detail="Failed to create user")

        user_id = result.get("user_id")
        is_new = result.get("is_new", False)

        logger.info(f"Yandex user {'created' if is_new else 'logged in'}: {email} (ID: {user_id})")

        # ✅ Устанавливаем cookies
        response.set_cookie(
            key="user_authenticated",
            value="true",
            max_age=604800,  # 7 дней
            httponly=True,
            secure=True,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="user_platform",
            value=AuthPlatform.YANDEX.value,
            max_age=604800,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="user_platform_id",
            value=yandex_id,  # ← yandex_id, НЕ email!
            max_age=604800,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="user_id",
            value=str(user_id),
            max_age=604800,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="user_name",
            value=name or email,
            max_age=604800,
            httponly=False,
            secure=True,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="user_email",
            value=email,
            max_age=604800,
            httponly=False,
            secure=True,
            samesite="lax",
            path="/"
        )

        # Редирект на главную
        return RedirectResponse("/", status_code=303)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Yandex callback error: {e}", exc_info=True)
        return RedirectResponse(
            f"/?error=oauth_failed",
            status_code=303
        )

@router.get("/logout")
async def logout(response: Response):
    """Выход из системы"""
    # Удаляем все cookies
    response.delete_cookie("user_platform", path="/")
    response.delete_cookie("user_platform_id", path="/")
    response.delete_cookie("user_authenticated", path="/")
    response.delete_cookie("user_name", path="/")
    response.delete_cookie("user_id", path="/")
    
    return RedirectResponse("/", status_code=303)

@router.get("/session")
async def get_session_info(request: Request):
    """Получить информацию о текущей сессии (для отладки)"""
    platform = request.cookies.get("user_platform")
    platform_id = request.cookies.get("user_platform_id")
    authenticated = request.cookies.get("user_authenticated") == "true"
    name = request.cookies.get("user_name")
    user_id = request.cookies.get("user_id")
    
    return JSONResponse({
        "authenticated": authenticated,
        "user": {
            "user_id": user_id,
            "name": name,
            "platform": platform,
            "platform_user_id": platform_id
        } if authenticated else None
    })
