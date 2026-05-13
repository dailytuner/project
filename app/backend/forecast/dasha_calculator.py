"""
dasha_calculator.py - Расчёт ведической системы Даша (Вимшоттари)
Версия 1.0 - Production Ready

Рассчитывает текущий период даша (махадаша, антардаша, пратьярадаша)
на основе натальной карты и целевой даты.

Система Вимшоттари Даша:
- Основана на положении Луны в накшатре при рождении
- Полный цикл 120 лет (9 периодов планет)
- Каждый период имеет иерархическую структуру: махадаша → антардаша → пратьярадаша

Планеты и их годы в Вимшоттари:
- Кету (Южный узел): 7 лет
- Венера: 20 лет
- Солнце: 6 лет
- Луна: 10 лет
- Марс: 7 лет
- Раху (Северный узел): 18 лет
- Юпитер: 16 лет
- Сатурн: 19 лет
- Меркурий: 17 лет
"""

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

# ============================================================
# КОНСТАНТЫ
# ============================================================

# Планеты и их годы в Вимшоттари Даша
DASHA_YEARS = {
    'Ketu': 7,
    'Venus': 20,
    'Sun': 6,
    'Moon': 10,
    'Mars': 7,
    'Rahu': 18,
    'Jupiter': 16,
    'Saturn': 19,
    'Mercury': 17,
}

# Порядок планет в Вимшоттари Даша (полный цикл 120 лет)
DASHA_ORDER = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']

# 27 накшатр (звёздных стоянок Луны) для определения начальной даши
NAKSHATRAS_WITH_LORDS = [
    # Накшатра, управитель (по порядку от Ашвини)
    ('Ashwini', 'Ketu'),
    ('Bharani', 'Venus'),
    ('Krittika', 'Sun'),
    ('Rohini', 'Moon'),
    ('Mrigashira', 'Mars'),
    ('Ardra', 'Rahu'),
    ('Punarvasu', 'Jupiter'),
    ('Pushya', 'Saturn'),
    ('Ashlesha', 'Mercury'),
    ('Magha', 'Ketu'),
    ('Purva Phalguni', 'Venus'),
    ('Uttara Phalguni', 'Sun'),
    ('Hasta', 'Moon'),
    ('Chitra', 'Mars'),
    ('Swati', 'Rahu'),
    ('Vishakha', 'Jupiter'),
    ('Anuradha', 'Saturn'),
    ('Jyeshtha', 'Mercury'),
    ('Mula', 'Ketu'),
    ('Purva Ashadha', 'Venus'),
    ('Uttara Ashadha', 'Sun'),
    ('Shravana', 'Moon'),
    ('Dhanishtha', 'Mars'),
    ('Shatabhisha', 'Rahu'),
    ('Purva Bhadrapada', 'Jupiter'),
    ('Uttara Bhadrapada', 'Saturn'),
    ('Revati', 'Mercury'),
]

# Словарь для быстрого поиска управителя накшатры
NAKSHATRA_LORD = {name: lord for name, lord in NAKSHATRAS_WITH_LORDS}

# Коэффициенты влияния даша-периодов на оси Magic Profile
DASHA_AXIS_INFLUENCE = {
    'Sun': {
        'energy_will': 0.08,
        'destiny_mission': 0.10,
        'luck_talent': 0.06,
    },
    'Moon': {
        'emotions_intuition': 0.10,
        'social_relations': 0.06,
        'health_physical': 0.04,
    },
    'Mars': {
        'energy_will': 0.10,
        'work_discipline': 0.06,
        'social_relations': -0.04,
    },
    'Mercury': {
        'intellect_logic': 0.10,
        'social_relations': 0.06,
        'work_discipline': 0.04,
    },
    'Jupiter': {
        'luck_talent': 0.12,
        'destiny_mission': 0.08,
        'social_relations': 0.06,
    },
    'Venus': {
        'social_relations': 0.10,
        'luck_talent': 0.08,
        'emotions_intuition': 0.06,
    },
    'Saturn': {
        'work_discipline': 0.10,
        'karma_cycles': 0.10,
        'health_physical': -0.06,
    },
    'Rahu': {
        'karma_cycles': 0.08,
        'energy_will': 0.06,
        'intellect_logic': -0.06,
    },
    'Ketu': {
        'karma_cycles': 0.08,
        'emotions_intuition': 0.06,
        'social_relations': -0.06,
    },
}

