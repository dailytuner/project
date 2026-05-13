"""
biorhythm_calculator.py - Расчёт биоритмов на дату
Версия 1.0 - Production Ready

Рассчитывает классические биоритмы:
- Физический цикл (23 дня) - влияет на энергию, выносливость, здоровье
- Эмоциональный цикл (28 дней) - влияет на настроение, чувствительность, отношения
- Интеллектуальный цикл (33 дня) - влияет на мышление, память, креативность

Также поддерживает расширенные циклы:
- Интуитивный цикл (38 дней)
- Духовный цикл (53 дня)

Выход: значения биоритмов на указанную дату (-1.0 до 1.0)
"""

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================
# КОНСТАНТЫ
# ============================================================

# Классические циклы (дни)
CLASSICAL_CYCLES = {
    'physical': 23,
    'emotional': 28,
    'intellectual': 33,
}

# Расширенные циклы (дни)
EXTENDED_CYCLES = {
    'intuitive': 38,
    'spiritual': 53,
    'creative': 45,
    'social': 43,
    'luck': 37,
}

# Все доступные циклы
ALL_CYCLES = {**CLASSICAL_CYCLES, **EXTENDED_CYCLES}

# Пороги для интерпретации значений
THRESHOLDS = {
    'high': 0.7,  # Высокое положительное значение
    'medium': 0.3,  # Среднее положительное
    'low': -0.3,  # Низкое отрицательное
    'critical': 0.9,  # Критически высокое (пик)
    'zero': 0.05,  # Близость к нулю (критический день)
}

# Коэффициенты влияния биоритмов на оси Magic Profile
AXIS_INFLUENCE = {
    'physical': {
        'energy_will': 0.8,
        'health_physical': 0.9,
        'work_discipline': 0.5,
    },
    'emotional': {
        'emotions_intuition': 0.9,
        'social_relations': 0.5,
        'energy_will': 0.3,
    },
    'intellectual': {
        'intellect_logic': 0.9,
        'luck_talent': 0.4,
        'work_discipline': 0.3,
    },
    'intuitive': {
        'emotions_intuition': 0.6,
        'luck_talent': 0.5,
        'destiny_mission': 0.4,
    },
    'spiritual': {
        'karma_cycles': 0.6,
        'destiny_mission': 0.5,
        'emotions_intuition': 0.3,
    },
}


# ============================================================
# ДАТАКЛАССЫ
# ============================================================

@dataclass
class BiorhythmValue:
    """Значение одного биоритма"""
    name: str
    cycle_days: int
    value: float
    phase_degrees: float
    phase_percent: float
    is_critical: bool
    is_peak: bool
    description: str

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'cycle_days': self.cycle_days,
            'value': round(self.value, 4),
            'phase_degrees': round(self.phase_degrees, 2),
            'phase_percent': round(self.phase_percent, 2),
            'is_critical': self.is_critical,
            'is_peak': self.is_peak,
            'description': self.description
        }

    def to_axis_modulation(self) -> float:
        """Преобразовать в коэффициент модуляции для осей (-1..1)"""
        # Для критических дней эффект сильнее
        if self.is_critical:
            return self.value * 1.5
        return self.value


