from datetime import date, timedelta, datetime, timezone
from typing import Dict, List, Optional

from .biorhythm_base import BiorhythmCore
from .biorhythm_utils import BiorhythmMapper, BiorhythmValidator


class BiorhythmDailyCalculator:
    """
    Расчет динамических данных биоритмов для профиля дня
    Данные в формате, аналогичном натальной карте
    """
    
    def __init__(self, use_extended_cycles: bool = False):
        self.core = BiorhythmCore(use_extended_cycles=use_extended_cycles)
        self.mapper = BiorhythmMapper()
        self.validator = BiorhythmValidator()
    
    def calculate_daily(self, 
                       birth_date: date, 
                       target_date: date,
                       forecast_days: int = 7) -> Dict:
        """
        Расчет данных на конкретный день + прогноз
        """
        if not self.validator.validate_target_date(birth_date, target_date):
            raise ValueError("Целевая дата раньше даты рождения")
        
        days_lived = self.core.calculate_days_lived(birth_date, target_date)
        
        # Текущие значения всех циклов
        current_cycles = self.core.calculate_all_cycles(days_lived)
        current_values = {name: data['value'] for name, data in current_cycles.items()}
        
        return {
            # Метаданные (как в примере)
            'date': target_date.isoformat(),
            'days_lived': days_lived,
            #'calculation_timestamp': datetime.utcnow().isoformat(),
            'calculation_timestamp': datetime.now(timezone.utc).isoformat(),
            
            # Текущие значения циклов (как planets в натальной карте)
            'current_values': {
                name: {
                    'value': data['value'],
                    'percentage': data['percentage'],
                    'derivative': data['derivative'],
                    'day_in_cycle': data['day_in_cycle'],
                    'phase': self.mapper.value_to_phase(data['value']),
                    'trend': self.mapper.derivative_to_trend(data['derivative'])
                }
                for name, data in current_cycles.items()
            },
            
            # Общая энергия
            'overall_energy': self.core.calculate_overall_energy(current_values),
            
            # Гармоническая интерференция
            'harmonic_interference': self.core.calculate_harmonic_interference(days_lived),
            
            # Критические точки
            'critical_points': {
                'critical_cycles': self.mapper.get_critical_cycles(current_values),
                'peak_cycles': self.mapper.get_peak_cycles(current_values)
            },
            
            # Прогноз на N дней (как forecast в примере)
            'forecast': self._calculate_forecast(birth_date, target_date, forecast_days),
            
            # ML фичи для этого дня
            'daily_ml_features': self._calculate_daily_ml_features(current_cycles)
        }
    
    def _calculate_forecast(self, 
                           birth_date: date, 
                           start_date: date, 
                           days: int) -> List[Dict]:
        """Прогноз на N дней вперед"""
        forecast = []
        
        for i in range(1, days + 1):
            current_date = start_date + timedelta(days=i)
            days_lived = self.core.calculate_days_lived(birth_date, current_date)
            cycles = self.core.calculate_all_cycles(days_lived)
            values = {name: data['value'] for name, data in cycles.items()}
            overall = self.core.calculate_overall_energy(values)
            
            forecast.append({
                'date': current_date.isoformat(),
                'overall_energy_percentage': overall['percentage'],
                'physical_percentage': cycles['physical']['percentage'],
                'emotional_percentage': cycles['emotional']['percentage'],
                'intellectual_percentage': cycles['intellectual']['percentage'],
                'intuitive_percentage': cycles['intuitive']['percentage'],
                'critical_cycles': self.mapper.get_critical_cycles(values),
                'peak_cycles': self.mapper.get_peak_cycles(values)
            })
        
        return forecast
    
    def _calculate_daily_ml_features(self, cycles: Dict) -> Dict:
        """ML фичи для конкретного дня"""
        values = [data['value'] for data in cycles.values()]
        derivatives = [data['derivative'] for data in cycles.values()]
        
        return {
            'mean_value': round(sum(values) / len(values), 6),
            'mean_derivative': round(sum(derivatives) / len(derivatives), 6),
            'max_value': max(values),
            'min_value': min(values),
            'value_range': max(values) - min(values),
            'positive_count': sum(1 for v in values if v > 0),
            'negative_count': sum(1 for v in values if v < 0)
        }