# Множитель для антардаши (подпериода)
ANTARDASHA_MULTIPLIER = 0.6

# Множитель для пратьярадаши (субподпериода)
PRATYARADASHA_MULTIPLIER = 0.3


# ============================================================
# ДАТАКЛАССЫ
# ============================================================

@dataclass
class DashaPeriod:
    """Период даша (махадаша, антардаша или пратьярадаша)"""
    planet: str
    years: float
    start_date: datetime
    end_date: datetime
    progress: float  # 0-1, сколько периода прошло
    level: str  # 'mahadasha', 'antardasha', 'pratyaradasha'
    sub_periods: List['DashaPeriod'] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'planet': self.planet,
            'years': round(self.years, 4),
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'progress': round(self.progress, 4),
            'level': self.level,
            'sub_periods': [p.to_dict() for p in self.sub_periods] if self.sub_periods else []
        }

    def get_axis_modulation(self, include_sub_periods: bool = True) -> Dict[str, float]:
        """
        Получить коэффициенты модуляции для осей Magic Profile

        Args:
            include_sub_periods: Учитывать влияние антардаши и пратьярадаши

        Returns:
            Словарь {axis_name: modulation} где modulation от -0.2 до +0.2
        """
        modulations = {}

        # Влияние махадаши
        if self.planet in DASHA_AXIS_INFLUENCE:
            for axis, delta in DASHA_AXIS_INFLUENCE[self.planet].items():
                modulations[axis] = delta * (1 - abs(self.progress - 0.5) * 0.5)

        # Влияние антардаши (подпериода)
        if include_sub_periods and self.sub_periods:
            for sub in self.sub_periods:
                if sub.level == 'antardasha' and sub.planet in DASHA_AXIS_INFLUENCE:
                    for axis, delta in DASHA_AXIS_INFLUENCE[sub.planet].items():
                        current = modulations.get(axis, 0)
                        modulations[axis] = current + delta * ANTARDASHA_MULTIPLIER * sub.progress

        # Ограничиваем диапазон
        for axis in modulations:
            modulations[axis] = max(-0.2, min(0.2, modulations[axis]))

        return {k: round(v, 4) for k, v in modulations.items()}


@dataclass
class DashaSet:
    """Полный набор даша-периодов на дату"""
    target_date: date
    birth_date: date
    birth_nakshatra: str
    birth_nakshatra_lord: str
    birth_nakshatra_pada: int  # 1-4
    mahadasha: DashaPeriod
    antardasha: Optional[DashaPeriod]
    pratyaradasha: Optional[DashaPeriod]

    def to_dict(self) -> Dict:
        result = {
            'target_date': self.target_date.isoformat(),
            'birth_date': self.birth_date.isoformat(),
            'birth_nakshatra': self.birth_nakshatra,
            'birth_nakshatra_lord': self.birth_nakshatra_lord,
            'birth_nakshatra_pada': self.birth_nakshatra_pada,
            'mahadasha': self.mahadasha.to_dict(),
        }
        if self.antardasha:
            result['antardasha'] = self.antardasha.to_dict()
        if self.pratyaradasha:
            result['pratyaradasha'] = self.pratyaradasha.to_dict()
        return result

    def get_axis_modulations(self) -> Dict[str, float]:
        """Получить комбинированные модуляции для всех уровней даша"""
        modulations = {}

        # Махадаша
        mahadasha_mod = self.mahadasha.get_axis_modulation(include_sub_periods=False)
        for axis, delta in mahadasha_mod.items():
            modulations[axis] = delta

        # Антардаша
        if self.antardasha:
            antardasha_mod = self.antardasha.get_axis_modulation(include_sub_periods=False)
            for axis, delta in antardasha_mod.items():
                current = modulations.get(axis, 0)
                modulations[axis] = current + delta * ANTARDASHA_MULTIPLIER

        # Пратьярадаша
        if self.pratyaradasha:
            pratyaradasha_mod = self.pratyaradasha.get_axis_modulation(include_sub_periods=False)
            for axis, delta in pratyaradasha_mod.items():
                current = modulations.get(axis, 0)
                modulations[axis] = current + delta * PRATYARADASHA_MULTIPLIER

        return {k: round(v, 4) for k, v in modulations.items()}


# ============================================================
# ОСНОВНОЙ КЛАСС КАЛЬКУЛЯТОРА
# ============================================================

