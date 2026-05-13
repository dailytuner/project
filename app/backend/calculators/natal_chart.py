"""
natal_charts.py - Модуль для расчета натальной карты
Адаптирован под новую базу ephemeris_calculator
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
import json
from .ephemeris_base import PlanetPosition, Aspect
from .ephemeris_base import (
    EphemerisCalculator, 
    RawEphemeris,
    GeoCoordinates,
    get_ephemeris_calculator,
    ZODIAC_SIGNS
)
from .geocoder import AsyncCityGeocoder

logger = logging.getLogger(__name__)


class NatalChartCalculator:
    """
    Калькулятор натальной карты, использующий EphemerisCalculator
    """
    
    def __init__(
        self,
        ephemeris_calculator: Optional[EphemerisCalculator] = None,
        geocoder: Optional[AsyncCityGeocoder] = None
    ):
        """
        Инициализация калькулятора
        
        Args:
            ephemeris_calculator: Экземпляр EphemerisCalculator
            geocoder: Экземпляр AsyncCityGeocoder
        """
        self.ephemeris = ephemeris_calculator
        self.geocoder = geocoder
        
        # Кэш координат
        self.coordinates_cache: Dict[str, GeoCoordinates] = {}
        
        # ML-фичи будут рассчитываться на лету
        self.ml_features_enabled = True
        
        logger.info("✅ NatalChartCalculator создан")
    
    async def ensure_initialized(self):
        """Проверка инициализации компонентов"""
        if self.ephemeris is None:
            self.ephemeris = await get_ephemeris_calculator()
        
        if self.geocoder is None:
            self.geocoder = AsyncCityGeocoder(
                user_agent="NatalBot/1.0",
                cache_db_path="/tmp/geocoder_cache.db"
            )
            await self.geocoder.initialize()
    
    async def get_city_coordinates(self, city_name: str) -> GeoCoordinates:
        """
        Получение координат города через геокодер
        
        Args:
            city_name: Название города
            
        Returns:
            GeoCoordinates с координатами
        """
        await self.ensure_initialized()
        
        cache_key = city_name.lower().strip()
        
        # Проверка кэша
        if cache_key in self.coordinates_cache:
            logger.debug(f"✅ Координаты из кэша: {city_name}")
            return self.coordinates_cache[cache_key]
        
        try:
            # Геокодирование
            coords = await self.geocoder.geocode(city_name, country_code="ru")
            
            if coords and coords.lat is not None and coords.lon is not None:
                geo = GeoCoordinates(
                    lat=coords.lat,
                    lon=coords.lon,
                    timezone=coords.timezone,
                    city=city_name,
                    country=coords.country_code
                )
                
                # Сохраняем в кэш
                self.coordinates_cache[cache_key] = geo
                logger.info(f"✅ Геокодирован: {city_name} → {coords.lat:.4f}, {coords.lon:.4f}")
                return geo
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка геокодирования {city_name}: {e}")
        
        # Fallback на Москву
        logger.warning(f"🗺️ Fallback Москва для {city_name}")
        geo = GeoCoordinates(
            lat=55.7558,
            lon=37.6173,
            timezone="Europe/Moscow",
            city="Moscow",
            country="RU"
        )
        self.coordinates_cache[cache_key] = geo
        return geo
    
    def _get_weekday(self, dt: datetime) -> str:
        """Получить день недели"""
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 
                    'Thursday', 'Friday', 'Saturday', 'Sunday']
        return weekdays[dt.weekday()]
    
    def _get_weekday_ruler(self, weekday: str) -> str:
        """Получить управителя дня"""
        rulers = {
            'Monday': 'Moon', 'Tuesday': 'Mars', 'Wednesday': 'Mercury',
            'Thursday': 'Jupiter', 'Friday': 'Venus', 'Saturday': 'Saturn',
            'Sunday': 'Sun'
        }
        return rulers.get(weekday, 'Sun')

    def _calculate_ml_features(self, chart: RawEphemeris) -> Dict[str, Any]:
        """Расчет ML-фич из эфемеридных данных"""
        if not self.ml_features_enabled:
            return {}

        # 1. Распределение по знакам
        sign_distribution = {sign: 0 for sign in ZODIAC_SIGNS}
        for planet in chart.planets.values():
            sign_distribution[planet.sign] += 1

        # 2. Баланс элементов
        elements = {
            'fire': ['Aries', 'Leo', 'Sagittarius'],
            'earth': ['Taurus', 'Virgo', 'Capricorn'],
            'air': ['Gemini', 'Libra', 'Aquarius'],
            'water': ['Cancer', 'Scorpio', 'Pisces']
        }

        element_balance = {element: 0 for element in elements}
        for planet in chart.planets.values():
            for element, signs in elements.items():
                if planet.sign in signs:
                    element_balance[element] += 1
                    break

        # 3. Паттерны аспектов
        aspect_patterns = {
            'conjunction': 0,
            'opposition': 0,
            'trine': 0,
            'square': 0,
            'sextile': 0,
            'other': 0
        }

        for aspect in chart.aspects:
            if aspect.aspect_type in aspect_patterns:
                aspect_patterns[aspect.aspect_type] += 1
            else:
                aspect_patterns['other'] += 1

        # 4. Сила аспектов (средний орб)
        avg_orb = 0
        if chart.aspects:
            avg_orb = sum(a.orb for a in chart.aspects) / len(chart.aspects)

        # 5. Распределение планет по домам
        house_distribution = {i: 0 for i in range(1, 13)}
        for planet in chart.planets.values():
            if planet.house:
                house_distribution[planet.house] += 1

        # 6. Статистика ретроградности
        retrograde_count = sum(1 for p in chart.planets.values() if p.retrograde)

        # 7. Фаза Луны
        moon_phase = chart.moon_phase
        if moon_phase < 45 or moon_phase > 315:
            moon_phase_name = "new"
        elif moon_phase < 135:
            moon_phase_name = "first_quarter"
        elif moon_phase < 225:
            moon_phase_name = "full"
        else:
            moon_phase_name = "last_quarter"

        # 8. Средний счет достоинств
        avg_dignity_score = 0
        dignity_scores = [p.dignity_score for p in chart.planets.values() if hasattr(p, 'dignity_score')]
        if dignity_scores:
            avg_dignity_score = sum(dignity_scores) / len(dignity_scores)

        # 9. Паттерны (количество активных)
        active_patterns = 0
        if chart.patterns:
            for pattern_name, pattern_value in chart.patterns.items():
                if pattern_name != 'stellium' and pattern_value:
                    if isinstance(pattern_value, dict) and pattern_value:
                        active_patterns += 1
                    elif isinstance(pattern_value, list) and pattern_value:
                        active_patterns += 1
                    elif pattern_value:
                        active_patterns += 1

        planet_strengths = {}
        for name, planet in chart.planets.items():
            planet_strengths[name] = self._calculate_planet_strength(planet)

        # Добавить ретроградные планеты списком
        retrograde_planets = [name for name, p in chart.planets.items() if p.retrograde]

        return {
            'sign_distribution': sign_distribution,
            'element_balance': element_balance,
            'aspect_patterns': aspect_patterns,
            'avg_aspect_orb': round(avg_orb, 4),
            'house_distribution': house_distribution,
            'retrograde_count': retrograde_count,
            'total_planets': len(chart.planets),
            'moon_phase': round(moon_phase, 4),
            'moon_phase_name': moon_phase_name,
            'has_void_of_course_moon': chart.void_of_course,
            'critical_degrees_count': len(chart.critical_degrees),
            'fixed_stars_count': len(chart.fixed_stars),
            'avg_dignity_score': round(avg_dignity_score, 2),
            'active_patterns_count': active_patterns,
            'aspect_qualities_count': len(chart.aspect_qualities) if chart.aspect_qualities else 0,
            'has_yod': bool(chart.patterns and chart.patterns.get('yod')) if chart.patterns else False,
            'has_t_square': bool(chart.patterns and chart.patterns.get('t_square')) if chart.patterns else False,
            'has_grand_trine': bool(chart.patterns and chart.patterns.get('grand_trine')) if chart.patterns else False,
            'planet_strengths': planet_strengths,      # Новое
            'retrograde_planets': retrograde_planets,  # Новое
            'avg_planet_strength': round(sum(planet_strengths.values()) / max(1, len(planet_strengths)), 4)
        }

    async def calculate_batch_with_progress(
            self,
            charts_data: List[Tuple[str, datetime, Optional[str]]],
            house_system: str = 'P',
            include_heavy: bool = False,
            progress_callback=None
    ) -> List[Optional[Dict]]:
        """
        Пакетный расчет с прогрессом
        """
        results = []
        total = len(charts_data)

        for i, (city_name, dt, tz) in enumerate(charts_data):
            try:
                chart = await self.calculate_natal_chart(
                    city_name=city_name,
                    birth_datetime_local=dt,
                    timezone_str=tz,
                    house_system=house_system,
                    include_all=True,
                    include_heavy=include_heavy
                )
                results.append(chart)

                if progress_callback:
                    await progress_callback(i + 1, total, city_name)

            except Exception as e:
                logger.error(f"Batch error for {city_name}: {e}")
                results.append(None)

        return results

    def _calculate_planet_strength(self, planet) -> float:
        """
        Расчет силы планеты на основе достоинства и ретроградности.
        Возвращает значение от 0.1 до 0.9.
        """
        # Базовое значение из достоинства (-5..5 -> 0..1)
        dignity_score = getattr(planet, 'dignity_score', 0)
        base = (dignity_score + 5) / 10.0

        # Штраф за ретроградность (-0.15)
        if getattr(planet, 'retrograde', False):
            base = max(0.1, base - 0.15)

        # Бонус за скорость (медленные планеты важнее)
        speed = abs(getattr(planet, 'speed_long', 1.0))
        if speed < 0.5:  # медленная планета
            base = min(0.9, base + 0.1)

        # Ограничиваем диапазон
        return max(0.1, min(0.9, base))

    def _format_planets_for_db(self, chart: RawEphemeris) -> Dict:
        """
        Форматирование планет для сохранения в БД
        """
        planets = {}
        for name, pos in chart.planets.items():
            strength = self._calculate_planet_strength(pos)
            planets[name] = {
                'longitude': pos.longitude,
                'latitude': pos.latitude,
                'distance': pos.distance,
                'speed_long': pos.speed_long,
                'sign': pos.sign,
                'sign_longitude': pos.sign_longitude,
                'retrograde': pos.retrograde,
                'house': pos.house,
                'dignity': pos.dignity,
                'dignity_score': pos.dignity_score,
                'strength': round(strength, 4)
            }
        return planets

    def _calculate_house_strength(self, chart: RawEphemeris, house_num: int) -> float:
        """
        Расчет силы дома = средняя сила планет в доме.
        Если планет нет, сила 0.3.
        """
        planets_in_house = []
        for planet_name, planet in chart.planets.items():
            if getattr(planet, 'house', None) == house_num:
                planets_in_house.append(planet)

        if not planets_in_house:
            return 0.3  # Нейтральное значение для пустого дома

        total_strength = sum(self._calculate_planet_strength(p) for p in planets_in_house)
        return min(0.9, total_strength / len(planets_in_house))

    def _format_houses_for_db(self, chart: RawEphemeris) -> Dict:
        # Предварительный расчет сил домов
        house_strengths = {}
        for num in range(1, 13):
            house_strengths[num] = self._calculate_house_strength(chart, num)

        houses = {}
        for num, cusp in chart.houses.houses.items():
            sign = ZODIAC_SIGNS[int(cusp / 30) % 12]
            houses[num] = {
                'cusp': cusp,
                'sign': sign,
                'position_in_sign': cusp % 30,
                'strength': round(house_strengths[num], 4)
            }
        return houses

    def _format_aspects_for_db(self, chart: RawEphemeris) -> List[Dict]:
        """Форматирование аспектов для сохранения в БД с расчетом силы"""
        aspects = []
        for asp in chart.aspects:
            # Если strength уже есть, используем его, иначе рассчитываем
            strength = getattr(asp, 'strength', None)
            if strength is None:
                strength = self._calculate_aspect_strength(asp)

            aspects.append({
                'planet1': asp.planet1,
                'planet2': asp.planet2,
                'aspect': asp.aspect_type,
                'angle': asp.angle,
                'orb': asp.orb,
                'applying': asp.applying,
                'strength': round(strength, 4)
            })
        return aspects

    def _calculate_aspect_strength(self, aspect) -> float:
        """
        Расчет силы аспекта на основе орбиса.
        Чем точнее аспект, тем выше сила.
        """
        orb = getattr(aspect, 'orb', 5.0)
        max_orb = 8.0

        # Чем меньше орб, тем выше сила (1 - orb/max_orb)
        strength = 1.0 - min(1.0, orb / max_orb)

        return max(0.1, min(0.9, strength))
    
    def _format_arabic_parts_for_db(self, chart: RawEphemeris) -> Dict:
        """
        Форматирование арабских частей для сохранения в БД
        """
        parts = {}
        for name, part in chart.arabic_parts.items():
            parts[name] = {
                'longitude': part.longitude,
                'sign': part.sign,
                'interpretation': part.interpretation
            }
        return parts
    
    def _format_fixed_stars_for_db(self, chart: RawEphemeris) -> List[Dict]:
        """
        Форматирование неподвижных звезд для сохранения в БД
        """
        stars = []
        for star in chart.fixed_stars:
            star_data = {
                'name': star.name,
                'longitude': star.longitude,
                'latitude': star.latitude,
                'magnitude': star.magnitude,
                'constellation': star.constellation,
                'conjunctions': []
            }
            
            for asp in star.aspects:
                star_data['conjunctions'].append({
                    'planet': asp['planet'],
                    'orb': asp['orb']
                })
            
            stars.append(star_data)
        return stars
    
    def _format_panchanga_for_db(self, chart: RawEphemeris) -> Dict:
        """
        Форматирование Panchanga для сохранения в БД
        """
        if not chart.panchanga:
            return {}
        
        return {
            'tithi': chart.panchanga.tithi,
            'tithi_name': chart.panchanga.tithi_name,
            'nakshatra': chart.panchanga.nakshatra,
            'nakshatra_name': chart.panchanga.nakshatra_name,
            'nakshatra_pada': chart.panchanga.nakshatra_pada,
            'yoga': chart.panchanga.yoga,
            'yoga_name': chart.panchanga.yoga_name,
            'karana': chart.panchanga.karana,
            'karana_name': chart.panchanga.karana_name
        }
    
    def _format_dasha_for_db(self, chart: RawEphemeris) -> Dict:
        """
        Форматирование Даши для сохранения в БД
        """
        if not chart.dasha:
            return {}
        
        def format_dasha_period(period):
            return {
                'planet': period.planet,
                'years': period.years,
                'start_date': period.start_date.isoformat(),
                'end_date': period.end_date.isoformat(),
                'sub_periods': [format_dasha_period(sp) for sp in period.sub_periods]
            }
        
        return format_dasha_period(chart.dasha)

    async def calculate_natal_chart(
            self,
            city_name: str,
            birth_datetime_local: datetime,
            timezone_str: Optional[str] = None,
            house_system: str = 'P',
            include_all: bool = True,
            include_heavy: bool = True  # ✅ Добавлен параметр
    ) -> Dict[str, Any]:
        """Основной метод расчета натальной карты"""
        try:
            logger.info(f"🔮 Расчет натальной карты для {city_name}")

            # 1. Инициализация
            await self.ensure_initialized()

            # 2. Получаем координаты
            geo = await self.get_city_coordinates(city_name)

            # 3. Используем переданную таймзону или из геоданных
            tz = timezone_str or geo.timezone

            # 4. Расчет эфемерид
            chart = await self.ephemeris.calculate(
                dt=birth_datetime_local,
                lat=geo.lat,
                lon=geo.lon,
                timezone=tz,
                hsys=house_system,
                include_all=include_all,
                include_heavy=include_heavy
            )

            # 5. Определяем день недели и управителя
            weekday = self._get_weekday(birth_datetime_local)
            weekday_ruler = self._get_weekday_ruler(weekday)

            # 6. Формируем результат для БД
            result = {
                # Основные поля
                'city_name': city_name,
                'birth_lat': round(geo.lat, 6),
                'birth_lng': round(geo.lon, 6),
                'birth_timezone': tz,
                'birth_country_code': geo.country,
                'system_language': 'ru',
                'geocoder_source': 'nominatim',

                # Временные метки
                'birth_datetime_local': birth_datetime_local.isoformat(),
                'birth_datetime_utc': chart.timestamp_ut.isoformat(),
                'julian_day': chart.jd_ut,
                'calculation_time_ms': int(chart.calculation_time * 1000),

                # Астрология
                'planets': self._format_planets_for_db(chart),
                'houses': self._format_houses_for_db(chart),
                'aspects': self._format_aspects_for_db(chart),

                # Метаданные расчетов
                'ayanamsa': round(chart.ayanamsa, 6),
                'sidereal_time': round(chart.sidereal_time, 4),
                'void_of_course_moon': chart.void_of_course,
                'moon_phase_degrees': round(chart.moon_phase, 2),

                # Календарные данные
                'weekday': weekday,
                'weekday_ruler': weekday_ruler,

                # Система домов
                'house_system': house_system,

                # Статус
                'calculation_status': 'success'
            }

            # 7. Дополнительные данные (если запрошены)
            if include_all:
                if chart.panchanga:
                    result['panchanga'] = self._format_panchanga_for_db(chart)
                if chart.dasha:
                    result['dasha'] = self._format_dasha_for_db(chart)
                if chart.arabic_parts:
                    result['arabic_parts'] = self._format_arabic_parts_for_db(chart)
                if chart.fixed_stars:
                    result['fixed_stars'] = self._format_fixed_stars_for_db(chart)
                if chart.planetary_hour:
                    result['planetary_hour'] = chart.planetary_hour
                if chart.lunar_data:
                    result['moon_data'] = chart.lunar_data.to_dict()
                if chart.solar_data:
                    result['solar_data'] = chart.solar_data.to_dict()
                if chart.critical_degrees:
                    result['critical_degrees'] = chart.critical_degrees
                if chart.midpoints:
                    result['midpoints'] = chart.midpoints
                if chart.aspect_qualities:
                    result['aspect_qualities'] = chart.aspect_qualities
                if chart.patterns:
                    result['patterns'] = chart.patterns
                if chart.star_interpretations:
                    result['star_interpretations'] = chart.star_interpretations
                if chart.arabic_connections:
                    result['arabic_connections'] = chart.arabic_connections

                # ML-фичи всегда добавляем
                result['ml_features'] = self._calculate_ml_features(chart)

            logger.info(
                f"✅ Натальная карта рассчитана: {city_name}, "
                f"планет={len(chart.planets)}, аспектов={len(chart.aspects)}, "
                f"время={chart.calculation_time:.2f}с"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка расчета натальной карты для {city_name}: {e}")
            return {
                'city_name': city_name,
                'calculation_status': 'failed',
                'error_message': str(e)
            }

    async def calculate_jyotish_chart(
            self,
            city_name: str,
            birth_datetime_local: datetime,
            timezone_str: Optional[str] = None,
            house_system: str = 'P',
            include_heavy: bool = True
    ) -> Dict[str, Any]:
        """
        Расчет натальной карты в джйотиш системе (сидерической)
        """
        try:
            logger.info(f"🔮 Расчет джйотиш карты для {city_name}")

            await self.ensure_initialized()
            geo = await self.get_city_coordinates(city_name)
            tz = timezone_str or geo.timezone

            # Используем специальный метод для джйотиш с передачей include_heavy
            chart = await self.ephemeris.calculate_jyotish(
                dt=birth_datetime_local,
                lat=geo.lat,
                lon=geo.lon,
                timezone=tz,
                hsys=house_system,
                include_all=True,
                include_heavy=include_heavy  # ✅ Добавлено!
            )

            # Формируем результат (аналогично обычной карте)
            result = await self.calculate_natal_chart(
                city_name=city_name,
                birth_datetime_local=birth_datetime_local,
                timezone_str=timezone_str,
                house_system=house_system,
                include_all=True,
                include_heavy=include_heavy
            )

            # Добавляем метаданные джйотиш
            result['system'] = 'jyotish'
            result['ayanamsa'] = round(chart.ayanamsa, 6)

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка расчета джйотиш карты: {e}")
            return {
                'city_name': city_name,
                'calculation_status': 'failed',
                'error_message': str(e)
            }
            
    
    async def calculate_batch(
        self,
        charts_data: List[Tuple[str, datetime, Optional[str]]],
        house_system: str = 'P',
        include_heavy: bool = False  # Для batch лучше выключить тяжелые расчеты
    ) -> List[Optional[Dict]]:
        """
        Пакетный расчет нескольких карт
        
        Args:
            charts_data: Список (city_name, datetime, timezone)
            house_system: Система домов
            include_heavy: Включить тяжелые расчеты
            
        Returns:
            Список результатов (None для ошибок)
        """
        results = []
        
        for city_name, dt, tz in charts_data:
            try:
                chart = await self.calculate_natal_chart(
                    city_name=city_name,
                    birth_datetime_local=dt,
                    timezone_str=tz,
                    house_system=house_system,
                    include_all=True,
                    include_heavy=include_heavy
                )
                results.append(chart)
            except Exception as e:
                logger.error(f"Batch error for {city_name}: {e}")
                results.append(None)
        
        return results
    
    def save_to_json(self, chart: Dict, filename: str) -> None:
        """
        Сохранение карты в JSON файл
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(chart, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 Карта сохранена в {filename}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
    
    async def clear_cache(self):
        """Очистка кэшей"""
        self.coordinates_cache.clear()
        if self.ephemeris:
            await self.ephemeris.cache.clear()
        logger.info("🧹 Кэши очищены")
    
    async def get_metrics(self) -> Dict:
        """Получение метрик"""
        metrics = {
            'coordinates_cache_size': len(self.coordinates_cache),
            'ml_features_enabled': self.ml_features_enabled
        }
        
        if self.ephemeris:
            metrics['ephemeris'] = await self.ephemeris.get_metrics()
        
        return metrics


# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ====================

_calculator_instance: Optional[NatalChartCalculator] = None


async def get_natal_calculator(
    ephemeris_calculator: Optional[EphemerisCalculator] = None,
    geocoder: Optional[AsyncCityGeocoder] = None
) -> NatalChartCalculator:
    """
    Получение глобального экземпляра калькулятора
    
    Args:
        ephemeris_calculator: Экземпляр EphemerisCalculator
        geocoder: Экземпляр AsyncCityGeocoder
        
    Returns:
        Инициализированный NatalChartCalculator
    """
    global _calculator_instance
    
    if _calculator_instance is None:
        _calculator_instance = NatalChartCalculator(
            ephemeris_calculator=ephemeris_calculator,
            geocoder=geocoder
        )
        await _calculator_instance.ensure_initialized()
        logger.info("✅ Глобальный экземпляр NatalChartCalculator создан")
    
    return _calculator_instance


async def cleanup_natal_calculator():
    """Очистка глобального экземпляра"""
    global _calculator_instance
    
    if _calculator_instance:
        await _calculator_instance.clear_cache()
        _calculator_instance = None
        logger.info("✅ Глобальный экземпляр очищен")


