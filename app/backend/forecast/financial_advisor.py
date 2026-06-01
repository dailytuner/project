"""
financial_advisor.py - Финансовый советник на основе транзитов и домов
Версия 1.0 - Анализ финансового потенциала дня

Использует ведическую астрологию для оценки:
- Финансового индекса дня (0-100)
- Благоприятных действий для денег
- Рисков потерь и мошенничества
- Направлений для инвестиций
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import date, datetime
from dataclasses import dataclass, field

from .axis_modulator import AxisName
from ..database.models import NatalChart

logger = logging.getLogger(__name__)


# ============================================================
# КОНСТАНТЫ
# ============================================================

# Дома богатства в ведической астрологии
WEALTH_HOUSES = {
    2: "личные сбережения",
    5: "спекуляции и инвестиции",
    7: "бизнес и партнёрство",
    8: "наследство и кредиты",
    11: "прибыль и доходы"
}

# Планеты-караки (индикаторы) финансов
FINANCE_KARAKAS = {
    'Jupiter': {'role': 'growth', 'weight': 1.0, 'positive_impact': 0.15},
    'Venus': {'role': 'comfort', 'weight': 0.9, 'positive_impact': 0.12},
    'Mercury': {'role': 'trade', 'weight': 0.7, 'positive_impact': 0.08},
    'Saturn': {'role': 'stability', 'weight': 0.6, 'positive_impact': 0.05},
    'Pluto': {'role': 'transformation', 'weight': 0.5, 'positive_impact': 0.10}
}

# Планеты с негативным влиянием на финансы
NEGATIVE_FINANCE_KARAKAS = {
    'Rahu': {'role': 'risk_greed', 'weight': 0.8, 'negative_impact': -0.12},
    'Ketu': {'role': 'detachment', 'weight': 0.6, 'negative_impact': -0.08},
    'Mars': {'role': 'impulse', 'weight': 0.5, 'negative_impact': -0.06}
}

# Знаки зодиака и их финансовые сферы
ZODIAC_FINANCE_MAP = {
    'Aries': "стартапы, спорт, инновации",
    'Taurus': "финансы, недвижимость, искусство",
    'Gemini': "коммуникации, IT, торговля",
    'Cancer': "недвижимость, дом, семья",
    'Leo': "развлечения, шоу-бизнес, инвестиции",
    'Virgo': "аналитика, бухгалтерия, медицина",
    'Libra': "партнёрства, юриспруденция, дизайн",
    'Scorpio': "инвестиции, страхование, наследство",
    'Sagittarius': "образование, туризм, международные проекты",
    'Capricorn': "реальное производство, земля, ресурсы",
    'Aquarius': "технологии, инновации, стартапы",
    'Pisces': "благотворительность, искусство, духовность"
}

# Фазы Луны и их финансовое влияние
MOON_PHASE_FINANCE = {
    'new': {'impact': -0.05, 'advice': "Не начинай новые финансовые проекты"},
    'first_quarter': {'impact': 0.05, 'advice': "Хорошо для планирования инвестиций"},
    'full': {'impact': 0.08, 'advice': "Благоприятно для крупных покупок и сделок"},
    'last_quarter': {'impact': -0.03, 'advice': "Завершай финансовые дела, не начинай новое"},
    'eclipse': {'impact': -0.15, 'advice': "⚠️ Затмение — избегай финансовых решений"}
}

# Ретроградные планеты и их влияние
RETROGRADE_PLANETS_FINANCE = {
    'Mercury': {'impact': -0.10, 'advice': "Будь внимателен с документами и переводами"},
    'Venus': {'impact': -0.08, 'advice': "Избегай крупных трат на удовольствия"},
    'Jupiter': {'impact': -0.05, 'advice': "Инвестируй только в проверенное"},
    'Saturn': {'impact': -0.06, 'advice': "Избегай долгосрочных обязательств"},
    'Mars': {'impact': -0.04, 'advice': "Не поддавайся импульсивным покупкам"}
}


# ============================================================
# ДАТАКЛАССЫ
# ============================================================

@dataclass
class FinancialAdvice:
    """Финансовая рекомендация на день"""
    index: float  # 0-100
    level: str  # 'high', 'medium', 'low'
    emoji: str
    advice: str
    investment_hint: Optional[str] = None
    risk_warnings: List[str] = field(default_factory=list)
    best_time: Optional[str] = None
    favorable_actions: List[str] = field(default_factory=list)
    avoid_actions: List[str] = field(default_factory=list)
    planet_influence: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            'index': round(self.index, 1),
            'level': self.level,
            'emoji': self.emoji,
            'advice': self.advice,
            'investment_hint': self.investment_hint,
            'risk_warnings': self.risk_warnings,
            'best_time': self.best_time,
            'favorable_actions': self.favorable_actions[:3],
            'avoid_actions': self.avoid_actions[:3],
            'planet_influence': self.planet_influence
        }


# ============================================================
# ОСНОВНОЙ КЛАСС
# ============================================================

class FinancialAdvisor:
    """
    Финансовый советник на основе транзитов и домов
    """

    def __init__(self):
        self.wealth_houses = WEALTH_HOUSES
        self.finance_karakas = FINANCE_KARAKAS
        self.negative_karakas = NEGATIVE_FINANCE_KARAKAS
        self.zodiac_map = ZODIAC_FINANCE_MAP
        self.moon_phase_finance = MOON_PHASE_FINANCE
        self.retrograde_finance = RETROGRADE_PLANETS_FINANCE

    def calculate_financial_index(
            self,
            transit_positions: Dict[str, Dict],
            natal_chart: Optional[NatalChart] = None,
            moon_phase: str = '',
            void_of_course_moon: bool = False,
            retrograde_planets: List[str] = None
    ) -> float:
        """
        Рассчитывает финансовый потенциал дня (0-100)

        Args:
            transit_positions: позиции транзитных планет
            natal_chart: натальная карта пользователя
            moon_phase: фаза Луны
            void_of_course_moon: Луна без курса
            retrograde_planets: список ретроградных планет

        Returns:
            financial_index: 0-100, где >70 благоприятный день
        """
        base_index = 50.0  # Нейтральное значение
        modifiers = []

        # 1. Влияние планет-карака финансов
        for planet_name, data in self.finance_karakas.items():
            if planet_name in transit_positions:
                planet_data = transit_positions[planet_name]
                # Учитываем силу планеты (например, в экзальтации сильнее)
                strength = self._get_planet_strength(planet_name, planet_data)
                impact = data['positive_impact'] * strength * data['weight']
                modifiers.append(impact)

        # 2. Негативное влияние
        for planet_name, data in self.negative_karakas.items():
            if planet_name in transit_positions:
                planet_data = transit_positions[planet_name]
                strength = self._get_planet_strength(planet_name, planet_data)
                impact = data['negative_impact'] * strength * data['weight']
                modifiers.append(impact)

        # 3. Влияние домов богатства (если есть натальная карта)
        if natal_chart and hasattr(natal_chart, 'houses'):
            house_impacts = self._calculate_house_impacts(
                transit_positions,
                natal_chart.houses if hasattr(natal_chart, 'houses') else {}
            )
            modifiers.extend(house_impacts)

        # 4. Влияние фазы Луны
        if moon_phase in self.moon_phase_finance:
            modifiers.append(self.moon_phase_finance[moon_phase]['impact'])

        # 5. Луна без курса
        if void_of_course_moon:
            modifiers.append(-0.08)

        # 6. Влияние ретроградных планет
        if retrograde_planets:
            for planet in retrograde_planets:
                if planet in self.retrograde_finance:
                    modifiers.append(self.retrograde_finance[planet]['impact'])

        # Применяем модификаторы
        for modifier in modifiers:
            base_index += modifier * 20  # Масштабируем влияние

        # Ограничиваем диапазон 0-100
        final_index = max(0.0, min(100.0, base_index))

        return final_index

    def _get_planet_strength(self, planet_name: str, planet_data: Dict) -> float:
        """
        Оценивает силу планеты в транзите
        Возвращает коэффициент от 0.5 до 1.5
        """
        strength = 1.0

        # Экзальтация/падение (упрощённо)
        sign = planet_data.get('sign', '')
        exaltation_signs = {
            'Sun': 'Aries', 'Moon': 'Taurus', 'Mercury': 'Virgo',
            'Venus': 'Pisces', 'Mars': 'Capricorn', 'Jupiter': 'Cancer',
            'Saturn': 'Libra'
        }

        fall_signs = {
            'Sun': 'Libra', 'Moon': 'Scorpio', 'Mercury': 'Pisces',
            'Venus': 'Virgo', 'Mars': 'Cancer', 'Jupiter': 'Capricorn',
            'Saturn': 'Aries'
        }

        if planet_name in exaltation_signs and exaltation_signs[planet_name] == sign:
            strength = 1.5
        elif planet_name in fall_signs and fall_signs[planet_name] == sign:
            strength = 0.5

        return strength

    def _calculate_house_impacts(
            self,
            transit_positions: Dict,
            natal_houses: Dict
    ) -> List[float]:
        """
        Рассчитывает влияние транзитных планет на дома богатства
        """
        impacts = []

        # Упрощённая логика: планеты в 2,5,7,8,11 домах усиливают финансы
        for planet_name, planet_data in transit_positions.items():
            planet_long = planet_data.get('longitude', 0)

            for house_num, house_desc in self.wealth_houses.items():
                # Проверяем, находится ли планета в доме (упрощённо)
                house_start = (house_num - 1) * 30
                house_end = house_num * 30

                if house_start <= planet_long % 360 < house_end:
                    # Планета в доме богатства
                    if planet_name in self.finance_karakas:
                        impact = 0.05 * self.finance_karakas[planet_name]['weight']
                        impacts.append(impact)
                    elif planet_name in self.negative_karakas:
                        impact = -0.04 * self.negative_karakas[planet_name]['weight']
                        impacts.append(impact)

        return impacts

    def get_financial_advice(
            self,
            financial_index: float,
            transit_positions: Dict,
            moon_phase: str = '',
            void_of_course_moon: bool = False,
            retrograde_planets: List[str] = None,
            planetary_hour: Dict = None
    ) -> FinancialAdvice:
        """
        Генерирует полную финансовую рекомендацию
        """
        # Определяем уровень
        if financial_index >= 70:
            level = 'high'
            emoji = '💰'
            advice = "Благоприятный день для финансовых решений, инвестиций и крупных покупок"
        elif financial_index >= 40:
            level = 'medium'
            emoji = '📊'
            advice = "Нейтральный фон — можно заниматься рутинными финансами, но избегай крупных рисков"
        else:
            level = 'low'
            emoji = '⚠️'
            advice = "День неблагоприятен для финансовых решений — лучше отложить крупные траты и инвестиции"

        # Инвестиционные подсказки
        investment_hint = self._get_investment_hint(transit_positions)

        # Риски
        risk_warnings = self._get_risk_warnings(
            transit_positions, moon_phase, void_of_course_moon, retrograde_planets
        )

        # Лучшее время
        best_time = self._get_best_financial_time(planetary_hour, moon_phase)

        # Благоприятные и неблагоприятные действия
        favorable_actions, avoid_actions = self._get_actions(financial_index, transit_positions)

        # Влияние планет
        planet_influence = self._get_planet_influence(transit_positions)

        return FinancialAdvice(
            index=financial_index,
            level=level,
            emoji=emoji,
            advice=advice,
            investment_hint=investment_hint,
            risk_warnings=risk_warnings,
            best_time=best_time,
            favorable_actions=favorable_actions,
            avoid_actions=avoid_actions,
            planet_influence=planet_influence
        )

    def _get_investment_hint(self, transit_positions: Dict) -> Optional[str]:
        """
        Определяет сферы для инвестиций на основе сильных планет
        """
        # Находим самую сильную планету
        strongest_planet = None
        highest_strength = 0

        for planet_name, planet_data in transit_positions.items():
            if planet_name in self.finance_karakas:
                strength = self._get_planet_strength(planet_name, planet_data)
                if strength > highest_strength:
                    highest_strength = strength
                    strongest_planet = planet_name

        if strongest_planet and highest_strength >= 1.2:
            sign = transit_positions.get(strongest_planet, {}).get('sign', '')
            if sign in self.zodiac_map:
                return f"{strongest_planet} в {sign} — благоприятны: {self.zodiac_map[sign]}"

        return None

    def _get_risk_warnings(
            self,
            transit_positions: Dict,
            moon_phase: str,
            void_of_course_moon: bool,
            retrograde_planets: List[str]
    ) -> List[str]:
        """
        Генерирует предупреждения о финансовых рисках
        """
        warnings = []

        # Фаза Луны
        if moon_phase in self.moon_phase_finance:
            moon_advice = self.moon_phase_finance[moon_phase]['advice']
            if 'избегай' in moon_advice or 'не начинай' in moon_advice:
                warnings.append(f"🌙 {moon_advice}")

        # Луна без курса
        if void_of_course_moon:
            warnings.append("🌑 Луна без курса — не начинай крупные финансовые проекты")

        # Ретроградные планеты
        if retrograde_planets:
            for planet in retrograde_planets:
                if planet in self.retrograde_finance:
                    warnings.append(f"🔄 {self.retrograde_finance[planet]['advice']}")

        # Раху в финансовых домах (упрощённо)
        if 'Rahu' in transit_positions:
            rahu_long = transit_positions['Rahu'].get('longitude', 0)
            # Проверяем Раху в Весах или Скорпионе
            if 180 <= rahu_long < 240:  # Весы/Скорпион
                warnings.append("⚠️ Раху в зоне риска — избегай мошеннических схем")

        return warnings

    def _get_best_financial_time(self, planetary_hour: Dict, moon_phase: str) -> Optional[str]:
        """
        Определяет лучшее время для финансовых дел
        """
        if planetary_hour:
            planet = planetary_hour.get('planet', '')
            hour_number = planetary_hour.get('hour_number', 0)
            is_day = planetary_hour.get('is_day', True)

            if planet in ['Jupiter', 'Venus', 'Mercury']:
                time_of_day = "утро" if is_day and hour_number <= 4 else "день"
                return f"Планетарный час {planet} ({time_of_day}) — благоприятен для финансов"

        if moon_phase == 'first_quarter' or moon_phase == 'full':
            return "Первая половина дня — лучшее время для финансовых решений"

        return None

    def _get_actions(self, financial_index: float, transit_positions: Dict) -> Tuple[List[str], List[str]]:
        """
        Определяет благоприятные и неблагоприятные финансовые действия
        """
        favorable = []
        avoid = []

        if financial_index >= 70:
            favorable = [
                "Инвестиции и покупка активов",
                "Открытие вкладов и счетов",
                "Крупные покупки",
                "Переговоры о финансах",
                "Погашение кредитов"
            ]
        elif financial_index >= 40:
            favorable = [
                "Планирование бюджета",
                "Рутинные платежи",
                "Анализ инвестиций"
            ]
            avoid = [
                "Спонтанные крупные траты",
                "Сомнительные инвестиции"
            ]
        else:
            avoid = [
                "Крупные покупки",
                "Финансовые переговоры",
                "Инвестиции",
                "Оформление кредитов"
            ]
            favorable = ["Планирование", "Проверка счетов"]

        return favorable, avoid

    def _get_planet_influence(self, transit_positions: Dict) -> Dict[str, float]:
        """
        Возвращает влияние планет на финансы
        """
        influence = {}

        for planet_name in self.finance_karakas:
            if planet_name in transit_positions:
                strength = self._get_planet_strength(planet_name, transit_positions[planet_name])
                influence[planet_name] = round(strength, 2)

        for planet_name in self.negative_karakas:
            if planet_name in transit_positions:
                strength = self._get_planet_strength(planet_name, transit_positions[planet_name])
                influence[planet_name] = round(-strength, 2)

        return influence


# ============================================================
# ФАБРИКА
# ============================================================

_financial_advisor: Optional[FinancialAdvisor] = None


def get_financial_advisor() -> FinancialAdvisor:
    """Получить глобальный экземпляр FinancialAdvisor"""
    global _financial_advisor
    if _financial_advisor is None:
        _financial_advisor = FinancialAdvisor()
    return _financial_advisor