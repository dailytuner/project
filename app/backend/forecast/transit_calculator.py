"""
transit_calculator.py - Расчёт транзитов планет для дневных прогнозов
Версия 1.0 - Production Ready

Вычисляет:
1. Положения всех транзитных планет на дату
2. Аспекты транзитных планет к натальным планетам
3. Аспекты транзитных планет к натальным углам (Асцендент, MC)
4. Индивидуальные коэффициенты влияния для каждой оси Magic Profile
"""

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database.models import NatalChart, User
from ..calculators.ephemeris_base import EphemerisCalculator, get_ephemeris_calculator

logger = logging.getLogger(__name__)


# ============================================================
# ДАТАКЛАССЫ ДЛЯ ТРАНЗИТОВ
# ============================================================

@dataclass
class TransitAspect:
    """Одиночный транзитный аспект"""
    transit_planet: str
    natal_planet: str
    aspect_type: str
    angle: float
    orb: float
    strength: float
    applying: bool

    def __post_init__(self):
        # Округляем значения для консистентности
        self.angle = round(self.angle, 2)
        self.orb = round(self.orb, 4)
        self.strength = round(self.strength, 4)


@dataclass
class DailyTransits:
    """Все транзиты на один день"""
    date: date
    transit_positions: Dict[str, Dict[str, Any]]
    aspects_to_natal: List[TransitAspect]
    aspects_to_angles: List[TransitAspect]
    planetary_hour_info: Dict[str, Any]
    void_of_course_moon: bool

    # Кэш для быстрого доступа
    _aspects_by_planet: Dict[str, List[TransitAspect]] = field(default_factory=dict, repr=False)

    def get_aspects_by_planet(self, planet_name: str) -> List[TransitAspect]:
        """Получить все аспекты для конкретной транзитной планеты"""
        if not self._aspects_by_planet:
            for aspect in self.aspects_to_natal:
                key = aspect.transit_planet
                if key not in self._aspects_by_planet:
                    self._aspects_by_planet[key] = []
                self._aspects_by_planet[key].append(aspect)
        return self._aspects_by_planet.get(planet_name, [])


# ============================================================
# КОНСТАНТЫ ДЛЯ АСПЕКТОВ
# ============================================================

# Базовые углы аспектов
ASPECT_ANGLES = {
    'conjunction': 0,
    'opposition': 180,
    'trine': 120,
    'square': 90,
    'sextile': 60,
    'quincunx': 150,
    'semisextile': 30,
    'semisquare': 45,
    'sesquiquadrate': 135
}

# Максимальные орбисы для разных типов планет
MAX_ORBS = {
    # Быстрые планеты (строгие орбисы)
    'Moon': 8.0,
    'Sun': 7.0,
    'Mercury': 7.0,
    'Venus': 7.0,
    'Mars': 7.0,

    # Социальные планеты (средние орбисы)
    'Jupiter': 8.0,
    'Saturn': 8.0,

    # Медленные планеты (широкие орбисы)
    'Uranus': 5.0,
    'Neptune': 5.0,
    'Pluto': 4.0,

    # Узлы и фиктивные точки
    'True_Node': 4.0,
    'Mean_Node': 4.0,
    'Chiron': 4.0,
    'Lilith': 4.0
}

# Сила аспекта в зависимости от типа (используется при расчёте модуляции осей)
ASPECT_STRENGTH_BASE = {
    'conjunction': 0.15,
    'opposition': 0.12,
    'trine': 0.10,
    'square': 0.12,
    'sextile': 0.08,
    'quincunx': 0.06,
    'semisextile': 0.04,
    'semisquare': 0.06,
    'sesquiquadrate': 0.06
}