class DashaCalculator:
    """
    Калькулятор ведической системы Даша (Вимшоттари)
    """

    def __init__(self):
        self._cache: Dict[str, DashaSet] = {}
        self._dasha_years = DASHA_YEARS
        self._dasha_order = DASHA_ORDER

    def _get_cache_key(self, birth_date: date, nakshatra: str, target_date: date) -> str:
        """Создать ключ для кэша"""
        return f"{birth_date.isoformat()}_{nakshatra}_{target_date.isoformat()}"

    def _get_nakshatra_info(self, moon_longitude: float) -> Tuple[str, int, float]:
        """
        Определить накшатру по долготе Луны

        Args:
            moon_longitude: Долгота Луны в градусах (0-360)

        Returns:
            Tuple (название_накшатры, пада_номер, остаток_в_градусах)
        """
        # Каждая накшатра занимает 13.33333 градуса (360/27)
        nakshatra_degrees = 360.0 / 27.0
        nakshatra_index = int(moon_longitude / nakshatra_degrees) % 27

        # Градусы внутри накшатры
        inside_degrees = moon_longitude % nakshatra_degrees

        # Пада (1-4): каждая пада это 1/4 накшатры = 3.33333 градуса
        pada = int(inside_degrees / (nakshatra_degrees / 4)) + 1

        nakshatra_name = NAKSHATRAS_WITH_LORDS[nakshatra_index][0]

        return nakshatra_name, pada, inside_degrees

    def _get_starting_dasha_planet(self, nakshatra_name: str) -> str:
        """Получить управителя накшатры — начальную планету даша"""
        return NAKSHATRA_LORD.get(nakshatra_name, 'Ketu')

    def _calculate_period_end_date(
            self,
            start_date: datetime,
            years: float
    ) -> datetime:
        """Рассчитать дату окончания периода"""
        # Преобразуем годы в дни (с учётом високосных лет)
        days = int(years * 365.2425)
        return start_date + timedelta(days=days)

    def _calculate_period_progress(
            self,
            start_date: datetime,
            end_date: datetime,
            target_date: datetime
    ) -> float:
        """Рассчитать прогресс периода (0-1)"""
        total_days = (end_date - start_date).days
        if total_days <= 0:
            return 0.5

        elapsed_days = (target_date - start_date).days
        progress = elapsed_days / total_days

        return max(0.0, min(1.0, progress))

    def _calculate_mahadasha(
            self,
            start_planet: str,
            birth_datetime: datetime,
            target_datetime: datetime
    ) -> DashaPeriod:
        """
        Рассчитать текущий махадаша-период

        Args:
            start_planet: Планета, с которой начинается даша (по накшатре)
            birth_datetime: Дата и время рождения
            target_datetime: Целевая дата и время
        """
        # Определяем, сколько лет прошло с рождения до целевой даты
        years_passed = (target_datetime - birth_datetime).days / 365.2425

        cumulative_years = 0.0
        current_period_start = birth_datetime

        # Находим индекс начальной планеты в порядке даша
        try:
            start_index = self._dasha_order.index(start_planet)
        except ValueError:
            start_index = 0

        # Проходим по циклам даша, пока не найдём текущий период
        for cycle in range(3):  # Максимум 3 цикла (360 лет)
            for i in range(len(self._dasha_order)):
                planet_index = (start_index + i) % len(self._dasha_order)
                planet = self._dasha_order[planet_index]
                period_years = self._dasha_years[planet]

                period_end = self._calculate_period_end_date(
                    current_period_start, period_years
                )

                if years_passed < cumulative_years + period_years:
                    # Текущий период найден
                    progress = self._calculate_period_progress(
                        current_period_start, period_end, target_datetime
                    )

                    return DashaPeriod(
                        planet=planet,
                        years=period_years,
                        start_date=current_period_start,
                        end_date=period_end,
                        progress=progress,
                        level='mahadasha',
                        sub_periods=[]
                    )

                cumulative_years += period_years
                current_period_start = period_end

        # Fallback (не должно произойти)
        return DashaPeriod(
            planet='Sun',
            years=6,
            start_date=birth_datetime,
            end_date=birth_datetime + timedelta(days=int(6 * 365.2425)),
            progress=0.5,
            level='mahadasha',
            sub_periods=[]
        )

    def _calculate_antardasha(
            self,
            mahadasha: DashaPeriod,
            target_datetime: datetime
    ) -> Optional[DashaPeriod]:
        """
        Рассчитать антардашу (подпериод) внутри махадаши

        Антардаша рассчитывается по тому же порядку планет,
        начиная с планеты махадаши.
        """
        planet = mahadasha.planet

        # Находим индекс планеты махадаши в порядке даша
        try:
            start_index = self._dasha_order.index(planet)
        except ValueError:
            return None

        # Общая длительность махадаши в днях
        total_days = (mahadasha.end_date - mahadasha.start_date).days
        if total_days <= 0:
            return None

        # Время, прошедшее с начала махадаши
        elapsed_days = (target_datetime - mahadasha.start_date).days
        elapsed_progress = elapsed_days / total_days

        # Проходим по периодам антардаши
        cumulative_progress = 0.0

        for i in range(len(self._dasha_order)):
            sub_planet_index = (start_index + i) % len(self._dasha_order)
            sub_planet = self._dasha_order[sub_planet_index]

            # Длительность антардаши = (годы подпериода / годы махадаши) * годы махадаши
            # По формуле: (годы планеты / 120) * годы махадаши
            sub_period_years = (self._dasha_years[sub_planet] / 120) * mahadasha.years

            sub_progress = sub_period_years / mahadasha.years

            if elapsed_progress < cumulative_progress + sub_progress:
                # Текущая антардаша найдена
                sub_start_offset_days = int(cumulative_progress * total_days)
                sub_start = mahadasha.start_date + timedelta(days=sub_start_offset_days)
                sub_end = sub_start + timedelta(days=int(sub_period_years * 365.2425))

                sub_elapsed = (target_datetime - sub_start).days
                sub_total = (sub_end - sub_start).days
                sub_progress_value = sub_elapsed / sub_total if sub_total > 0 else 0.5

                return DashaPeriod(
                    planet=sub_planet,
                    years=sub_period_years,
                    start_date=sub_start,
                    end_date=sub_end,
                    progress=max(0.0, min(1.0, sub_progress_value)),
                    level='antardasha',
                    sub_periods=[]
                )

            cumulative_progress += sub_progress

        return None

    def _calculate_pratyaradasha(
            self,
            antardasha: DashaPeriod,
            target_datetime: datetime
    ) -> Optional[DashaPeriod]:
        """
        Рассчитать пратьярадашу (субподпериод) внутри антардаши
        """
        if not antardasha:
            return None

        planet = antardasha.planet

        try:
            start_index = self._dasha_order.index(planet)
        except ValueError:
            return None

        total_days = (antardasha.end_date - antardasha.start_date).days
        if total_days <= 0:
            return None

        elapsed_days = (target_datetime - antardasha.start_date).days
        elapsed_progress = elapsed_days / total_days

        cumulative_progress = 0.0

        for i in range(len(self._dasha_order)):
            sub_planet_index = (start_index + i) % len(self._dasha_order)
            sub_planet = self._dasha_order[sub_planet_index]

            # Длительность пратьярадаши по аналогичной формуле
            sub_period_years = (self._dasha_years[sub_planet] / 120) * antardasha.years

            sub_progress = sub_period_years / antardasha.years if antardasha.years > 0 else 0

            if elapsed_progress < cumulative_progress + sub_progress:
                sub_start_offset_days = int(cumulative_progress * total_days)
                sub_start = antardasha.start_date + timedelta(days=sub_start_offset_days)
                sub_end = sub_start + timedelta(days=int(sub_period_years * 365.2425))

                sub_elapsed = (target_datetime - sub_start).days
                sub_total = (sub_end - sub_start).days
                sub_progress_value = sub_elapsed / sub_total if sub_total > 0 else 0.5

                return DashaPeriod(
                    planet=sub_planet,
                    years=sub_period_years,
                    start_date=sub_start,
                    end_date=sub_end,
                    progress=max(0.0, min(1.0, sub_progress_value)),
                    level='pratyaradasha',
                    sub_periods=[]
                )

            cumulative_progress += sub_progress

        return None

    async def calculate_from_natal_chart(
            self,
            user_id: int,
            target_date: date,
            session: AsyncSession
    ) -> Optional[DashaSet]:
        """
        Рассчитать даша-периоды из натальной карты пользователя

        Args:
            user_id: ID пользователя
            target_date: Целевая дата
            session: Асинхронная сессия БД

        Returns:
            DashaSet или None, если данные не найдены
        """
        from ..database.models import NatalChart

        # Получаем натальную карту
        result = await session.execute(
            select(NatalChart)
            .where(NatalChart.user_id == user_id)
            .order_by(NatalChart.calculation_date.desc())
            .limit(1)
        )
        natal_chart = result.scalar_one_or_none()

        if not natal_chart:
            logger.warning(f"Натальная карта для user={user_id} не найдена")
            return None

        # Извлекаем информацию о Луне и накшатре из панчанги
        panchanga = natal_chart.panchanga
        nakshatra = panchanga.get('nakshatra_name', '')
        nakshatra_pada = panchanga.get('nakshatra_pada', 1)

        if not nakshatra:
            logger.warning(f"Накшатра для user={user_id} не найдена")
            return None

        # Дата и время рождения
        birth_datetime = natal_chart.birth_datetime_utc
        if not birth_datetime:
            birth_datetime = natal_chart.birth_datetime_local
        if not birth_datetime:
            logger.warning(f"Дата рождения для user={user_id} не найдена")
            return None

        # Преобразуем target_date в datetime
        target_datetime = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)

        # Рассчитываем даша
        return self.calculate(
            birth_datetime=birth_datetime,
            target_datetime=target_datetime,
            nakshatra=nakshatra,
            nakshatra_pada=nakshatra_pada
        )

    def calculate(
            self,
            birth_datetime: datetime,
            target_datetime: datetime,
            nakshatra: str,
            nakshatra_pada: int = 1
    ) -> DashaSet:
        """
        Рассчитать даша-периоды на целевую дату

        Args:
            birth_datetime: Дата и время рождения
            target_datetime: Целевая дата и время
            nakshatra: Название накшатры рождения
            nakshatra_pada: Пада накшатры (1-4)

        Returns:
            DashaSet с рассчитанными периодами
        """
        # Проверка кэша
        cache_key = self._get_cache_key(
            birth_datetime.date(), nakshatra, target_datetime.date()
        )
        if cache_key in self._cache:
            logger.debug(f"✅ Даша из кэша: {cache_key}")
            return self._cache[cache_key]

        # Определяем начальную планету даша
        start_planet = self._get_starting_dasha_planet(nakshatra)

        # Рассчитываем махадашу
        mahadasha = self._calculate_mahadasha(
            start_planet, birth_datetime, target_datetime
        )

        # Рассчитываем антардашу
        antardasha = self._calculate_antardasha(mahadasha, target_datetime)

        # Рассчитываем пратьярадашу
        pratyaradasha = None
        if antardasha:
            pratyaradasha = self._calculate_pratyaradasha(antardasha, target_datetime)

        # Связываем периоды
        if antardasha:
            mahadasha.sub_periods = [antardasha]
        if pratyaradasha and antardasha:
            antardasha.sub_periods = [pratyaradasha]

        # Определяем управителя накшатры
        nakshatra_lord = NAKSHATRA_LORD.get(nakshatra, 'Ketu')

        result = DashaSet(
            target_date=target_datetime.date(),
            birth_date=birth_datetime.date(),
            birth_nakshatra=nakshatra,
            birth_nakshatra_lord=nakshatra_lord,
            birth_nakshatra_pada=nakshatra_pada,
            mahadasha=mahadasha,
            antardasha=antardasha,
            pratyaradasha=pratyaradasha
        )

        # Сохраняем в кэш
        self._cache[cache_key] = result
        if len(self._cache) > 365:
            oldest = min(self._cache.keys())
            del self._cache[oldest]

        logger.info(
            f"✅ Рассчитана даша: махадаша={mahadasha.planet}, "
            f"антардаша={antardasha.planet if antardasha else 'none'}, "
            f"на {target_datetime.date()}"
        )

        return result

    def calculate_for_user(
            self,
            birth_datetime: datetime,
            nakshatra: str,
            target_date: date
    ) -> Dict[str, Any]:
        """
        Упрощённый метод для получения даша-информации

        Returns:
            Словарь с информацией о даша-периодах
        """
        target_datetime = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)

        dasha_set = self.calculate(birth_datetime, target_datetime, nakshatra)

        return {
            'mahadasha': dasha_set.mahadasha.planet,
            'mahadasha_progress': dasha_set.mahadasha.progress,
            'antardasha': dasha_set.antardasha.planet if dasha_set.antardasha else None,
            'antardasha_progress': dasha_set.antardasha.progress if dasha_set.antardasha else None,
            'pratyaradasha': dasha_set.pratyaradasha.planet if dasha_set.pratyaradasha else None,
            'pratyaradasha_progress': dasha_set.pratyaradasha.progress if dasha_set.pratyaradasha else None,
        }


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИНТЕГРАЦИИ
# ============================================================

