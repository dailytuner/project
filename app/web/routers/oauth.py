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
    #logger.info("=" * 60)
    #logger.info("🔵 STEP 2: YANDEX CALLBACK RECEIVED")
    #logger.info(f"📥 Request URL: {request.url}")
    #logger.info(f"📥 Code: {code}")
    #logger.info(f"📥 State: {state}")
    #logger.info(f"📥 Request headers: {dict(request.headers)}")
    #logger.info(f"📥 Client: {request.client}")

    try:
        # Проверяем state
        #logger.info(f"🔍 Checking state in store: {list(STATE_STORE.keys())}")
        if not state or state not in STATE_STORE:
            logger.error(f"❌ Invalid state: {state}")
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        #logger.info(f"✅ State validated: {state}")
        del STATE_STORE[state]

        # Получаем данные от Яндекса
        #logger.info("🔄 Getting user info from Yandex...")
        user_info = await yandex_service.authenticate(code)

        #logger.info(f"📦 Yandex user_info: {user_info}")

        if not user_info.get("success"):
            logger.error("❌ Yandex authentication failed")
            raise HTTPException(status_code=400, detail="Failed to get user info")

        yandex_id = user_info.get("yandex_id")
        email = user_info.get("email")
        login = user_info.get("login")
        name = user_info.get("full_name") or user_info.get("login")
        access_token = user_info.get("access_token")
        refresh_token = user_info.get("refresh_token")
        expires_in = user_info.get("expires_in", 3600)

        #logger.info(f"👤 User data:")
        #logger.info(f"   - yandex_id: {yandex_id}")
        #logger.info(f"   - email: {email}")
        #logger.info(f"   - login: {login}")
        #logger.info(f"   - name: {name}")
        #logger.info(f"   - access_token: {access_token[:20]}...")
        #logger.info(f"   - refresh_token: {refresh_token}")
        #logger.info(f"   - expires_in: {expires_in}")

        if not email:
            logger.error("❌ Email not provided by Yandex")
            raise HTTPException(status_code=400, detail="Email not provided by Yandex")

        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
        #logger.info(f"⏰ expires_at: {expires_at}")

        # Создаем пользователя
        #logger.info("🔵 STEP 3: CREATING YANDEX USER")
        #logger.info(f"📤 Sending to backend:")
        #logger.info(f"   - yandex_id: {yandex_id}")
        #logger.info(f"   - email: {email}")
        #logger.info(f"   - login: {login}")
        #logger.info(f"   - access_token: {access_token[:20]}...")
        #logger.info(f"   - expires_at: {expires_at}")
        #logger.info(f"   - refresh_token: {refresh_token}")

        from ..web_client import web_client

        result = await web_client.create_yandex_user(
            yandex_id=yandex_id,
            email=email,
            login=login,
            access_token=access_token,
            expires_at=expires_at,
            refresh_token=refresh_token
        )

        #logger.info(f"📥 Backend response: {result}")

        if not result.get("success"):
            logger.error(f"❌ Failed to create yandex user: {result}")
            raise HTTPException(status_code=400, detail="Failed to create user")

        user_id = result.get("user_id")
        is_new = result.get("is_new", False)

        #logger.info(f"✅ User processed: ID={user_id}, is_new={is_new}")

        # Устанавливаем cookies
        #logger.info("🔵 STEP 4: SETTING COOKIES")

        cookies_to_set = {
            "user_authenticated": "true",
            "user_platform": AuthPlatform.YANDEX.value,
            "user_platform_id": yandex_id,
            "user_id": str(user_id),
            "user_name": name or email,
            "user_email": email
        }

        for key, value in cookies_to_set.items():
            logger.info(f"   - Setting cookies...")
            response.set_cookie(
                key=key,
                value=value,
                max_age=604800,
                httponly=True if key not in ["user_name", "user_email"] else False,
                secure=True,
                samesite="lax",
                path="/"
            )

        #logger.info("✅ Cookies set successfully")
        #logger.info("🔵 STEP 5: REDIRECTING TO HOME")
        #logger.info("=" * 60)

        # Создаем RedirectResponse через response
        response.status_code = 303
        response.headers["Location"] = "/"
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Yandex callback error: {e}", exc_info=True)
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


@router.get("/yandex")
async def yandex_login(request: Request):
    """Начало авторизации через Яндекс"""
    #logger.info("=" * 60)
    #logger.info("🔵 STEP 1: YANDEX LOGIN STARTED")
    #logger.info(f"📥 Request headers: {dict(request.headers)}")
    #logger.info(f"📥 Request client: {request.client}")

    try:
        state = secrets.token_urlsafe(32)
        STATE_STORE[state] = {"created_at": datetime.now(timezone.utc).isoformat()}

        logger.info(f"🔑 Generated state: {state}")
        logger.info(f"💾 State store: {list(STATE_STORE.keys())}")

        auth_url = yandex_service.get_auth_url(state)
        logger.info(f"🔗 Redirecting to Yandex: {auth_url}")
        logger.info("=" * 60)

        return RedirectResponse(auth_url)

    except Exception as e:
        logger.error(f"❌ Yandex login error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
