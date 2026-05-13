"""
natal_chart_service.py - Сервис для работы с натальными картами
Адаптирован под новую структуру данных из ephemeris_base.py
"""

from ..calculators.natal_chart import get_natal_calculator
from ..database.core import async_session
from ..database.models import NatalChart
from sqlalchemy import select, func
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Union
import pytz
from dateutil import parser

logger = logging.getLogger(__name__)


def parse_iso_datetime(dt_value: Union[str, datetime, None], tz_name: Optional[str] = None) -> Optional[datetime]:
    """
    Универсальный парсер datetime из строки или объекта
    
    Args:
        dt_value: строка ISO формата, datetime объект или None
        tz_name: название часового пояса для локализации naive datetime
    
    Returns:
        timezone-aware datetime объект или None при ошибке
    """
    if dt_value is None:
        return None
    
    # Если это уже datetime объект
    if isinstance(dt_value, datetime):
        dt = dt_value
    else:
        try:
            # Парсим строку (работает с 'Z', '+00:00', 'T' разделителем и т.д.)
            dt = parser.parse(str(dt_value))
            logger.debug(f"Parsed datetime from string: {dt_value} -> {dt}")
        except Exception as e:
            logger.warning(f"Failed to parse datetime from string '{dt_value}': {e}")
            return None
    
    # Добавляем timezone если нужно и указан часовой пояс
    if tz_name and dt.tzinfo is None:
        try:
            tz = pytz.timezone(tz_name)
            dt = tz.localize(dt)
            logger.debug(f"Localized naive datetime to timezone {tz_name}: {dt}")
        except Exception as e:
            logger.warning(f"Failed to localize datetime to timezone {tz_name}: {e}")
    
    return dt


async def create_and_save_natal_chart(
        user_id: int,
        city: str,
        birth_datetime: datetime,
        timezone: str = 'Europe/Moscow',
        house_system: str = 'P'
) -> NatalChart:
    """
    Создание и сохранение натальной карты — ПОЛНАЯ ВЕРСИЯ с новыми полями
    """
    try:
        logger.info(f"🌟 Создание натальной карты для user_id={user_id}, город={city}")

        # 1. Получаем калькулятор и рассчитываем карту
        calculator = await get_natal_calculator()
        natal_data = await calculator.calculate_natal_chart(
            city_name=city,
            birth_datetime_local=birth_datetime,
            timezone_str=timezone,
            house_system=house_system,
            include_all=True,
            include_heavy=True  # ✅ Явно указываем
        )

        # 2. Проверяем статус расчета
        if natal_data.get('calculation_status') == 'failed':
            error_msg = natal_data.get('error_message', 'Unknown error')
            logger.error(f"❌ Расчет карты failed: {error_msg}")
            raise ValueError(f"Failed to calculate natal chart: {error_msg}")

        # 3. Извлекаем данные для сохранения
        async with async_session() as session:
            # Проверяем существующую карту
            result = await session.execute(
                select(NatalChart)
                .where(NatalChart.user_id == user_id)
                .order_by(NatalChart.calculation_date.desc())
                .limit(1)
            )
            existing_chart = result.scalar_one_or_none()

            if existing_chart:
                chart = existing_chart
                logger.info(f"📝 Обновление карты #{chart.id} для user_id={user_id}")
            else:
                chart = NatalChart(user_id=user_id)
                logger.info(f"🆕 Создание новой карты для user_id={user_id}")

            # 4. Заполняем все поля из natal_data
            # Геоданные
            chart.city_name = city
            chart.birth_lat = natal_data.get('birth_lat')
            chart.birth_lng = natal_data.get('birth_lng')
            chart.birth_timezone = natal_data.get('birth_timezone', timezone)
            chart.birth_country_code = natal_data.get('birth_country_code', 'RU')
            chart.system_language = natal_data.get('system_language', 'ru')
            chart.geocoder_cache_key = natal_data.get('geocoder_cache_key')
            chart.geocoder_source = natal_data.get('geocoder_source', 'nominatim')

            # Временные метки
            chart.birth_datetime_local = parse_iso_datetime(
                natal_data.get('birth_datetime_local'),
                natal_data.get('birth_timezone', timezone)
            )
            chart.birth_datetime_utc = parse_iso_datetime(
                natal_data.get('birth_datetime_utc')
            )

            logger.info(f"✅ birth_datetime_local: {chart.birth_datetime_local}")
            logger.info(f"✅ birth_datetime_utc: {chart.birth_datetime_utc}")

            chart.julian_day = natal_data.get('julian_day')
            chart.calculation_time_ms = natal_data.get('calculation_time_ms')

            # Основные астрологические данные
            chart.planets = natal_data.get('planets', {})
            chart.houses = natal_data.get('houses', {})
            chart.aspects = natal_data.get('aspects', [])

            # Джйотиш
            chart.panchanga = natal_data.get('panchanga', {})
            chart.dasha = natal_data.get('dasha', {})

            # Дополнительные расчеты
            chart.arabic_parts = natal_data.get('arabic_parts', {})
            chart.fixed_stars = natal_data.get('fixed_stars', [])
            chart.planetary_hour = natal_data.get('planetary_hour', {})

            # Метаданные расчетов
            chart.ayanamsa = natal_data.get('ayanamsa')
            chart.sidereal_time = natal_data.get('sidereal_time')
            chart.void_of_course_moon = natal_data.get('void_of_course_moon', False)
            chart.moon_phase_degrees = natal_data.get('moon_phase_degrees')

            # Детальные данные Луны и Солнца
            chart.moon_data = natal_data.get('moon_data', {})
            chart.solar_data = natal_data.get('solar_data', {})

            # ✅ НОВЫЕ ПОЛЯ (с проверкой наличия в модели)
            if hasattr(chart, 'aspect_qualities'):
                chart.aspect_qualities = natal_data.get('aspect_qualities', [])

            if hasattr(chart, 'patterns'):
                chart.patterns = natal_data.get('patterns', {})

            if hasattr(chart, 'star_interpretations'):
                chart.star_interpretations = natal_data.get('star_interpretations', [])

            if hasattr(chart, 'arabic_connections'):
                chart.arabic_connections = natal_data.get('arabic_connections', {})

            # Дополнительные точки
            chart.critical_degrees = natal_data.get('critical_degrees', [])
            chart.midpoints = natal_data.get('midpoints', {})

            # Календарные данные
            chart.weekday = natal_data.get('weekday', 'Monday')
            chart.weekday_ruler = natal_data.get('weekday_ruler')

            # ML-признаки (уже содержат все новые метрики)
            chart.ml_features = natal_data.get('ml_features', {})

            # ✅ Метаданные расчета
            chart.calculation_metadata = {
                'calculation_time_ms': natal_data.get('calculation_time_ms'),
                'include_all': True,
                'include_heavy': True,
                'aspect_qualities_count': len(natal_data.get('aspect_qualities', [])),
                'patterns_count': len(natal_data.get('patterns', {})) if natal_data.get('patterns') else 0,
                'star_interpretations_count': len(natal_data.get('star_interpretations', [])),
                'arabic_connections_count': len(natal_data.get('arabic_connections', {}))
            }

            # Система домов и статус
            chart.house_system = natal_data.get('house_system', house_system)
            chart.calculation_status = natal_data.get('calculation_status', 'success')
            chart.error_message = natal_data.get('error_message')

            # Обновляем даты
            chart.calculation_date = func.current_date()
            chart.calculation_timestamp = func.now()

            # Сохраняем
            if not existing_chart:
                session.add(chart)

            await session.commit()
            await session.refresh(chart)

            logger.info(f"💾 Натальная карта #{chart.id} сохранена для user_id={user_id}")

            return chart

    except Exception as e:
        logger.error(f"❌ Ошибка создания натальной карты для user_id={user_id}: {e}")
        raise
            
    except Exception as e:
        logger.error(f"❌ Ошибка создания натальной карты для user_id={user_id}: {e}")
        raise