def dasha_to_axis_modulation(dasha_info: Dict[str, Any]) -> Dict[str, float]:
    """
    Преобразовать даша-информацию в модуляторы для осей Magic Profile

    Args:
        dasha_info: Словарь из DashaCalculator.calculate_for_user()

    Returns:
        Словарь {axis_name: modulation} где modulation от -0.2 до +0.2
    """
    modulations = {}

    # Влияние махадаши
    mahadasha = dasha_info.get('mahadasha')
    mahadasha_progress = dasha_info.get('mahadasha_progress', 0.5)

    if mahadasha in DASHA_AXIS_INFLUENCE:
        for axis, delta in DASHA_AXIS_INFLUENCE[mahadasha].items():
            # Прогресс периода влияет на силу влияния
            progress_factor = 1 - abs(mahadasha_progress - 0.5) * 0.5
            modulations[axis] = delta * progress_factor

    # Влияние антардаши
    antardasha = dasha_info.get('antardasha')
    antardasha_progress = dasha_info.get('antardasha_progress', 0.5)

    if antardasha and antardasha in DASHA_AXIS_INFLUENCE:
        for axis, delta in DASHA_AXIS_INFLUENCE[antardasha].items():
            current = modulations.get(axis, 0)
            progress_factor = 1 - abs(antardasha_progress - 0.5) * 0.5
            modulations[axis] = current + delta * ANTARDASHA_MULTIPLIER * progress_factor

    # Ограничиваем диапазон
    for axis in modulations:
        modulations[axis] = max(-0.2, min(0.2, modulations[axis]))

    return {k: round(v, 4) for k, v in modulations.items()}


