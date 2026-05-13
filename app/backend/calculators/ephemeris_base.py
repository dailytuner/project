"""
ephemeris_base.py - Полноценный астрологический калькулятор
Западная + Джйотиш астрология, Fixed Stars, Arabic Parts, Panchanga, Vimsottari Dasha
"""

import logging
from typing import Dict, List, Tuple, Any, Optional, Union
from collections import OrderedDict
from datetime import datetime, timedelta
import pytz
import swisseph as swe
from dataclasses import dataclass, asdict, field
import time
import asyncio
from enum import Enum
import math
import hashlib
import json

from .ephemeris_constants import (ZODIAC_SIGNS, NAKSHATRAS, YOGAS, TITHIS, KARANAS, ASPECT_ORBS,
                                  ASPECT_ANGLES, FIXED_STARS_PSYCHOLOGY, FIXED_STARS, ARABIC_PARTS,
                                  DASHA_ORDER, DASHA_YEARS, RULERS,EXALTATIONS, DETRIMENT_SIGNS,
                                  FALL_SIGNS, TRIPLICITIES, SIGN_ELEMENTS, FACES, TERMS, ALL_ARABIC_PARTS)

logger = logging.getLogger(__name__)

# ==================== ИСКЛЮЧЕНИЯ ====================

class EphemerisError(Exception):
    """Базовое исключение для ошибок эфемерид"""
    pass


class CalculationError(EphemerisError):
    """Ошибка расчета"""
    pass


# ==================== DATACLASSES ====================

@dataclass(frozen=True)
class GeoCoordinates:
    """Географические координаты для расчета"""
    lat: float
    lon: float
    timezone: str = "UTC"
    elevation: float = 0.0
    city: Optional[str] = None
    country: Optional[str] = None
    
    def __post_init__(self):
        if not -90 <= self.lat <= 90:
            raise ValueError(f"Invalid latitude: {self.lat}")
        if not -180 <= self.lon <= 180:
            raise ValueError(f"Invalid longitude: {self.lon}")


@dataclass
class PlanetPosition:
    """Позиция планеты с дополнительными атрибутами"""
    longitude: float
    latitude: float
    distance: float
    speed_long: float
    speed_lat: float
    speed_dist: float
    flags: int
    sign: str = ""  # Знак зодиака
    sign_longitude: float = 0.0  # Градус в знаке
    retrograde: bool = False
    dignity: Dict[str, str] = field(default_factory=dict)
    dignity_score: float = 0.0  # Суммарная сила достоинств
    house: int = 0  # Номер дома
    
    def __post_init__(self):
        self.retrograde = self.speed_long < 0
        # ✅ Используем глобальную константу
        self.sign = ZODIAC_SIGNS[int(self.longitude / 30) % 12]
        self.sign_longitude = self.longitude % 30
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'longitude': self.longitude,
            'latitude': self.latitude,
            'distance': self.distance,
            'speed_long': self.speed_long,
            'speed_lat': self.speed_lat,
            'speed_dist': self.speed_dist,
            'sign': self.sign,
            'sign_longitude': self.sign_longitude,
            'retrograde': self.retrograde,
            'dignity': self.dignity,
            'dignity_score': self.dignity_score,
            'house': self.house
        }


@dataclass
class HouseCusps:
    """Домовые куспиды"""
    cusps: List[float]
    ascendant: float
    mc: float
    houses: Dict[int, float]
    
    @classmethod
    def from_cusps_ascmc(cls, cusps: List[float], ascmc: List[float], hsys: str):
        """Создание из результатов swe.houses"""
        houses = {i+1: cusps[i] % 360 for i in range(12)}
        return cls(
            cusps=[c % 360 for c in cusps],
            ascendant=ascmc[0] % 360,
            mc=ascmc[1] % 360,
            houses=houses
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'cusps': self.cusps,
            'ascendant': self.ascendant,
            'mc': self.mc,
            'houses': self.houses
        }


@dataclass
class FixedStar:
    """Неподвижная звезда"""
    name: str
    longitude: float
    latitude: float
    magnitude: float  # Звездная величина
    constellation: str
    mundane_house: int = 0
    aspects: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'magnitude': self.magnitude,
            'constellation': self.constellation,
            'mundane_house': self.mundane_house,
            'aspects': self.aspects
        }


@dataclass
class Aspect:
    """Аспект между планетами"""
    planet1: str
    planet2: str
    aspect_type: str  # conjunction, opposition, trine, square, sextile
    angle: float
    orb: float
    applying: bool
    strength: float = 1.0  # Сила аспекта (0-1)
    
    def to_dict(self) -> Dict:
        return {
            'planet1': self.planet1,
            'planet2': self.planet2,
            'aspect_type': self.aspect_type,
            'angle': self.angle,
            'orb': self.orb,
            'applying': self.applying,
            'strength': self.strength
        }


@dataclass
class Panchanga:
    """Джйотиш: 5 частей времени"""
    tithi: int  # 1-30
    tithi_name: str
    nakshatra: int  # 1-27
    nakshatra_name: str
    nakshatra_pada: int  # 1-4
    yoga: int  # 1-27
    yoga_name: str
    karana: int  # 1-11
    karana_name: str
    
    def to_dict(self) -> Dict:
        return {
            'tithi': self.tithi,
            'tithi_name': self.tithi_name,
            'nakshatra': self.nakshatra,
            'nakshatra_name': self.nakshatra_name,
            'nakshatra_pada': self.nakshatra_pada,
            'yoga': self.yoga,
            'yoga_name': self.yoga_name,
            'karana': self.karana,
            'karana_name': self.karana_name
        }


@dataclass
class DashaPeriod:
    """Период даши (Вимшоттари)"""
    planet: str
    years: float
    start_date: datetime
    end_date: datetime
    sub_periods: List['DashaPeriod'] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'planet': self.planet,
            'years': self.years,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'sub_periods': [sp.to_dict() for sp in self.sub_periods]
        }


@dataclass
class ArabicPart:
    """Арабская часть"""
    name: str
    longitude: float
    formula: str
    interpretation: str = ""
    sign: str = ""
    
    def __post_init__(self):
        # ✅ Используем глобальную константу
        self.sign = ZODIAC_SIGNS[int(self.longitude / 30) % 12]
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'longitude': self.longitude,
            'sign': self.sign,
            'formula': self.formula,
            'interpretation': self.interpretation
        }


@dataclass
class LunarData:
    """Детальные данные о Луне"""
    phase_angle: float
    phase_name: str
    illumination: float
    age_days: float
    distance_km: float
    is_void: bool
    next_phase: str
    days_to_next_phase: float
    is_super_moon: bool
    is_blue_moon: bool
    is_eclipse_season: bool
    nakshatra: str
    nakshatra_pada: int
    tithi: int
    sign: str
    house: int

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SolarData:
    """Детальные данные о Солнце"""
    season: str
    is_solstice: bool
    is_equinox: bool
    distance_km: float
    declination: float
    right_ascension: float
    sign: str
    house: int
    dignity: Dict[str, str]
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None
    day_length: float = 12.0

    def to_dict(self) -> Dict:
        result = asdict(self)
        if self.sunrise:
            result['sunrise'] = self.sunrise.isoformat()
        if self.sunset:
            result['sunset'] = self.sunset.isoformat()
        return result


@dataclass
class AspectQuality:
    """Психологическое качество аспекта"""
    type: str
    nature: str
    planets: Tuple[str, str]
    psychological: str
    strength: float
    applying: bool
    orb: float


