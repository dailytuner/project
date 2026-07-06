# web/routers/oauth.py
import secrets
import logging
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

        email = user_info.get("email")
        yandex_id = user_info.get("yandex_id")
        name = user_info.get("full_name") or user_info.get("login")

        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Yandex")

        logger.info(f"Yandex auth for: {email} (ID: {yandex_id})")

        # Проверяем существование пользователя
        validate_result = await user_service.validate_user(
            platform=AuthPlatform.EMAIL.value,
            platform_user_id=email
        )

        if validate_result.get("success"):
            # Пользователь существует - логиним
            logger.info(f"Existing user logged in: {email}")
        else:
            # Новый пользователь - создаем профиль
            logger.info(f"New user registered: {email}")
            # TODO: Создать профиль пользователя через API если нужно

        # Сохраняем данные в cookies
        response.set_cookie(
            key="user_platform",
            value=AuthPlatform.EMAIL.value,
            max_age=604800,  # 7 дней
            httponly=True,
            secure=True,  # Для HTTPS
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="user_platform_id",
            value=email,
            max_age=604800,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/"
        )
        response.set_cookie(
            key="user_authenticated",
            value="true",
            max_age=604800,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/"
        )

        # Добавляем имя пользователя в cookie (для отображения)
        if name:
            response.set_cookie(
                key="user_name",
                value=name,
                max_age=604800,
                httponly=False,  # Чтобы JS мог прочитать
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

    return RedirectResponse("/", status_code=303)


@router.get("/session")
async def get_session_info(request: Request):
    """Получить информацию о текущей сессии (для отладки)"""
    platform = request.cookies.get("user_platform")
    platform_id = request.cookies.get("user_platform_id")
    authenticated = request.cookies.get("user_authenticated") == "true"
    name = request.cookies.get("user_name")

    return JSONResponse({
        "authenticated": authenticated,
        "user": {
            "name": name,
            "platform": platform,
            "platform_user_id": platform_id
        } if authenticated else None
    })