# Влияние аспектов на оси Magic Profile
ASPECT_AXIS_EFFECTS = {
    # (планета, тип_аспекта, натальная_планета) -> (ось, направление, сила)
    # направление: + (усиление), - (ослабление)

    # Энергия и воля (energy_will)
    ('Mars', 'conjunction', 'Sun'): ('energy_will', +0.15),
    ('Mars', 'trine', 'Sun'): ('energy_will', +0.10),
    ('Mars', 'opposition', 'Sun'): ('energy_will', -0.05),
    ('Mars', 'conjunction', 'Mars'): ('energy_will', +0.12),
    ('Mars', 'square', 'Moon'): ('energy_will', -0.08),
    ('Mars', 'sextile', 'Jupiter'): ('energy_will', +0.06),

    # Интеллект и логика (intellect_logic)
    ('Mercury', 'conjunction', 'Mercury'): ('intellect_logic', +0.15),
    ('Mercury', 'trine', 'Mercury'): ('intellect_logic', +0.10),
    ('Mercury', 'square', 'Saturn'): ('intellect_logic', -0.10),
    ('Mercury', 'opposition', 'Neptune'): ('intellect_logic', -0.06),
    ('Uranus', 'conjunction', 'Mercury'): ('intellect_logic', +0.12),
    ('Uranus', 'trine', 'Mercury'): ('intellect_logic', +0.08),

    # Эмоции и интуиция (emotions_intuition)
    ('Moon', 'conjunction', 'Moon'): ('emotions_intuition', +0.15),
    ('Moon', 'square', 'Mars'): ('emotions_intuition', -0.10),
    ('Moon', 'trine', 'Venus'): ('emotions_intuition', +0.08),
    ('Moon', 'opposition', 'Saturn'): ('emotions_intuition', -0.12),
    ('Neptune', 'conjunction', 'Moon'): ('emotions_intuition', +0.12),
    ('Neptune', 'trine', 'Moon'): ('emotions_intuition', +0.08),

    # Труд и дисциплина (work_discipline)
    ('Saturn', 'conjunction', 'Saturn'): ('work_discipline', +0.15),
    ('Saturn', 'trine', 'Mars'): ('work_discipline', +0.10),
    ('Saturn', 'square', 'Jupiter'): ('work_discipline', -0.06),
    ('Saturn', 'opposition', 'Moon'): ('work_discipline', -0.08),
    ('Mars', 'conjunction', 'Saturn'): ('work_discipline', +0.10),

    # Социальные отношения (social_relations)
    ('Venus', 'conjunction', 'Venus'): ('social_relations', +0.15),
    ('Venus', 'trine', 'Venus'): ('social_relations', +0.10),
    ('Venus', 'square', 'Mars'): ('social_relations', -0.08),
    ('Venus', 'opposition', 'Saturn'): ('social_relations', -0.10),
    ('Moon', 'conjunction', 'Venus'): ('social_relations', +0.08),
    ('Jupiter', 'trine', 'Venus'): ('social_relations', +0.06),

    # Удача и таланты (luck_talent)
    ('Jupiter', 'conjunction', 'Jupiter'): ('luck_talent', +0.15),
    ('Jupiter', 'trine', 'Sun'): ('luck_talent', +0.10),
    ('Jupiter', 'square', 'Saturn'): ('luck_talent', -0.08),
    ('Venus', 'conjunction', 'Jupiter'): ('luck_talent', +0.10),
    ('Sun', 'trine', 'Jupiter'): ('luck_talent', +0.08),

    # Финансы (отдельная ось, но можно добавить в общую систему)
    ('Jupiter', 'conjunction', 'SecondHouse'): ('finances', +0.15),
    ('Venus', 'trine', 'SecondHouse'): ('finances', +0.10),
    ('Saturn', 'square', 'SecondHouse'): ('finances', -0.12),
    ('Mars', 'opposition', 'SecondHouse'): ('finances', -0.08),

    # Кармические циклы (karma_cycles)
    ('Saturn', 'conjunction', 'True_Node'): ('karma_cycles', +0.12),
    ('Saturn', 'square', 'Saturn'): ('karma_cycles', -0.10),
    ('Pluto', 'conjunction', 'True_Node'): ('karma_cycles', +0.15),
    ('Uranus', 'opposition', 'Saturn'): ('karma_cycles', -0.08),

    # Судьба и миссия (destiny_mission)
    ('Pluto', 'conjunction', 'Sun'): ('destiny_mission', +0.15),
    ('Uranus', 'conjunction', 'Sun'): ('destiny_mission', +0.12),
    ('Saturn', 'square', 'Sun'): ('destiny_mission', -0.10),
    ('Neptune', 'trine', 'Sun'): ('destiny_mission', +0.08),
}

