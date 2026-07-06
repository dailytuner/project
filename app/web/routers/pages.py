# web/routers/pages.py
import os
import logging
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pages"])

# Настройка Jinja2
templates = Jinja2Templates(directory="web/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница"""
    # Получаем данные из cookies
    user_authenticated = request.cookies.get("user_authenticated") == "true"
    user_platform = request.cookies.get("user_platform")
    user_platform_id = request.cookies.get("user_platform_id")
    user_name = request.cookies.get("user_name")

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
        "user_name": user_name,
        "yandex_oauth_enabled": yandex_oauth_enabled,
    }

    return templates.TemplateResponse("index.html", context)


@router.get("/health")
async def health():
    return {"status": "ok"}