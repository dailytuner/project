# assistant_api.py

import logging
import os
import asyncio
import secrets  # для генерации state
import jwt
from datetime import datetime, date, timezone, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
import uvicorn
from sqlalchemy import text, select

from .database.core import async_session
from .database.models import NatalChart, PsyhoMatrix, Biorhythm, MagicProfile
from .users.users_auth import AuthPlatform, get_user_id_by_platform  # ✅ ТОЛЬКО ОДИН РАЗ
from .users.user_services import user_service, User, UserProfile
from .users.password_auth import has_password as check_has_password
from .services.activity_services import activity_optimizer_service
from .services.chart_services import create_and_save_natal_chart
from .services.matrix_services import calculate_and_save_psyho_matrix
from .services.biorhythm_services import get_user_biorhythm_profile
from .magic.magic_services import MagicProfileService
from .forecast.daily_forecast_service import get_forecast_service
from .services.yandex_oauth import (  # ✅ ТОЛЬКО ИСПОЛЬЗУЕМЫЕ
    yandex_oauth_service,
    get_yandex_auth_url,
)

# JWT настройки


def read_secret_file(file_path: str) -> str:
    """Безопасно читает секрет из файла"""
    if not file_path:
        return ""
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"Failed to read secret from {file_path}: {e}")
        return ""


# Загрузка JWT_SECRET
def load_jwt_secret() -> str:
    """Загружает JWT_SECRET из файла или переменной окружения"""
    # Сначала пробуем файл секрета
    secret_file = os.getenv('JWT_SECRET_FILE')
    if secret_file:
        secret = read_secret_file(secret_file)
        if secret:
            return secret

    # Затем переменную окружения
    secret = os.getenv('JWT_SECRET')
    if secret:
        return secret

    # В крайнем случае используем стандартный (для разработки)
    logger.warning("⚠️ JWT_SECRET not set, using default (INSECURE!)")
    return "your-secret-key-change-in-production"


# Загружаем JWT секрет
JWT_SECRET = load_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 часа
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 дней


