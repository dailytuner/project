"""
Модуль расчета профиля пользователя.
Содержит чистую бизнес-логику расчетов без работы с БД.
v2.0 - Production Ready
"""

import json
import logging
import math
import hashlib
from datetime import datetime, date
from functools import lru_cache
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.future import select
import asyncio

from ..users.user_services import user_service
from ..database.core import async_session
from ..database.models import NatalChart, PsyhoMatrix, Biorhythm, User
from .constants import (
    PLANET_WEIGHTS,
    HOUSE_WEIGHTS,
    ELEMENT_MODIFIERS,
    PROFILE_VERSION,
    AXIS_NAMES,
    AXIS_PLANETS,
    ASPECT_TYPES,
    KARMIC_INTERPRETATIONS,
    house_meanings
)

import functools
import time

def timeout(seconds):
    """Декоратор для таймаута функций"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(f"Таймаут функции {func.__name__}")
                raise
        return wrapper
    return decorator

logger = logging.getLogger(__name__)


class MagicProfileCalculator:
    """
    Калькулятор психологических профилей для ML моделей.
    Версия 2.0 с 9 осями личности.
    """

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self._cache = {}
        logger.info("✅ MagicProfileCalculator v2.0 инициализирован")

    # ==================== Базовые математические методы ====================

    def _sigmoid(self, x: float, steepness: float = 6.0) -> float:
        """
        Улучшенная сигмоида с регулируемой крутизной.
        steepness=6 дает хороший диапазон [0.1, 0.9] при x в [0,1]
        """
        # Нормализуем x в диапазон [-1, 1]
        x_norm = 2.0 * x - 1.0
        return 1.0 / (1.0 + math.exp(-steepness * x_norm))

    def _normalize(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Нормализация значения в заданный диапазон"""
        return max(min_val, min(max_val, value))

    # ==================== Методы доступа к данным с кэшированием ====================

    def _get_cache_key(self, *args) -> str:
        """Генерация ключа кэша"""
        key_str = "_".join(str(arg) for arg in args)
        return hashlib.md5(key_str.encode()).hexdigest()

    #@lru_cache(maxsize=256)
    def _get_planet_influence(self, planets: Dict, planet_name: str, placements: Dict = None) -> float:
        """
        Унифицированный метод получения влияния планеты.
        Возвращает значение в диапазоне [0.1, 0.9].
        """
        planet = planets.get(planet_name, {})

        # Базовая сила (0-1)
        strength = planet.get('strength', 0.5)

        # Достоинства (-5..+5 -> 0..1)
        dignity_score = planet.get('dignity_score', 0)
        dignity_factor = (dignity_score + 5) / 10.0

        # Ретроградность
        retrograde = planet.get('retrograde', False)

        # Базовое влияние (60% сила, 40% достоинства)
        base = strength * 0.6 + dignity_factor * 0.4

        # Штраф за ретроградность (аддитивный)
        if retrograde:
            base = max(0.1, base - 0.15)

        # Бонус за дом
        if placements and planet_name in placements:
            house = placements[planet_name]
            house_weight = HOUSE_WEIGHTS.get(house, 1.0)
            # Аддитивный бонус за важный дом
            if house_weight > 1.0:
                base = min(0.9, base + 0.1)
            elif house_weight < 0.8:
                base = max(0.1, base - 0.05)

        return self._sigmoid(base)

    def _calculate_house_influence(self, house_data: Dict, house_number: int) -> float:
        """Расчет влияния дома с учетом планет в нем"""
        if not house_data:
            return 0.5
        
        # Базовая сила из данных
        strength = house_data.get('strength', 0.5)
        
        # Учитываем вес дома
        house_weight = HOUSE_WEIGHTS.get(house_number, 1.0)
        
        # Корректируем на основе веса
        adjusted = strength * (0.7 + 0.3 * house_weight)
        
        return self._sigmoid(adjusted)

    def _calculate_aspect_tension(self, aspects: List[Dict]) -> float:
        """
        Расчет напряженности аспектов с учетом силы и точности.
        """
        if not aspects:
            return 0.5

        tension = 0.0
        total_weight = 0.0

        for aspect in aspects:
            aspect_type = aspect.get('type', '')
            strength = aspect.get('strength', 0.5)
            orb = aspect.get('orb', 5.0)

            # Вес: чем точнее аспект, тем важнее
            weight = max(0.0, 1.0 - (orb / 8.0))

            # Базовое влияние по типу аспекта
            if aspect_type in ['square', 'opposition']:
                tension += strength * weight * 0.3
            elif aspect_type in ['trine', 'sextile']:
                tension -= strength * weight * 0.1
            elif aspect_type == 'conjunction':
                # Конъюнкция может быть разной
                if strength > 0.7:
                    tension += strength * weight * 0.15
                else:
                    tension -= strength * weight * 0.05

            total_weight += weight

        if total_weight < 0.1:
            return 0.5

        avg_tension = 0.5 + tension / total_weight
        return self._normalize(avg_tension, 0.3, 0.7)

    # ==================== Методы для конфликтов ====================

    def _determine_conflict_approach(self, planets: Dict, ml_features: Dict) -> str:
        """
        Определение подхода к конфликтам на основе Марса и других факторов.
        """
        mars = self._get_planet_influence(planets, 'Mars')
        
        # Учитываем также влияние Плутона для глубины
        pluto = self._get_planet_influence(planets, 'Pluto')
        
        # Комбинированный score
        conflict_score = mars * 0.7 + pluto * 0.3
        
        if conflict_score > 0.75:
            return "confrontational"
        elif conflict_score > 0.6:
            return "assertive"
        elif conflict_score > 0.4:
            return "diplomatic"
        elif conflict_score > 0.25:
            return "avoidant"
        else:
            return "passive"

    def _determine_anger_expression(self, planets: Dict, aspects: List[Dict]) -> str:
        """
        Определение паттерна выражения гнева.
        """
        mars = self._get_planet_influence(planets, 'Mars')
        
        # Анализируем аспекты Марса
        mars_aspects = [a for a in aspects if 'Mars' in [a.get('planet1'), a.get('planet2')]]
        tension = self._calculate_aspect_tension(mars_aspects)
        
        # Комбинированный score
        anger_score = mars * 0.6 + tension * 0.4
        
        if anger_score > 0.8 and mars > 0.7:
            return "explosive"
        elif anger_score > 0.6:
            return "assertive"
        elif anger_score > 0.4:
            return "controlled"
        elif anger_score > 0.2:
            return "suppressed"
        else:
            return "peaceful"

    # ==================== Кармические интерпретации ====================

    def _interpret_karmic_task(self, sign: str, house: int,
                               north_node: Dict = None, south_node: Dict = None) -> str:
        """
        Полная интерпретация кармической задачи на основе узлов.
        """
        # Базовые интерпретации знаков
        sign_meanings = {
            'Aries': "научиться проявлять инициативу, не будучи эгоистичным",
            'Taurus': "развить стабильность и ценности, не становясь упрямым",
            'Gemini': "обрести глубину знаний, не оставаясь поверхностным",
            'Cancer': "научиться заботиться, не растворяясь в других",
            'Leo': "сиять и творить, не затмевая окружающих",
            'Virgo': "совершенствовать и служить, не критикуя",
            'Libra': "стремиться к гармонии, избегая конфликтов",
            'Scorpio': "трансформироваться, не разрушая",
            'Sagittarius': "искать истину, не осуждая",
            'Capricorn': "достигать целей, не застывая в структурах",
            'Aquarius': "быть уникальным, не отвергая общество",
            'Pisces': "сливаться с целым, не теряя себя"
        }

        sign_text = sign_meanings.get(sign, "развить осознанность")
        house_text = house_meanings.get(house, "в соответствующей сфере")

        # Если есть информация о южном узле (прошлом)
        if south_node:
            past_sign = south_node.get('sign', '')
            past_text = sign_meanings.get(past_sign, "старые паттерны")
            return f"Ваша задача — {sign_text} {house_text}, отпустив {past_text} из прошлого"

        return f"Ваша кармическая задача — {sign_text} {house_text}"

    # ==================== Вспомогательные методы доступа ====================

    def _get_uranus_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Урана"""
        return self._get_planet_influence(planets, 'Uranus', placements)

    def _get_pluto_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Плутона"""
        return self._get_planet_influence(planets, 'Pluto', placements)

    def _get_saturn_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Сатурна"""
        return self._get_planet_influence(planets, 'Saturn', placements)

    def _get_jupiter_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Юпитера"""
        return self._get_planet_influence(planets, 'Jupiter', placements)

    def _get_venus_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Венеры"""
        return self._get_planet_influence(planets, 'Venus', placements)

    def _get_mars_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Марса"""
        return self._get_planet_influence(planets, 'Mars', placements)

    def _get_mercury_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Меркурия"""
        return self._get_planet_influence(planets, 'Mercury', placements)

    def _get_moon_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Луны"""
        return self._get_planet_influence(planets, 'Moon', placements)

    def _get_sun_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Солнца"""
        return self._get_planet_influence(planets, 'Sun', placements)

    def _get_neptune_influence(self, planets: Dict, placements: Dict) -> float:
        """Получение влияния Нептуна"""
        return self._get_planet_influence(planets, 'Neptune', placements)

    # ==================== Валидация входных данных ====================

    def validate_inputs(self, natal_chart: Dict, psyho_matrix: Dict, 
                       biorhythms: Dict, user_profile: Dict) -> Tuple[bool, List[str]]:
        """
        Валидация всех входных данных перед расчетом.
        Возвращает (is_valid, список_ошибок)
        """
        errors = []
        
        # Проверка натальной карты
        if not natal_chart:
            errors.append("natal_chart отсутствует")
        else:
            required_natal = ['planets', 'houses', 'aspects']
            missing = [f for f in required_natal if f not in natal_chart]
            if missing:
                errors.append(f"natal_chart: отсутствуют {missing}")
        
        # Проверка психоматрицы
        if not psyho_matrix:
            errors.append("psyho_matrix отсутствует")
        
        # Проверка биоритмов (статических)
        if not biorhythms:
            errors.append("biorhythms отсутствуют")
        elif 'ml_indicators' not in biorhythms:
            errors.append("biorhythms: отсутствуют ml_indicators")
        
        # Проверка профиля пользователя
        if not user_profile:
            errors.append("user_profile отсутствует")
        
        return len(errors) == 0, errors

    # ==================== Расчет confidence score ====================

    def _calculate_confidence_score(self, *data_sources) -> float:
        """Расчет уверенности в данных на основе полноты"""
        scores = []
        
        for data in data_sources:
            if data and isinstance(data, dict):
                # Оцениваем полноту данных
                total_fields = 10  # приблизительное ожидаемое количество полей
                actual_fields = len(data)
                completeness = min(1.0, actual_fields / total_fields)
                scores.append(completeness)
            else:
                scores.append(0.0)
        
        return sum(scores) / len(scores) if scores else 0.5

    # ==================== Расчет 9 осей ====================

    @timeout(5.0)
    async def _calculate_axis_energy_will(self, natal_chart: Dict, psyho_matrix: Dict, biorhythms_static: Dict) -> Dict:
        planets = natal_chart.get('planets', {})
        houses = natal_chart.get('houses', {})
        placements = natal_chart.get('placements', {})

        mars = self._get_mars_influence(planets, placements)
        mars_retro = planets.get('Mars', {}).get('retrograde', False)
        sun = self._get_sun_influence(planets, placements)

        first_house = houses.get(1, {})
        first_house_influence = self._calculate_house_influence(first_house, 1)

        physical_entropy = biorhythms_static.get('ml_indicators', {}).get('physical_entropy', 0.5)

        # Психоматрица - цифра 1 (характер)
        digit_1_count = self._get_matrix_digit_count(psyho_matrix, 1)
        digit_1_strength = min(1.0, digit_1_count / 3)  # 3+ цифры = максимум

        return {
            "static_potential": {
                "willpower_base": round(self._sigmoid(
                    mars * 0.4 + sun * 0.25 + first_house_influence * 0.2 + digit_1_strength * 0.15
                ), 4),
                "initiative_tendency": round(
                    self._sigmoid(mars * 0.6 + first_house_influence * 0.25 + digit_1_strength * 0.15), 4),
                "leadership_quality": round(self._sigmoid(sun * 0.6 + mars * 0.2 + digit_1_strength * 0.2), 4),
            },
            "dynamic_modulators": {
                "entropy": round(physical_entropy, 4),
                "retrograde_penalty": 0.8 if mars_retro else 1.0,
            },
            "calculated_metrics": {
                "drive_intensity": round(self._sigmoid(mars * 0.5 + sun * 0.3 + digit_1_strength * 0.2), 4),
                "stamina_level": round(
                    self._sigmoid(mars * 0.4 + (1 - physical_entropy) * 0.4 + digit_1_strength * 0.2), 4),
                "courage_quotient": round(
                    self._sigmoid(mars * 0.6 + first_house_influence * 0.2 + digit_1_strength * 0.2), 4),
            }
        }

    async def _calculate_axis_health_physical(self, natal_chart: Dict, psyho_matrix: Dict,
                                              biorhythms_static: Dict) -> Dict:
        planets = natal_chart.get('planets', {})
        houses = natal_chart.get('houses', {})
        aspects = natal_chart.get('aspects', [])
        placements = natal_chart.get('placements', {})

        sixth_house = houses.get(6, {})
        sixth_house_influence = self._calculate_house_influence(sixth_house, 6)
        moon = self._get_moon_influence(planets, placements)
        saturn = self._get_saturn_influence(planets, placements)

        health_aspects = [a for a in aspects if a.get('house') == 6]
        aspect_tension = self._calculate_aspect_tension(health_aspects)

        # Психоматрица - цифра 4 (здоровье)
        digit_4_count = self._get_matrix_digit_count(psyho_matrix, 4)
        health_strength = min(1.0, digit_4_count / 2)  # 2+ цифры = хорошо

        return {
            "static_potential": {
                "constitution_strength": round(
                    self._sigmoid(
                        sixth_house_influence * 0.4 + moon * 0.3 + (1 - aspect_tension) * 0.2 + health_strength * 0.1),
                    4),
                "recovery_speed": round(self._sigmoid(moon * 0.5 + (1 - saturn) * 0.3 + health_strength * 0.2), 4),
            },
            "vulnerability_areas": {
                "chronic_risk": round(saturn * 0.6 + aspect_tension * 0.3 + (1 - health_strength) * 0.1, 4),
                "stress_susceptibility": round((1 - moon) * 0.4 + aspect_tension * 0.4 + (1 - health_strength) * 0.2,
                                               4),
            },
            "calculated_metrics": {
                "vitality_index": round(self._sigmoid(sixth_house_influence * 0.5 + moon * 0.3 + health_strength * 0.2),
                                        4),
                "immune_strength": round(self._sigmoid(moon * 0.4 + (1 - saturn) * 0.3 + health_strength * 0.3), 4),
            }
        }

    async def _calculate_axis_intellect_logic(self, natal_chart: Dict, psyho_matrix: Dict) -> Dict:
        planets = natal_chart.get('planets', {})
        houses = natal_chart.get('houses', {})
        aspects = natal_chart.get('aspects', [])
        placements = natal_chart.get('placements', {})

        mercury = self._get_mercury_influence(planets, placements)
        mercury_dignity = planets.get('Mercury', {}).get('dignity_score', 0)
        third_house = self._calculate_house_influence(houses.get(3, {}), 3)
        ninth_house = self._calculate_house_influence(houses.get(9, {}), 9)

        mercury_aspects = [a for a in aspects if 'Mercury' in [a.get('planet1'), a.get('planet2')]]
        aspect_complexity = min(1.0, len(mercury_aspects) / 10)

        # Психоматрица - цифра 5 (логика)
        digit_5_count = self._get_matrix_digit_count(psyho_matrix, 5)
        logic_strength = min(1.0, digit_5_count / 2)  # 2+ цифры = хорошо

        return {
            "static_potential": {
                "iq_base": round(self._sigmoid(
                    mercury * 0.6 + (mercury_dignity + 5) / 20 * 0.2 + logic_strength * 0.2
                ), 4),
                "learning_speed": round(self._sigmoid(
                    mercury * 0.4 + third_house * 0.3 + logic_strength * 0.3
                ), 4),
                "abstract_thinking": round(self._sigmoid(mercury * 0.4 + ninth_house * 0.5 + logic_strength * 0.1), 4),
            },
            "thinking_styles": {
                "analytical_depth": round(
                    self._sigmoid(mercury * 0.5 + (1 - aspect_complexity) * 0.3 + logic_strength * 0.2), 4),
                "creative_divergence": round(
                    self._sigmoid(mercury * 0.3 + aspect_complexity * 0.5 + logic_strength * 0.2), 4),
                "practical_focus": round(self._sigmoid(mercury * 0.3 + third_house * 0.4 + logic_strength * 0.3), 4),
            },
            "calculated_metrics": {
                "curiosity_level": round(self._sigmoid(mercury * 0.4 + ninth_house * 0.4 + logic_strength * 0.2), 4),
                "skepticism_tendency": round(
                    self._sigmoid(mercury * 0.2 + (1 - ninth_house) * 0.5 + (1 - logic_strength) * 0.3), 4),
            }
        }

    async def _calculate_axis_emotions_intuition(self, natal_chart: Dict, biorhythms_static: Dict) -> Dict:
        """
        Ось 4: Эмоции/Интуиция
        Источники: Луна, Нептун, 4/12 дома, биокорреляции
        """
        planets = natal_chart.get('planets', {})
        houses = natal_chart.get('houses', {})
        placements = natal_chart.get('placements', {})

        # Луна (эмоции)
        moon = self._get_moon_influence(planets, placements)

        # Нептун (интуиция)
        neptune = self._get_neptune_influence(planets, placements)

        # 4 дом (эмоциональная база)
        fourth_house = self._calculate_house_influence(houses.get(4, {}), 4)

        # 12 дом (подсознание)
        twelfth_house = self._calculate_house_influence(houses.get(12, {}), 12)

        # Статические корреляции из биоритмов
        correlations = biorhythms_static.get('cycle_correlations', {})
        intuitive_luck = correlations.get('intuitive_luck', -0.1)
        emotional_entropy = biorhythms_static.get('ml_indicators', {}).get('emotional_entropy', 0.5)

        return {
            "static_potential": {
                "emotional_depth": round(self._sigmoid(moon * 0.6 + fourth_house * 0.4), 4),
                "intuitive_strength": round(self._sigmoid(neptune * 0.7 + twelfth_house * 0.3), 4),
                "empathy_capacity": round(self._sigmoid(moon * 0.8 + neptune * 0.2), 4),
            },
            "dynamic_modulators": {
                "emotional_entropy": round(emotional_entropy, 4),
                "intuition_luck_correlation": round(intuitive_luck, 4),
            },
            "calculated_metrics": {
                "emotional_stability": round(self._sigmoid(moon * 0.4 + (1 - emotional_entropy) * 0.6), 4),
                "mood_variability": round(emotional_entropy, 4),
                "intuition_reliability": round(self._sigmoid(neptune * 0.5 + (1 - abs(intuitive_luck)) * 0.5), 4),
            }
        }

    async def _calculate_axis_work_discipline(self, natal_chart: Dict, psyho_matrix: Dict) -> Dict:
        """
        Ось 5: Труд/Дисциплина
        Источники: Сатурн, 6/10 дома, психоматрица 6/8
        """
        planets = natal_chart.get('planets', {})
        houses = natal_chart.get('houses', {})
        placements = natal_chart.get('placements', {})

        # Сатурн (дисциплина)
        saturn = self._get_saturn_influence(planets, placements)

        # 6 дом (работа)
        sixth_house = self._calculate_house_influence(houses.get(6, {}), 6)

        # 10 дом (карьера)
        tenth_house = self._calculate_house_influence(houses.get(10, {}), 10)

        # Учитываем также Марс для трудолюбия
        mars = self._get_mars_influence(planets, placements)

        # Психоматрица - цифры 6 (труд) и 8 (долг)
        digit_6_count = self._get_matrix_digit_count(psyho_matrix, 6)
        digit_8_count = self._get_matrix_digit_count(psyho_matrix, 8)
        work_strength = min(1.0, (digit_6_count + digit_8_count) / 4)  # 4+ цифры = максимум


        return {
            "static_potential": {
                "discipline_base": round(self._sigmoid(saturn * 0.5 + sixth_house * 0.2 + mars * 0.1 + work_strength * 0.2
                ), 4),
                "work_ethic": round(self._sigmoid(saturn * 0.4 + tenth_house * 0.2 + mars * 0.2 + work_strength * 0.2
                ), 4),
                "persistence_capacity": round(self._sigmoid(saturn * 0.8 + sixth_house * 0.1 + mars * 0.1), 4),
            },
            "work_styles": {
                "structured_preference": round(
                    self._sigmoid(saturn * 0.7 + (1 - self._get_uranus_influence(planets, placements)) * 0.3), 4),
                "deadline_respect": round(self._sigmoid(saturn * 0.6 + sixth_house * 0.2 + mars * 0.2), 4),
                "overtime_willingness": round(self._sigmoid(mars * 0.5 + tenth_house * 0.3 + saturn * 0.2), 4),
            },
            "calculated_metrics": {
                "follow_through_ability": round(self._sigmoid(saturn * 0.6 + sixth_house * 0.2 + mars * 0.2), 4),
                "procrastination_tendency": round(1 - self._sigmoid(saturn * 0.5 + mars * 0.5), 4),
            }
        }

    async def _calculate_axis_luck_talent(self, natal_chart: Dict, psyho_matrix: Dict) -> Dict:
        """
        Ось 6: Удача/Таланты
        Источники: Юпитер, 5 дом, арабские части, неподвижные звезды
        """
        planets = natal_chart.get('planets', {})
        houses = natal_chart.get('houses', {})
        arabic_parts = natal_chart.get('arabic_parts', {})
        fixed_stars = natal_chart.get('fixed_stars', [])
        placements = natal_chart.get('placements', {})

        # Юпитер (удача)
        jupiter = self._get_jupiter_influence(planets, placements)

        # 5 дом (творчество)
        fifth_house = self._calculate_house_influence(houses.get(5, {}), 5)

        # Арабские части
        fortune_part = arabic_parts.get('Fortune', {})
        fortune_influence = 0.7 if fortune_part else 0.5

        # Неподвижные звезды (Спика)
        spica_conjunctions = [s for s in fixed_stars if s.get('name') == 'Spica' and s.get('conjunctions')]
        spica_influence = 0.9 if spica_conjunctions else 0.5

        return {
            "static_potential": {
                "luck_base": round(self._sigmoid(jupiter * 0.5 + fortune_influence * 0.3 + spica_influence * 0.2), 4),
                "talent_magnitude": round(self._sigmoid(fifth_house * 0.4 + spica_influence * 0.3 + jupiter * 0.3), 4),
                "creative_flow": round(self._sigmoid(jupiter * 0.4 + fifth_house * 0.4 + spica_influence * 0.2), 4),
            },
            "special_gifts": {
                "has_spica_conjunction": len(spica_conjunctions) > 0,
                "spica_planets": [s.get('planet') for s in spica_conjunctions],
                "fortune_house": fortune_part.get('house', 0),
                "fortune_sign": fortune_part.get('sign', ''),
            },
            "calculated_metrics": {
                "synchronicity_frequency": round(self._sigmoid(jupiter * 0.4 + fortune_influence * 0.3 + spica_influence * 0.3), 4),
                "opportunity_recognition": round(self._sigmoid(jupiter * 0.5 + fifth_house * 0.3 + spica_influence * 0.2), 4),
            }
        }

    async def _calculate_axis_social_relations(self, natal_chart: Dict, psyho_matrix: Dict,
                                               biorhythms_static: Dict) -> Dict:
        planets = natal_chart.get('planets', {})
        houses = natal_chart.get('houses', {})
        aspects = natal_chart.get('aspects', [])
        placements = natal_chart.get('placements', {})

        venus = self._get_venus_influence(planets, placements)
        seventh_house = self._calculate_house_influence(houses.get(7, {}), 7)
        eleventh_house = self._calculate_house_influence(houses.get(11, {}), 11)

        venus_aspects = [a for a in aspects if 'Venus' in [a.get('planet1'), a.get('planet2')]]
        harmony_aspects = sum(1 for a in venus_aspects if a.get('type') in ['trine', 'sextile'])
        harmony_score = min(1.0, harmony_aspects / 5)

        moon = self._get_moon_influence(planets, placements)

        # Психоматрица - столбец 4-5-6 (адаптация в социуме)
        digit_4 = self._get_matrix_digit_count(psyho_matrix, 4)
        digit_5 = self._get_matrix_digit_count(psyho_matrix, 5)
        digit_6 = self._get_matrix_digit_count(psyho_matrix, 6)
        social_adaptation = min(1.0, (digit_4 + digit_5 + digit_6) / 6)

        return {
            "static_potential": {
                "social_charm": round(self._sigmoid(
                    venus * 0.4 + seventh_house * 0.2 + harmony_score * 0.2 + social_adaptation * 0.2
                ), 4),
                "friendship_depth": round(self._sigmoid(
                    venus * 0.3 + eleventh_house * 0.3 + moon * 0.2 + social_adaptation * 0.2
                ), 4),
                "partnership_orientation": round(self._sigmoid(
                    seventh_house * 0.4 + venus * 0.2 + moon * 0.2 + social_adaptation * 0.2
                ), 4),
            },
            "relationship_patterns": {
                "conflict_approach": self._determine_conflict_approach(planets, {}),
                "trust_building_speed": round(
                    self._sigmoid(venus * 0.3 + moon * 0.2 + (
                                1 - self._get_pluto_influence(planets, placements)) * 0.2 + social_adaptation * 0.3),
                    4),
                "commitment_readiness": round(
                    self._sigmoid(seventh_house * 0.3 + self._get_saturn_influence(planets,
                                                                                   placements) * 0.2 + venus * 0.2 + social_adaptation * 0.3),
                    4),
            },
            "calculated_metrics": {
                "extroversion_level": round(self._sigmoid(
                    venus * 0.2 + seventh_house * 0.2 + eleventh_house * 0.2 + moon * 0.2 + social_adaptation * 0.2
                ), 4),
                "empathy_capacity": round(self._sigmoid(
                    moon * 0.3 + venus * 0.2 + harmony_score * 0.2 + social_adaptation * 0.3
                ), 4),
            }
        }

    async def _calculate_axis_karma_cycles(self, natal_chart: Dict, biorhythms_static: Dict) -> Dict:
        """
        Ось 8: Карма/Циклы
        Источники: Северный/Южный узел, Сатурн, Плутон, долгие циклы биоритмов
        """
        planets = natal_chart.get('planets', {})
        placements = natal_chart.get('placements', {})

        # Северный узел (задача)
        north_node = planets.get('True_Node', {})
        north_node_sign = north_node.get('sign', '')
        north_node_house = north_node.get('house', 1)

        # Южный узел (прошлое) - обычно в противоположном знаке/доме
        south_node = planets.get('Mean_Node', {})
        south_node_sign = south_node.get('sign', '')
        south_node_house = south_node.get('house', 7)  # по умолчанию оппозиция

        # Сатурн (кармический учитель)
        saturn = self._get_saturn_influence(planets, placements)

        # Плутон (трансформация)
        pluto = self._get_pluto_influence(planets, placements)

        # Долгие циклы из биоритмов
        cycle_stats = biorhythms_static.get('cycle_statistics', {})
        seven_year_mean = cycle_stats.get('seven_year', {}).get('mean', 0)
        nine_year_mean = cycle_stats.get('nine_year', {}).get('mean', 0)
        eleven_year_mean = cycle_stats.get('eleven_year', {}).get('mean', 0)

        return {
            "karmic_task": {
                "node_sign": north_node_sign,
                "node_house": north_node_house,
                "past_life_sign": south_node_sign,
                "past_life_house": south_node_house,
                "task_description": self._interpret_karmic_task(north_node_sign, north_node_house),
            },
            "transformative_potential": {
                "crisis_frequency": round(self._sigmoid(pluto * 0.6 + saturn * 0.2 + (1 - saturn) * 0.2), 4),
                "rebirth_capacity": round(self._sigmoid(pluto * 0.7 + saturn * 0.2 + nine_year_mean * 0.1), 4),
            },
            "long_cycles": {
                "seven_year_phase": "positive" if seven_year_mean > 0 else "negative",
                "seven_year_intensity": round(abs(seven_year_mean), 4),
                "nine_year_phase": "positive" if nine_year_mean > 0 else "negative",
                "nine_year_intensity": round(abs(nine_year_mean), 4),
                "eleven_year_phase": "positive" if eleven_year_mean > 0 else "negative",
                "eleven_year_intensity": round(abs(eleven_year_mean), 4),
            }
        }

    async def _calculate_axis_destiny_mission(self, natal_chart: Dict, psyho_matrix: Dict) -> Dict:
        """
        Ось 9: Судьба/Миссия
        Источники: Стеллумы, йод, Спика, число судьбы
        """
        planets = natal_chart.get('planets', {})
        patterns = natal_chart.get('patterns', {})
        fixed_stars = natal_chart.get('fixed_stars', [])
        ml_features = natal_chart.get('ml_features', {})

        # Поиск стеллумов
        stelliums = patterns.get('stellium', {})
        main_stellium = stelliums.get('by_sign', {})

        # Поиск йод
        yod = patterns.get('yod', {})
        has_yod = yod and yod.get('planets')

        # Спика
        spica = next((s for s in fixed_stars if s.get('name') == 'Spica'), None)
        spica_conjunctions = spica.get('conjunctions', []) if spica else []

        # Число судьбы из психоматрицы (упрощенно)
        destiny_number = psyho_matrix.get('destiny_number', 1)

        # Считаем интенсивность миссии
        mission_score = 0.5
        mission_score += (len(main_stellium) * 0.1)
        mission_score += 0.2 if has_yod else 0
        mission_score += 0.3 if spica_conjunctions else 0
        mission_score += 0.1 if destiny_number in [1, 8, 11, 22] else 0  # мастер-числа

        return {
            "life_purpose": {
                "has_stellium": len(main_stellium) > 0,
                "stellium_sign": list(main_stellium.keys())[0] if main_stellium else None,
                "stellium_planets": list(main_stellium.values())[0] if main_stellium else 0,
            },
            "fate_markers": {
                "has_yod": has_yod,
                "yod_apex": yod.get('apex') if has_yod else None,
                "yod_planets": yod.get('planets') if has_yod else [],
                "has_spica": spica_conjunctions,
                "spica_planets": spica_conjunctions,
                "destiny_number": destiny_number,
            },
            "mission_indicators": {
                "destiny_intensity": round(self._sigmoid(mission_score), 4),
                "mission_clarity": round(self._sigmoid(mission_score * 0.8 + len(spica_conjunctions) * 0.2), 4),
            }
        }

    # ==================== Расчет ML features ====================

    def _calculate_ml_features_v2(self, axes_results: Dict, biorhythms_static: Dict) -> Dict:
        """
        ML features на основе 9 осей и статических биоритмов.
        Возвращает словарь с raw features, Big5 и специальными индикаторами.
        """
        # Извлекаем ключевые метрики из каждой оси
        features = {}

        # Ось 1: Энергия/Воля
        energy = axes_results.get('energy_will', {})
        features['drive_intensity'] = energy.get('calculated_metrics', {}).get('drive_intensity', 0.5)
        features['stamina'] = energy.get('calculated_metrics', {}).get('stamina_level', 0.5)

        # Ось 2: Здоровье/Физика
        health = axes_results.get('health_physical', {})
        features['vitality'] = health.get('calculated_metrics', {}).get('vitality_index', 0.5)
        features['chronic_risk'] = health.get('vulnerability_areas', {}).get('chronic_risk', 0.5)

        # Ось 3: Интеллект/Логика
        intellect = axes_results.get('intellect_logic', {})
        features['iq_base'] = intellect.get('static_potential', {}).get('iq_base', 0.5)
        features['learning_speed'] = intellect.get('static_potential', {}).get('learning_speed', 0.5)

        # Ось 4: Эмоции/Интуиция
        emotions = axes_results.get('emotions_intuition', {})
        features['emotional_stability'] = emotions.get('calculated_metrics', {}).get('emotional_stability', 0.5)
        features['intuition_reliability'] = emotions.get('calculated_metrics', {}).get('intuition_reliability', 0.5)

        # Ось 5: Труд/Дисциплина
        work = axes_results.get('work_discipline', {})
        features['follow_through'] = work.get('calculated_metrics', {}).get('follow_through_ability', 0.5)
        features['work_ethic'] = work.get('static_potential', {}).get('work_ethic', 0.5)

        # Ось 6: Удача/Таланты
        luck = axes_results.get('luck_talent', {})
        features['luck_base'] = luck.get('static_potential', {}).get('luck_base', 0.5)
        features['talent_magnitude'] = luck.get('static_potential', {}).get('talent_magnitude', 0.5)

        # Ось 7: Социум/Отношения
        social = axes_results.get('social_relations', {})
        features['extroversion'] = social.get('calculated_metrics', {}).get('extroversion_level', 0.5)
        features['empathy'] = social.get('calculated_metrics', {}).get('empathy_capacity', 0.5)

        # Ось 8: Карма/Циклы
        karma = axes_results.get('karma_cycles', {})
        features['transformative_potential'] = karma.get('transformative_potential', {}).get('rebirth_capacity', 0.5)

        # Ось 9: Судьба/Миссия
        destiny = axes_results.get('destiny_mission', {})
        features['destiny_intensity'] = destiny.get('mission_indicators', {}).get('destiny_intensity', 0.5)

        # Добавляем статические метрики из биоритмов
        ml_indicators = biorhythms_static.get('ml_indicators', {})
        features['system_stability'] = ml_indicators.get('system_stability', 0.5)
        features['predictability'] = ml_indicators.get('predictability', 0.5)

        # Добавляем ключевые корреляции
        correlations = biorhythms_static.get('cycle_correlations', {})
        features['intuition_luck_corr'] = correlations.get('intuitive_luck', 0)

        # Формируем Big 5 на основе наших осей
        big_five = {
            'openness': (features.get('iq_base', 0.5) + features.get('talent_magnitude', 0.5)) / 2,
            'conscientiousness': (features.get('follow_through', 0.5) + features.get('work_ethic', 0.5)) / 2,
            'extraversion': features.get('extroversion', 0.5),
            'agreeableness': (features.get('empathy', 0.5) + (1 - features.get('chronic_risk', 0.5))) / 2,
            'neuroticism': 1 - features.get('emotional_stability', 0.5),
        }

        return {
            'raw_features': features,
            'big_five': big_five,
            'special_indicators': {
                'has_spica': destiny.get('fate_markers', {}).get('has_spica', False),
                'has_yod': destiny.get('fate_markers', {}).get('has_yod', False),
                'destiny_intensity': features.get('destiny_intensity', 0.5),
            },
            'metadata': {
                'version': '2.0',
                'feature_count': len(features),
                'calculated_at': datetime.now().isoformat()
            }
        }

    def _create_feature_vector_v2(self, ml_features: Dict) -> List[float]:
        """
        Создание feature vector для ML моделей из ML features.
        Возвращает список чисел фиксированной длины.
        """
        features = []

        # Добавляем raw features в фиксированном порядке
        raw = ml_features.get('raw_features', {})
        raw_keys = sorted(raw.keys())  # сортируем для стабильности порядка
        for key in raw_keys:
            features.append(raw.get(key, 0.5))

        # Добавляем Big 5 в фиксированном порядке
        big5 = ml_features.get('big_five', {})
        big5_keys = ['openness', 'conscientiousness', 'extraversion', 'agreeableness', 'neuroticism']
        for key in big5_keys:
            features.append(big5.get(key, 0.5))

        # Добавляем специальные индикаторы как числа
        special = ml_features.get('special_indicators', {})
        features.append(1.0 if special.get('has_spica', False) else 0.0)
        features.append(1.0 if special.get('has_yod', False) else 0.0)
        features.append(special.get('destiny_intensity', 0.5))

        return features


    def _create_psychological_blueprint_v2(self, axes_results: Dict) -> Dict:
        """
        Создание интегрированного психологического блюпринта на основе 9 осей.
        Используется для ML моделей и интерпретации.
        """

        def _safe_get(axis, path, default=0.5):
            """Безопасное извлечение значения из оси"""
            try:
                value = axes_results.get(axis, {})
                for key in path.split('.'):
                    value = value.get(key, {})
                return float(value) if isinstance(value, (int, float)) else default
            except:
                return default

        return {
            "core_personality": {
                # Целостность = воля + ответственность
                "integrity_index": round(
                    (_safe_get('energy_will', 'static_potential.willpower_base') +
                     _safe_get('work_discipline', 'calculated_metrics.follow_through_ability')) / 2, 4
                ),
                # Открытость = любопытство + интуиция
                "openness_balance": round(
                    (_safe_get('intellect_logic', 'calculated_metrics.curiosity_level') +
                     _safe_get('emotions_intuition', 'static_potential.intuitive_strength')) / 2, 4
                ),
                # Надежность = дисциплина + ответственность
                "dependability_score": round(
                    (_safe_get('work_discipline', 'static_potential.work_ethic') +
                     _safe_get('work_discipline', 'calculated_metrics.follow_through_ability')) / 2, 4
                ),
                # Аутентичность = воля - социальная маска
                "authenticity_level": round(
                    _safe_get('energy_will', 'static_potential.willpower_base') * 0.7 +
                    (1 - _safe_get('social_relations', 'static_potential.social_charm')) * 0.3, 4
                ),
            },

            "emotional_architecture": {
                "stability": _safe_get('emotions_intuition', 'calculated_metrics.emotional_stability'),
                "empathy": _safe_get('social_relations', 'calculated_metrics.empathy_capacity'),
                "resilience": round(
                    _safe_get('emotions_intuition', 'calculated_metrics.emotional_stability') * 0.6 +
                    _safe_get('energy_will', 'calculated_metrics.stamina_level') * 0.4, 4
                ),
            },

            "cognitive_style": {
                "analytical": _safe_get('intellect_logic', 'thinking_styles.analytical_depth'),
                "creative": _safe_get('intellect_logic', 'thinking_styles.creative_divergence'),
                "practical": _safe_get('intellect_logic', 'thinking_styles.practical_focus'),
            },

            "social_dynamics": {
                "extroversion": _safe_get('social_relations', 'calculated_metrics.extroversion_level'),
                "diplomacy": _safe_get('social_relations', 'static_potential.social_charm'),
                "leadership": _safe_get('energy_will', 'static_potential.leadership_quality'),
            },

            "life_purpose_indicators": {
                "destiny_intensity": _safe_get('destiny_mission', 'mission_indicators.destiny_intensity'),
                "transformative_potential": _safe_get('karma_cycles', 'transformative_potential.rebirth_capacity'),
                "luck_factor": _safe_get('luck_talent', 'static_potential.luck_base'),
            }
        }

    # ==================== Основной метод расчета ====================

    import asyncio
    from datetime import datetime
    from typing import Dict, List

    # Константы (добавить в начало файла)
    AXIS_NAMES = [
        'energy_will', 'health_physical', 'intellect_logic',
        'emotions_intuition', 'work_discipline', 'luck_talent',
        'social_relations', 'karma_cycles', 'destiny_mission'
    ]
    PROFILE_VERSION = "2.0"

    async def calculate_magic_profile_v2(self, user_id: int,
                                         natal_chart: Dict,
                                         psyho_matrix: Dict,
                                         biorhythms_static: Dict,
                                         user_profile: Dict) -> Dict:
        """
        Основной метод расчета magic profile с 9 осями.
        """
        logger.info(f"🔄 Расчет magic profile v2 для пользователя {user_id}")

        # Валидация входных данных
        is_valid, errors = self.validate_inputs(natal_chart, psyho_matrix, biorhythms_static, user_profile)
        if not is_valid:
            error_msg = f"Ошибка валидации: {errors}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # 🔥 ПАРАЛЛЕЛЬНЫЕ расчеты по 9 осям
        calculation_tasks = [
            asyncio.create_task(self._calculate_axis_energy_will(natal_chart, psyho_matrix, biorhythms_static)),
            asyncio.create_task(self._calculate_axis_health_physical(natal_chart, psyho_matrix, biorhythms_static)),
            asyncio.create_task(self._calculate_axis_intellect_logic(natal_chart, psyho_matrix)),
            asyncio.create_task(self._calculate_axis_emotions_intuition(natal_chart, biorhythms_static)),
            asyncio.create_task(self._calculate_axis_work_discipline(natal_chart, psyho_matrix)),
            asyncio.create_task(self._calculate_axis_luck_talent(natal_chart, psyho_matrix)),
            asyncio.create_task(self._calculate_axis_social_relations(natal_chart, psyho_matrix, biorhythms_static)),
            asyncio.create_task(self._calculate_axis_karma_cycles(natal_chart, biorhythms_static)),
            asyncio.create_task(self._calculate_axis_destiny_mission(natal_chart, psyho_matrix))
        ]

        try:
            results = await asyncio.gather(*calculation_tasks, return_exceptions=True)

            # Проверяем на ошибки в результатах
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Ошибка в расчете оси {AXIS_NAMES[i]}: {result}")
                    raise result

            # Формируем axes по именам
            axes_results = dict(zip(AXIS_NAMES, results))

            # ML features на основе осей
            ml_features = self._calculate_ml_features_v2(axes_results, biorhythms_static)

            # ✅ Feature vector для ML моделей - ГАРАНТИРУЕМ, ЧТО ЭТО СПИСОК!
            feature_vector = self._create_feature_vector_v2(ml_features)

            # КРИТИЧЕСКАЯ ПРОВЕРКА: преобразуем строку в список, если нужно
            if isinstance(feature_vector, str):
                try:
                    import json
                    feature_vector = json.loads(feature_vector)
                    logger.info(f"✅ Преобразовали feature_vector из строки в список, длина: {len(feature_vector)}")
                except Exception as e:
                    logger.error(f"❌ Ошибка преобразования feature_vector: {e}")
                    feature_vector = []

            # Убедимся, что это список
            if not isinstance(feature_vector, list):
                logger.error(f"❌ feature_vector не является списком: {type(feature_vector)}")
                feature_vector = []

            # Проверим, что все элементы - числа
            feature_vector = [float(x) if not isinstance(x, float) else x for x in feature_vector]

            logger.info(f"✅ feature_vector готов: тип={type(feature_vector)}, длина={len(feature_vector)}")
            logger.info(f"✅ Первые 5 значений: {feature_vector[:5]}")

            # Психологический блюпринт
            psychological_blueprint = self._create_psychological_blueprint_v2(axes_results)

            # Confidence score
            confidence_score = self._calculate_confidence_score(
                natal_chart, psyho_matrix, biorhythms_static, user_profile
            )

            logger.info(f"✅ Magic profile v2 успешно рассчитан для {user_id} (9 осей, {len(feature_vector)} features)")

            return {
                'user_id': user_id,
                'axes': axes_results,
                'psychological_blueprint': psychological_blueprint,
                'ml_features': ml_features,
                'feature_vector': feature_vector,  # ✅ ТОЧНО СПИСОК!
                'cluster_id': None,
                'anomaly_score': 0.0,
                'profile_version': f"{PROFILE_VERSION}",
                'calculation_metadata': {
                    'calculated_at': datetime.now().isoformat(),
                    'data_sources': ['natal_chart', 'psyho_matrix', 'biorhythms_static', 'user_profile'],
                    'confidence_score': confidence_score,
                    'axis_count': len(AXIS_NAMES),
                    'feature_count': len(feature_vector),
                    'calculation_time_ms': 2500
                },
                'is_valid': True,
                'validation_errors': []
            }

        except Exception as e:
            logger.error(f"❌ Критическая ошибка расчета magic profile v2 для {user_id}: {e}")
            raise

    def _get_matrix_digit_count(self, psyho_matrix: Dict, digit: int) -> int:
        """Получение количества цифр в психоматрице"""
        try:
            matrix_digits = psyho_matrix.get('matrix_digits', {})
            return matrix_digits.get(str(digit), 0)
        except Exception as e:
            logger.warning(f"Ошибка получения цифры {digit} из матрицы: {e}")
            return 0

    def _get_retrograde_planets(self, planets: Dict) -> List[str]:
        """Получение списка ретроградных планет"""
        retro = []
        for planet_name, planet_data in planets.items():
            if planet_data.get('retrograde', False):
                retro.append(planet_name)
        return retro

   

    # извлечь birth_date для биоритмов
    def _get_birth_date(self, user_profile: Dict) -> date:
        """Извлечение даты рождения из профиля"""
        try:
            birth_date_str = user_profile.get('birth_date')
            if birth_date_str:
                return datetime.fromisoformat(birth_date_str).date()
        except Exception as e:
            logger.warning(f"Не удалось извлечь дату рождения: {e}")
        return None

    # ==================== Daily модули ====================

    '''async def calculate_daily_modulators(self, static_profile: Dict, target_date: date) -> Dict:
        """
        Расчет дневных модуляторов для 9 осей.
        Возвращает модулированные значения осей на указанную дату.
        """
        from .daily import (
            calculate_biorhythms,
            calculate_moon_transit,
            calculate_dasha_phase,
            calculate_void_moon
        )

        birth_date = datetime.fromisoformat(static_profile.get('birth_date')).date()
        
        # Параллельные расчеты дневных модуляторов
        tasks = [
            calculate_biorhythms(birth_date, target_date),
            calculate_moon_transit(target_date),
            calculate_dasha_phase(static_profile.get('dasha'), target_date),
            calculate_void_moon(target_date)
        ]
        
        modulators = await asyncio.gather(*tasks)
        biorhythms, moon_transit, dasha_phase, void_moon = modulators
        
        # Модуляция 9 осей
        daily_axes = {}
        axes_data = static_profile.get('axes', {})
        
        for axis_name in AXIS_NAMES:
            axis_data = axes_data.get(axis_name, {})
            static_score = axis_data.get('static_potential', {}).get(list(axis_data.get('static_potential', {}).keys())[0], 0.5)
            
            # Получаем соответствующий модулятор для оси
            modulator = self._get_axis_modulator(axis_name, biorhythms, moon_transit, dasha_phase, void_moon)
            
            # Применяем модуляцию (±30% от статики)
            modulated = static_score * (0.7 + 0.6 * modulator)
            daily_axes[axis_name] = round(self._normalize(modulated), 4)
        
        return {
            'date': target_date.isoformat(),
            'modulators': {
                'biorhythms': biorhythms,
                'moon_transit': moon_transit,
                'dasha_phase': dasha_phase,
                'void_moon': void_moon
            },
            'daily_axes': daily_axes
        }'''

    def _get_axis_modulator(self, axis_name: str, biorhythms: Dict, 
                           moon_transit: Dict, dasha_phase: Dict, void_moon: bool) -> float:
        """
        Получение модулятора для конкретной оси на основе дневных данных.
        """
        modulators = {
            'energy_will': biorhythms.get('physical', 0.5),
            'health_physical': (biorhythms.get('physical', 0.5) + (0.5 if void_moon else 0.0)) / 2,
            'intellect_logic': biorhythms.get('intellectual', 0.5),
            'emotions_intuition': (biorhythms.get('emotional', 0.5) + moon_transit.get('phase', 0.5)) / 2,
            'work_discipline': (biorhythms.get('physical', 0.5) + biorhythms.get('intellectual', 0.5)) / 2,
            'luck_talent': dasha_phase.get('progress', 0.5),
            'social_relations': (biorhythms.get('emotional', 0.5) + (0.7 if not void_moon else 0.3)) / 2,
            'karma_cycles': dasha_phase.get('mahadasha_progress', 0.5),
            'destiny_mission': (dasha_phase.get('antardasha_progress', 0.5) + moon_transit.get('nakshatra_factor', 0.5)) / 2
        }
        
        return modulators.get(axis_name, 0.5)


# Экспорт для использования в других модулях
__all__ = ['MagicProfileCalculator']
