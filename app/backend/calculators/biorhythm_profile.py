from datetime import date, timedelta
from typing import Dict, List, Optional
import statistics
import math

from .biorhythm_base import BiorhythmCore
from .biorhythm_utils import BiorhythmValidator


class BiorhythmProfileCalculator:
    """
    Расчет статических характеристик биоритмов для профиля пользователя
    Данные в формате, аналогичном натальной карте
    """
    
    def __init__(self, use_extended_cycles: bool = False):
        self.core = BiorhythmCore(use_extended_cycles=use_extended_cycles)
        self.validator = BiorhythmValidator()
    
    def calculate_profile(self, 
                         birth_date: date,
                         analysis_years: int = 5) -> Dict:
        """
        Расчет всех статических характеристик для профиля
        
        Args:
            birth_date: Дата рождения
            analysis_years: Количество лет для анализа
        
        Returns:
            Словарь со статическими характеристиками (машиночитаемый)
        """
        if not self.validator.validate_birth_date(birth_date):
            raise ValueError("Некорректная дата рождения")
        
        today = date.today()
        analysis_days = analysis_years * 365
        
        # Собираем исторические данные
        history = self._collect_historical_data(birth_date, today, analysis_days)
        
        return {
            # Базовые периоды (как base_periods в примере)
            "base_periods": {
                name: length
                for name, length in self.core.cycles.items()
            },
            
            # Фазы при рождении (как planets в примере, но только наши данные)
            "birth_phase": self._calculate_birth_phase(birth_date),
            
            # Статистические характеристики циклов
            "cycle_statistics": self._calculate_cycle_statistics(history),
            
            # Корреляции между циклами
            "cycle_correlations": self._calculate_correlations(history),
            
            # ML индикаторы (как ml_features в примере)
            "ml_indicators": self._calculate_ml_indicators(history),

            #"lunar_biorhythms": self.calculate_lunar_biorhythms(moon_data),
            
            # Метаданные (как calculation_metadata в примере)
            "calculation_metadata": {
                "days_analyzed": len(history),
                "years_analyzed": round(len(history) / 365, 1),
                "cycles_count": len(self.core.cycles),
                "use_extended_cycles": self.core.use_extended_cycles
            }
        }
    
    def _collect_historical_data(self, 
                                 birth_date: date, 
                                 end_date: date, 
                                 days_back: int) -> List[Dict]:
        """Сбор исторических данных"""
        history = []
        start_date = max(birth_date, end_date - timedelta(days=days_back))
        
        current = start_date
        while current <= end_date:
            days_lived = self.core.calculate_days_lived(birth_date, current)
            cycles = self.core.calculate_all_cycles(days_lived)
            
            values = {name: data['value'] for name, data in cycles.items()}
            
            history.append({
                'date': current.isoformat(),
                'days_lived': days_lived,
                'cycles': cycles,
                'values': values,
                'overall_energy': self.core.calculate_overall_energy(values)
            })
            
            current += timedelta(days=1)
        
        return history
    
    def _calculate_birth_phase(self, birth_date: date) -> Dict:
        """Фазы при рождении (как planets в натальной карте)"""
        cycles = self.core.calculate_all_cycles(0)
        
        return {
            name: {
                'value': data['value'],
                'percentage': data['percentage'],
                'day_in_cycle': data['day_in_cycle']
            }
            for name, data in cycles.items()
        }
    
    def _calculate_cycle_statistics(self, history: List[Dict]) -> Dict:
        """Статистические характеристики циклов"""
        stats = {}
        
        for cycle in self.core.cycles.keys():
            values = [h['cycles'][cycle]['value'] for h in history]
            
            if not values:
                continue
            
            stats[cycle] = {
                'mean': round(statistics.mean(values), 6),
                'median': round(statistics.median(values), 6),
                'std_dev': round(statistics.stdev(values) if len(values) > 1 else 0, 6),
                'min': round(min(values), 6),
                'max': round(max(values), 6),
                'range': round(max(values) - min(values), 6),
                'peak_frequency': self._calculate_peak_frequency(history, cycle),
                'critical_frequency': self._calculate_critical_frequency(history, cycle)
            }
        
        return stats
    
    def _calculate_peak_frequency(self, history: List[Dict], cycle: str) -> float:
        """Частота пиков в год"""
        peaks = sum(1 for h in history if h['cycles'][cycle]['value'] > 0.8)
        years = len(history) / 365
        return round(peaks / years, 2) if years > 0 else 0
    
    def _calculate_critical_frequency(self, history: List[Dict], cycle: str) -> float:
        """Частота критических дней в год"""
        critical = sum(1 for h in history if abs(h['cycles'][cycle]['value']) > 0.9)
        years = len(history) / 365
        return round(critical / years, 2) if years > 0 else 0
    
    def _calculate_correlations(self, history: List[Dict]) -> Dict[str, float]:
        """Корреляции между циклами"""
        if len(history) < 30:
            return {}
        
        correlations = {}
        cycle_names = list(self.core.cycles.keys())
        
        for i, cycle1 in enumerate(cycle_names):
            for cycle2 in cycle_names[i+1:]:
                values1 = [h['cycles'][cycle1]['value'] for h in history]
                values2 = [h['cycles'][cycle2]['value'] for h in history]
                
                n = len(values1)
                sum1 = sum(values1)
                sum2 = sum(values2)
                sum1_sq = sum(v*v for v in values1)
                sum2_sq = sum(v*v for v in values2)
                sum12 = sum(v1*v2 for v1, v2 in zip(values1, values2))
                
                numerator = n * sum12 - sum1 * sum2
                denominator = math.sqrt((n * sum1_sq - sum1*sum1) * (n * sum2_sq - sum2*sum2))
                
                if denominator != 0:
                    corr = numerator / denominator
                    correlations[f"{cycle1}_{cycle2}"] = round(corr, 4)
                else:
                    correlations[f"{cycle1}_{cycle2}"] = 0
        
        return correlations
    
    def _calculate_ml_indicators(self, history: List[Dict]) -> Dict:
        """ML индикаторы (как ml_features в примере)"""
        if len(history) < 30:
            return {}
        
        indicators = {}
        
        # Энтропия циклов
        for cycle in self.core.cycles.keys():
            values = [h['cycles'][cycle]['value'] for h in history]
            
            # Упрощенная энтропия
            bins = [-1 + i*0.1 for i in range(21)]
            hist_counts = [0] * 20
            
            for v in values:
                for i in range(20):
                    if bins[i] <= v < bins[i+1]:
                        hist_counts[i] += 1
                        break
            
            probs = [c/len(values) for c in hist_counts if c > 0]
            if probs:
                entropy = -sum(p * math.log2(p) for p in probs)
                indicators[f"{cycle}_entropy"] = round(entropy / 5, 4)
        
        # Автокорреляции
        if len(history) > 100:
            for cycle, period in self.core.cycles.items():
                if period < 100:  # Только для коротких циклов
                    values = [h['cycles'][cycle]['value'] for h in history]
                    autocorr = self._autocorrelation(values, lag=period)
                    indicators[f"{cycle}_autocorr"] = round(autocorr, 4)
        
        # Системные метрики
        indicators['system_stability'] = self._calculate_system_stability(history)
        indicators['predictability'] = self._calculate_predictability(history)
        
        return indicators
    
    def _autocorrelation(self, values: List[float], lag: int) -> float:
        """Автокорреляция"""
        n = len(values)
        if n <= lag:
            return 0
        
        mean = statistics.mean(values)
        
        numerator = 0
        denominator = 0
        
        for i in range(n - lag):
            numerator += (values[i] - mean) * (values[i + lag] - mean)
        
        for i in range(n):
            denominator += (values[i] - mean) ** 2
        
        if denominator == 0:
            return 0
        
        return numerator / denominator
    
    def _calculate_system_stability(self, history: List[Dict]) -> float:
        """Стабильность системы"""
        if len(history) < 30:
            return 0.5
        
        energy_values = [h['overall_energy']['value'] for h in history]
        energy_std = statistics.stdev(energy_values)
        
        return round(max(0, min(1, 1 - energy_std)), 4)
    
    def _calculate_predictability(self, history: List[Dict]) -> float:
        """Предсказуемость (насколько циклы следуют паттерну)"""
        if len(history) < 100:
            return 0.5
        
        predictability = 0
        cycles_count = 0
        
        for cycle, period in self.core.cycles.items():
            if period > 100:  # Пропускаем длинные циклы
                continue
                
            values = [h['cycles'][cycle]['value'] for h in history]
            
            # Проверяем корреляцию с задержкой в половину периода
            lag = period // 2
            if len(values) > lag * 2:
                corr = self._autocorrelation(values, lag)
                # Ожидаем отрицательную корреляцию для синусоиды
                predictability += max(0, -corr)
                cycles_count += 1
        
        if cycles_count > 0:
            return round(predictability / cycles_count, 4)
        
        return 0.5