import math
from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class BiorhythmCore:
    """
    Ядро расчетов биоритмов - чистая математика
    """
    
    # Периоды биоритмов в днях
    PHYSICAL_CYCLE = 23
    EMOTIONAL_CYCLE = 28
    INTELLECTUAL_CYCLE = 33
    INTUITIVE_CYCLE = 38
    
    # Дополнительные циклы (высшего порядка)
    SPIRITUAL_CYCLE = 53      # Духовный цикл
    CREATIVE_CYCLE = 45       # Творческий цикл
    SOCIAL_CYCLE = 43         # Социальный цикл
    LUCK_CYCLE = 37           # Цикл удачи
    
    # Многолетние циклы
    SEVEN_YEAR_CYCLE = 2555   # 7-летний цикл
    NINE_YEAR_CYCLE = 3285    # 9-летний цикл
    ELEVEN_YEAR_CYCLE = 4015  # 11-летний цикл
    
    # Веса для общего уровня энергии
    ENERGY_WEIGHTS = {
        'physical': 0.3,
        'emotional': 0.25,
        'intellectual': 0.25,
        'intuitive': 0.2,
        'spiritual': 0.15,    # Добавили с меньшим весом
        'creative': 0.15,
        'social': 0.15,
        'luck': 0.1
    }
    
    # Пороговые значения
    CRITICAL_THRESHOLD = 0.9
    PEAK_THRESHOLD = 0.8
    TREND_THRESHOLD = 0.1
    
    def __init__(self, use_extended_cycles: bool = False):
        # Базовые циклы (всегда есть)
        self.cycles = {
            'physical': self.PHYSICAL_CYCLE,
            'emotional': self.EMOTIONAL_CYCLE,
            'intellectual': self.INTELLECTUAL_CYCLE,
            'intuitive': self.INTUITIVE_CYCLE
        }
        
        # Расширенные циклы (опционально)
        self.use_extended_cycles = use_extended_cycles
        if use_extended_cycles:
            self.extended_cycles = {
                'spiritual': self.SPIRITUAL_CYCLE,
                'creative': self.CREATIVE_CYCLE,
                'social': self.SOCIAL_CYCLE,
                'luck': self.LUCK_CYCLE,
                'seven_year': self.SEVEN_YEAR_CYCLE,
                'nine_year': self.NINE_YEAR_CYCLE,
                'eleven_year': self.ELEVEN_YEAR_CYCLE
            }
            self.cycles.update(self.extended_cycles)
    
    def calculate_days_lived(self, birth_date: date, target_date: date) -> int:
        """Количество прожитых дней"""
        return (target_date - birth_date).days
    
    def calculate_phase(self, days_lived: int, cycle_length: int) -> float:
        """
        Расчет фазы биоритма
        Возвращает значение от -1 до +1
        """
        phase = (2 * math.pi * days_lived) / cycle_length
        return math.sin(phase)
    
    def calculate_derivative(self, days_lived: int, cycle_length: int) -> float:
        """
        Производная (скорость изменения)
        Возвращает значение от -1 до +1
        """
        phase = (2 * math.pi * days_lived) / cycle_length
        return math.cos(phase)
    
    def calculate_all_cycles(self, days_lived: int) -> Dict[str, Dict]:
        """
        Расчет всех циклов сразу
        """
        results = {}
        
        for cycle_name, cycle_length in self.cycles.items():
            value = self.calculate_phase(days_lived, cycle_length)
            derivative = self.calculate_derivative(days_lived, cycle_length)
            
            results[cycle_name] = {
                'value': round(value, 6),
                'percentage': round(((value + 1) / 2) * 100, 4),
                'derivative': round(derivative, 6),
                'day_in_cycle': days_lived % cycle_length
            }
        
        return results
    
    def calculate_overall_energy(self, cycle_values: Dict[str, float]) -> Dict:
        """
        Расчет общего уровня энергии
        Используем только доступные циклы с соответствующими весами
        """
        total = 0
        total_weight = 0
        
        for cycle_name, value in cycle_values.items():
            if cycle_name in self.ENERGY_WEIGHTS:
                weight = self.ENERGY_WEIGHTS[cycle_name]
                total += value * weight
                total_weight += weight
        
        # Нормализуем если использованы не все веса
        if total_weight > 0:
            normalized_total = total / total_weight
        else:
            normalized_total = 0
        
        percentage = ((normalized_total + 1) / 2) * 100
        
        return {
            'value': round(normalized_total, 6),
            'percentage': round(percentage, 4)
        }
    
    def calculate_harmonic_interference(self, days_lived: int) -> Dict:
        """
        Расчет гармонической интерференции между циклами
        """
        phases = {}
        for cycle_name, cycle_length in self.cycles.items():
            phase = (2 * math.pi * days_lived) / cycle_length
            phases[cycle_name] = phase
        
        # Интерференция пар циклов
        interference = {}
        cycle_names = list(self.cycles.keys())
        
        for i, c1 in enumerate(cycle_names):
            for c2 in cycle_names[i+1:]:
                key = f"{c1}_{c2}"
                interference[key] = round(
                    math.sin(phases[c1]) * math.sin(phases[c2]), 6
                )
        
        # Суперпозиция всех циклов
        if cycle_names:
            superposition = sum(math.sin(phases[c]) for c in cycle_names) / len(cycle_names)
        else:
            superposition = 0
        
        return {
            'interference': interference,
            'superposition': round(superposition, 6)
        }
