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
    user_authenticated = request.cookies.get("user_authenticated") == "true"
    user_platform = request.cookies.get("user_platform")
    user_platform_id = request.cookies.get("user_platform_id")
    user_name = request.cookies.get("user_name")
    user_email = request.cookies.get("user_email")  # ← Для Яндекса

    # Если платформа Яндекс, показываем email как идентификатор
    display_name = user_name
    if user_platform == "yandex" and not display_name:
        display_name = user_email or user_platform_id

    context = {
        "request": request,
        "user_authenticated": user_authenticated,
        "user_platform": user_platform,
        "user_platform_id": user_platform_id,
        "user_name": display_name,  # ← Показываем email для Яндекса
        "yandex_oauth_enabled": yandex_oauth_enabled,
    }

    return templates.TemplateResponse("index.html", context)


@router.get("/health")
async def health():
    return {"status": "ok"}