def create_jwt_token(user_id: int, expires_delta: timedelta) -> str:
    """Создает JWT токен"""
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    """Создает refresh токен"""
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Optional[dict]:
    """Декодирует JWT токен"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None

logger = logging.getLogger(__name__)


def iso_timestamp() -> str:
    return datetime.now().isoformat()

# API Key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    try:
        with open("/run/secrets/backend-api-key", "r") as f:
            expected_key = f.read().strip()
        if api_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API Key")
        return api_key
    except Exception as e:
        logger.error(f"API key verification failed: {e}")
        raise HTTPException(status_code=401, detail="API Key unavailable")

app = FastAPI(
    title="Personal Assistant API",
    description="API для оптимальных активностей и астрологических расчетов",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dailytuner.ru",
        "http://localhost:8080",  # для локальной разработки
        "http://localhost:80",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic модели
class UserProfileCreate(BaseModel):
    model_config = ConfigDict(repr=False)
    birth_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    birth_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    birth_city: str
    current_city: Optional[str] = None
    profession: Optional[str] = None
    job_position: Optional[str] = None

class PlatformUserRequest(BaseModel):
    model_config = ConfigDict(repr=False)
    platform: AuthPlatform
    platform_user_id: str


class OptimalActivitiesRequest(PlatformUserRequest):
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @property
    def parsed_date(self) -> Optional[date]:
        """Конвертирует строку даты в date объект"""
        if self.date is None:
            return None
        try:
            return date.fromisoformat(self.date)
        except ValueError:
            logger.warning(f"Invalid date format: {self.date}")
            return None

class BaseResponse(BaseModel):
    model_config = ConfigDict(repr=False)
    success: bool
    timestamp: str = Field(default_factory=iso_timestamp)

class ProfileResponse(BaseResponse):
    user_id: Optional[int]
    platform: AuthPlatform
    platform_user_id: str
    has_complete_data: bool = False
    missing_fields: List[str] = []

class OptimalActivitiesResponse(BaseResponse):
    user_id: int
    platform: AuthPlatform
    platform_user_id: str
    calculation_date: str
    optimal_activities: List[int]
    activity_scores: Dict[str, float]
    energy_level: float
    recommendations_ready: bool = True

class ErrorResponse(BaseResponse):
    success: bool = False
    error: str
    error_code: str


class PredictionRequest(PlatformUserRequest):
    date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @property
    def parsed_date(self) -> Optional[date]:
        """Конвертирует строку даты в date объект"""
        if self.date is None:
            return None
        try:
            return date.fromisoformat(self.date)
        except ValueError:
            logger.warning(f"Invalid date format: {self.date}")
            return None

class PredictionResponse(BaseResponse):
    user_id: int
    platform: AuthPlatform
    platform_user_id: str
    prediction_date: str
    recommendations: List[str]
    warnings: List[str]
    aspects_count: int
    strong_aspects_count: int

class FeedbackRequest(BaseModel):
    model_config = ConfigDict(repr=False)
    user_id: int
    forecast_date: str  # YYYY-MM-DD
    axis_name: str
    user_rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

# ========== PYDANTIC МОДЕЛИ ДЛЯ ПАСПОРТА ==========

class SetPasswordRequest(BaseModel):
    """Запрос на установку пароля"""
    platform: AuthPlatform
    platform_user_id: str
    password: str = Field(..., min_length=6, description="Пароль минимум 6 символов")


class LoginRequest(BaseModel):
    """Запрос на вход с паролем"""
    platform: AuthPlatform
    platform_user_id: str
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """Ответ при успешном входе"""
    success: bool
    user_id: int
    has_profile: bool
    has_complete_data: bool
    message: str


class AuthStatusResponse(BaseModel):
    """Статус аутентификации"""
    success: bool
    has_password: bool
    user_id: Optional[int] = None
    platform_user_id: Optional[str] = None
    platform: Optional[str] = None


class ApiProxyService:
    async def get_optimal_activities(
        self, user_id: int, target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        return await activity_optimizer_service.get_ml_activities(user_id, target_date)

    async def get_activity_descriptions(self, activity_list: List[str]) -> Dict[str, str]:
        ACTIVITY_MAP = {
            "physical": "Физические упражнения, йога, прогулки",
            "spiritual": "Медитация, дыхательные практики", 
            "learning": "Изучение, чтение, курсы",
            "psychological": "Терапия, рефлексия",
            "career": "Работа, планирование карьеры",
            "self_realization": "Творчество, хобби",
            "finances": "Финансовое планирование"
        }
        return {act: ACTIVITY_MAP.get(act, "Неизвестная активность") for act in activity_list}

# МОДЕЛИ ДЛЯ YANDEX OAUTH


class YandexAuthResponse(BaseResponse):
    """Ответ при авторизации через Яндекс"""
    user_id: int
    platform: str = "yandex"
    email: Optional[str] = None
    login: Optional[str] = None
    is_new_user: bool = False
    access_token: str  # JWT токен нашего приложения
    refresh_token: str  # JWT refresh токен нашего приложения


class YandexLoginUrlResponse(BaseResponse):
    """URL для перенаправления на Яндекс"""
    auth_url: str
    state: str


class YandexUserDataResponse(BaseResponse):
    """Данные пользователя из Яндекса"""
    user_id: int
    yandex_id: str
    email: Optional[str]
    login: Optional[str]
    avatar_url: Optional[str]
    is_verified: bool

assistant_api_service = ApiProxyService()

# Health checks
@app.get("/")
async def root():
    return {"message": "Personal Assistant API", "version": "1.0.0", "status": "active"}

@app.get("/health")
async def health_check():
    async with async_session() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "healthy", "database": "connected"}

# ✅ ОСНОВНЫЕ ЭНДПОИНТЫ
@app.get("/api/v1/activities/descriptions")
async def get_activities_descriptions(
        activities: str,
        api_key: str = Depends(verify_api_key)
):
    """
    Получение описаний активностей по их кодам.
    - activities: строка с кодами через запятую (например "physical,learning,career")
    """
    try:
        activity_list = [a.strip() for a in activities.split(",") if a.strip()]
        descriptions = await assistant_api_service.get_activity_descriptions(activity_list)

        return {
            "success": True,
            "activities": descriptions,
            "timestamp": iso_timestamp()
        }
    except Exception as e:
        logger.error(f"❌ Error in /activities/descriptions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@app.post("/api/v1/optimal-activities")
async def get_optimal_activities(
        request: OptimalActivitiesRequest,
        api_key: str = Depends(verify_api_key)
):
    async with async_session() as session:
        user_id = await get_user_id_by_platform(session, request.platform, request.platform_user_id)
        if not user_id:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        target_date = request.parsed_date

        result = await assistant_api_service.get_optimal_activities(user_id, target_date)

        # ✅ Убедимся, что user_id в result совпадает
        if result.get('user_id') != user_id:
            logger.warning(f"user_id mismatch: result has {result.get('user_id')}, expected {user_id}")
            result['user_id'] = user_id

        return OptimalActivitiesResponse(
            success=True,
            platform=request.platform,
            platform_user_id=request.platform_user_id,
            **result
        )

@app.post("/api/v1/user/profile", response_model=ProfileResponse)
async def save_user_profile(
    request: PlatformUserRequest, profile: UserProfileCreate, 
    api_key: str = Depends(verify_api_key)
):
    """✅ УНИВЕРСАЛЬНОЕ сохранение профиля"""
    created, user, user_profile = await user_service.create_or_update_full_profile(
        platform=request.platform, platform_user_id=request.platform_user_id,
        birth_date=profile.birth_date, birth_time=profile.birth_time,
        birth_city=profile.birth_city, current_city=profile.current_city,
        profession=profile.profession, job_position=profile.job_position
    )
    
    # ✅ Запускаем pipeline с user.id
    asyncio.create_task(_run_calculations(user.id))
    
    return ProfileResponse(
        success=True, user_id=user.id, platform=request.platform,
        platform_user_id=request.platform_user_id, has_complete_data=True
    )

@app.get("/api/v1/user/profile")
async def get_user_profile(
    platform: AuthPlatform = Query(...), platform_user_id: str = Query(...),
    include_extended: bool = Query(False), api_key: str = Depends(verify_api_key)
):
    profile_data = await user_service.get_user_profile(
        platform, platform_user_id, include_extended
    )
    if not profile_data:
        raise HTTPException(status_code=404, detail="Профиль не найден")
    return {"success": True, "profile": profile_data}


# В существующий эндпоинт /api/v1/user/validate добавить параметр password
@app.get("/api/v1/user/validate", response_model=ProfileResponse)
async def validate_user(
        platform: AuthPlatform = Query(...),
        platform_user_id: str = Query(...),
        password: Optional[str] = Query(None),
        api_key: str = Depends(verify_api_key)
        ):
    validation_result = await user_service.validate_user_profile(platform, platform_user_id)

    # Если передан пароль - проверяем его
    if password and validation_result.get('user_id'):
        is_valid = await user_service.authenticate(platform, platform_user_id, password)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Invalid password")

    return ProfileResponse(
        success=True,
        user_id=validation_result.get('user_id'),
        platform=platform,
        platform_user_id=platform_user_id,
        has_complete_data=validation_result.get('has_complete_data', False),
        missing_fields=validation_result.get('missing_fields', [])
    )


async def _verify_calculations(user_id: int):
    """Подробная проверка результатов расчетов для отладки"""
    try:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                logger.error(f"❌ Пользователь {user_id} не найден")
                return

            logger.info("=" * 60)
            logger.info(f"🔍 ПРОВЕРКА ДАННЫХ ДЛЯ user_id={user_id}")

            # ✅ PsyhoMatrix (УЖЕ ПРАВИЛЬНО)
            matrix_result = await session.execute(
                select(PsyhoMatrix).where(PsyhoMatrix.user_id == user_id)
            )
            matrix = matrix_result.scalars().first()
            logger.info(f"📊 PsyhoMatrix: {'✅ Есть' if matrix else '❌ НЕТ'}")
            if matrix:
                logger.info(f"   - first_number: {matrix.first_number}")

            # ✅ BIORHYTHMS (ИСПРАВЛЕНО)
            biorhythm_result = await session.execute(
                select(Biorhythm).where(Biorhythm.user_id == user_id)
                .order_by(Biorhythm.calculation_date.desc()).limit(1)
            )
            biorhythm = biorhythm_result.scalars().first()  # ← ФИКС!
            logger.info(f"🔄 Biorhythms: {'✅ Есть' if biorhythm else '❌ НЕТ'}")
            if biorhythm:
                logger.info(f"   - date: {biorhythm.calculation_date}")

            # ✅ NATAL CHART (ИСПРАВЛЕНО)
            natal_result = await session.execute(
                select(NatalChart).where(NatalChart.user_id == user_id)
                .order_by(NatalChart.calculation_date.desc()).limit(1)
            )
            natal = natal_result.scalars().first()  # ← ФИКС!
            logger.info(f"🌟 Natal Chart: {'✅ Есть' if natal else '❌ НЕТ'}")
            if natal:
                logger.info(f"   - date: {natal.calculation_date}")

            # ✅ MagicProfile (УЖЕ ПРАВИЛЬНО)
            magic_result = await session.execute(
                select(MagicProfile).where(MagicProfile.user_id == user_id)
            )
            magic_row = magic_result.first()
            magic = magic_row[0] if magic_row else None
            logger.info(f"✨ Magic Profile: {'✅ Есть' if magic else '❌ НЕТ'}")

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке расчетов: {e}")



async def _run_calculations(user_id: int):
    """Полный pipeline расчетов для user_id"""
    try:
        logger.info(f"🚀 Pipeline для user_id={user_id}")

        # Получаем данные профиля
        async with async_session() as session:
            profile = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = profile.scalar_one_or_none()

            if not profile or not profile.birth_date:
                logger.error(f"❌ Нет данных профиля для user_id={user_id}")
                return

            logger.info(f"📋 Профиль: {profile.birth_city}, {profile.birth_date}")

            # Подготавливаем задачи
            tasks = [
                calculate_and_save_psyho_matrix(user_id=user_id),
                get_user_biorhythm_profile(user_id=user_id),
            ]

            # Добавляем натальную карту, если есть время
            if profile.birth_time:
                birth_datetime = datetime.combine(profile.birth_date, profile.birth_time)
                tasks.append(
                    create_and_save_natal_chart(
                        user_id=user_id,
                        city=profile.birth_city,
                        birth_datetime=birth_datetime,
                        timezone=profile.birth_timezone or 'Europe/Kaliningrad'
                    )
                )

            # ✅ Запускаем все базовые расчеты параллельно с таймаутом
            try:
                await asyncio.wait_for(asyncio.gather(*tasks), timeout=45.0)
                logger.info(f"✅ Базовые расчеты завершены для user_id={user_id}")
            except asyncio.TimeoutError:
                logger.error(f"❌ Таймаут базовых расчетов для user_id={user_id}")
                # Продолжаем, даже если часть расчетов не завершилась
            except Exception as e:
                logger.error(f"❌ Ошибка в базовых расчетах: {e}")

            # Небольшая пауза для завершения записи в БД
            await asyncio.sleep(1)

            # Проверяем результаты (для отладки)
            await _verify_calculations(user_id)

            # ✅ Магический профиль и ML активности с таймаутом
            try:
                magic_service = MagicProfileService()
                await asyncio.wait_for(
                    magic_service.calculate_and_save_magic_profile(user_id=user_id),
                    timeout=60.0
                )
                logger.info(f"✅ Magic profile создан для user_id={user_id}")
            except asyncio.TimeoutError:
                logger.error(f"❌ Таймаут создания magic profile для user_id={user_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка создания magic profile: {e}")

            try:
                await asyncio.wait_for(
                    activity_optimizer_service.get_ml_activities(user_id),
                    timeout=15.0
                )
                logger.info(f"✅ ML активности получены для user_id={user_id}")
            except asyncio.TimeoutError:
                logger.error(f"❌ Таймаут получения ML активностей для user_id={user_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка получения ML активностей: {e}")

            logger.info(f"🎉 Pipeline завершен для user_id={user_id}")

    except Exception as e:
        logger.error(f"💥 Pipeline user_id={user_id} failed: {e}", exc_info=True)


# Обработчики ошибок
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error=exc.detail, error_code=f"HTTP_{exc.status_code}").model_dump()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error="Internal server error", error_code="INTERNAL_ERROR").model_dump()
    )


@app.post("/api/v1/forecast/feedback")
async def submit_feedback(
        request: FeedbackRequest,
        api_key: str = Depends(verify_api_key)
):
    """Отправить обратную связь о точности прогноза"""
    from .database.models import ForecastFeedback

    async with async_session() as session:
        feedback = ForecastFeedback(
            user_id=request.user_id,
            forecast_date=datetime.strptime(request.forecast_date, "%Y-%m-%d").date(),
            axis_name=request.axis_name,
            user_rating=request.user_rating,
            comment=request.comment
        )
        session.add(feedback)
        await session.commit()

    return BaseResponse(success=True)


@app.get("/api/v1/forecast")
async def get_forecast(
        platform: AuthPlatform = Query(...),
        platform_user_id: str = Query(...),
        forecast_date: Optional[str] = Query(None),
        force_recalculate: bool = Query(False),
        api_key: str = Depends(verify_api_key)
):
    """
    Получить прогноз на указанную дату (новая версия).
    - Если прогноз уже есть в кэше — вернуть из кэша
    - Если нет — рассчитать и сохранить
    """

    async with async_session() as session:
        user_id = await get_user_id_by_platform(session, platform, platform_user_id)
        if not user_id:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Парсим дату
        target_date = None
        if forecast_date:
            try:
                target_date = datetime.strptime(forecast_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Неверный формат даты")

        # Получаем прогноз через новый сервис
        forecast_service = get_forecast_service()

        try:
            forecast = await forecast_service.get_daily_forecast(
                user_id=user_id,
                forecast_date=target_date,
                force_recalculate=force_recalculate
            )

            return {
                "success": True,
                "user_id": user_id,
                "forecast_date": forecast.forecast_date.isoformat(),
                "axes": [a.to_dict() for a in forecast.axes],
                "summary": forecast.summary,
                "top_advice": forecast.top_advice,
                "caution_advice": forecast.caution_advice,
                "best_time": forecast.best_time,
                "moon_info": forecast.moon_info,
                "planetary_hour": forecast.planetary_hour,
                "dasha_info": forecast.dasha_info,
                "financial_advice": forecast.financial_advice,
                "timestamp": iso_timestamp()
            }

        except Exception as e:
            logger.error(f"Ошибка получения прогноза: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# ========== ЭНДПОИНТЫ ДЛЯ ПАРОЛЬНОЙ АУТЕНТИФИКАЦИИ ==========

@app.post("/api/v1/auth/set-password")
async def set_password_endpoint(
        request: SetPasswordRequest,
        api_key: str = Depends(verify_api_key)
):
    """
    Установка пароля для существующего пользователя.
    Если пароль уже был установлен - перезаписывает.
    """
    try:
        async with async_session() as session:
            # Проверяем существование пользователя
            user_id = await get_user_id_by_platform(
                session, request.platform, request.platform_user_id
            )

            if not user_id:
                raise HTTPException(
                    status_code=404,
                    detail=f"User not found: {request.platform}:{request.platform_user_id}"
                )

            # Устанавливаем пароль
            await user_service.set_password(
                request.platform,
                request.platform_user_id,
                request.password
            )

            return {
                "success": True,
                "message": "Password set successfully",
                "user_id": user_id
            }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in set_password: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/v1/auth/login")
async def login_endpoint(
        request: LoginRequest,
        api_key: str = Depends(verify_api_key)
):
    """
    Вход пользователя с паролем.
    Проверяет пароль и возвращает статус профиля.
    """
    try:
        # Аутентифицируем пользователя
        user_id = await user_service.authenticate(
            request.platform,
            request.platform_user_id,
            request.password
        )

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

        # Проверяем полноту профиля
        validation = await user_service.validate_user_profile(
            request.platform,
            request.platform_user_id
        )

        return LoginResponse(
            success=True,
            user_id=user_id,
            has_profile=validation.get('exists', False),
            has_complete_data=validation.get('has_complete_data', False),
            message="Login successful"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in login: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/auth/status")
async def auth_status_endpoint(
        platform: AuthPlatform = Query(...),
        platform_user_id: str = Query(...),
        api_key: str = Depends(verify_api_key)
):
    """
    Проверка статуса аутентификации пользователя.
    Возвращает, установлен ли пароль.
    """
    try:
        async with async_session() as session:
            user_id = await get_user_id_by_platform(
                session, platform, platform_user_id
            )

            if not user_id:
                return AuthStatusResponse(
                    success=False,
                    has_password=False,
                    user_id=None,
                    platform_user_id=platform_user_id,
                    platform=platform.value
                )

            # Проверяем наличие пароля
            has_pass = await user_service.has_password(platform, platform_user_id)

            return AuthStatusResponse(
                success=True,
                has_password=has_pass,
                user_id=user_id,
                platform_user_id=platform_user_id,
                platform=platform.value
            )

    except Exception as e:
        logger.error(f"Error in auth_status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# assistant_api.py - добавить после существующих эндпоинтов

# =============================================
# 🆕 YANDEX OAUTH ЭНДПОИНТЫ
# =============================================

@app.get("/api/v1/auth/yandex/login")
async def yandex_login(
        redirect_uri: Optional[str] = Query(None, description="Custom redirect URI (optional)")
):
    """
    Направляет пользователя на страницу авторизации Яндекса

    Возвращает URL для редиректа с state для защиты от CSRF
    """
    try:
        # Генерируем случайный state для защиты от CSRF
        state = secrets.token_urlsafe(32)

        # Получаем URL для авторизации
        auth_url = await get_yandex_auth_url(
            state=state,
            redirect_uri=redirect_uri
        )

        # Сохраняем state в сессии или кэше для проверки в callback
        # Для простоты используем временное хранилище, но в продакшене
        # лучше использовать Redis или кэш
        # TODO: добавить Redis для хранения state
        # await redis.setex(f"yandex_state:{state}", 300, "1")

        return YandexLoginUrlResponse(
            success=True,
            auth_url=auth_url,
            state=state,
            timestamp=iso_timestamp()
        )

    except ValueError as e:
        logger.error(f"Yandex login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Yandex login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate Yandex login URL"
        )


@app.get("/api/v1/auth/yandex/callback")
async def yandex_callback(
        code: str = Query(..., description="Authorization code from Yandex"),
        state: Optional[str] = Query(None, description="State parameter for CSRF protection"),
        error: Optional[str] = Query(None, description="Error from Yandex"),
        error_description: Optional[str] = Query(None, description="Error description from Yandex")
):
    """Обработка callback от Яндекса после авторизации"""
    try:
        if error:
            logger.error(f"Yandex OAuth error: {error} - {error_description}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Yandex OAuth error: {error} - {error_description}"
            )

        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authorization code"
            )

        # 1. Аутентифицируем пользователя через Яндекс
        user, user_info, tokens = await yandex_oauth_service.authenticate_with_code(
            code=code,
            create_user=True
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found and could not be created"
            )

        # 2. Создаем JWT токены для нашего приложения
        access_token = create_jwt_token(
            user.id,
            timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        refresh_token = create_refresh_token(user.id)

        # 3. Определяем, новый ли пользователь
        # Простой способ: проверяем, есть ли у пользователя профиль
        async with async_session() as session:
            from .database.models import UserProfile
            profile_result = await session.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            has_profile = profile_result.scalar_one_or_none() is not None

        # 4. Возвращаем ответ
        return YandexAuthResponse(
            success=True,
            user_id=user.id,
            platform="yandex",
            email=user_info.email,
            login=user_info.login,
            is_new_user=not has_profile,  # ✅ Более точная проверка
            access_token=access_token,
            refresh_token=refresh_token,
            timestamp=iso_timestamp()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Yandex callback error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Yandex authentication failed: {str(e)}"
        )


@app.get("/api/v1/auth/yandex/user")
async def get_yandex_user_data(
        user_id: int = Query(..., description="User ID"),
        api_key: str = Depends(verify_api_key)
):
    """
    Получить данные пользователя из Яндекса

    Требуется API Key для доступа
    """
    try:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            if not user.yandex_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User does not have Yandex account"
                )

            return YandexUserDataResponse(
                success=True,
                user_id=user.id,
                yandex_id=user.yandex_id,
                email=user.yandex_email or user.login,  # ✅ ИСПРАВЛЕНО
                login=user.yandex_login,
                avatar_url=user.yandex_avatar_url,
                is_verified=user.is_verified,
                timestamp=iso_timestamp()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Yandex user data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get Yandex user data"
        )


@app.post("/api/v1/auth/yandex/refresh")
async def refresh_yandex_token(
        user_id: int = Query(..., description="User ID"),
        api_key: str = Depends(verify_api_key)
):
    """
    Принудительно обновить Яндекс токен пользователя

    Используется для ручного обновления или при ошибках
    """
    try:
        new_token = await user_service.refresh_yandex_token(user_id)

        if not new_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to refresh Yandex token"
            )

        return BaseResponse(
            success=True,
            timestamp=iso_timestamp()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing Yandex token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh Yandex token"
        )


@app.post("/api/v1/auth/yandex/logout")
async def yandex_logout(
        user_id: int = Query(..., description="User ID"),
        api_key: str = Depends(verify_api_key)
):
    """
    Выход из Яндекс аккаунта (очистка токенов в БД)
    """
    try:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )

            # Очищаем Яндекс токены
            user.yandex_access_token = None
            user.yandex_refresh_token = None
            user.yandex_token_expires_at = None

            await session.commit()

            return BaseResponse(
                success=True,
                timestamp=iso_timestamp()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during Yandex logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout from Yandex"
        )

if __name__ == "__main__":
    uvicorn.run("backend.assistant_api:app", host="0.0.0.0", port=8000, reload=True)