# Планеты, которые нужно учитывать в транзитах
TRANSIT_PLANETS = [
    'Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
    'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto',
    'True_Node', 'Mean_Node'
]

# Углы натальной карты (для аспектов)
NATAL_ANGLES = ['Ascendant', 'Midheaven']


# ============================================================
# ТРАНЗИТНЫЙ КАЛЬКУЛЯТОР
# ============================================================

class TransitCalculator:
    """
    Калькулятор транзитов для дневных прогнозов.
    Один экземпляр на всё приложение.
    """

    def __init__(self):
        self._ephemeris: Optional[EphemerisCalculator] = None
        self._transit_cache: Dict[str, Dict] = {}

    async def _get_ephemeris(self) -> EphemerisCalculator:
        """Ленивая инициализация эфемеридного калькулятора"""
        if self._ephemeris is None:
            self._ephemeris = await get_ephemeris_calculator()
        return self._ephemeris

    def _get_cache_key(self, date: date, lat: float, lon: float, tz_name: str) -> str:
        """Создать ключ для кэша транзитов"""
        return f"{date.isoformat()}_{lat}_{lon}_{tz_name}"

    async def get_daily_transits(
            self,
            target_date: date,
            latitude: float,
            longitude: float,
            tz_name: str = 'Europe/Moscow'
    ) -> Dict:
        """
        Получить положения всех транзитных планет на указанную дату.
        Использует глобальный кэш (транзиты не зависят от пользователя).
        """
        cache_key = self._get_cache_key(target_date, latitude, longitude, tz_name)

        if cache_key in self._transit_cache:
            logger.debug(f"✅ Транзиты из кэша для {target_date}")
            return self._transit_cache[cache_key]

        ephemeris = await self._get_ephemeris()

        # Создаём datetime с полуднём для расчёта (позиции планет мало меняются за день)
        #dt = datetime.combine(target_date, datetime.min.time().replace(hour=12))
        dt = datetime.combine(target_date, datetime.min.time().replace(hour=12), tzinfo=timezone.utc)

        # Рассчитываем карту транзитов
        transit_chart = await ephemeris.calculate(
            dt=dt,
            lat=latitude,
            lon=longitude,
            timezone=tz_name,
            hsys='P',
            include_all=True,
            include_heavy=False  # Для транзитов не нужны тяжёлые расчёты
        )

        # Собираем положения планет
        positions = {}
        for planet_name in TRANSIT_PLANETS:
            if planet_name in transit_chart.planets:
                planet = transit_chart.planets[planet_name]
                positions[planet_name] = {
                    'longitude': planet.longitude,
                    'sign_longitude': planet.sign_longitude,
                    'sign': planet.sign,
                    'speed': planet.speed_long,
                    'retrograde': planet.retrograde,
                    'house': planet.house,
                    'latitude': planet.latitude,
                    'distance': planet.distance
                }

        result = {
            'date': target_date.isoformat(),
            'positions': positions,
            'moon_phase': transit_chart.moon_phase,
            'void_of_course_moon': transit_chart.void_of_course,
            'sidereal_time': transit_chart.sidereal_time,
            'planetary_hour': transit_chart.planetary_hour
        }

        # Сохраняем в кэш (ограничиваем размер)
        self._transit_cache[cache_key] = result
        if len(self._transit_cache) > 365:  # Храним не более года
            oldest = min(self._transit_cache.keys())
            del self._transit_cache[oldest]

        logger.info(f"✅ Рассчитаны транзиты для {target_date}")
        return result

    async def get_natal_chart_data(self, user_id: int, session: AsyncSession) -> Dict:
        """Получить натальную карту пользователя в удобном формате"""
        result = await session.execute(
            select(NatalChart)
            .where(NatalChart.user_id == user_id)
            .order_by(NatalChart.calculation_date.desc())
            .limit(1)
        )
        natal_chart = result.scalar_one_or_none()

        if not natal_chart:
            raise ValueError(f"Натальная карта для user_id={user_id} не найдена")

        # Извлекаем положения планет
        planets = {}
        for name, data in natal_chart.planets.items():
            if name in TRANSIT_PLANETS:
                planets[name] = {
                    'longitude': data.get('longitude', 0),
                    'sign_longitude': data.get('sign_longitude', 0),
                    'sign': data.get('sign', ''),
                    'house': data.get('house'),
                    'retrograde': data.get('retrograde', False)
                }

        # Извлекаем углы (Асцендент и MC)
        angles = {}
        houses = natal_chart.houses
        if houses:
            angles['Ascendant'] = houses.get('1', {}).get('cusp', 0)
            angles['Midheaven'] = houses.get('10', {}).get('cusp', 0)

        return {
            'planets': planets,
            'angles': angles,
            'user_id': user_id,
            'birth_lat': float(natal_chart.birth_lat),
            'birth_lng': float(natal_chart.birth_lng),
            'birth_timezone': natal_chart.birth_timezone
        }

    def _calculate_angle_diff(self, angle1: float, angle2: float) -> float:
        """Вычислить минимальную разницу между двумя углами (0-180)"""
        diff = abs(angle1 - angle2) % 360
        if diff > 180:
            diff = 360 - diff
        return diff

    def _get_aspect_type(self, angle_diff: float, max_orb: float) -> Optional[Tuple[str, float]]:
        """Определить тип аспекта по угловой разнице"""
        for aspect_name, target_angle in ASPECT_ANGLES.items():
            orb = abs(angle_diff - target_angle)
            if orb <= max_orb:
                return (aspect_name, orb)
        return None

    def _calculate_aspect_strength(self, orb: float, max_orb: float, aspect_type: str) -> float:
        """Рассчитать силу аспекта (0-1), чем точнее, тем выше"""
        # Точность аспекта
        accuracy = 1.0 - (orb / max_orb) if max_orb > 0 else 1.0

        # Базовый вес аспекта
        base_strength = ASPECT_STRENGTH_BASE.get(aspect_type, 0.05)

        # Итоговая сила
        strength = accuracy * base_strength * 2  # Нормализуем до ~0.1-0.3

        return max(0.05, min(0.35, strength))

    def _is_applying(self, transit_speed: float, natal_speed: float = 0) -> bool:
        """
        Определить, является ли аспект нарастающим (applying)
        Для быстрых планет (Луна) важно, для медленных — менее критично
        """
        # Если транзитная планета быстрее натальной, аспект нарастает
        return transit_speed > natal_speed

    async def calculate_transit_aspects(
            self,
            user_id: int,
            target_date: date,
            session: AsyncSession
    ) -> DailyTransits:
        """
        Основной метод: рассчитать все транзитные аспекты для пользователя на дату
        """
        # 1. Получаем натальную карту пользователя
        natal_data = await self.get_natal_chart_data(user_id, session)

        # 2. Получаем транзитные положения
        transits_data = await self.get_daily_transits(
            target_date=target_date,
            latitude=natal_data['birth_lat'],
            longitude=natal_data['birth_lng'],
            tz_name=natal_data['birth_timezone']
        )

        transit_positions = transits_data['positions']

        # 3. Вычисляем все аспекты к натальным планетам
        aspects_to_natal = []

        for transit_name, transit_pos in transit_positions.items():
            transit_long = transit_pos['longitude']
            transit_speed = transit_pos.get('speed', 1.0)

            for natal_name, natal_pos in natal_data['planets'].items():
                # Не сравниваем планету с самой собой
                if transit_name == natal_name:
                    continue

                natal_long = natal_pos['longitude']
                angle_diff = self._calculate_angle_diff(transit_long, natal_long)

                # Определяем максимальный орбис
                max_orb = max(
                    MAX_ORBS.get(transit_name, 7.0),
                    MAX_ORBS.get(natal_name, 7.0)
                )

                aspect_info = self._get_aspect_type(angle_diff, max_orb)

                if aspect_info:
                    aspect_type, orb = aspect_info
                    strength = self._calculate_aspect_strength(orb, max_orb, aspect_type)
                    applying = self._is_applying(transit_speed)

                    aspects_to_natal.append(TransitAspect(
                        transit_planet=transit_name,
                        natal_planet=natal_name,
                        aspect_type=aspect_type,
                        angle=angle_diff,
                        orb=orb,
                        strength=strength,
                        applying=applying
                    ))

        # 4. Вычисляем аспекты к натальным углам
        aspects_to_angles = []

        for transit_name, transit_pos in transit_positions.items():
            transit_long = transit_pos['longitude']

            for angle_name, angle_long in natal_data['angles'].items():
                angle_diff = self._calculate_angle_diff(transit_long, angle_long)
                max_orb = MAX_ORBS.get(transit_name, 6.0)

                aspect_info = self._get_aspect_type(angle_diff, max_orb)

                if aspect_info:
                    aspect_type, orb = aspect_info
                    strength = self._calculate_aspect_strength(orb, max_orb, aspect_type)

                    aspects_to_angles.append(TransitAspect(
                        transit_planet=transit_name,
                        natal_planet=angle_name,
                        aspect_type=aspect_type,
                        angle=angle_diff,
                        orb=orb,
                        strength=strength,
                        applying=False  # Для углов сложно определить applying
                    ))

        logger.info(
            f"✅ Рассчитано транзитов для user={user_id} на {target_date}: "
            f"{len(aspects_to_natal)} к планетам, {len(aspects_to_angles)} к углам"
        )

        return DailyTransits(
            date=target_date,
            transit_positions=transit_positions,
            aspects_to_natal=aspects_to_natal,
            aspects_to_angles=aspects_to_angles,
            planetary_hour_info=transits_data.get('planetary_hour', {}),
            void_of_course_moon=transits_data.get('void_of_course_moon', False)
        )