async def get_user_natal_chart(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение последней натальной карты пользователя (полная версия)
    """
    try:
        async with async_session() as session:
            result = await session.execute(
                select(NatalChart)
                .where(NatalChart.user_id == user_id)
                .order_by(NatalChart.calculation_date.desc())
                .limit(1)
            )
            chart = result.scalar_one_or_none()

            if not chart:
                logger.info(f"ℹ️ Карта для user_id={user_id} не найдена")
                return None

            # Преобразуем в словарь со всеми полями
            result_dict = {
                'id': chart.id,
                'user_id': chart.user_id,

                # Геоданные
                'city_name': chart.city_name,
                'latitude': float(chart.birth_lat) if chart.birth_lat else None,
                'longitude': float(chart.birth_lng) if chart.birth_lng else None,
                'timezone': chart.birth_timezone,
                'country_code': chart.birth_country_code,
                'geocoder_source': chart.geocoder_source,

                # Временные метки
                'birth_datetime_local': chart.birth_datetime_local.isoformat() if chart.birth_datetime_local else None,
                'birth_datetime_utc': chart.birth_datetime_utc.isoformat() if chart.birth_datetime_utc else None,
                'julian_day': float(chart.julian_day) if chart.julian_day else None,
                'calculation_date': chart.calculation_date.isoformat() if chart.calculation_date else None,

                # Астрологические данные
                'planets': chart.planets,
                'houses': chart.houses,
                'aspects': chart.aspects,

                # Джйотиш
                'panchanga': chart.panchanga,
                'dasha': chart.dasha,

                # Дополнительные расчеты
                'arabic_parts': chart.arabic_parts,
                'fixed_stars': chart.fixed_stars,
                'planetary_hour': chart.planetary_hour,

                # Метаданные
                'ayanamsa': float(chart.ayanamsa) if chart.ayanamsa else None,
                'sidereal_time': float(chart.sidereal_time) if chart.sidereal_time else None,
                'void_of_course_moon': chart.void_of_course_moon,
                'moon_phase_degrees': float(chart.moon_phase_degrees) if chart.moon_phase_degrees else None,

                # Детальные данные Луны и Солнца
                'moon_data': chart.moon_data,
                'solar_data': chart.solar_data,

                # ✅ НОВЫЕ ПОЛЯ
                'aspect_qualities': getattr(chart, 'aspect_qualities', []),
                'patterns': getattr(chart, 'patterns', {}),
                'star_interpretations': getattr(chart, 'star_interpretations', []),
                'arabic_connections': getattr(chart, 'arabic_connections', {}),

                # Дополнительные точки
                'critical_degrees': chart.critical_degrees,
                'midpoints': chart.midpoints,

                # Календарные данные
                'weekday': chart.weekday,
                'weekday_ruler': chart.weekday_ruler,

                # ML-признаки
                'ml_features': chart.ml_features,

                # Метаданные расчета
                'calculation_metadata': getattr(chart, 'calculation_metadata', {}),

                # Система домов и статус
                'house_system': chart.house_system,
                'calculation_status': chart.calculation_status,
                'error_message': chart.error_message,

                # Метаданные записи
                'created_at': chart.created_at.isoformat() if chart.created_at else None,
                'updated_at': chart.updated_at.isoformat() if chart.updated_at else None,

                # Флаг полной версии
                'full_record': True
            }

            return result_dict

    except Exception as e:
        logger.error(f"❌ Ошибка получения карты для user_id={user_id}: {e}")
        return None


async def get_user_natal_chart_legacy(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение натальной карты в старом формате (обратная совместимость)
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Словарь в старом формате или None
    """
    try:
        full_chart = await get_user_natal_chart(user_id)
        
        if not full_chart:
            return None
        
        # Конвертируем в старый формат
        return {
            'id': full_chart['id'],
            'planets': full_chart['planets'],
            'houses': full_chart['houses'],
            'aspects': full_chart['aspects'],
            'ml_features': full_chart['ml_features'],
            'latitude': full_chart['latitude'],
            'longitude': full_chart['longitude'],
            'house_system': full_chart['house_system'],
            'city_name': full_chart['city_name'],
            'birth_timezone': full_chart['timezone'],
            'geocoder_source': full_chart['geocoder_source'],
            'calculation_date': full_chart['calculation_date']
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения legacy карты для user_id={user_id}: {e}")
        return None


async def get_user_natal_chart_by_id(chart_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение натальной карты по ID
    
    Args:
        chart_id: ID карты
        
    Returns:
        Словарь с данными карты или None
    """
    try:
        async with async_session() as session:
            result = await session.execute(
                select(NatalChart)
                .where(NatalChart.id == chart_id)
            )
            chart = result.scalar_one_or_none()
            
            if not chart:
                return None
            
            # Используем тот же формат, что и get_user_natal_chart
            return await get_user_natal_chart(chart.user_id)
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения карты по ID {chart_id}: {e}")
        return None


async def delete_user_natal_chart(user_id: int, chart_id: Optional[int] = None) -> bool:
    """
    Удаление натальной карты пользователя
    
    Args:
        user_id: ID пользователя
        chart_id: ID конкретной карты (если None - удалить все)
        
    Returns:
        True если успешно, False если ошибка
    """
    try:
        async with async_session() as session:
            query = select(NatalChart).where(NatalChart.user_id == user_id)
            
            if chart_id:
                query = query.where(NatalChart.id == chart_id)
            
            result = await session.execute(query)
            charts = result.scalars().all()
            
            if not charts:
                logger.info(f"ℹ️ Карты для user_id={user_id} не найдены")
                return False
            
            for chart in charts:
                await session.delete(chart)
            
            await session.commit()
            
            logger.info(f"🗑️ Удалено {len(charts)} карт для user_id={user_id}" + 
                       (f" (ID={chart_id})" if chart_id else ""))
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка удаления карты для user_id={user_id}: {e}")
        return False


async def get_natal_chart_stats() -> Dict[str, Any]:
    """
    Статистика по натальным картам
    
    Returns:
        Словарь со статистикой
    """
    try:
        async with async_session() as session:
            # Общее количество
            total_result = await session.execute(
                select(func.count(NatalChart.id))
            )
            total = total_result.scalar()
            
            # Количество успешных
            success_result = await session.execute(
                select(func.count(NatalChart.id))
                .where(NatalChart.calculation_status == 'success')
            )
            success = success_result.scalar()
            
            # Количество с ошибками
            failed_result = await session.execute(
                select(func.count(NatalChart.id))
                .where(NatalChart.calculation_status == 'failed')
            )
            failed = failed_result.scalar()
            
            # Уникальные пользователи
            users_result = await session.execute(
                select(func.count(func.distinct(NatalChart.user_id)))
            )
            unique_users = users_result.scalar()
            
            # Распределение по системам домов
            houses_result = await session.execute(
                select(NatalChart.house_system, func.count(NatalChart.id))
                .group_by(NatalChart.house_system)
            )
            house_systems = {row[0]: row[1] for row in houses_result}
            
            return {
                'total_charts': total,
                'successful': success,
                'failed': failed,
                'unique_users': unique_users,
                'house_systems': house_systems,
                'success_rate': round(success / total * 100, 2) if total > 0 else 0
            }
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return {}


# Алиасы для обратной совместимости
get_user_natal_chart_latest = get_user_natal_chart