# ============================================================
# ФАБРИКА ДЛЯ СОЗДАНИЯ КАЛЬКУЛЯТОРА
# ============================================================

_dasha_calculator: Optional[DashaCalculator] = None


def get_dasha_calculator() -> DashaCalculator:
    """Получить глобальный экземпляр DashaCalculator"""
    global _dasha_calculator
    if _dasha_calculator is None:
        _dasha_calculator = DashaCalculator()
    return _dasha_calculator


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

def example_usage():
    """Пример использования калькулятора даша"""
    calculator = get_dasha_calculator()

    # Пример данных
    birth_datetime = datetime(1990, 6, 15, 10, 30, 0)
    target_datetime = datetime(2024, 4, 23, 12, 0, 0)
    nakshatra = 'Rohini'  # Пример накшатры

    print("\n=== ВИМШОТТАРИ ДАША ===\n")
    print(f"📅 Дата рождения: {birth_datetime.date()}")
    print(f"🎯 Целевая дата: {target_datetime.date()}")
    print(f"🌟 Накшатра рождения: {nakshatra}\n")

    # Расчёт даша
    dasha_set = calculator.calculate(birth_datetime, target_datetime, nakshatra)

    print("📊 МАХАДАША:")
    print(f"   Планета: {dasha_set.mahadasha.planet}")
    print(f"   Годы: {dasha_set.mahadasha.years}")
    print(f"   Начало: {dasha_set.mahadasha.start_date.date()}")
    print(f"   Конец: {dasha_set.mahadasha.end_date.date()}")
    print(f"   Прогресс: {dasha_set.mahadasha.progress:.1%}\n")

    if dasha_set.antardasha:
        print("📊 АНТАРДАША:")
        print(f"   Планета: {dasha_set.antardasha.planet}")
        print(f"   Прогресс: {dasha_set.antardasha.progress:.1%}\n")

    if dasha_set.pratyaradasha:
        print("📊 ПРАТЬЯРАДАША:")
        print(f"   Планета: {dasha_set.pratyaradasha.planet}")
        print(f"   Прогресс: {dasha_set.pratyaradasha.progress:.1%}\n")

    print("=== МОДУЛЯЦИИ ДЛЯ MAGIC PROFILE ===")
    modulations = dasha_set.get_axis_modulations()
    for axis, delta in modulations.items():
        if abs(delta) > 0.01:
            print(f"  {axis}: {delta:+.3f}")

    return dasha_set


if __name__ == "__main__":
    example_usage()