@dataclass
class BiorhythmSet:
    """Набор биоритмов на дату"""
    date: date
    birth_date: date
    days_alive: int
    cycles: Dict[str, BiorhythmValue]
    combined_physical_emotional: float
    combined_all: float

    def to_dict(self) -> Dict:
        return {
            'date': self.date.isoformat(),
            'birth_date': self.birth_date.isoformat(),
            'days_alive': self.days_alive,
            'cycles': {k: v.to_dict() for k, v in self.cycles.items()},
            'combined_physical_emotional': round(self.combined_physical_emotional, 4),
            'combined_all': round(self.combined_all, 4)
        }

    def get_axis_modulations(self) -> Dict[str, float]:
        """
        Получить коэффициенты модуляции для осей Magic Profile
        Возвращает словарь {axis_name: modulation_value} где modulation_value от -0.3 до +0.3
        """
        modulations = {}

        for cycle_name, cycle in self.cycles.items():
            influence = AXIS_INFLUENCE.get(cycle_name, {})
            cycle_value = cycle.to_axis_modulation()

            for axis_name, coefficient in influence.items():
                delta = cycle_value * coefficient * 0.15  # Максимум ~0.15 на один цикл
                current = modulations.get(axis_name, 0.0)
                modulations[axis_name] = max(-0.25, min(0.25, current + delta))

        # Дополнительно: комбинированный эффект
        if abs(self.combined_physical_emotional) > 0.7:
            modulations['energy_will'] = max(-0.25, min(0.25,
                                                        modulations.get('energy_will',
                                                                        0) + self.combined_physical_emotional * 0.1))
            modulations['emotions_intuition'] = max(-0.25, min(0.25,
                                                               modulations.get('emotions_intuition',
                                                                               0) + self.combined_physical_emotional * 0.1))

        return {k: round(v, 4) for k, v in modulations.items()}


# ============================================================
# ОСНОВНОЙ КЛАСС КАЛЬКУЛЯТОРА
# ============================================================

