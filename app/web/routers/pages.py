import os
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="web/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница"""
    user_authenticated = request.cookies.get("user_authenticated") == "true"
    user_platform = request.cookies.get("user_platform")
    user_platform_id = request.cookies.get("user_platform_id")
    user_name = request.cookies.get("user_name")
    user_email = request.cookies.get("user_email")

    # Определяем отображаемое имя
    display_name = user_name
    if user_platform == "yandex" and user_email:
        display_name = user_email  # Для Яндекс показываем email
    elif not display_name:
        display_name = user_platform_id

    # Проверяем включен ли Яндекс OAuth
    yandex_oauth_enabled = bool(
        os.getenv("YANDEX_CLIENT_ID") or
        os.path.exists("/run/secrets/yandex-client-id")
    )

    context = {
        "request": request,
        "user_authenticated": user_authenticated,
        "user_platform": user_platform,
        "user_platform_id": user_platform_id,
        "user_name": display_name,
        "yandex_oauth_enabled": yandex_oauth_enabled,
        "user_birth_region": request.cookies.get("user_birth_region"),
        "user_birth_country": request.cookies.get("user_birth_country"),
    }

    return templates.TemplateResponse("index.html", context)


@router.get("/health")
async def health():
    """Проверка здоровья сервиса"""
    return {"status": "ok"}


# ========== СТРАНИЦЫ ПОЛИТИКИ И УСЛОВИЙ ==========

@router.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    """Страница политики конфиденциальности"""
    context = {
        "request": request,
    }
    return templates.TemplateResponse("privacy_policy.html", context)


@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    """Страница условий использования"""
    context = {
        "request": request,
    }
    return templates.TemplateResponse("terms.html", context)