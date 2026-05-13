import json
import logging
from datetime import date, timedelta

from sqlalchemy import and_, select, delete

from ..calculators.biorhythm_profile import BiorhythmProfileCalculator
from ..database.core import async_session
from ..database.models import Biorhythm
from ..users.user_services import user_service

logger = logging.getLogger(__name__)

# Константы
DEFAULT_ANALYSIS_YEARS = 5
PROFILE_VERSION = "1.0"


async def get_user_biorhythm_profile(user_id: int) -> dict | None:
    """
    Получение СТАТИЧЕСКОГО профиля биоритмов пользователя.
    Если профиля нет - рассчитывает и сохраняет.
    """
    try:
        async with async_session() as session:
            # Ищем существующий профиль (один на пользователя)
            result = await session.execute(
                select(Biorhythm)
                .where(Biorhythm.user_id == user_id)
                .limit(1)
            )
            profile = result.scalar_one_or_none()

            if profile and profile.profile_data:
                logger.info(f"✅ Найден профиль биоритмов для user {user_id}")
                profile_data = profile.profile_data
                if isinstance(profile_data, str):
                    profile_data = json.loads(profile_data)

                return {
                    "user_id": user_id,
                    "profile_version": profile.profile_version,
                    "calculated_at": profile.profile_calculated_at.isoformat() if profile.profile_calculated_at else None,
                    "days_analyzed": profile.days_analyzed,
                    "birth_phase": {
                        "physical": profile.birth_physical,
                        "emotional": profile.birth_emotional,
                        "intellectual": profile.birth_intellectual,
                        "intuitive": profile.birth_intuitive,
                    },
                    "ml_indicators": {
                        "system_stability": profile.system_stability,
                        "predictability": profile.predictability,
                    },
                    "profile_data": profile_data,  # Полные данные для Mistral
                }

            # Если нет - рассчитываем
            logger.info(f"🔄 Профиль не найден, рассчитываем для user {user_id}")
            return await calculate_and_save_biorhythm_profile(user_id)

    except Exception as e:
        logger.error(f"❌ Ошибка получения профиля {user_id}: {e}", exc_info=True)
        return None


async def calculate_and_save_biorhythm_profile(user_id: int) -> dict | None:
    """Расчет и сохранение статического профиля биоритмов."""
    try:
        # 1. Получаем данные пользователя
        user_profile = await user_service.get_user_profile_by_id(
            user_id=user_id, include_extended=True
        )
        if not user_profile or not user_profile.get("birth_date"):
            raise ValueError(f"Пользователь {user_id} не имеет даты рождения")

        birth_date = user_profile["birth_date"]
        logger.info(f"📅 Расчет профиля для {user_id}, рожден {birth_date}")

        # 2. Рассчитываем профиль
        calculator = BiorhythmProfileCalculator(use_extended_cycles=True)
        profile_data = calculator.calculate_profile(
            birth_date=birth_date,
            analysis_years=DEFAULT_ANALYSIS_YEARS
        )

        # 3. Извлекаем ключевые метрики
        birth_phase = profile_data.get("birth_phase", {})
        ml_indicators = profile_data.get("ml_indicators", {})
        metadata = profile_data.get("calculation_metadata", {})

        # 4. Сохраняем в БД
        async with async_session() as session:
            # Удаляем старый профиль (если есть)
            await session.execute(
                delete(Biorhythm).where(Biorhythm.user_id == user_id)
            )

            today = date.today()

            new_profile = Biorhythm(
                user_id=user_id,
                calculation_date=today,

                # Профильные поля
                profile_version=PROFILE_VERSION,
                profile_calculated_at=today,
                days_analyzed=metadata.get("days_analyzed", 1825),

                # Фазы рождения
                birth_physical=birth_phase.get("physical", {}).get("value", 0.0),
                birth_emotional=birth_phase.get("emotional", {}).get("value", 0.0),
                birth_intellectual=birth_phase.get("intellectual", {}).get("value", 0.0),
                birth_intuitive=birth_phase.get("intuitive", {}).get("value", 0.0),

                # ML метрики
                system_stability=ml_indicators.get("system_stability", 0.5),
                predictability=ml_indicators.get("predictability", 0.5),

                # Полный JSON профиля
                profile_data=profile_data,  # SQLAlchemy сам сериализует в JSONB
            )

            session.add(new_profile)
            await session.commit()

            logger.info(f"✅ Профиль биоритмов сохранен для user {user_id}")

            return {
                "user_id": user_id,
                "profile_version": PROFILE_VERSION,
                "calculated_at": today.isoformat(),
                "days_analyzed": metadata.get("days_analyzed", 1825),
                "birth_phase": birth_phase,
                "ml_indicators": ml_indicators,
                "profile_data": profile_data,
            }

    except Exception as e:
        logger.error(f"❌ Ошибка расчета профиля {user_id}: {e}", exc_info=True)
        return None