import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Any

from sqlalchemy.future import select
from sqlalchemy import func, and_

from ..database.core import async_session
from ..users.users_auth import get_user_id_by_platform
from ..database.models import Recommendation

from ..predictions import AstroPredictor
from ..services.chart_services import get_user_natal_chart
from ..services.biorhythm_services import get_user_biorhythm_profile

logger = logging.getLogger(__name__)


class PredictionCombiner:
    """Класс для объединения астрологических предсказаний и биоритмов"""

    def __init__(self):
        pass

    def combine_recommendations(self, astro_prediction: dict, biorhythm_data: dict) -> list:
        """Объединение рекомендаций из астрологии и биоритмов на основе РАСЧЕТОВ"""

        # Берем рекомендации из обоих источников
        astro_recommendations = astro_prediction.get('recommendations', [])
        biorhythm_recommendations = biorhythm_data.get('recommendations', [])

        # Объединяем рекомендации
        all_recommendations = astro_recommendations + biorhythm_recommendations

        # Сортируем по приоритету на основе РАСЧЕТОВ
        priority_recommendations = self._prioritize_recommendations(all_recommendations)

        return priority_recommendations[:8]  # Не более 8 рекомендаций

    def _prioritize_recommendations(self, recommendations: list) -> list:
        """Приоритизация рекомендаций на основе РАСЧЕТОВ"""
        high_priority = []
        medium_priority = []
        low_priority = []

        for rec in recommendations:
            rec_lower = rec.lower()

            # Высокий приоритет - предостережения и критические дни на основе РАСЧЕТОВ
            if any(word in rec_lower for word in
                   ['осторожн', 'избегай', 'опасн', 'критич', 'не рискуй', 'береги', 'ретроградн']):
                high_priority.append(rec)
            # Средний приоритет - активные действия на основе РАСЧЕТОВ
            elif any(word in rec_lower for word in ['идеальн', 'отличн', 'благоприятн', 'используй', 'высок', 'пик']):
                medium_priority.append(rec)
            # Низкий приоритет - информационные рекомендации
            else:
                low_priority.append(rec)

        return high_priority + medium_priority + low_priority

    def generate_energy_analysis(self, astro_prediction: dict, biorhythm_data: dict) -> str:
        """Анализ энергетического состояния на основе РАСЧЕТОВ обоих методов"""

        # Данные из биоритмов
        energy_level = biorhythm_data.get('overall_energy_level', 'medium')
        energy_percentage = biorhythm_data.get('overall_energy_percentage', 50)

        # Данные из астрологии
        aspects = astro_prediction.get('significant_aspects', [])
        strong_aspects = [a for a in aspects if a.get('strength', 0) > 0.7]
        challenging_aspects = [a for a in strong_aspects if a.get('aspect') in ['square', 'opposition']]
        harmonious_aspects = [a for a in strong_aspects if a.get('aspect') in ['trine', 'sextile', 'conjunction']]

        # Формируем анализ на основе РАСЧЕТОВ
        analysis_parts = []

        # Анализ энергии из биоритмов
        energy_level_ru = {
            'very_low': 'очень низкий',
            'low': 'низкий', 
            'medium': 'средний',
            'high': 'высокий',
            'very_high': 'очень высокий'
        }.get(energy_level, 'средний')
        
        analysis_parts.append(f"⚡ Уровень энергии: {energy_level_ru} ({energy_percentage:.1f}%)")

        # Анализ аспектов из астрологии
        if challenging_aspects:
            analysis_parts.append(f"🎯 Сложных аспектов: {len(challenging_aspects)}")

        if harmonious_aspects:
            analysis_parts.append(f"🌟 Гармоничных аспектов: {len(harmonious_aspects)}")

        # Общий вывод на основе РАСЧЕТОВ
        if energy_percentage > 70 and len(challenging_aspects) == 0:
            analysis_parts.append("✅ Идеальный день для активных действий")
        elif energy_percentage < 30 and len(challenging_aspects) > 2:
            analysis_parts.append("⚠️ Сохраняйте спокойствие, избегайте нагрузок")
        elif len(harmonious_aspects) > len(challenging_aspects):
            analysis_parts.append("📊 Преобладают гармоничные влияния")
        else:
            analysis_parts.append("📈 Сбалансированный энергетический профиль")

        return " | ".join(analysis_parts)

    def create_daily_schedule(self, biorhythm_data: dict) -> list:
        """Создание рекомендуемого расписания дня на основе РАСЧЕТОВ биоритмов"""

        schedule = []

        # Утренние рекомендации на основе РАСЧЕТОВ интеллектуального цикла
        morning_rec = "🌅 Утро: "
        intellectual_percentage = biorhythm_data.get('intellectual_percentage', 50)
        if intellectual_percentage > 60:
            morning_rec += f"планирование и анализ (интеллектуальный цикл: {intellectual_percentage:.1f}%)"
        else:
            morning_rec += f"легкая разминка и рутина (интеллектуальный цикл: {intellectual_percentage:.1f}%)"
        schedule.append(morning_rec)

        # Дневные рекомендации на основе РАСЧЕТОВ физического цикла
        day_rec = "🌞 День: "
        physical_percentage = biorhythm_data.get('physical_percentage', 50)
        if physical_percentage > 70:
            day_rec += f"активная работа и движение (физический цикл: {physical_percentage:.1f}%)"
        elif physical_percentage > 40:
            day_rec += f"умеренная активность (физический цикл: {physical_percentage:.1f}%)"
        else:
            day_rec += f"спокойная деятельность (физический цикл: {physical_percentage:.1f}%)"
        schedule.append(day_rec)

        # Вечерние рекомендации на основе РАСЧЕТОВ эмоционального цикла
        evening_rec = "🌙 Вечер: "
        emotional_percentage = biorhythm_data.get('emotional_percentage', 50)
        if emotional_percentage > 60:
            evening_rec += f"общение и творчество (эмоциональный цикл: {emotional_percentage:.1f}%)"
        else:
            evening_rec += f"отдых и уединение (эмоциональный цикл: {emotional_percentage:.1f}%)"
        schedule.append(evening_rec)

        return schedule

    def _extract_critical_notes(self, astro_prediction: dict, biorhythm_data: dict) -> list:
        """Извлечение критических замечаний на основе РАСЧЕТОВ обоих источников"""
        critical_notes = []

        # Критические дни из биоритмов на основе РАСЧЕТОВ
        if biorhythm_data.get('is_critical_day', False):
            critical_notes.append("⚠️ Сегодня критический день по биоритмам")

        # Сложные аспекты из астрологии на основе РАСЧЕТОВ
        aspects = astro_prediction.get('significant_aspects', [])
        challenging_aspects = [a for a in aspects if
                               a.get('aspect') in ['square', 'opposition'] and a.get('strength', 0) > 0.7]

        for aspect in challenging_aspects[:2]:  # Не более 2 самых сильных
            planet1 = aspect.get('transit_planet', '')
            planet2 = aspect.get('natal_planet', '')
            aspect_type = aspect.get('aspect', '')
            strength = aspect.get('strength', 0)

            planet1_ru = self._get_planet_name_ru(planet1)
            planet2_ru = self._get_planet_name_ru(planet2)

            if aspect_type == 'square':
                critical_notes.append(f"🔺 Напряженный аспект: {planet1_ru} - {planet2_ru} (сила: {strength:.2f})")
            elif aspect_type == 'opposition':
                critical_notes.append(f"⚖️ Сложный выбор: {planet1_ru} - {planet2_ru} (сила: {strength:.2f})")

        # Предостережения из астрологии
        warnings = astro_prediction.get('warnings', [])
        critical_notes.extend(warnings[:2])  # Не более 2 предостережений

        return critical_notes[:4]  # Не более 4 критических заметок

    def _get_planet_name_ru(self, planet_name: str) -> str:
        """Получение русского названия планеты"""
        planet_names_ru = {
            'Sun': 'Солнце', 'Moon': 'Луна', 'Mercury': 'Меркурий',
            'Venus': 'Венера', 'Mars': 'Марс', 'Jupiter': 'Юпитер',
            'Saturn': 'Сатурн', 'Uranus': 'Уран', 'Neptune': 'Нептун', 'Pluto': 'Плутон'
        }
        return planet_names_ru.get(planet_name, planet_name)