class BiorhythmCalculator:
    """
    Калькулятор биоритмов для любой даты
    """

    def __init__(self, use_extended: bool = True):
        """
        Args:
            use_extended: Включить расширенные циклы (интуитивный, духовный и др.)
        """
        self.use_extended = use_extended
        self._cache: Dict[str, BiorhythmSet] = {}

    def _get_cache_key(self, birth_date: date, target_date: date) -> str:
        """Создать ключ для кэша"""
        return f"{birth_date.isoformat()}_{target_date.isoformat()}"

    def _days_between(self, birth_date: date, target_date: date) -> int:
        """Количество дней между датами"""
        return (target_date - birth_date).days

    def _calculate_single_cycle(
            self,
            cycle_name: str,
            cycle_length: int,
            days: int
    ) -> BiorhythmValue:
        """
        Рассчитать один биоритмический цикл

        Args:
            cycle_name: Название цикла
            cycle_length: Длина цикла в днях
            days: Количество дней с момента рождения

        Returns:
            BiorhythmValue с рассчитанными значениями
        """
        # Позиция в цикле (0..cycle_length-1)
        position = days % cycle_length

        # Угол в радианах (0..2π)
        angle_rad = 2 * math.pi * position / cycle_length

        # Значение по синусоиде (-1..1)
        value = math.sin(angle_rad)

        # Угол в градусах (0..360)
        angle_deg = angle_rad * 180 / math.pi

        # Фаза в процентах (0..100)
        phase_percent = (position / cycle_length) * 100

        # Проверка на критический день (близость к нулю)
        is_critical = abs(value) < THRESHOLDS['zero']

        # Проверка на пик (близость к максимуму или минимуму)
        is_peak = abs(value) > THRESHOLDS['critical']

        # Описание состояния
        description = self._get_cycle_description(cycle_name, value, is_critical, is_peak)

        return BiorhythmValue(
            name=cycle_name,
            cycle_days=cycle_length,
            value=round(value, 4),
            phase_degrees=angle_deg,
            phase_percent=phase_percent,
            is_critical=is_critical,
            is_peak=is_peak,
            description=description
        )

    def _get_cycle_description(
            self,
            cycle_name: str,
            value: float,
            is_critical: bool,
            is_peak: bool
    ) -> str:
        """Получить текстовое описание состояния цикла"""
        descriptions = {
            'physical': {
                'high': "Высокая физическая энергия, хорошая выносливость",
                'low': "Сниженная физическая активность, быстрая утомляемость",
                'critical': "Критический день физического цикла — будь осторожен",
                'peak': "Пик физической формы — занимайся спортом",
            },
            'emotional': {
                'high': "Эмоциональный подъём, хорошее настроение",
                'low': "Эмоциональный спад, повышенная чувствительность",
                'critical': "Критический день эмоционального цикла — избегай конфликтов",
                'peak': "Пик эмоциональной активности — твори и общайся",
            },
            'intellectual': {
                'high': "Высокая умственная активность, ясность мысли",
                'low': "Сниженная концентрация, рассеянность",
                'critical': "Критический день интеллектуального цикла — не берись за сложное",
                'peak': "Пик интеллекта — решай сложные задачи",
            },
            'intuitive': {
                'high': "Обострённая интуиция, хорошее предчувствие",
                'low': "Интуиция притуплена, лучше полагаться на логику",
                'critical': "Критический день интуиции — не доверяй первому чувству",
                'peak': "Пик интуиции — доверяй внутреннему голосу",
            },
            'spiritual': {
                'high': "Духовный подъём, поиск смыслов",
                'low': "Духовный спад, отсутствие вдохновения",
                'critical': "Критический день духовного цикла",
                'peak': "Пик духовной активности — медитируй",
            },
        }

        cycle_desc = descriptions.get(cycle_name, {})

        if is_critical:
            return cycle_desc.get('critical', f"Критический день цикла {cycle_name}")
        if is_peak:
            return cycle_desc.get('peak', f"Пик цикла {cycle_name}")
        if value > THRESHOLDS['high']:
            return cycle_desc.get('high', f"Высокое значение цикла {cycle_name}")
        if value < THRESHOLDS['low']:
            return cycle_desc.get('low', f"Низкое значение цикла {cycle_name}")

        return f"Нейтральное состояние цикла {cycle_name}"

    def calculate(
            self,
            birth_date: date,
            target_date: Optional[date] = None,
            use_cache: bool = True
    ) -> BiorhythmSet:
        """
        Рассчитать биоритмы на указанную дату

        Args:
            birth_date: Дата рождения
            target_date: Целевая дата (по умолчанию сегодня)
            use_cache: Использовать кэш

        Returns:
            BiorhythmSet с рассчитанными значениями
        """
        if target_date is None:
            target_date = date.today()

        # Проверка кэша
        if use_cache:
            cache_key = self._get_cache_key(birth_date, target_date)
            if cache_key in self._cache:
                logger.debug(f"✅ Биоритмы из кэша: {cache_key}")
                return self._cache[cache_key]

        # Расчёт
        days = self._days_between(birth_date, target_date)

        if days < 0:
            logger.warning(f"Дата рождения {birth_date} позже целевой даты {target_date}")
            days = abs(days)

        cycles = {}

        # Классические циклы
        for name, length in CLASSICAL_CYCLES.items():
            cycles[name] = self._calculate_single_cycle(name, length, days)

        # Расширенные циклы (опционально)
        if self.use_extended:
            for name, length in EXTENDED_CYCLES.items():
                cycles[name] = self._calculate_single_cycle(name, length, days)

        # Комбинированные показатели
        physical = cycles.get('physical', cycles.get('physical')).value if 'physical' in cycles else 0
        emotional = cycles.get('emotional', cycles.get('emotional')).value if 'emotional' in cycles else 0
        intellectual = cycles.get('intellectual', cycles.get('intellectual')).value if 'intellectual' in cycles else 0

        combined_physical_emotional = (physical + emotional) / 2
        combined_all = (physical + emotional + intellectual) / 3

        result = BiorhythmSet(
            date=target_date,
            birth_date=birth_date,
            days_alive=days,
            cycles=cycles,
            combined_physical_emotional=combined_physical_emotional,
            combined_all=combined_all
        )

        # Сохраняем в кэш (ограничиваем размер)
        if use_cache:
            self._cache[cache_key] = result
            if len(self._cache) > 365:
                oldest = min(self._cache.keys())
                del self._cache[oldest]

        logger.info(f"✅ Рассчитаны биоритмы для даты {target_date}, дней={days}")

        return result

    def calculate_for_user(
            self,
            birth_date: date,
            target_date: Optional[date] = None
    ) -> Dict[str, float]:
        """
        Упрощённый метод для получения значений биоритмов для модуляции осей

        Returns:
            Словарь {cycle_name: value} где value от -1 до 1
        """
        biorhythms = self.calculate(birth_date, target_date)

        result = {}
        for name, cycle in biorhythms.cycles.items():
            result[name] = cycle.value

        return result

    def get_critical_days(
            self,
            birth_date: date,
            start_date: Optional[date] = None,
            days_ahead: int = 30
    ) -> List[Tuple[date, List[str]]]:
        """
        Получить критические дни в указанном периоде

        Args:
            birth_date: Дата рождения
            start_date: Начальная дата (по умолчанию сегодня)
            days_ahead: Количество дней вперёд для анализа

        Returns:
            Список кортежей (дата, [список_циклов_на_критическом_дне])
        """
        if start_date is None:
            start_date = date.today()

        critical_days = []

        for i in range(days_ahead):
            target_date = start_date + timedelta(days=i)
            biorhythms = self.calculate(birth_date, target_date)

            critical_cycles = []
            for name, cycle in biorhythms.cycles.items():
                if cycle.is_critical:
                    critical_cycles.append(name)

            if critical_cycles:
                critical_days.append((target_date, critical_cycles))

        return critical_days

    def get_peaks(
            self,
            birth_date: date,
            start_date: Optional[date] = None,
            days_ahead: int = 30
    ) -> List[Tuple[date, List[Tuple[str, float]]]]:
        """
        Получить пиковые дни (максимумы/минимумы) в указанном периоде

        Returns:
            Список кортежей (дата, [(цикл, значение), ...])
        """
        if start_date is None:
            start_date = date.today()

        peaks = []

        for i in range(days_ahead):
            target_date = start_date + timedelta(days=i)
            biorhythms = self.calculate(birth_date, target_date)

            peak_cycles = []
            for name, cycle in biorhythms.cycles.items():
                if cycle.is_peak:
                    peak_cycles.append((name, cycle.value))

            if peak_cycles:
                peaks.append((target_date, peak_cycles))

        return peaks

    def get_optimal_days_for_activity(
            self,
            birth_date: date,
            activity_type: str,
            start_date: Optional[date] = None,
            days_ahead: int = 30
    ) -> List[date]:
        """
        Получить оптимальные дни для определённого типа активности

        Args:
            birth_date: Дата рождения
            activity_type: Тип активности ('physical', 'mental', 'creative')
            start_date: Начальная дата
            days_ahead: Количество дней

        Returns:
            Список дат с высокими значениями соответствующих циклов
        """
        if start_date is None:
            start_date = date.today()

        optimal_days = []

        # Какие циклы важны для каждого типа активности
        cycle_weights = {
            'physical': {'physical': 0.8, 'emotional': 0.2},
            'mental': {'intellectual': 0.7, 'intuitive': 0.3},
            'creative': {'emotional': 0.5, 'intuitive': 0.3, 'intellectual': 0.2},
            'social': {'emotional': 0.6, 'spiritual': 0.4},
            'rest': {'physical': -0.5, 'emotional': -0.5},  # Противопоказания
        }

        weights = cycle_weights.get(activity_type, {'physical': 0.5, 'emotional': 0.5})

        for i in range(days_ahead):
            target_date = start_date + timedelta(days=i)
            biorhythms = self.calculate(birth_date, target_date)

            score = 0.0
            for cycle_name, weight in weights.items():
                if cycle_name in biorhythms.cycles:
                    cycle_value = biorhythms.cycles[cycle_name].value
                    # Для отрицательных весов (отдых) используем обратную зависимость
                    if weight < 0:
                        score += abs(weight) * (1 - abs(cycle_value))
                    else:
                        score += weight * cycle_value

            if score > 0.5:
                optimal_days.append(target_date)

        return optimal_days