@dataclass
class RawEphemeris:
    """Результат расчета эфемерид - ПОЛНАЯ ВЕРСИЯ"""
    jd_ut: float
    timestamp_ut: datetime
    planets: Dict[str, PlanetPosition]
    houses: HouseCusps
    ayanamsa: float
    sidereal_time: float
    moon_phase: float
    geo: GeoCoordinates

    # Дополнительные поля
    fixed_stars: List[FixedStar] = field(default_factory=list)
    aspects: List[Aspect] = field(default_factory=list)
    arabic_parts: Dict[str, ArabicPart] = field(default_factory=dict)
    panchanga: Optional[Panchanga] = None
    dignities: Dict[str, Dict] = field(default_factory=dict)
    midpoints: Dict[str, float] = field(default_factory=dict)
    critical_degrees: List[Dict] = field(default_factory=list)
    void_of_course: bool = False
    planetary_hour: Dict = field(default_factory=dict)
    dasha: Optional[DashaPeriod] = None
    aspect_qualities: List[Dict] = field(default_factory=list)
    patterns: Dict = field(default_factory=dict)
    star_interpretations: List[Dict] = field(default_factory=list)
    arabic_connections: Dict = field(default_factory=dict)
    lunar_data: Optional[LunarData] = None
    solar_data: Optional[SolarData] = None

    calculation_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'jd_ut': self.jd_ut,
            'timestamp_ut': self.timestamp_ut.isoformat(),
            'planets': {name: pos.to_dict() for name, pos in self.planets.items()},
            'houses': self.houses.to_dict(),
            'ayanamsa': self.ayanamsa,
            'sidereal_time': self.sidereal_time,
            'moon_phase': self.moon_phase,
            'geo': asdict(self.geo),
            'fixed_stars': [star.to_dict() for star in self.fixed_stars],
            'aspects': [asp.to_dict() for asp in self.aspects],
            'arabic_parts': {name: part.to_dict() for name, part in self.arabic_parts.items()},
            'panchanga': self.panchanga.to_dict() if self.panchanga else None,
            'void_of_course': self.void_of_course,
            'planetary_hour': self.planetary_hour,
            'dasha': self.dasha.to_dict() if self.dasha else None,
        }

        if self.lunar_data:
            result['lunar_data'] = self.lunar_data.to_dict()
        if self.solar_data:
            result['solar_data'] = self.solar_data.to_dict()
        if self.aspect_qualities:
            result['aspect_qualities'] = self.aspect_qualities
        if self.patterns:
            result['patterns'] = self.patterns
        if self.star_interpretations:
            result['star_interpretations'] = self.star_interpretations
        if self.arabic_connections:
            result['arabic_connections'] = self.arabic_connections

        return result


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def safe_swe_calc(jd_ut: float, planet_id: int, flags: int) -> Tuple[List[float], int]:
    """
    Безопасный вызов swe.calc_ut с обработкой разных форматов возврата
    
    Returns:
        Tuple[values, flags]
    """
    try:
        result = swe.calc_ut(jd_ut, planet_id, flags)
        
        if isinstance(result, tuple) and len(result) >= 2:
            # Формат: (values_array, flags)
            values = result[0]
            ret_flags = result[1]
        elif isinstance(result, (list, tuple)) and len(result) == 6:
            # Старый формат: [lon, lat, dist, speed_lon, speed_lat, speed_dist]
            values = result
            ret_flags = 0
        else:
            logger.error(f"Unexpected result format: {type(result)}")
            return [0.0] * 6, 0
            
        # Убеждаемся что values содержит 6 элементов
        if len(values) < 6:
            values = list(values) + [0.0] * (6 - len(values))
            
        return values[:6], ret_flags
        
    except Exception as e:
        logger.error(f"swe.calc_ut failed: {e}")
        return [0.0] * 6, 0


def get_aspect_type(angle: float, planet1: str = "default", planet2: str = "default") -> Optional[Tuple[str, float]]:
    """Определить тип аспекта по углу с учетом орбов для конкретных планет"""
    for target_angle, aspect_name in ASPECT_ANGLES.items():
        orb = min(abs(angle - target_angle), abs(angle - (360 - target_angle)))
        
        # Определяем максимальный орб для этого аспекта
        max_orb = ASPECT_ORBS.get(aspect_name, {}).get('default', 8)
        
        # Проверяем особые орбы для Солнца и Луны
        if planet1 in ['Sun', 'Moon'] or planet2 in ['Sun', 'Moon']:
            max_orb = ASPECT_ORBS.get(aspect_name, {}).get(planet1 if planet1 in ['Sun', 'Moon'] else planet2, max_orb)
        
        if orb <= max_orb:
            return aspect_name, orb
    return None


# ==================== КЭШ ====================