def safe_json_serialize(obj: Any) -> str:
    """Безопасная сериализация объекта в JSON"""
    def default_serializer(o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if hasattr(o, '__dict__'):
            return o.__dict__
        return str(o)
    
    return json.dumps(obj, default=default_serializer, ensure_ascii=False)


async def generate_and_save_prediction(user_id: int, target_date: date) -> Dict:
    """Генерация и сохранение предсказания с биоритмами на основе РАСЧЕТОВ"""
    
    # ✅ ОДИН БЛОК async_session ДЛЯ ВСЕХ ОПЕРАЦИЙ
    async with async_session() as session:
        try:
            logger.info(f"🔮 Генерация предсказания для пользователя {user_id} на {target_date}")

            # Получаем пользователя и user_id
            user = await get_user_id_by_platform(session, user_id)
            if not user:
                logger.warning(f"⚠️ Пользователь с telegram_id {user_id} не найден")
                raise ValueError(f"Пользователь с telegram_id {user_id} не найден")
            
            #user_id = user.id
            logger.info(f"✅ Найден user_id: {user_id} для telegram_id: {user_id}")

            # Получаем натальную карту пользователя
            natal_data = await get_user_natal_chart(user_id)
            if not natal_data:
                logger.warning(f"⚠️ Натальная карта не найдена для пользователя {user_id}")
                raise ValueError("Натальная карта не найдена. Сначала создайте натальную карту с помощью /start")

            logger.info(f"✅ Натальная карта найдена для {user_id}")

            # Рассчитываем биоритмы на основе РАСЧЕТОВ
            biorhythm_data = await get_user_biorhythm_profile(user_id, target_date)
            logger.info(f"✅ Биоритмы рассчитаны для {user_id}")

            # Генерируем астрологическое предсказание на основе РАСЧЕТОВ
            predictor = AstroPredictor(natal_data)
            astro_prediction = predictor.generate_prediction(target_date)
            logger.info(f"✅ Астрологическое предсказание сгенерировано для {user_id}")

            # Объединяем предсказания на основе РАСЧЕТОВ
            combiner = PredictionCombiner()
            combined_recommendations = combiner.combine_recommendations(astro_prediction, biorhythm_data)
            
            # ✅ ЗАЩИТА ОТ ПУСТЫХ РЕКОМЕНДАЦИЙ
            if not combined_recommendations:
                combined_recommendations = ["Сбалансированный день для планирования и отдыха"]
                logger.warning(f"⚠️ Созданы базовые рекомендации для {user_id}")
            
            energy_analysis = combiner.generate_energy_analysis(astro_prediction, biorhythm_data)
            daily_schedule = combiner.create_daily_schedule(biorhythm_data)
            critical_notes = combiner._extract_critical_notes(astro_prediction, biorhythm_data)

            # Создаем финальное предсказание на основе РАСЧЕТОВ
            final_prediction = {
                'prediction_date': target_date.isoformat(),
                'energy_analysis': energy_analysis,
                'biorhythms_summary': {
                    'overall_energy_level': biorhythm_data.get('overall_energy_level', 'medium'),
                    'overall_energy_percentage': biorhythm_data.get('overall_energy_percentage', 50),
                    'physical_percentage': biorhythm_data.get('physical_percentage', 50),
                    'physical_phase': biorhythm_data.get('physical_phase', 'neutral'),
                    'physical_trend': biorhythm_data.get('physical_trend', 'stable'),
                    'emotional_percentage': biorhythm_data.get('emotional_percentage', 50),
                    'emotional_phase': biorhythm_data.get('emotional_phase', 'neutral'),
                    'emotional_trend': biorhythm_data.get('emotional_trend', 'stable'),
                    'intellectual_percentage': biorhythm_data.get('intellectual_percentage', 50),
                    'intellectual_phase': biorhythm_data.get('intellectual_phase', 'neutral'),
                    'intellectual_trend': biorhythm_data.get('intellectual_trend', 'stable'),
                    'is_critical_day': biorhythm_data.get('is_critical_day', False),
                    'is_peak_day': biorhythm_data.get('is_peak_day', False)
                },
                'astro_summary': {
                    'significant_aspects_count': len(astro_prediction.get('significant_aspects', [])),
                    'strong_aspects_count': len([a for a in astro_prediction.get('significant_aspects', []) 
                                               if a.get('strength', 0) > 0.7]),
                    'transits_count': astro_prediction.get('transits_count', 0),
                    'key_aspects': astro_prediction.get('significant_aspects', [])[:3]
                },
                'combined_recommendations': combined_recommendations,
                'daily_schedule': daily_schedule,
                'critical_notes': critical_notes,
                
                # Полные данные для детального анализа
                'full_astro_prediction': astro_prediction,
                'full_biorhythm_data': biorhythm_data,

                # Мета-информация о расчетах
                'calculation_metadata': {
                    'calculation_timestamp': datetime.now().isoformat(),
                    'data_sources': ['astrology', 'biorhythms'],
                    'calculation_methods': ['swiss_ephemeris', 'sine_wave_analysis'],
                    'user_id': user_id
                }
            }

            logger.info(f"✅ Комбинированное предсказание создано для {user_id}")

            # ✅ БЕЗОПАСНАЯ СЕРИАЛИЗАЦИЯ В JSON
            prediction_json = safe_json_serialize(final_prediction)

            # Проверяем существующую запись
            result = await session.execute(
                select(Recommendation).where(
                    and_(
                        Recommendation.user_id == user_id,
                        Recommendation.calculation_date == target_date,
                        Recommendation.category == 'daily_prediction'
                    )
                )
            )
            existing_record = result.scalar_one_or_none()

            if existing_record:
                # Обновляем существующую запись
                existing_record.content = prediction_json
                existing_record.summary = energy_analysis
                existing_record.sections = safe_json_serialize({
                    'biorhythms_summary': final_prediction['biorhythms_summary'],
                    'astro_summary': final_prediction['astro_summary'],
                    'recommendations': final_prediction['combined_recommendations'],
                    'schedule': final_prediction['daily_schedule']
                })
                existing_record.relevance_score = 0.8
                existing_record.confidence_score = 0.7
                existing_record.personalization_score = 0.9
                existing_record.data_sources = ['astrology', 'biorhythms']
                existing_record.based_on = safe_json_serialize({
                    'astro_prediction': True,
                    'biorhythms': True,
                    'user_profile': True
                })
                existing_record.updated_at = datetime.now()  # ✅ ПРЯМОЕ ИСПОЛЬЗОВАНИЕ datetime
                logger.info(f"📝 Обновлена рекомендация для user_id {user_id} на дату {target_date}")
            else:
                # Создаем новую запись в recommendations
                new_recommendation = Recommendation(
                    user_id=user_id,
                    calculation_date=target_date,
                    title=f"Персональное предсказание на {target_date.strftime('%d.%m.%Y')}",
                    content=prediction_json,
                    summary=energy_analysis,
                    sections=safe_json_serialize({
                        'biorhythms_summary': final_prediction['biorhythms_summary'],
                        'astro_summary': final_prediction['astro_summary'],
                        'recommendations': final_prediction['combined_recommendations'],
                        'schedule': final_prediction['daily_schedule']
                    }),
                    activities=safe_json_serialize([]),
                    time_suggestions=safe_json_serialize({}),
                    category='daily_prediction',
                    tags=['астрология', 'биоритмы', 'предсказание'],
                    priority=3,
                    relevance_score=0.8,
                    confidence_score=0.7,
                    personalization_score=0.9,
                    data_sources=['astrology', 'biorhythms'],
                    based_on=safe_json_serialize({
                        'astro_prediction': True,
                        'biorhythms': True,
                        'user_profile': True
                    }),
                    is_ai_generated=True,
                    model_name='AstroPredictor_v1.0',
                    cache_key=f"prediction_{user_id}_{target_date.strftime('%Y%m%d')}",
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(new_recommendation)
                logger.info(f"🆕 Создана новая рекомендация для user_id {user_id} на дату {target_date}")

            await session.commit()
            logger.info(f"💾 Предсказание успешно сохранено в БД для {user_id}")

            return final_prediction

        except ValueError as e:
            logger.warning(f"❌ Ошибка валидации для {user_id}: {e}")
            await session.rollback()
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации предсказания для {user_id}: {e}")
            await session.rollback()
            raise Exception(f"Не удалось сгенерировать предсказание на основе расчетов: {str(e)}")


async def get_user_predictions(user_id: int, limit: int = 10) -> List[Dict]:
    """Получение предсказаний пользователя из новой таблицы recommendations"""
    try:
        async with async_session() as session:
            # Получаем user_id
            user = await get_user_id_by_platform(session, user_id)
            if not user:
                logger.warning(f"⚠️ Пользователь с telegram_id {user_id} не найден")
                return []
            
            #user_id = user.id
            
            # Получаем рекомендации
            result = await session.execute(
                select(Recommendation)
                .where(
                    and_(
                        Recommendation.user_id == user_id,
                        Recommendation.category == 'daily_prediction'
                    )
                )
                .order_by(Recommendation.calculation_date.desc())
                .limit(limit)
            )
            recommendations = result.scalars().unique().all()  # ✅ SQLAlchemy 2.0

            predictions = []
            for rec in recommendations:
                try:
                    # ✅ БЕЗОПАСНОЕ ЧТЕНИЕ JSON (не eval!)
                    if isinstance(rec.content, str):
                        try:
                            content = json.loads(rec.content)
                        except json.JSONDecodeError:
                            logger.error(f"❌ Невалидный JSON в рекомендации {rec.id}")
                            continue
                    else:
                        content = rec.content
                    
                    predictions.append({
                        'prediction_date': rec.calculation_date.isoformat(),
                        'title': rec.title,
                        'summary': rec.summary,
                        'content': content,
                        'created_at': rec.created_at.isoformat() if rec.created_at else None,
                        'relevance_score': rec.relevance_score,
                        'confidence_score': rec.confidence_score
                    })
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки рекомендации {rec.id}: {e}")
                    continue

            return predictions

    except Exception as e:
        logger.error(f"❌ Ошибка при получении предсказаний для {user_id}: {e}")
        return []


async def get_todays_prediction(user_id: int) -> Optional[Dict]:
    """Получение предсказания на сегодня"""
    try:
        today = datetime.now().date()
        
        async with async_session() as session:
            # Получаем user_id
            user = await get_user_id_by_platform(session, user_id)
            if not user:
                logger.warning(f"⚠️ Пользователь с telegram_id {user_id} не найден")
                return None
            
            #user_id = user.id
            
            # Пробуем найти сохраненное предсказание на сегодня
            result = await session.execute(
                select(Recommendation).where(
                    and_(
                        Recommendation.user_id == user_id,
                        Recommendation.calculation_date == today,
                        Recommendation.category == 'daily_prediction'
                    )
                )
            )
            existing_record = result.scalar_one_or_none()

            if existing_record and existing_record.content:
                try:
                    # ✅ БЕЗОПАСНОЕ ЧТЕНИЕ JSON
                    if isinstance(existing_record.content, str):
                        content = json.loads(existing_record.content)
                    else:
                        content = existing_record.content
                    
                    logger.info(f"✅ Использовано сохраненное предсказание для {user_id}")
                    return content
                except (json.JSONDecodeError, Exception) as e:
                    logger.error(f"❌ Ошибка парсинга сохраненного предсказания: {e}")
                    # Если не получается распарсить, генерируем заново

        # Если предсказания на сегодня нет или ошибка парсинга, генерируем новое
        logger.info(f"🔄 Генерация нового предсказания для {user_id}")
        return await generate_and_save_prediction(user_id, today)

    except Exception as e:
        logger.error(f"❌ Ошибка при получении сегодняшнего предсказания {user_id}: {e}")
        return None


async def format_prediction_for_display(prediction: dict) -> str:
    """Форматирование предсказания для отображения в боте на основе РАСЧЕТОВ"""
    if not prediction:
        return "❌ Не удалось получить предсказание на основе расчетов"

    try:
        lines = []
        prediction_date = prediction.get('prediction_date', 'сегодня')
        if prediction_date != 'сегодня':
            try:
                date_obj = datetime.fromisoformat(prediction_date.replace('Z', '+00:00')).date()
                prediction_date = date_obj.strftime('%d.%m.%Y')
            except:
                pass
        
        lines.append(f"🔮 **Ваше предсказание на {prediction_date}**")
        lines.append("")

        # Анализ энергии на основе РАСЧЕТОВ
        energy_analysis = prediction.get('energy_analysis', '')
        if energy_analysis:
            lines.append(f"⚡ {energy_analysis}")
            lines.append("")

        # Биоритмы на основе РАСЧЕТОВ
        biorhythms = prediction.get('biorhythms_summary', {})
        if biorhythms:
            energy_level_ru = {
                'very_low': 'очень низкий',
                'low': 'низкий', 
                'medium': 'средний',
                'high': 'высокий',
                'very_high': 'очень высокий'
            }.get(biorhythms.get('overall_energy_level', 'medium'), 'средний')
            
            lines.append(
                f"📊 **Биоритмы:** {energy_level_ru} уровень энергии ({biorhythms.get('overall_energy_percentage', 0):.1f}%)")

            # Физический цикл
            physical_phase_ru = {
                'positive': 'положительная',
                'negative': 'отрицательная', 
                'critical': 'критическая',
                'neutral': 'нейтральная'
            }.get(biorhythms.get('physical_phase', 'neutral'), 'нейтральная')
            
            physical_trend_ru = {
                'rising': 'растет',
                'falling': 'падает',
                'stable': 'стабильно'
            }.get(biorhythms.get('physical_trend', 'stable'), 'стабильно')
            
            lines.append(
                f"💪 Физический: {physical_phase_ru} ({biorhythms.get('physical_percentage', 0):.1f}%) - {physical_trend_ru}")

            # Эмоциональный цикл
            emotional_phase_ru = {
                'positive': 'положительная',
                'negative': 'отрицательная', 
                'critical': 'критическая',
                'neutral': 'нейтральная'
            }.get(biorhythms.get('emotional_phase', 'neutral'), 'нейтральная')
            
            emotional_trend_ru = {
                'rising': 'растет',
                'falling': 'падает',
                'stable': 'стабильно'
            }.get(biorhythms.get('emotional_trend', 'stable'), 'стабильно')
            
            lines.append(
                f"😊 Эмоциональный: {emotional_phase_ru} ({biorhythms.get('emotional_percentage', 0):.1f}%) - {emotional_trend_ru}")

            # Интеллектуальный цикл
            intellectual_phase_ru = {
                'positive': 'положительная',
                'negative': 'отрицательная', 
                'critical': 'критическая',
                'neutral': 'нейтральная'
            }.get(biorhythms.get('intellectual_phase', 'neutral'), 'нейтральная')
            
            intellectual_trend_ru = {
                'rising': 'растет',
                'falling': 'падает',
                'stable': 'стабильно'
            }.get(biorhythms.get('intellectual_trend', 'stable'), 'стабильно')
            
            lines.append(
                f"🧠 Интеллектуальный: {intellectual_phase_ru} ({biorhythms.get('intellectual_percentage', 0):.1f}%) - {intellectual_trend_ru}")
            lines.append("")

        # Астрологическая сводка на основе РАСЧЕТОВ
        astro_summary = prediction.get('astro_summary', {})
        if astro_summary:
            lines.append(
                f"🌟 **Астрология:** {astro_summary.get('significant_aspects_count', 0)} аспектов, {astro_summary.get('strong_aspects_count', 0)} сильных")
            lines.append("")

        # Расписание дня на основе РАСЧЕТОВ биоритмов
        schedule = prediction.get('daily_schedule', [])
        if schedule:
            lines.append("🕒 **Рекомендуемое расписание на основе биоритмов:**")
            for item in schedule:
                lines.append(f"   {item}")
            lines.append("")

        # Рекомендации на основе РАСЧЕТОВ
        recommendations = prediction.get('combined_recommendations', [])
        if recommendations:
            lines.append("💫 **Рекомендации на день (на основе расчетов):**")
            for i, rec in enumerate(recommendations[:6], 1):  # Не более 6 рекомендаций
                lines.append(f"{i}. {rec}")
            lines.append("")

        # Критические заметки на основе РАСЧЕТОВ
        critical_notes = prediction.get('critical_notes', [])
        if critical_notes:
            lines.append("⚠️ **Обратите внимание (на основе расчетов):**")
            for note in critical_notes[:3]:  # Не более 3 заметок
                lines.append(f"   • {note}")
            lines.append("")

        # Информация о расчетах
        lines.append("📈 *Все рекомендации основаны на математических расчетах:*")
        lines.append("   • Астрологические транзиты и аспекты")
        lines.append("   • Биоритмы (физический, эмоциональный, интеллектуальный циклы)")
        lines.append("   • Статистический анализ влияний")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"❌ Ошибка форматирования предсказания: {e}")
        return "❌ Произошла ошибка при формировании предсказания на основе расчетов"


async def get_prediction_statistics(user_id: int) -> Dict:
    """Получение статистики предсказаний пользователя"""
    try:
        async with async_session() as session:
            # Получаем user_id
            user = await get_user_id_by_platform(session, user_id)
            if not user:
                logger.warning(f"⚠️ Пользователь с telegram_id {user_id} не найден")
                return {}
            
            #user_id = user.id
            
            # Статистика по рекомендациям
            result = await session.execute(
                select(func.count(Recommendation.id))
                .where(
                    and_(
                        Recommendation.user_id == user_id,
                        Recommendation.category == 'daily_prediction'
                    )
                )
            )
            total_predictions = result.scalar() or 0
            
            # Последнее предсказание
            result = await session.execute(
                select(Recommendation)
                .where(
                    and_(
                        Recommendation.user_id == user_id,
                        Recommendation.category == 'daily_prediction'
                    )
                )
                .order_by(Recommendation.calculation_date.desc())
                .limit(1)
            )
            last_prediction = result.scalar_one_or_none()
            
            if last_prediction and last_prediction.content:
                try:
                    # ✅ БЕЗОПАСНОЕ ЧТЕНИЕ JSON
                    if isinstance(last_prediction.content, str):
                        content = json.loads(last_prediction.content)
                    else:
                        content = last_prediction.content
                        
                    return {
                        'total_predictions': total_predictions,
                        'last_prediction_date': last_prediction.calculation_date.isoformat(),
                        'last_prediction_energy': content.get('biorhythms_summary', {}).get('overall_energy_percentage', 0),
                        'last_prediction_aspects': content.get('astro_summary', {}).get('significant_aspects_count', 0),
                        'relevance_score': last_prediction.relevance_score or 0.5,
                        'confidence_score': last_prediction.confidence_score or 0.5,
                        'personalization_score': last_prediction.personalization_score or 0.5
                    }
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга последнего предсказания: {e}")
            
            return {
                'total_predictions': total_predictions,
                'last_prediction_date': None,
                'last_prediction_energy': 0,
                'last_prediction_aspects': 0,
                'relevance_score': 0.5,
                'confidence_score': 0.5,
                'personalization_score': 0.5
            }

    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики для {user_id}: {e}")
        return {}


async def validate_prediction_data(telegram_id: int) -> bool:
    """Проверка корректности данных предсказания"""
    try:
        prediction = await get_todays_prediction(telegram_id)
        if not prediction:
            return False

        # Проверяем наличие обязательных полей
        required_fields = ['prediction_date', 'energy_analysis', 'combined_recommendations']
        for field in required_fields:
            if field not in prediction or not prediction[field]:
                return False

        # Проверяем что рекомендации не пустые
        if not prediction.get('combined_recommendations'):
            return False

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка валидации данных предсказания для {telegram_id}: {e}")
        return False


async def cleanup_old_predictions(days_to_keep: int = 30):
    """Очистка устаревших предсказаний (для администрирования)"""
    try:
        async with async_session() as session:
            cutoff_date = datetime.now().date() - timedelta(days=days_to_keep)
            
            # Удаляем старые рекомендации
            result = await session.execute(
                select(Recommendation).where(
                    and_(
                        Recommendation.category == 'daily_prediction',
                        Recommendation.calculation_date < cutoff_date
                    )
                )
            )
            old_predictions = result.scalars().unique().all()
            
            count = 0
            for prediction in old_predictions:
                await session.delete(prediction)
                count += 1
            
            await session.commit()
            logger.info(f"🧹 Удалено {count} устаревших предсказаний старше {days_to_keep} дней")
            return count

    except Exception as e:
        logger.error(f"❌ Ошибка при очистке предсказаний: {e}")
        return 0


async def get_prediction_by_date(user_id: int, target_date: date) -> Optional[Dict]:
    """Получение предсказания на конкретную дату"""
    try:
        async with async_session() as session:
            # Получаем user_id
            user = await get_user_id_by_platform(session, user_id)
            if not user:
                logger.warning(f"⚠️ Пользователь с telegram_id {user_id} не найден")
                return None
            
            #user_id = user.id
            
            # Ищем предсказание на указанную дату
            result = await session.execute(
                select(Recommendation).where(
                    and_(
                        Recommendation.user_id == user_id,
                        Recommendation.calculation_date == target_date,
                        Recommendation.category == 'daily_prediction'
                    )
                )
            )
            prediction_record = result.scalar_one_or_none()
            
            if prediction_record and prediction_record.content:
                try:
                    # ✅ БЕЗОПАСНОЕ ЧТЕНИЕ JSON
                    if isinstance(prediction_record.content, str):
                        content = json.loads(prediction_record.content)
                    else:
                        content = prediction_record.content
                    return content
                except Exception as e:
                    logger.error(f"❌ Ошибка парсинга предсказания на {target_date}: {e}")
            
            # Если нет сохраненного предсказания, генерируем новое
            logger.info(f"🔄 Генерация нового предсказания для {user_id} на {target_date}")
            return await generate_and_save_prediction(user_id, target_date)

    except Exception as e:
        logger.error(f"❌ Ошибка при получении предсказания на {target_date} для {user_id}: {e}")
        return None


async def update_prediction_feedback(user_id: int, date: date, rating: int, feedback: str = None) -> bool:
    """Обновление обратной связи пользователя о предсказании"""
    try:
        async with async_session() as session:
            # Получаем user_id
            user = await get_user_id_by_platform(session, user_id)
            if not user:
                logger.warning(f"⚠️ Пользователь с telegram_id {user_id} не найден")
                return False
            
            #user_id = user.id
            
            # Находим предсказание
            result = await session.execute(
                select(Recommendation).where(
                    and_(
                        Recommendation.user_id == user_id,
                        Recommendation.calculation_date == date,
                        Recommendation.category == 'daily_prediction'
                    )
                )
            )
            prediction_record = result.scalar_one_or_none()
            
            if not prediction_record:
                logger.warning(f"⚠️ Предсказание на {date} для {user_id} не найдено")
                return False
            
            # Обновляем обратную связь
            prediction_record.user_rating = rating
            if feedback:
                prediction_record.feedback = feedback
            prediction_record.updated_at = datetime.now()
            
            await session.commit()
            logger.info(f"✅ Обратная связь обновлена для предсказания на {date} для {user_id}")
            return True

    except Exception as e:
        logger.error(f"❌ Ошибка обновления обратной связи для {user_id}: {e}")
        return False