# ============================================================
# УТИЛИТЫ ДЛЯ ИНТЕГРАЦИИ С MAGIC PROFILE
# ============================================================

def biorhythms_to_axis_modulation(
        biorhythms: Dict[str, float],
        use_extended: bool = True
) -> Dict[str, float]:
    """
    Преобразовать биоритмы в модуляторы для осей Magic Profile

    Args:
        biorhythms: Словарь {cycle_name: value} от -1 до 1
        use_extended: Учитывать расширенные циклы

    Returns:
        Словарь {axis_name: modulation} где modulation от -0.3 до +0.3
    """
    modulations = {}

    for cycle_name, value in biorhythms.items():
        if not use_extended and cycle_name not in CLASSICAL_CYCLES:
            continue

        influence = AXIS_INFLUENCE.get(cycle_name, {})
        for axis_name, coefficient in influence.items():
            delta = value * coefficient * 0.15  # Максимум ~0.15 от одного цикла
            current = modulations.get(axis_name, 0.0)
            modulations[axis_name] = max(-0.25, min(0.25, current + delta))

    return {k: round(v, 4) for k, v in modulations.items()}


# ============================================================
# ФАБРИКА ДЛЯ СОЗДАНИЯ КАЛЬКУЛЯТОРА
# ============================================================