# ============================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ МОДУЛЯТОРОВ ОСЕЙ
# ============================================================

class AxisModulator:
    """
    Преобразует транзитные аспекты в модуляторы для 9 осей Magic Profile
    """

    def __init__(self):
        self._aspect_effects = ASPECT_AXIS_EFFECTS

    def calculate_axis_modulators(
            self,
            transits: DailyTransits
    ) -> Dict[str, float]:
        """
        Рассчитать коэффициенты модуляции для каждой оси.
        Возвращает словарь {axis_name: delta_value}, где delta_value от -0.3 до +0.3
        """
        # Инициализируем все оси нулевыми дельтами
        deltas = {
            'energy_will': 0.0,
            'intellect_logic': 0.0,
            'emotions_intuition': 0.0,
            'work_discipline': 0.0,
            'social_relations': 0.0,
            'luck_talent': 0.0,
            'karma_cycles': 0.0,
            'destiny_mission': 0.0,
            'finances': 0.0
        }

        # Обрабатываем аспекты к натальным планетам
        for aspect in transits.aspects_to_natal:
            effect_key = (aspect.transit_planet, aspect.aspect_type, aspect.natal_planet)

            if effect_key in self._aspect_effects:
                axis_name, direction = self._aspect_effects[effect_key]
                delta = direction * aspect.strength
                deltas[axis_name] = max(-0.3, min(0.3, deltas.get(axis_name, 0) + delta))

        # Особая обработка для Луны (быстрая планета, сильное влияние)
        moon_aspects = transits.get_aspects_by_planet('Moon')
        for aspect in moon_aspects:
            # Луна сильно влияет на эмоции
            if aspect.aspect_type in ['conjunction', 'opposition', 'square']:
                delta = -0.05 if aspect.aspect_type == 'square' else 0.05
                deltas['emotions_intuition'] = max(-0.3, min(0.3, deltas['emotions_intuition'] + delta))

            # Луна также влияет на интуицию
            if aspect.aspect_type in ['trine', 'sextile']:
                deltas['emotions_intuition'] = min(0.3, deltas['emotions_intuition'] + 0.04)

        # Void of course Moon — особый случай
        if transits.void_of_course_moon:
            # Луна без аспектов — не начинай новых дел
            deltas['emotions_intuition'] = max(-0.3, deltas['emotions_intuition'] - 0.1)
            deltas['work_discipline'] = max(-0.3, deltas['work_discipline'] - 0.05)

        # Округляем до 4 знаков
        for axis in deltas:
            deltas[axis] = round(deltas[axis], 4)

        return deltas

    def get_axis_summary(
            self,
            static_axes: Dict[str, float],
            deltas: Dict[str, float]
    ) -> Dict[str, Dict[str, float]]:
        """
        Получить итоговые значения осей после модуляции
        """
        result = {}

        for axis_name, static_value in static_axes.items():
            delta = deltas.get(axis_name, 0.0)
            daily_value = max(0.05, min(0.95, static_value + delta))

            result[axis_name] = {
                'static': static_value,
                'delta': delta,
                'daily': daily_value,
                'trend': 'rising' if delta > 0.02 else ('falling' if delta < -0.02 else 'stable')
            }

        return result