class LRUCache:
    """LRU кэш для эфемерид"""
    
    def __init__(self, max_size: int = 1000):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def _make_key(self, jd_ut: float, lat: float, lon: float, hsys: str, options: Dict) -> str:
        """Создать ключ кэша из всех параметров"""
        key_data = {
            'jd': round(jd_ut, 6),
            'lat': round(lat, 4),
            'lon': round(lon, 4),
            'hsys': hsys,
            'options': options
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(self, jd_ut: float, lat: float, lon: float, hsys: str, options: Dict) -> Optional[Any]:
        key = self._make_key(jd_ut, lat, lon, hsys, options)
        if key in self.cache:
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def set(self, jd_ut: float, lat: float, lon: float, hsys: str, options: Dict, value: Any):
        key = self._make_key(jd_ut, lat, lon, hsys, options)
        if key in self.cache:
            self.cache.move_to_end(key)
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = value
    
    def get_stats(self) -> Dict:
        total = self.hits + self.misses
        return {
            'size': len(self.cache),
            'hits': self.hits,
            'misses': self.misses,
            'hit_ratio': self.hits / total if total > 0 else 0
        }


# ==================== ОСНОВНОЙ КАЛЬКУЛЯТОР ====================

class EphemerisCalculator:
    """
    Полноценный астрологический калькулятор
    Западная + Джйотиш астрология, Fixed Stars, Arabic Parts, Vimsottari Dasha
    """
    
    # Маппинг планет Swiss Ephemeris
    PLANETS = {
        swe.SUN: 'Sun',
        swe.MOON: 'Moon',
        swe.MERCURY: 'Mercury',
        swe.VENUS: 'Venus',
        swe.MARS: 'Mars',
        swe.JUPITER: 'Jupiter',
        swe.SATURN: 'Saturn',
        swe.URANUS: 'Uranus',
        swe.NEPTUNE: 'Neptune',
        swe.PLUTO: 'Pluto',
        swe.TRUE_NODE: 'True_Node',
        swe.MEAN_NODE: 'Mean_Node',
        swe.CHIRON: 'Chiron',
        swe.VERTEX: 'Vertex'
    }
    
    # Флаги Swiss Ephemeris
    FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED | swe.FLG_MOSEPH
    
    def __init__(
        self,
        ephemeris_path: Optional[str] = None,
        cache_size: int = 1000,
        include_fixed_stars: bool = True,
        include_arabic_parts: bool = True,
        star_orb: float = 1.0
    ):
        self.ephemeris_path = ephemeris_path
        self.include_fixed_stars = include_fixed_stars
        self.include_arabic_parts = include_arabic_parts
        self.star_orb = star_orb
        
        self.cache = LRUCache(max_size=cache_size)
        
        self._setup_swiss_ephemeris()
        
        self.metrics = {
            'total_calculations': 0,
            'errors': 0,
            'avg_calculation_time': 0.0
        }
        self._metrics_lock = asyncio.Lock()
    
    def _setup_swiss_ephemeris(self):
        """Настройка Swiss Ephemeris"""
        try:
            if self.ephemeris_path:
                swe.set_ephe_path(self.ephemeris_path)
                logger.info(f"Swiss Ephemeris path: {self.ephemeris_path}")
            
            swe.calc_ut(2451545.0, swe.SUN, self.FLAGS)
            logger.info("✅ Swiss Ephemeris initialized")
            
        except Exception as e:
            logger.error(f"Failed to init Swiss Ephemeris: {e}")
            logger.warning("Using Moshier ephemeris")
            self.FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED
    
    def _validate_datetime(self, dt: datetime, timezone: str) -> Tuple[datetime, float]:
        """Валидация даты и конвертация в JD"""
        if dt.tzinfo is None:
            try:
                tz = pytz.timezone(timezone)
                dt_local = tz.localize(dt)
            except Exception as e:
                raise CalculationError(f"Invalid timezone {timezone}: {e}")
        else:
            dt_local = dt
        
        dt_utc = dt_local.astimezone(pytz.utc)
        
        decimal_hour = (
            dt_utc.hour +
            dt_utc.minute / 60 +
            dt_utc.second / 3600 +
            dt_utc.microsecond / 3600000000
        )
        
        jd_ut = swe.julday(
            dt_utc.year,
            dt_utc.month,
            dt_utc.day,
            decimal_hour
        )
        
        return dt_utc, jd_ut

    def _calculate_planets(self, jd_ut: float) -> Dict[str, PlanetPosition]:
        """Расчет позиций планет с гарантией наличия всех основных планет"""
        planets = {}

        # Основные планеты (всегда должны быть)
        core_planets = {
            swe.SUN: 'Sun',
            swe.MOON: 'Moon',
            swe.MERCURY: 'Mercury',
            swe.VENUS: 'Venus',
            swe.MARS: 'Mars',
            swe.JUPITER: 'Jupiter',
            swe.SATURN: 'Saturn',
        }

        # Дополнительные планеты
        extra_planets = {
            swe.URANUS: 'Uranus',
            swe.NEPTUNE: 'Neptune',
            swe.PLUTO: 'Pluto',
            swe.TRUE_NODE: 'True_Node',
            swe.MEAN_NODE: 'Mean_Node',
            swe.CHIRON: 'Chiron',
        }

        # Сначала рассчитываем основные планеты
        for swe_id, name in core_planets.items():
            try:
                values, flags = safe_swe_calc(jd_ut, swe_id, self.FLAGS)
                
                planets[name] = PlanetPosition(
                    longitude=values[0],
                    latitude=values[1],
                    distance=values[2],
                    speed_long=values[3],
                    speed_lat=values[4],
                    speed_dist=values[5],
                    flags=flags
                )
                logger.debug(f"✅ Calculated {name}: lon={values[0]:.2f}°")

            except Exception as e:
                logger.error(f"Failed to calculate core planet {name}: {e}")
                # Для core планет создаем заглушку
                planets[name] = PlanetPosition(0, 0, 0, 0, 0, 0, 0)

        # Затем дополнительные планеты (опционально)
        for swe_id, name in extra_planets.items():
            try:
                values, flags = safe_swe_calc(jd_ut, swe_id, self.FLAGS)
                
                planets[name] = PlanetPosition(
                    longitude=values[0],
                    latitude=values[1],
                    distance=values[2],
                    speed_long=values[3],
                    speed_lat=values[4],
                    speed_dist=values[5],
                    flags=flags
                )

            except Exception as e:
                logger.warning(f"Failed to calculate extra planet {name}: {e}")
                # Для extra планет просто пропускаем

        # Добавляем Lilith (Черная Луна) если есть Mean_Node
        if 'Mean_Node' in planets:
            mean_node = planets['Mean_Node']
            planets['Lilith'] = PlanetPosition(
                longitude=(mean_node.longitude + 180) % 360,
                latitude=mean_node.latitude,
                distance=mean_node.distance,
                speed_long=mean_node.speed_long,
                speed_lat=mean_node.speed_lat,
                speed_dist=mean_node.speed_dist,
                flags=mean_node.flags
            )

        logger.info(f"✅ Calculated {len(planets)} planets")
        return planets

    def _calculate_houses(
        self,
        jd_ut: float,
        lat: float,
        lon: float,
        hsys: str = 'P'
    ) -> HouseCusps:
        """Расчет домов"""
        try:
            # В pyswisseph hsys может быть строкой
            if isinstance(hsys, str):
                hsys_param = hsys.encode('ascii') if hasattr(hsys, 'encode') else hsys
            else:
                hsys_param = hsys

            # houses возвращает (cusps_array, ascmc_array)
            cusps, ascmc = swe.houses(jd_ut, lat, lon, hsys_param)

            # Преобразуем в float и нормализуем
            cusps_list = [float(c) % 360 for c in cusps]
            ascendant = float(ascmc[0]) % 360
            mc = float(ascmc[1]) % 360

            return HouseCusps(
                cusps=cusps_list,
                ascendant=ascendant,
                mc=mc,
                houses={i + 1: cusps_list[i] for i in range(12)}
            )

        except Exception as e:
            logger.error(f"Failed to calculate houses: {e}")
            # Возвращаем пустые дома
            return HouseCusps(
                cusps=[0.0] * 12,
                ascendant=0.0,
                mc=0.0,
                houses={i + 1: 0.0 for i in range(12)}
            )

    def _calculate_sidereal_time(self, jd_ut: float) -> float:
        """Расчет звездного времени"""
        try:
            # sidtime возвращает звездное время в часах
            sidereal_hours = swe.sidtime(jd_ut)
            # Конвертируем в градусы (1 час = 15 градусов)
            return sidereal_hours * 15.0
        except Exception as e:
            logger.error(f"Failed to calculate sidereal time: {e}")
            return 0.0

    def _calculate_ayanamsa(self, jd_ut: float) -> float:
        """Расчет аянамши"""
        try:
            return swe.get_ayanamsa_ut(jd_ut)
        except Exception as e:
            logger.warning(f"Failed to calculate ayanamsa: {e}")
            return 0.0

    def _calculate_dignities(self, planet: PlanetPosition, planet_name: str, is_day: bool = True) -> Dict[str, str]:
        """
        Полный расчет психологических достоинств планеты (essential dignities)
        """
        dignities = {}
        score = 0

        # 1. Управление (Rulership) - +5
        if RULERS.get(planet.sign) == planet_name:
            dignities['rulership'] = 'Domicile'
            score += 5

        # 2. Экзальтация (Exaltation) - +4
        if planet_name in EXALTATIONS:
            deg_diff = abs(planet.sign_longitude - EXALTATIONS[planet_name])
            if deg_diff < 2:
                dignities['exaltation'] = 'Exalted'
                score += 4
            elif deg_diff < 6:
                dignities['exaltation'] = 'Near Exalted'
                score += 2

        # 3. Изгнание (Detriment) - -5
        if DETRIMENT_SIGNS.get(planet_name) == planet.sign:
            dignities['detriment'] = 'Detriment'
            score -= 5

        # 4. Падение (Fall) - -4
        if FALL_SIGNS.get(planet_name) == planet.sign:
            dignities['fall'] = 'Fall'
            score -= 4

        # 5. Триплицитет (Triplicity) - +3
        element = SIGN_ELEMENTS.get(planet.sign, 'Fire')
        key = (element, 'day' if is_day else 'night')
        triplicity_rulers = TRIPLICITIES.get(key, (None, None))

        if planet_name in triplicity_rulers:
            if planet_name == triplicity_rulers[0]:
                dignities['triplicity'] = f'Triplicity Ruler (Day)'
                score += 3
            elif planet_name == triplicity_rulers[1]:
                dignities['triplicity'] = f'Triplicity Ruler (Night)'
                score += 2

        # 6. Термы (Terms) - +2
        if planet.sign in TERMS:
            for start, end, ruler in TERMS[planet.sign]:
                if start <= planet.sign_longitude < end:
                    if ruler == planet_name:
                        dignities['term'] = f'Term ({start}-{end}°)'
                        score += 2
                    elif ruler:  # Термы принадлежат другой планете - нейтрально
                        dignities['term'] = f'Term of {ruler}'
                    break

        # 7. Фейсы (Faces/Decans) - +1
        if planet.sign in FACES:
            decan = int(planet.sign_longitude / 10) * 10
            if decan in FACES[planet.sign]:
                if FACES[planet.sign][decan] == planet_name:
                    dignities['face'] = f'Face ({decan}-{decan + 10}°)'
                    score += 1
                else:
                    dignities['face'] = f'Face of {FACES[planet.sign][decan]}'

        planet.dignity_score = score
        return dignities

    def _calculate_aspects(self, planets: Dict[str, PlanetPosition]) -> List[Aspect]:
        """Расчет аспектов между планетами (включая Vertex)"""
        aspects = []
        planet_list = list(planets.items())

        # Список планет для аспектов (включая Vertex если есть)
        aspect_planets = [p for p in planet_list if p[0] != 'Vertex' or p[0] in planets]

        for i, (name1, pos1) in enumerate(aspect_planets):
            for name2, pos2 in aspect_planets[i + 1:]:
                # Пропускаем если обе планеты - Vertex (только одна может быть)
                if name1 == 'Vertex' and name2 == 'Vertex':
                    continue

                angle = abs(pos1.longitude - pos2.longitude) % 360
                if angle > 180:
                    angle = 360 - angle

                aspect_info = get_aspect_type(angle, name1, name2)
                if aspect_info:
                    aspect_type, orb = aspect_info

                    # Определяем аппликативный/сепаративный
                    speed_diff = pos1.speed_long - pos2.speed_long
                    if aspect_type in ['conjunction', 'opposition']:
                        applying = abs(speed_diff) > 0.001
                    else:
                        target = 0 if aspect_type == 'conjunction' else 180
                        applying = (speed_diff > 0 and angle < target) or (speed_diff < 0 and angle > target)

                    max_orb = ASPECT_ORBS.get(aspect_type, {}).get('default', 8)
                    strength = max(0, min(1, 1 - (orb / max_orb)))

                    aspects.append(Aspect(
                        planet1=name1,
                        planet2=name2,
                        aspect_type=aspect_type,
                        angle=angle,
                        orb=orb,
                        applying=applying,
                        strength=strength
                    ))

        return aspects

    def _get_aspect_quality(self, aspect: Aspect) -> Dict:
        """Определение психологического качества аспекта"""
        aspect_meanings = {
            'conjunction': {
                'nature': 'синтез',
                'positive': 'интеграция качеств',
                'negative': 'смешение, путаница',
                'planets': {
                    ('Sun', 'Moon'): 'осознание эмоций',
                    ('Sun', 'Mercury'): 'ясность ума',
                    ('Sun', 'Venus'): 'творческая гармония',
                    ('Sun', 'Mars'): 'волевая активность',
                    ('Sun', 'Jupiter'): 'экспансивность',
                    ('Sun', 'Saturn'): 'структурирование',
                    ('Sun', 'Uranus'): 'гениальность',
                    ('Sun', 'Neptune'): 'мистицизм',
                    ('Sun', 'Pluto'): 'трансформация',
                    ('Moon', 'Mercury'): 'интуитивный ум',
                    ('Moon', 'Venus'): 'эмоциональная теплота',
                    ('Moon', 'Mars'): 'эмоциональная агрессия',
                    ('Moon', 'Jupiter'): 'эмоциональный рост',
                    ('Moon', 'Saturn'): 'эмоциональный контроль',
                    ('Moon', 'Uranus'): 'эмоциональная нестабильность',
                    ('Moon', 'Neptune'): 'экстрасенсорика',
                    ('Moon', 'Pluto'): 'эмоциональная глубина',
                    ('Venus', 'Mars'): 'страсть vs гармония',
                    ('Venus', 'Jupiter'): 'щедрость',
                    ('Venus', 'Saturn'): 'верность',
                    ('Venus', 'Uranus'): 'свободная любовь',
                    ('Venus', 'Neptune'): 'идеальная любовь',
                    ('Venus', 'Pluto'): 'одержимость',
                    ('Mars', 'Jupiter'): 'энтузиазм',
                    ('Mars', 'Saturn'): 'дисциплина',
                    ('Mars', 'Uranus'): 'импульсивность',
                    ('Mars', 'Neptune'): 'духовный воин',
                    ('Mars', 'Pluto'): 'сила воли',
                    ('Jupiter', 'Saturn'): 'рост через ограничения',
                    ('Jupiter', 'Uranus'): 'расширение сознания',
                    ('Jupiter', 'Neptune'): 'мистицизм',
                    ('Jupiter', 'Pluto'): 'власть',
                    ('Saturn', 'Uranus'): 'революция',
                    ('Saturn', 'Neptune'): 'духовный поиск',
                    ('Saturn', 'Pluto'): 'трансформация',
                    ('Uranus', 'Neptune'): 'инновации',
                    ('Uranus', 'Pluto'): 'переворот',
                    ('Neptune', 'Pluto'): 'коллективное бессознательное'
                }
            },
            'opposition': {
                'nature': 'напряжение/проекция',
                'positive': 'осознание через других',
                'negative': 'конфликт, поляризация'
            },
            'trine': {
                'nature': 'гармония/талант',
                'positive': 'легкость, поток',
                'negative': 'лень, недоиспользование'
            },
            'square': {
                'nature': 'кризис/рост',
                'positive': 'мотивация, действие',
                'negative': 'фрустрация, блоки'
            },
            'sextile': {
                'nature': 'возможность',
                'positive': 'шанс, потенциал',
                'negative': 'нереализованность'
            },
            'quincunx': {
                'nature': 'настройка/адаптация',
                'positive': 'гибкость, обучение',
                'negative': 'дискомфорт, неловкость'
            },
            'semisextile': {
                'nature': 'развитие',
                'positive': 'потенциал роста',
                'negative': 'трение, раздражение'
            },
            'semisquare': {
                'nature': 'напряжение',
                'positive': 'мотивация',
                'negative': 'фрустрация'
            },
            'sesquiquadrate': {
                'nature': 'кризис',
                'positive': 'очищение',
                'negative': 'разрушение'
            }
        }

        base = aspect_meanings.get(aspect.aspect_type, {})
        pair_key = (aspect.planet1, aspect.planet2)
        reversed_key = (aspect.planet2, aspect.planet1)

        specific = base.get('planets', {}).get(pair_key) or base.get('planets', {}).get(reversed_key, '')

        return {
            'type': aspect.aspect_type,
            'nature': base.get('nature', ''),
            'psychological': f"{base.get('positive', '')}. {specific}",
            'strength': aspect.strength,
            'applying': aspect.applying,
            'orb': aspect.orb
        }
    
    def _assign_houses(self, planets: Dict[str, PlanetPosition], houses: HouseCusps):
        """Определение домов планет"""
        cusps = houses.cusps
        
        for planet_name, planet in planets.items():
            lon = planet.longitude
            
            for i in range(12):
                cusp1 = cusps[i]
                cusp2 = cusps[(i + 1) % 12]
                
                # Обработка перехода через 0°
                if cusp1 <= cusp2:
                    if cusp1 <= lon < cusp2:
                        planet.house = i + 1
                        break
                else:
                    if lon >= cusp1 or lon < cusp2:
                        planet.house = i + 1
                        break
            else:
                planet.house = 1  # Fallback
    
    def _is_day_chart(self, sun_lon: float, ascendant: float) -> bool:
        """Определение дневной/ночной карты"""
        diff = (sun_lon - ascendant) % 360
        return 0 < diff < 180
    
    def _calculate_fixed_stars(
        self,
        jd_ut: float,
        planets: Dict[str, PlanetPosition]
    ) -> List[FixedStar]:
        """Расчет соединений с неподвижными звездами"""
        stars = []
        
        for star_data in FIXED_STARS:
            try:
                star_pos = swe.fixstar(star_data['swe_name'], jd_ut)
                star_lon = star_pos[0][0] % 360
                star_lat = star_pos[1][0]
                
                star = FixedStar(
                    name=star_data['name'],
                    longitude=star_lon,
                    latitude=star_lat,
                    magnitude=star_data['mag'],
                    constellation=star_data['const']
                )
                
                # Проверяем соединения с планетами
                for planet_name, planet_pos in planets.items():
                    angle = abs(planet_pos.longitude - star_lon) % 360
                    if angle > 180:
                        angle = 360 - angle
                    
                    if angle <= self.star_orb:
                        star.aspects.append({
                            'planet': planet_name,
                            'orb': angle,
                            'type': 'conjunction'
                        })
                
                stars.append(star)
                
            except Exception as e:
                logger.debug(f"Failed to calculate star {star_data['name']}: {e}")
        
        return stars

    def _interpret_fixed_stars(self, chart: RawEphemeris) -> List[Dict]:
        """Психологическая интерпретация соединений со звездами"""
        interpretations = []

        for star in chart.fixed_stars:
            for conj in star.aspects:
                planet = conj['planet']
                star_data = FIXED_STARS_PSYCHOLOGY.get(star.name, {})

                key = f"with_{planet.lower()}"
                specific = star_data.get(key, star_data.get('meaning', ''))

                interpretations.append({
                    'star': star.name,
                    'planet': planet,
                    'orb': conj['orb'],
                    'meaning': specific,
                    'positive': star_data.get('positive', ''),
                    'negative': star_data.get('negative', '')
                })

        return interpretations


    def _calculate_arabic_parts(
            self,
            ascendant: float,
            planets: Dict[str, PlanetPosition],
            is_day: bool
    ) -> Dict[str, ArabicPart]:
        """БЕЗОПАСНЫЙ расчет арабских частей с лямбда-функциями"""
        coords = {
            'ASC': ascendant,
            'Sun': planets['Sun'].longitude,
            'Moon': planets['Moon'].longitude,
            'Mercury': planets['Mercury'].longitude,
            'Venus': planets['Venus'].longitude,
            'Mars': planets['Mars'].longitude,
            'Jupiter': planets['Jupiter'].longitude,
            'Saturn': planets['Saturn'].longitude,
            'Uranus': planets.get('Uranus', PlanetPosition(0, 0, 0, 0, 0, 0, 0)).longitude,
            'Neptune': planets.get('Neptune', PlanetPosition(0, 0, 0, 0, 0, 0, 0)).longitude,
            'Pluto': planets.get('Pluto', PlanetPosition(0, 0, 0, 0, 0, 0, 0)).longitude,
            'Chiron': planets.get('Chiron', PlanetPosition(0, 0, 0, 0, 0, 0, 0)).longitude
        }

        parts = {}

        for name, config in ALL_ARABIC_PARTS.items():
            try:
                if 'formula' in config:
                    # ✅ Прямой вызов лямбда-функции
                    longitude = config['formula'](coords)
                else:
                    # ✅ Для частей с day/night режимами
                    if is_day and 'day' in config:
                        longitude = config['day'](coords)
                    elif not is_day and 'night' in config:
                        longitude = config['night'](coords)
                    else:
                        continue

                parts[name] = ArabicPart(
                    name=name,
                    longitude=longitude,
                    formula=name,
                    interpretation=config['interpretation']
                )

            except KeyError as e:
                logger.warning(f"Missing planet for {name}: {e}")
            except Exception as e:
                logger.error(f"Failed to calculate {name}: {e}")

        logger.info(f"✅ Calculated {len(parts)} Arabic Parts (is_day={is_day})")
        return parts
    
    def _calculate_panchanga(
        self,
        sun_sidereal: float,
        moon_sidereal: float
    ) -> Panchanga:
        """Расчет Panchanga (5 частей времени) для джйотиш"""
        
        tithi_value = ((moon_sidereal - sun_sidereal) % 360) / 12
        tithi_idx = int(tithi_value) % 30
        
        nakshatra_value = moon_sidereal / (360 / 27)
        nakshatra_idx = int(nakshatra_value) % 27
        pada = int((moon_sidereal % (360/27)) / (360/27/4)) + 1
        
        yoga_value = ((sun_sidereal + moon_sidereal) % 360) / (360 / 27)
        yoga_idx = int(yoga_value) % 27
        
        karana_idx = int(tithi_value * 2) % 11
        
        return Panchanga(
            tithi=tithi_idx + 1,
            tithi_name=TITHIS[tithi_idx],
            nakshatra=nakshatra_idx + 1,
            nakshatra_name=NAKSHATRAS[nakshatra_idx],
            nakshatra_pada=pada,
            yoga=yoga_idx + 1,
            yoga_name=YOGAS[yoga_idx],
            karana=karana_idx + 1,
            karana_name=KARANAS[karana_idx]
        )
    
    def _calculate_dasha(
        self,
        birth_date: datetime,
        moon_sidereal: float
    ) -> DashaPeriod:
        """Расчет Вимшоттари Даши с рекурсивными подпериодами"""
        
        nakshatra_idx = int(moon_sidereal / (360 / 27)) % 27
        
        nakshatra_start = nakshatra_idx * (360 / 27)
        nakshatra_passed = (moon_sidereal - nakshatra_start) / (360 / 27)
        
        current_dasha_planet = DASHA_ORDER[nakshatra_idx % 9]
        current_dasha_years = DASHA_YEARS[nakshatra_idx % 9]
        remaining_years = current_dasha_years * (1 - nakshatra_passed)
        
        current_date = birth_date
        
        def create_dasha_period(planet: str, years: float, start: datetime, depth: int = 0) -> DashaPeriod:
            """Рекурсивное создание периодов даши"""
            end = start + timedelta(days=years * 365.25)
            
            period = DashaPeriod(
                planet=planet,
                years=years,
                start_date=start,
                end_date=end
            )
            
            # Добавляем подпериоды (бхукти) для глубины > 0
            if depth < 2:  # Ограничиваем глубину для производительности
                sub_periods = []
                sub_start = start
                
                for sub_planet in DASHA_ORDER:
                    sub_years = (years * DASHA_YEARS[DASHA_ORDER.index(sub_planet)] / 120)
                    if sub_years > 0.01:  # Минимальный период
                        sub_period = create_dasha_period(
                            sub_planet, sub_years, sub_start, depth + 1
                        )
                        sub_periods.append(sub_period)
                        sub_start = sub_period.end_date
                
                period.sub_periods = sub_periods
            
            return period
        
        root_dasha = create_dasha_period(
            current_dasha_planet, remaining_years, current_date
        )
        
        return root_dasha
    
    def _calculate_midpoints(self, planets: Dict[str, PlanetPosition]) -> Dict[str, float]:
        """Расчет средних точек"""
        midpoints = {}
        planet_list = list(planets.keys())
        
        for i, p1 in enumerate(planet_list):
            for p2 in planet_list[i+1:]:
                lon1 = planets[p1].longitude
                lon2 = planets[p2].longitude
                
                if abs(lon1 - lon2) > 180:
                    if lon1 > lon2:
                        lon2 += 360
                    else:
                        lon1 += 360
                
                midpoint = (lon1 + lon2) / 2 % 360
                midpoints[f"{p1}_{p2}"] = midpoint
        
        return midpoints
    
    def _check_void_of_course(
        self,
        jd_ut: float,
        moon: PlanetPosition,
        planets: Dict[str, PlanetPosition]
    ) -> bool:
        """Проверка Луны без курса (Void of Course)"""
        
        current_sign = int(moon.longitude / 30)
        degrees_to_next = ((current_sign + 1) * 30 - moon.longitude) % 30
        time_to_next_sign = degrees_to_next / abs(moon.speed_long) / 24 if moon.speed_long != 0 else float('inf')
        
        for planet_name, planet_pos in planets.items():
            if planet_name == 'Moon':
                continue
            
            angle = abs(moon.longitude - planet_pos.longitude) % 360
            if angle > 180:
                angle = 360 - angle
            
            aspect = get_aspect_type(angle)
            if aspect:
                target_angle = 0 if aspect[0] == 'conjunction' else 180
                time_to_aspect = abs(angle - target_angle) / abs(moon.speed_long) / 24 if moon.speed_long != 0 else float('inf')
                
                if time_to_aspect < time_to_next_sign:
                    return False
        
        return True
    
    def _calculate_critical_degrees(
        self,
        planets: Dict[str, PlanetPosition]
    ) -> List[Dict]:
        """Поиск критических градусов (0, 13, 26)"""
        critical = []
        critical_degrees = [0, 13, 26]
        
        for planet_name, pos in planets.items():
            sign_degree = pos.longitude % 30
            
            for crit_deg in critical_degrees:
                if abs(sign_degree - crit_deg) <= 1:
                    critical.append({
                        'planet': planet_name,
                        'degree': sign_degree,
                        'critical_degree': crit_deg,
                        'sign': pos.sign
                    })
        
        return critical

    def _calculate_planetary_hour(
        self,
        dt_utc: datetime,
        lat: float,
        lon: float
    ) -> Dict:
        """Расчет планетарного часа"""
        try:
            jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, 0.0)

            # Восход
            try:
                sunrise_result = swe.rise_trans(jd, swe.SUN, lon, lat, 0, 0)
                if isinstance(sunrise_result, tuple) and len(sunrise_result) > 1:
                    sunrise = sunrise_result[1][0]
                else:
                    sunrise = sunrise_result[0]
            except:
                sunrise = jd + 0.25

            # Закат
            try:
                sunset_result = swe.rise_trans(jd, swe.SUN, lon, lat, 1, 0)
                if isinstance(sunset_result, tuple) and len(sunset_result) > 1:
                    sunset = sunset_result[1][0]
                else:
                    sunset = sunset_result[0]
            except:
                sunset = jd + 0.75

            sunrise_dt = dt_utc.replace(hour=0, minute=0, second=0, microsecond=0) + \
                         timedelta(days=float(sunrise) - jd)
            sunset_dt = dt_utc.replace(hour=0, minute=0, second=0, microsecond=0) + \
                        timedelta(days=float(sunset) - jd)

            day_duration = (sunset_dt - sunrise_dt).total_seconds() / 3600
            night_duration = 24.0 - day_duration

            current_time = dt_utc
            weekday = dt_utc.weekday()

            if sunrise_dt <= current_time < sunset_dt:
                time_diff = (current_time - sunrise_dt).total_seconds()
                hour_num = int(time_diff / 3600)
                total_hours = day_duration
                is_day = True
            else:
                if current_time >= sunset_dt:
                    night_start = sunset_dt
                else:
                    night_start = sunset_dt - timedelta(days=1)

                time_diff = (current_time - night_start).total_seconds()
                hour_num = int(time_diff / 3600) % 12
                total_hours = night_duration
                is_day = False

            chaldean_order = ['Saturn', 'Jupiter', 'Mars', 'Sun', 'Venus', 'Mercury', 'Moon']

            if is_day:
                weekday_rulers = ['Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Sun']
                start_planet = weekday_rulers[weekday]
            else:
                day_ruler = ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn'][weekday]
                night_ruler = chaldean_order[(chaldean_order.index(day_ruler) + 3) % 7]
                start_planet = night_ruler

            start_idx = chaldean_order.index(start_planet)
            planet_idx = (start_idx + hour_num) % 7

            return {
                'planet': chaldean_order[planet_idx],
                'hour_number': hour_num + 1,
                'is_day': is_day,
                'day_hours': round(day_duration, 2),
                'night_hours': round(night_duration, 2),
                'sunrise': sunrise_dt.isoformat(),
                'sunset': sunset_dt.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to calculate planetary hour: {e}")
            return {
                'planet': 'Sun',
                'hour_number': 1,
                'is_day': True,
                'day_hours': 12.0,
                'night_hours': 12.0,
                'sunrise': dt_utc.replace(hour=6, minute=0).isoformat(),
                'sunset': dt_utc.replace(hour=18, minute=0).isoformat(),
                'error': str(e)
            }


    def _find_house(self, houses: HouseCusps, longitude: float) -> int:
        """Определить дом по долготе"""
        for i in range(12):
            cusp1 = houses.cusps[i]
            cusp2 = houses.cusps[(i + 1) % 12]

            if cusp1 <= cusp2:
                if cusp1 <= longitude < cusp2:
                    return i + 1
            else:
                if longitude >= cusp1 or longitude < cusp2:
                    return i + 1
        return 1

    def _interpret_part(self, part_name: str, house: int, conjunctions: List) -> str:
        """Интерпретация арабской части в контексте"""
        interpretations = {
            'Fortune': f"Фортуна в {house} доме: удача через сферу дома",
            'Spirit': f"Дух в {house} доме: духовный рост через сферу дома",
            'Love': f"Любовь в {house} доме: отношения через сферу дома",
            'Passion': f"Страсть в {house} доме: творческая энергия",
            'Commerce': f"Бизнес в {house} доме: успех в делах",
            'Faith': f"Вера в {house} доме: философские убеждения",
            'Victory': f"Победа в {house} доме: достижения",
            'Marriage': f"Брак в {house} доме: партнерство",
            'Children': f"Дети в {house} доме: творчество",
            'Sickness': f"Здоровье в {house} доме: болезни",
            'Death': f"Трансформация в {house} доме: потери",
            'Father': f"Отец в {house} доме: отношения с отцом",
            'Mother': f"Мать в {house} доме: отношения с матерью"
        }

        base = interpretations.get(part_name, f"{part_name} в {house} доме")

        if conjunctions:
            planets = ', '.join([c['planet'] for c in conjunctions[:3]])
            if len(conjunctions) > 3:
                planets += f" и еще {len(conjunctions) - 3}"
            base += f". Соединение с {planets} усиливает влияние"

        return base

    def _detect_t_square(self, planets: Dict, aspects: List[Aspect]) -> Optional[Dict]:
        """Поиск Тау-квадрата (2 оппозиции + 2 квадрата к третьей)"""
        # Собираем все оппозиции
        oppositions = [a for a in aspects if a.aspect_type == 'opposition']

        for opp in oppositions:
            p1, p2 = opp.planet1, opp.planet2

            # Ищем планету, делающую квадраты к обоим
            for p3 in planets.keys():
                if p3 in [p1, p2]:
                    continue

                # Проверяем квадраты
                square1 = False
                square2 = False

                for asp in aspects:
                    if asp.aspect_type != 'square':
                        continue

                    if {asp.planet1, asp.planet2} == {p1, p3}:
                        square1 = True
                    if {asp.planet1, asp.planet2} == {p2, p3}:
                        square2 = True

                if square1 and square2:
                    return {
                        'apex': p3,
                        'base': [p1, p2],
                        'planets': [p1, p2, p3],
                        'description': f"Тау-квадрат с вершиной на {p3}"
                    }

        return None

    def _detect_grand_trine(self, planets: Dict, aspects: List[Aspect]) -> List[Dict]:
        """Поиск Большого трина (3 трина)"""
        trines = [a for a in aspects if a.aspect_type == 'trine']
        grand_trines = []

        # Группируем трины по элементам
        for element in ['Fire', 'Earth', 'Air', 'Water']:
            element_signs = [s for s in ZODIAC_SIGNS if SIGN_ELEMENTS.get(s) == element]
            element_planets = []

            for name, planet in planets.items():
                if planet.sign in element_signs:
                    element_planets.append(name)

            # Проверяем, есть ли трины между всеми тремя
            if len(element_planets) >= 3:
                trine_count = 0
                for i, p1 in enumerate(element_planets):
                    for p2 in element_planets[i + 1:]:
                        for asp in trines:
                            if {asp.planet1, asp.planet2} == {p1, p2}:
                                trine_count += 1

                if trine_count >= 3:  # Минимум 3 трина
                    grand_trines.append({
                        'element': element,
                        'planets': element_planets[:3],
                        'description': f"Большой трин в {element} знаках"
                    })

        return grand_trines

    def _detect_grand_cross(self, planets: Dict, aspects: List[Aspect]) -> Optional[Dict]:
        """Поиск Большого креста (2 оппозиции, 4 квадрата)"""
        # Ищем 4 планеты в кардинальных/фиксированных/мутабельных знаках
        modalities = {
            'cardinal': ['Aries', 'Cancer', 'Libra', 'Capricorn'],
            'fixed': ['Taurus', 'Leo', 'Scorpio', 'Aquarius'],
            'mutable': ['Gemini', 'Virgo', 'Sagittarius', 'Pisces']
        }

        for mod_name, mod_signs in modalities.items():
            mod_planets = []
            for name, planet in planets.items():
                if planet.sign in mod_signs:
                    mod_planets.append(name)

            if len(mod_planets) >= 4:
                # Проверяем оппозиции и квадраты
                opp_count = 0
                square_count = 0

                for i, p1 in enumerate(mod_planets[:4]):
                    for p2 in mod_planets[i + 1:4]:
                        for asp in aspects:
                            if {asp.planet1, asp.planet2} == {p1, p2}:
                                if asp.aspect_type == 'opposition':
                                    opp_count += 1
                                elif asp.aspect_type == 'square':
                                    square_count += 1

                if opp_count >= 2 and square_count >= 4:
                    return {
                        'modality': mod_name,
                        'planets': mod_planets[:4],
                        'description': f"Большой крест в {mod_name} знаках"
                    }

        return None

    def _detect_yod(self, planets: Dict, aspects: List[Aspect]) -> Optional[Dict]:
        """Поиск Йода (2 квиконса к одной планете)"""
        quincunxes = [a for a in aspects if a.aspect_type == 'quincunx']

        # Собираем все планеты, к которым есть квиконсы
        target_planets = {}
        for asp in quincunxes:
            for p in [asp.planet1, asp.planet2]:
                target_planets[p] = target_planets.get(p, 0) + 1

        # Ищем планеты с двумя квиконсами
        for planet, count in target_planets.items():
            if count >= 2:
                # Находим обе планеты в квиконсе
                yod_planets = []
                for asp in quincunxes:
                    if asp.planet1 == planet:
                        yod_planets.append(asp.planet2)
                    elif asp.planet2 == planet:
                        yod_planets.append(asp.planet1)

                if len(yod_planets) >= 2:
                    return {
                        'apex': planet,
                        'base': yod_planets[:2],
                        'planets': [planet] + yod_planets[:2],
                        'description': f"Йод (Палец Бога) с вершиной на {planet}"
                    }

        return None

    def _detect_bucket(self, planets: Dict, aspects: List[Aspect]) -> Optional[Dict]:
        """Поиск Корзины (одна планета в оппозиции к стеллиуму)"""
        # Находим стеллиумы
        sign_counts = {}
        for name, planet in planets.items():
            sign_counts[planet.sign] = sign_counts.get(planet.sign, []) + [name]

        for sign, planet_list in sign_counts.items():
            if len(planet_list) >= 3:  # Стеллмум
                # Ищем планету в оппозиции
                for asp in aspects:
                    if asp.aspect_type != 'opposition':
                        continue

                    # Проверяем, не входит ли планета оппозиции в стеллмум
                    if asp.planet1 in planet_list and asp.planet2 not in planet_list:
                        return {
                            'handle': asp.planet2,
                            'bucket': planet_list,
                            'sign': sign,
                            'description': f"Корзина: стеллмум в {sign} с ручкой на {asp.planet2}"
                        }
                    elif asp.planet2 in planet_list and asp.planet1 not in planet_list:
                        return {
                            'handle': asp.planet1,
                            'bucket': planet_list,
                            'sign': sign,
                            'description': f"Корзина: стеллмум в {sign} с ручкой на {asp.planet1}"
                        }

        return None

    def _detect_locomotive(self, planets: Dict) -> Optional[Dict]:
        """Поиск Локомотива (пустой сектор 60-120°)"""
        longitudes = [p.longitude for p in planets.values()]
        longitudes.sort()

        # Находим самый большой пустой сектор
        max_gap = 0
        gap_start = 0

        for i in range(len(longitudes)):
            gap = (longitudes[(i + 1) % len(longitudes)] - longitudes[i]) % 360
            if gap > max_gap:
                max_gap = gap
                gap_start = longitudes[i]

        if 60 <= max_gap <= 120:  # Пустой сектор подходит
            return {
                'gap_size': max_gap,
                'gap_start': gap_start,
                'planets': list(planets.keys()),
                'description': f"Локомотив: пустой сектор {max_gap:.1f}°"
            }

        return None

    def _detect_splash(self, planets: Dict) -> Optional[Dict]:
        """Поиск Фонтана (планеты во всех знаках)"""
        signs_with_planets = set(p.sign for p in planets.values())

        if len(signs_with_planets) >= 10:  # Минимум 10 знаков занято
            return {
                'signs_occupied': len(signs_with_planets),
                'planets': list(planets.keys()),
                'description': f"Фонтан: планеты в {len(signs_with_planets)} знаках"
            }

        return None

    def _detect_bundle(self, planets: Dict) -> Optional[Dict]:
        """Поиск Пучка (все планеты в 2-3 знаках)"""
        signs_with_planets = set(p.sign for p in planets.values())

        if len(signs_with_planets) <= 3:
            return {
                'signs': list(signs_with_planets),
                'planets': list(planets.keys()),
                'description': f"Пучок: все планеты в {len(signs_with_planets)} знаках"
            }

        return None

    def _detect_bowl(self, planets: Dict) -> Optional[Dict]:
        """Поиск Чаши (планеты в 180° секторе)"""
        longitudes = [p.longitude for p in planets.values()]
        longitudes.sort()

        # Находим минимальный сектор, содержащий все планеты
        min_span = 360
        for i in range(len(longitudes)):
            span = (longitudes[(i + len(longitudes) - 1) % len(longitudes)] - longitudes[i]) % 360
            if span < min_span:
                min_span = span

        if min_span <= 180:
            return {
                'span': min_span,
                'planets': list(planets.keys()),
                'description': f"Чаша: планеты в секторе {min_span:.1f}°"
            }

        return None

    def _detect_seesaw(self, planets: Dict, aspects: List[Aspect]) -> Optional[Dict]:
        """Поиск Качелей (две группы планет в оппозиции)"""
        # Группируем планеты по полушариям
        left_planets = []
        right_planets = []

        for name, planet in planets.items():
            if 0 <= planet.longitude < 180:
                left_planets.append(name)
            else:
                right_planets.append(name)

        # Проверяем, есть ли оппозиции между группами
        if len(left_planets) >= 2 and len(right_planets) >= 2:
            opp_count = 0
            for asp in aspects:
                if asp.aspect_type == 'opposition':
                    if (asp.planet1 in left_planets and asp.planet2 in right_planets) or \
                            (asp.planet2 in left_planets and asp.planet1 in right_planets):
                        opp_count += 1

            if opp_count >= 2:
                return {
                    'left_group': left_planets,
                    'right_group': right_planets,
                    'oppositions': opp_count,
                    'description': f"Качели: {len(left_planets)} vs {len(right_planets)} планет"
                }

        return None

    def _detect_kite(self, planets: Dict, aspects: List[Aspect], grand_trines: List[Dict]) -> Optional[Dict]:
        """Поиск Воздушного змея (большой трин + оппозиция)"""
        for gt in grand_trines:
            # Для каждого большого трина ищем оппозицию к одной из планет
            for planet in gt['planets']:
                for asp in aspects:
                    if asp.aspect_type != 'opposition':
                        continue

                    if asp.planet1 == planet or asp.planet2 == planet:
                        other = asp.planet2 if asp.planet1 == planet else asp.planet1

                        return {
                            'grand_trine': gt['planets'],
                            'opposition': {'planet': planet, 'to': other},
                            'description': f"Воздушный змей: {gt['element']} трин + оппозиция"
                        }

        return None

    def _detect_mystic_rectangle(self, planets: Dict, aspects: List[Aspect]) -> Optional[Dict]:
        """Поиск Мистического прямоугольника (2 оппозиции + 2 трина + 2 секстиля)"""
        # Сложная конфигурация, требует анализа всех аспектов
        # Упрощенная реализация
        oppositions = [a for a in aspects if a.aspect_type == 'opposition']
        trines = [a for a in aspects if a.aspect_type == 'trine']
        sextiles = [a for a in aspects if a.aspect_type == 'sextile']

        if len(oppositions) >= 2 and len(trines) >= 2 and len(sextiles) >= 2:
            return {
                'description': "Мистический прямоугольник (возможен)",
                'confidence': 'low'
            }

        return None

    def _detect_castle(self, planets: Dict, aspects: List[Aspect], grand_trines: List[Dict]) -> Optional[Dict]:
        """Поиск Замка (два больших трина)"""
        if len(grand_trines) >= 2:
            return {
                'grand_trines': [gt['planets'] for gt in grand_trines[:2]],
                'description': "Замок: два больших трина"
            }

        return None

    def _detect_patterns(self, planets: Dict, aspects: List[Aspect]) -> Dict:
        """
        Обнаружение целостных астрологических конфигураций
        """
        patterns = {
            'stellium': {},
            't_square': None,
            'grand_trine': [],
            'grand_cross': None,
            'yod': None,
            'kite': None,
            'castle': None,
            'mystic_rectangle': None,
            'bucket': None,  # Корзина (одна планета в оппозиции к стеллиуму)
            'locomotive': None,  # Локомотив (пустой сектор 60-120°)
            'splash': None,  # Фонтан (планеты во всех знаках)
            'bundle': None,  # Пучок (все планеты в 2-3 знаках)
            'bowl': None,  # Чаша (планеты в 180° секторе)
            'seesaw': None  # Качели (две группы планет в оппозиции)
        }

        # 1. Стеллмум (психологический фокус)
        sign_counts = {}
        house_counts = {}
        for name, planet in planets.items():
            sign_counts[planet.sign] = sign_counts.get(planet.sign, 0) + 1
            house_counts[planet.house] = house_counts.get(planet.house, 0) + 1

        patterns['stellium'] = {
            'by_sign': {s: c for s, c in sign_counts.items() if c >= 3},
            'by_house': {h: c for h, c in house_counts.items() if c >= 3}
        }

        # 2. Тау-квадрат (T-square)
        patterns['t_square'] = self._detect_t_square(planets, aspects)

        # 3. Большой трин (Grand Trine)
        patterns['grand_trine'] = self._detect_grand_trine(planets, aspects)

        # 4. Большой крест (Grand Cross)
        patterns['grand_cross'] = self._detect_grand_cross(planets, aspects)

        # 5. Йод (Yod) - Палец Бога
        patterns['yod'] = self._detect_yod(planets, aspects)

        # 6. Корзина (Bucket)
        patterns['bucket'] = self._detect_bucket(planets, aspects)

        # 7. Локомотив (Locomotive)
        patterns['locomotive'] = self._detect_locomotive(planets)

        # 8. Фонтан (Splash)
        patterns['splash'] = self._detect_splash(planets)

        # 9. Пучок (Bundle)
        patterns['bundle'] = self._detect_bundle(planets)

        # 10. Чаша (Bowl)
        patterns['bowl'] = self._detect_bowl(planets)

        # 11. Качели (Seesaw)
        patterns['seesaw'] = self._detect_seesaw(planets, aspects)

        # 12. Воздушный змей (Kite)
        if patterns['grand_trine']:
            patterns['kite'] = self._detect_kite(planets, aspects, patterns['grand_trine'])

        # 13. Мистический прямоугольник
        patterns['mystic_rectangle'] = self._detect_mystic_rectangle(planets, aspects)

        # 14. Замок (Castle) - два больших трина
        if len(patterns['grand_trine']) >= 2:
            patterns['castle'] = self._detect_castle(planets, aspects, patterns['grand_trine'])

        return patterns


    def _analyze_arabic_parts(self, chart: RawEphemeris) -> Dict:
        """
        Анализ связей арабских частей с планетами и домами
        """
        connections = {}

        for part_name, part in chart.arabic_parts.items():
            house = self._find_house(chart.houses, part.longitude)

            conjunctions = []
            for planet_name, planet in chart.planets.items():
                angle = abs(part.longitude - planet.longitude) % 360
                if min(angle, 360 - angle) < 3:
                    conjunctions.append({
                        'planet': planet_name,
                        'orb': min(angle, 360 - angle),
                        'house': planet.house
                    })

            aspects = []
            for planet_name, planet in chart.planets.items():
                angle = abs(part.longitude - planet.longitude) % 360
                if angle > 180:
                    angle = 360 - angle

                for asp_angle, asp_name in [(0, 'conjunction'), (60, 'sextile'),
                                            (90, 'square'), (120, 'trine'), (180, 'opposition')]:
                    if abs(angle - asp_angle) < 5:
                        aspects.append({
                            'planet': planet_name,
                            'aspect': asp_name,
                            'orb': abs(angle - asp_angle)
                        })

            connections[part_name] = {
                'longitude': part.longitude,
                'sign': part.sign,
                'house': house,
                'conjunctions': conjunctions,
                'aspects': aspects,
                'interpretation': self._interpret_part(part_name, house, conjunctions)
            }

        return connections

    async def calculate(
        self,
        dt: datetime,
        lat: float,
        lon: float,
        timezone: Optional[str] = None,
        hsys: str = 'P',
        include_all: bool = True,
        include_heavy: bool = True
    ) -> RawEphemeris:
        """
        ПОЛНЫЙ расчет астрологической карты
        """
        start_time = time.time()

        async with self._metrics_lock:
            self.metrics['total_calculations'] += 1

        try:
            # ✅ 1. Сначала валидация (нужна для jd_ut)
            geo = GeoCoordinates(lat=lat, lon=lon, timezone=timezone or "UTC")
            dt_utc, jd_ut = self._validate_datetime(dt, geo.timezone)

            # ✅ 2. Потом проверка кэша
            cache_options = {
                'include_all': include_all,
                'include_heavy': include_heavy
            }
            cached = self.cache.get(jd_ut, lat, lon, hsys, cache_options)
            if cached:
                logger.debug(f"Cache hit for {dt}")
                return cached
            # Валидация
            geo = GeoCoordinates(lat=lat, lon=lon, timezone=timezone or "UTC")
            dt_utc, jd_ut = self._validate_datetime(dt, geo.timezone)

            # Базовые расчеты
            planets = self._calculate_planets(jd_ut)
            houses = self._calculate_houses(jd_ut, lat, lon, hsys)
            ayanamsa = self._calculate_ayanamsa(jd_ut)
            sidereal_time = self._calculate_sidereal_time(jd_ut) * 15

            # Фаза Луны
            moon_phase = 0
            if 'Moon' in planets and 'Sun' in planets:
                moon_phase = (planets['Moon'].longitude - planets['Sun'].longitude) % 360

            # Определяем дома планет
            self._assign_houses(planets, houses)

            # Создаем базовый результат
            result = RawEphemeris(
                jd_ut=jd_ut,
                timestamp_ut=dt_utc,
                planets=planets,
                houses=houses,
                ayanamsa=ayanamsa,
                sidereal_time=sidereal_time,
                moon_phase=moon_phase,
                geo=geo,
                calculation_time=time.time() - start_time
            )

            # Быстрые расчеты (всегда)
            result.critical_degrees = self._calculate_critical_degrees(planets)
            result.midpoints = self._calculate_midpoints(planets)
            result.void_of_course = self._check_void_of_course(jd_ut, planets['Moon'], planets)

            # Средние по сложности
            if include_all:
                result.aspects = self._calculate_aspects(planets)
                result.aspect_qualities = [
                    self._get_aspect_quality(aspect)
                    for aspect in result.aspects
                ]

                is_day = self._is_day_chart(planets['Sun'].longitude, houses.ascendant)
                
                # Достоинства планет
                for name, planet in result.planets.items():
                    if name in RULERS or name in EXALTATIONS:
                        planet.dignity = self._calculate_dignities(planet, name, is_day)

                result.arabic_parts = self._calculate_arabic_parts(
                    houses.ascendant, planets, is_day
                )

                result.planetary_hour = self._calculate_planetary_hour(dt_utc, lat, lon)

                result.lunar_data = await self._calculate_lunar_data(result)
                result.solar_data = await self._calculate_solar_data(result, lat, lon)

            # Тяжелые расчеты
            if include_heavy:
                result.fixed_stars = self._calculate_fixed_stars(jd_ut, planets)

                sun_sid = (planets['Sun'].longitude - ayanamsa) % 360
                moon_sid = (planets['Moon'].longitude - ayanamsa) % 360
                result.panchanga = self._calculate_panchanga(sun_sid, moon_sid)
                result.dasha = self._calculate_dasha(dt_utc, moon_sid)

                if result.arabic_parts:
                    result.arabic_connections = self._analyze_arabic_parts(result)

                if result.fixed_stars:
                    result.star_interpretations = self._interpret_fixed_stars(result)

                result.patterns = self._detect_patterns(planets, result.aspects)

            result.calculation_time = time.time() - start_time
            
            # Сохраняем в кэш
            self.cache.set(jd_ut, lat, lon, hsys, cache_options, result)
            
            logger.info(
                f"✅ Chart calculated: "
                f"planets={len(planets)}, "
                f"aspects={len(result.aspects)}, "
                f"stars={len(result.fixed_stars)}, "
                f"time={result.calculation_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Calculation failed: {e}")
            async with self._metrics_lock:
                self.metrics['errors'] += 1
            raise CalculationError(f"Ephemeris calculation failed: {e}") from e
    
    async def calculate_jyotish(
        self,
        dt: datetime,
        lat: float,
        lon: float,
        timezone: Optional[str] = None,
        hsys: str = 'P'
    ) -> RawEphemeris:
        """Расчет для джйотиш (сидерический)"""
        chart = await self.calculate(dt, lat, lon, timezone, hsys)
        
        for planet in chart.planets.values():
            planet.longitude = (planet.longitude - chart.ayanamsa) % 360
        
        return chart
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Получить метрики работы"""
        async with self._metrics_lock:
            metrics = self.metrics.copy()
        
        metrics['cache'] = self.cache.get_stats()
        return metrics

    async def _calculate_lunar_data(self, chart: RawEphemeris) -> LunarData:
        """Расчет детальных данных Луны"""
        moon = chart.planets['Moon']
        sun = chart.planets['Sun']

        phase = chart.moon_phase

        if phase < 45 or phase > 315:
            phase_name = "New Moon"
            illumination = 0
        elif phase < 90:
            phase_name = "Waxing Crescent"
            illumination = phase / 90
        elif phase < 135:
            phase_name = "First Quarter"
            illumination = 0.5
        elif phase < 180:
            phase_name = "Waxing Gibbous"
            illumination = 0.75
        elif phase < 225:
            phase_name = "Full Moon"
            illumination = 1.0
        elif phase < 270:
            phase_name = "Waning Gibbous"
            illumination = 0.75
        elif phase < 315:
            phase_name = "Last Quarter"
            illumination = 0.5
        else:
            phase_name = "Waning Crescent"
            illumination = 0.25

        age_days = (phase / 360) * 29.53
        distance_km = moon.distance * 149597870.7
        is_super_moon = distance_km < 360000 and phase_name == "Full Moon"

        nodes = [chart.planets['True_Node'].longitude,
                 (chart.planets['True_Node'].longitude + 180) % 360]
        moon_node_distance = min(abs(moon.longitude - n) % 360 for n in nodes)
        is_eclipse_season = moon_node_distance < 15 or moon_node_distance > 345

        next_phase_angles = [0, 90, 180, 270]
        next_phase = min(next_phase_angles, key=lambda x: abs((x - phase) % 360))
        days_to_next = (abs(next_phase - phase) / 360) * 29.53

        next_phase_names = {0: "New Moon", 90: "First Quarter",
                            180: "Full Moon", 270: "Last Quarter"}

        is_blue_moon = False
        if phase_name == "Full Moon" and chart.timestamp_ut.day > 28:
            next_full_date = chart.timestamp_ut + timedelta(days=29.53)
            if next_full_date.month == chart.timestamp_ut.month:
                is_blue_moon = True

        return LunarData(
            phase_angle=phase,
            phase_name=phase_name,
            illumination=illumination,
            age_days=round(age_days, 2),
            distance_km=round(distance_km),
            is_void=chart.void_of_course,
            next_phase=next_phase_names[next_phase],
            days_to_next_phase=round(days_to_next, 2),
            is_super_moon=is_super_moon,
            is_blue_moon=is_blue_moon,
            is_eclipse_season=is_eclipse_season,
            nakshatra=chart.panchanga.nakshatra_name if chart.panchanga else "",
            nakshatra_pada=chart.panchanga.nakshatra_pada if chart.panchanga else 0,
            tithi=chart.panchanga.tithi if chart.panchanga else 0,
            sign=moon.sign,
            house=moon.house
        )

    async def _calculate_solar_data(self, chart: RawEphemeris, lat: float, lon: float) -> SolarData:
        """Расчет детальных данных Солнца"""
        sun = chart.planets['Sun']

        seasons = {
            'Aries': 'spring', 'Taurus': 'spring', 'Gemini': 'spring',
            'Cancer': 'summer', 'Leo': 'summer', 'Virgo': 'summer',
            'Libra': 'autumn', 'Scorpio': 'autumn', 'Sagittarius': 'autumn',
            'Capricorn': 'winter', 'Aquarius': 'winter', 'Pisces': 'winter'
        }
        season = seasons.get(sun.sign, 'unknown')

        is_solstice = sun.sign in ['Cancer', 'Capricorn'] and 14 <= sun.sign_longitude <= 16
        is_equinox = sun.sign in ['Aries', 'Libra'] and 14 <= sun.sign_longitude <= 16

        distance_km = sun.distance * 149597870.7
        declination = sun.latitude
        right_ascension = sun.longitude / 15

        try:
            jd = chart.jd_ut
            sunrise = swe.rise_trans(jd, swe.SUN, lon, lat, 0, 0)[1][0]
            sunset = swe.rise_trans(jd, swe.SUN, lon, lat, 1, 0)[1][0]

            sunrise_dt = chart.timestamp_ut.replace(hour=0) + timedelta(days=sunrise - jd)
            sunset_dt = chart.timestamp_ut.replace(hour=0) + timedelta(days=sunset - jd)
            day_length = (sunset_dt - sunrise_dt).seconds / 3600
        except:
            sunrise_dt = sunset_dt = None
            day_length = 12

        return SolarData(
            season=season,
            is_solstice=is_solstice,
            is_equinox=is_equinox,
            distance_km=round(distance_km),
            declination=round(declination, 4),
            right_ascension=round(right_ascension, 4),
            sign=sun.sign,
            house=sun.house,
            dignity=sun.dignity,
            sunrise=sunrise_dt,
            sunset=sunset_dt,
            day_length=round(day_length, 2)
        )


# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ====================

_calculator_instance: Optional[EphemerisCalculator] = None
_calculator_lock = asyncio.Lock()


async def get_ephemeris_calculator(
    ephemeris_path: Optional[str] = None,
    cache_size: int = 1000,
    include_fixed_stars: bool = True,
    include_arabic_parts: bool = True
) -> EphemerisCalculator:
    """Получить глобальный экземпляр калькулятора"""
    global _calculator_instance
    
    async with _calculator_lock:
        if _calculator_instance is None:
            _calculator_instance = EphemerisCalculator(
                ephemeris_path=ephemeris_path,
                cache_size=cache_size,
                include_fixed_stars=include_fixed_stars,
                include_arabic_parts=include_arabic_parts
            )
        return _calculator_instance