_biorhythm_calculator: Optional[BiorhythmCalculator] = None


def get_biorhythm_calculator(use_extended: bool = True) -> BiorhythmCalculator:
    """Получить глобальный экземпляр BiorhythmCalculator"""
    global _biorhythm_calculator
    if _biorhythm_calculator is None:
        _biorhythm_calculator = BiorhythmCalculator(use_extended=use_extended)
    return _biorhythm_calculator

async def calculate_for_user_async(self, birth_date: date, target_date: date) -> Dict[str, float]:
    """Асинхронный метод для получения биоритмов"""
    return self.calculate_for_user(birth_date, target_date)

# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

def example_usage():
    """Пример использования калькулятора биоритмов"""
    calculator = get_biorhythm_calculator(use_extended=True)

    # Дата рождения (пример)
    birth_date = date(1990, 6, 15)
    today = date.today()

    print("\n=== БИОРИТМЫ НА СЕГОДНЯ ===\n")

    # Расчёт биоритмов
    biorhythms = calculator.calculate(birth_date, today)

    print(f"📅 Дата: {biorhythms.date}")
    print(f"🎂 Дней с рождения: {biorhythms.days_alive}\n")

    for name, cycle in biorhythms.cycles.items():
        status = ""
        if cycle.is_critical:
            status = "⚠️ КРИТИЧЕСКИЙ ДЕНЬ!"
        elif cycle.is_peak:
            status = "⚡ ПИК!"
        elif cycle.value > 0.5:
            status = "📈 Высокий"
        elif cycle.value < -0.5:
            status = "📉 Низкий"

        print(f"  {name.upper()}: {cycle.value:+.2f} ({status})")
        print(f"      {cycle.description}")
        print(f"      Фаза: {cycle.phase_percent:.0f}%")
        print()

    print("\n=== МОДУЛЯЦИИ ДЛЯ MAGIC PROFILE ===")
    modulations = biorhythms.get_axis_modulations()
    for axis, delta in modulations.items():
        if abs(delta) > 0.02:
            print(f"  {axis}: {delta:+.3f}")

    print("\n=== КРИТИЧЕСКИЕ ДНИ В БЛИЖАЙШИЕ 14 ДНЕЙ ===")
    critical_days = calculator.get_critical_days(birth_date, today, 14)
    for day, cycles in critical_days:
        print(f"  {day}: критические циклы {', '.join(cycles)}")

    print("\n=== ОПТИМАЛЬНЫЕ ДНИ ДЛЯ ФИЗИЧЕСКОЙ АКТИВНОСТИ ===")
    optimal = calculator.get_optimal_days_for_activity(birth_date, 'physical', today, 14)
    for day in optimal:
        print(f"  {day}")

    return biorhythms


if __name__ == "__main__":
    example_usage()