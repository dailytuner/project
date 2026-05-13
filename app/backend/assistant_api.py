# assistant_api.py
import logging
import asyncio
from datetime import datetime, date,timezone
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
from .users.users_auth import AuthPlatform, get_user_id_by_platform
from .users.user_services import user_service, User, UserProfile
from .users.password_auth import has_password as check_has_password
from .services.activity_services import activity_optimizer_service
from .services.chart_services import create_and_save_natal_chart
from .services.matrix_services import calculate_and_save_psyho_matrix
from .services.biorhythm_services import get_user_biorhythm_profile
from .magic.magic_services import MagicProfileService
#from .predictions import AstroPredictor, create_predictor_from_user_id
from .forecast.daily_forecast_service import get_forecast_service

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
    allow_origins=["*"],
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
        password: Optional[str] = Query(None),  # ✅ НОВЫЙ параметр
        api_key: str = Depends(verify_api_key)
):
    validation_result = await user_service.validate_user_profile(platform, platform_user_id)

    # ✅ Если передан пароль - проверяем его
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

if __name__ == "__main__":
    uvicorn.run("backend.assistant_api:app", host="0.0.0.0", port=8000, reload=True)
