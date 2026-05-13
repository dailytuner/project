from typing import Dict, List, Tuple
from datetime import date


class BiorhythmMapper:
    """
    Маппинг математических значений в ENUM для БД
    (используется только для создания enum полей)
    """
    
    @staticmethod
    def value_to_phase(value: float) -> str:
        """value -> phase_type ENUM"""
        if value >= 0.5:
            return 'positive'
        elif value <= -0.5:
            return 'negative'
        elif abs(value) > 0.9:
            return 'critical'
        else:
            return 'neutral'
    
    @staticmethod
    def derivative_to_trend(derivative: float) -> str:
        """derivative -> trend_type ENUM"""
        if derivative > 0.1:
            return 'rising'
        elif derivative < -0.1:
            return 'falling'
        else:
            return 'stable'
    
    @staticmethod
    def get_critical_cycles(values: Dict[str, float]) -> List[str]:
        """Список критических циклов (|value| > 0.9)"""
        return [cycle for cycle, value in values.items() if abs(value) > 0.9]
    
    @staticmethod
    def get_peak_cycles(values: Dict[str, float]) -> List[str]:
        """Список пиковых циклов (value > 0.8)"""
        return [cycle for cycle, value in values.items() if value > 0.8]


class BiorhythmValidator:
    """
    Валидация данных биоритмов
    """
    
    @staticmethod
    def validate_birth_date(birth_date: date) -> bool:
        """Проверка даты рождения"""
        return birth_date <= date.today()
    
    @staticmethod
    def validate_target_date(birth_date: date, target_date: date) -> bool:
        """Проверка целевой даты"""
        return target_date >= birth_date