# ============================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================================

_transit_calculator: Optional[TransitCalculator] = None


async def get_transit_calculator() -> TransitCalculator:
    """Получить глобальный экземпляр TransitCalculator"""
    global _transit_calculator
    if _transit_calculator is None:
        _transit_calculator = TransitCalculator()
    return _transit_calculator


# ============================================================
# UNIT-ТЕСТЫ (для проверки)
# ============================================================

async def test_transit_calculator(user_id: int, target_date: date):
    """Тестовая функция для проверки работы калькулятора"""
    from ..database.core import async_session

    async with async_session() as session:
        calculator = await get_transit_calculator()
        modulator = AxisModulator()

        # Рассчитываем транзиты
        transits = await calculator.calculate_transit_aspects(
            user_id=user_id,
            target_date=target_date,
            session=session
        )

        print(f"\n=== ТРАНЗИТЫ ДЛЯ {target_date} ===")
        print(f"Аспектов к планетам: {len(transits.aspects_to_natal)}")
        print(f"Аспектов к углам: {len(transits.aspects_to_angles)}")
        print(f"Void of course Moon: {transits.void_of_course_moon}")

        print("\n=== ВАЖНЕЙШИЕ АСПЕКТЫ ===")
        for aspect in transits.aspects_to_natal[:10]:
            print(f"  {aspect.transit_planet} {aspect.aspect_type} {aspect.natal_planet} "
                  f"(орб: {aspect.orb:.2f}°, сила: {aspect.strength:.3f})")

        # Рассчитываем модуляторы
        deltas = modulator.calculate_axis_modulators(transits)

        print("\n=== МОДУЛЯТОРЫ ОСЕЙ ===")
        for axis, delta in deltas.items():
            if abs(delta) > 0.01:
                trend = "⬆️" if delta > 0 else "⬇️"
                print(f"  {axis}: {trend} {delta:+.3f}")

        return transits, deltas


if __name__ == "__main__":
    import asyncio


    async def main():
        # Тест для пользователя 1 на текущую дату
        await test_transit_calculator(1, date.today())


    asyncio.run(main())
