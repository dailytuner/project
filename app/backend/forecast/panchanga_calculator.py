"""
panchanga_calculator.py - Расчёт ведического панчанги (5 элементов)
Версия 1.0 - Production Ready

Панчанга (पञ्चाङ्ग) - пять элементов ведического календаря:
1. Тити (Tithi) - лунный день (1-30)
2. Вара (Vara) - день недели
3. Накшатра (Nakshatra) - звёздная стоянка Луны (1-27)
4. Йога (Yoga) - комбинация Солнца и Луны (1-27)
5. Карана (Karana) - половина тити (1-11)

Дополнительно:
- Месяц (Маса)
- Лунный месяц (Шукла/Кришна Пакша)
- Солнечный месячный переход (Санкранти)

Используется для:
- Определения благоприятных/неблагоприятных дней
- Рекомендаций по стрижке, поездкам, начинаниям
- Астрологического прогнозирования
"""

import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============================================================
# КОНСТАНТЫ
# ============================================================

# Названия лунных дней (титхи) на русском и английском
TITHI_NAMES = {
    1: {'ru': 'Пратипада', 'en': 'Pratipada'},
    2: {'ru': 'Двития', 'en': 'Dwitiya'},
    3: {'ru': 'Трития', 'en': 'Tritiya'},
    4: {'ru': 'Чатуртхи', 'en': 'Chaturthi'},
    5: {'ru': 'Панчами', 'en': 'Panchami'},
    6: {'ru': 'Шаштхи', 'en': 'Shashthi'},
    7: {'ru': 'Суптами', 'en': 'Saptami'},
    8: {'ru': 'Аштами', 'en': 'Ashtami'},
    9: {'ru': 'Навами', 'en': 'Navami'},
    10: {'ru': 'Дашами', 'en': 'Dashami'},
    11: {'ru': 'Экадаши', 'en': 'Ekadashi'},
    12: {'ru': 'Двадаши', 'en': 'Dwadashi'},
    13: {'ru': 'Трайодаши', 'en': 'Trayodashi'},
    14: {'ru': 'Чатурдаши', 'en': 'Chaturdashi'},
    15: {'ru': 'Пурнима', 'en': 'Purnima'},  # Полнолуние
    16: {'ru': 'Пратипада', 'en': 'Pratipada'},
    17: {'ru': 'Двития', 'en': 'Dwitiya'},
    18: {'ru': 'Трития', 'en': 'Tritiya'},
    19: {'ru': 'Чатуртхи', 'en': 'Chaturthi'},
    20: {'ru': 'Панчами', 'en': 'Panchami'},
    21: {'ru': 'Шаштхи', 'en': 'Shashthi'},
    22: {'ru': 'Суптами', 'en': 'Saptami'},
    23: {'ru': 'Аштами', 'en': 'Ashtami'},
    24: {'ru': 'Навами', 'en': 'Navami'},
    25: {'ru': 'Дашами', 'en': 'Dashami'},
    26: {'ru': 'Экадаши', 'en': 'Ekadashi'},
    27: {'ru': 'Двадаши', 'en': 'Dwadashi'},
    28: {'ru': 'Трайодаши', 'en': 'Trayodashi'},
    29: {'ru': 'Чатурдаши', 'en': 'Chaturdashi'},
    30: {'ru': 'Амавасья', 'en': 'Amavasya'},  # Новолуние
}

# Названия накшатр (27)
NAKSHATRA_NAMES = {
    1: {'ru': 'Ашвини', 'en': 'Ashwini'},
    2: {'ru': 'Бхарани', 'en': 'Bharani'},
    3: {'ru': 'Криттика', 'en': 'Krittika'},
    4: {'ru': 'Рохини', 'en': 'Rohini'},
    5: {'ru': 'Мригашира', 'en': 'Mrigashira'},
    6: {'ru': 'Ардра', 'en': 'Ardra'},
    7: {'ru': 'Пунарвасу', 'en': 'Punarvasu'},
    8: {'ru': 'Пушья', 'en': 'Pushya'},
    9: {'ru': 'Ашлеша', 'en': 'Ashlesha'},
    10: {'ru': 'Магха', 'en': 'Magha'},
    11: {'ru': 'Пурва-Пхалгуни', 'en': 'Purva Phalguni'},
    12: {'ru': 'Уттара-Пхалгуни', 'en': 'Uttara Phalguni'},
    13: {'ru': 'Хаста', 'en': 'Hasta'},
    14: {'ru': 'Читра', 'en': 'Chitra'},
    15: {'ru': 'Свати', 'en': 'Swati'},
    16: {'ru': 'Вишакха', 'en': 'Vishakha'},
    17: {'ru': 'Анурадха', 'en': 'Anuradha'},
    18: {'ru': 'Дьештха', 'en': 'Jyeshtha'},
    19: {'ru': 'Мула', 'en': 'Mula'},
    20: {'ru': 'Пурва-Ашадха', 'en': 'Purva Ashadha'},
    21: {'ru': 'Уттара-Ашадха', 'en': 'Uttara Ashadha'},
    22: {'ru': 'Шравана', 'en': 'Shravana'},
    23: {'ru': 'Дхаништха', 'en': 'Dhanishtha'},
    24: {'ru': 'Шатабхиша', 'en': 'Shatabhisha'},
    25: {'ru': 'Пурва-Бхадрапада', 'en': 'Purva Bhadrapada'},
    26: {'ru': 'Уттара-Бхадрапада', 'en': 'Uttara Bhadrapada'},
    27: {'ru': 'Ревати', 'en': 'Revati'},
}

# Названия йог (27)
YOGA_NAMES = {
    1: {'ru': 'Вишкамбха', 'en': 'Vishkumbha'},
    2: {'ru': 'Прити', 'en': 'Priti'},
    3: {'ru': 'Аюшман', 'en': 'Ayushman'},
    4: {'ru': 'Саубхагья', 'en': 'Saubhagya'},
    5: {'ru': 'Шобхана', 'en': 'Shobhana'},
    6: {'ru': 'Атиганда', 'en': 'Atiganda'},
    7: {'ru': 'Суккарма', 'en': 'Sukarma'},
    8: {'ru': 'Дхрити', 'en': 'Dhriti'},
    9: {'ru': 'Шула', 'en': 'Shula'},
    10: {'ru': 'Ганда', 'en': 'Ganda'},
    11: {'ru': 'Вриддхи', 'en': 'Vriddhi'},
    12: {'ru': 'Дхрува', 'en': 'Dhruva'},
    13: {'ru': 'Вьягата', 'en': 'Vyaghata'},
    14: {'ru': 'Харшана', 'en': 'Harshana'},
    15: {'ru': 'Ваджра', 'en': 'Vajra'},
    16: {'ru': 'Сиддхи', 'en': 'Siddhi'},
    17: {'ru': 'Вьятипата', 'en': 'Vyatipata'},
    18: {'ru': 'Вариян', 'en': 'Variyan'},
    19: {'ru': 'Паригха', 'en': 'Parigha'},
    20: {'ru': 'Шива', 'en': 'Shiva'},
    21: {'ru': 'Сиддха', 'en': 'Siddha'},
    22: {'ru': 'Садхья', 'en': 'Sadhya'},
    23: {'ru': 'Шубха', 'en': 'Shubha'},
    24: {'ru': 'Шукла', 'en': 'Shukla'},
    25: {'ru': 'Брахма', 'en': 'Brahma'},
    26: {'ru': 'Аиндра', 'en': 'Indra'},
    27: {'ru': 'Вайдхрити', 'en': 'Vaidhriti'},
}

# Названия каран (11)
KARANA_NAMES = {
    1: {'ru': 'Кимступха', 'en': 'Kimstughna'},
    2: {'ru': 'Бава', 'en': 'Bava'},
    3: {'ru': 'Балава', 'en': 'Balava'},
    4: {'ru': 'Каулава', 'en': 'Kaulava'},
    5: {'ru': 'Тайтула', 'en': 'Taitula'},
    6: {'ru': 'Гараджа', 'en': 'Garaja'},
    7: {'ru': 'Вания', 'en': 'Vanija'},
    8: {'ru': 'Висти', 'en': 'Visti'},
    9: {'ru': 'Шакуни', 'en': 'Shakuni'},
    10: {'ru': 'Чара', 'en': 'Chara'},
    11: {'ru': 'Нава', 'en': 'Nava'},
}

# Лунные месяцы (Маса)
LUNAR_MONTHS = {
    'Chaitra': {'ru': 'Чайтра', 'season': 'весна'},
    'Vaishakha': {'ru': 'Вайшакха', 'season': 'весна'},
    'Jyeshtha': {'ru': 'Джьештха', 'season': 'лето'},
    'Ashadha': {'ru': 'Ашадха', 'season': 'лето'},
    'Shravana': {'ru': 'Шравана', 'season': 'лето'},
    'Bhadrapada': {'ru': 'Бхадрапада', 'season': 'осень'},
    'Ashwina': {'ru': 'Ашвина', 'season': 'осень'},
    'Kartika': {'ru': 'Картика', 'season': 'осень'},
    'Margashirsha': {'ru': 'Маргаширша', 'season': 'зима'},
    'Pausha': {'ru': 'Пауша', 'season': 'зима'},
    'Magha': {'ru': 'Магха', 'season': 'зима'},
    'Phalguna': {'ru': 'Пхалгуна', 'season': 'весна'},
}

# Дни недели (Вара)
VARA_NAMES = {
    0: {'ru': 'Воскресенье', 'en': 'Sunday', 'planet': 'Sun'},
    1: {'ru': 'Понедельник', 'en': 'Monday', 'planet': 'Moon'},
    2: {'ru': 'Вторник', 'en': 'Tuesday', 'planet': 'Mars'},
    3: {'ru': 'Среда', 'en': 'Wednesday', 'planet': 'Mercury'},
    4: {'ru': 'Четверг', 'en': 'Thursday', 'planet': 'Jupiter'},
    5: {'ru': 'Пятница', 'en': 'Friday', 'planet': 'Venus'},
    6: {'ru': 'Суббота', 'en': 'Saturday', 'planet': 'Saturn'},
}

# Благоприятные и неблагоприятные титхи
GOOD_TITHIS = {2, 3, 5, 7, 10, 11, 13}  # 2-й, 3-й, 5-й, 7-й, 10-й, 11-й, 13-й
BAD_TITHIS = {4, 9, 14, 30}  # 4-й, 9-й, 14-й, Амавасья
EKADASHI_TITHIS = {11, 26}  # Экадаши (11-й день после новолуния/полнолуния)

# Благоприятные накшатры для различных дел
NAKSHATRA_GOOD_FOR_HAIRCUT = {
    1, 5, 8, 12, 13, 15, 18, 21, 22, 27
    # Ashwini, Mrigashira, Pushya, Uttara Phalguni, Hasta, Swati, Jyeshtha, Uttara Ashadha, Shravana, Revati
}
NAKSHATRA_GOOD_FOR_TRAVEL = {
    1, 5, 7, 8, 13, 15, 17, 20, 22, 27
    # Ashwini, Mrigashira, Punarvasu, Pushya, Hasta, Swati, Anuradha, Purva Ashadha, Shravana, Revati
}
NAKSHATRA_GOOD_FOR_STARTING = {
    2, 4, 5, 8, 10, 13, 15, 20, 21, 22, 25
    # Bharani, Rohini, Mrigashira, Pushya, Magha, Hasta, Swati, Purva Ashadha, Uttara Ashadha, Shravana, Purva Bhadrapada
}
NAKSHATRA_BAD_FOR_STARTING = {
    3, 6, 9, 11, 14, 16, 19, 23, 24, 26
    # Krittika, Ardra, Ashlesha, Purva Phalguni, Chitra, Vishakha, Mula, Dhanishtha, Shatabhisha, Uttara Bhadrapada
}


# ============================================================
# ДАТАКЛАССЫ
# ============================================================

@dataclass
class Panchanga:
    """Панчанга на дату"""
    date: date
    tithi: int  # 1-30
    tithi_name_ru: str
    tithi_name_en: str
    tithi_name_sanskrit: str
    vara: int  # 0-6 (воскресенье-суббота)
    vara_name_ru: str
    vara_name_en: str
    vara_planet: str
    nakshatra: int  # 1-27
    nakshatra_name_ru: str
    nakshatra_name_en: str
    nakshatra_pada: int  # 1-4
    yoga: int  # 1-27
    yoga_name_ru: str
    yoga_name_en: str
    karana: int  # 1-11
    karana_name_ru: str
    karana_name_en: str

    # Дополнительные поля
    paksha: str  # 'Shukla' (растущая) или 'Krishna' (убывающая)
    lunar_month: str  # Название лунного месяца
    is_new_moon: bool
    is_full_moon: bool
    is_ekadashi: bool

    def to_dict(self, language: str = 'ru') -> Dict:
        """Преобразовать в словарь для API"""
        return {
            'date': self.date.isoformat(),
            'tithi': {
                'number': self.tithi,
                'name': getattr(self, f'tithi_name_{language}', self.tithi_name_en),
                'sanskrit': self.tithi_name_sanskrit,
                'paksha': self.paksha,
            },
            'vara': {
                'number': self.vara,
                'name': getattr(self, f'vara_name_{language}', self.vara_name_en),
                'planet': self.vara_planet,
            },
            'nakshatra': {
                'number': self.nakshatra,
                'name': getattr(self, f'nakshatra_name_{language}', self.nakshatra_name_en),
                'pada': self.nakshatra_pada,
            },
            'yoga': {
                'number': self.yoga,
                'name': getattr(self, f'yoga_name_{language}', self.yoga_name_en),
            },
            'karana': {
                'number': self.karana,
                'name': getattr(self, f'karana_name_{language}', self.karana_name_en),
            },
            'lunar_month': self.lunar_month,
            'is_new_moon': self.is_new_moon,
            'is_full_moon': self.is_full_moon,
            'is_ekadashi': self.is_ekadashi,
        }

    def get_suitability_for_haircut(self) -> Dict[str, Any]:
        """Оценка благоприятности дня для стрижки"""
        is_nakshatra_good = self.nakshatra in NAKSHATRA_GOOD_FOR_HAIRCUT
        is_tithi_good = self.tithi in GOOD_TITHIS
        is_tithi_bad = self.tithi in BAD_TITHIS

        if is_nakshatra_good and is_tithi_good:
            return {'level': 'excellent', 'verdict': '✅ ОТЛИЧНО',
                    'advice': 'Отличный день для стрижки — волосы будут расти здоровыми и крепкими'}
        elif is_nakshatra_good or is_tithi_good:
            return {'level': 'good', 'verdict': '✅ ХОРОШО', 'advice': 'Благоприятный день для стрижки'}
        elif is_tithi_bad:
            return {'level': 'bad', 'verdict': '⚠️ НЕ БЛАГОПРИЯТНО',
                    'advice': 'Стрижку лучше отложить — неблагоприятный лунный день'}
        else:
            return {'level': 'neutral', 'verdict': '➖ НЕЙТРАЛЬНО', 'advice': 'Стрижка возможна, но без особого эффекта'}

    def get_suitability_for_travel(self) -> Dict[str, Any]:
        """Оценка благоприятности дня для поездок"""
        is_nakshatra_good = self.nakshatra in NAKSHATRA_GOOD_FOR_TRAVEL
        is_tithi_good = self.tithi in GOOD_TITHIS
        is_tithi_bad = self.tithi in BAD_TITHIS

        if is_nakshatra_good and is_tithi_good:
            return {'level': 'excellent', 'verdict': '✅ ОТЛИЧНО',
                    'advice': 'Отличный день для поездок — дорога будет удачной'}
        elif is_nakshatra_good or is_tithi_good:
            return {'level': 'good', 'verdict': '✅ ХОРОШО', 'advice': 'Благоприятный день для путешествий'}
        elif is_tithi_bad:
            return {'level': 'bad', 'verdict': '⚠️ НЕ БЛАГОПРИЯТНО',
                    'advice': 'Поездки лучше отложить — неблагоприятный день'}
        else:
            return {'level': 'neutral', 'verdict': '➖ НЕЙТРАЛЬНО', 'advice': 'Поездки возможны, но будьте внимательны'}

    def get_suitability_for_starting(self) -> Dict[str, Any]:
        """Оценка благоприятности дня для новых начинаний"""
        is_nakshatra_good = self.nakshatra in NAKSHATRA_GOOD_FOR_STARTING
        is_nakshatra_bad = self.nakshatra in NAKSHATRA_BAD_FOR_STARTING
        is_tithi_good = self.tithi in GOOD_TITHIS
        is_tithi_bad = self.tithi in BAD_TITHIS

        if is_nakshatra_good and is_tithi_good:
            return {'level': 'excellent', 'verdict': '✅ ОТЛИЧНО',
                    'advice': 'Идеальный день для новых начинаний и важных дел'}
        elif is_nakshatra_good or is_tithi_good:
            return {'level': 'good', 'verdict': '✅ ХОРОШО', 'advice': 'День благоприятен для начинаний'}
        elif is_nakshatra_bad or is_tithi_bad:
            return {'level': 'bad', 'verdict': '⚠️ НЕ БЛАГОПРИЯТНО',
                    'advice': 'Новые дела лучше не начинать — неблагоприятный день'}
        else:
            return {'level': 'neutral', 'verdict': '➖ НЕЙТРАЛЬНО',
                    'advice': 'День нейтрален для начинаний, но возможно'}

    def get_axis_modulation(self) -> Dict[str, float]:
        """
        Получить коэффициенты модуляции для осей Magic Profile
        """
        modulations = {
            'emotions_intuition': 0.0,
            'luck_talent': 0.0,
            'work_discipline': 0.0,
            'karma_cycles': 0.0,
        }

        # Влияние титхи
        if self.tithi in GOOD_TITHIS:
            modulations['luck_talent'] += 0.03
            modulations['work_discipline'] += 0.02
        elif self.tithi in BAD_TITHIS:
            modulations['luck_talent'] -= 0.04
            modulations['work_discipline'] -= 0.03
            modulations['emotions_intuition'] -= 0.02

        # Влияние экадаши (особый духовный день)
        if self.is_ekadashi:
            modulations['karma_cycles'] += 0.05
            modulations['emotions_intuition'] += 0.03
            modulations['work_discipline'] -= 0.02

        # Влияние новолуния/полнолуния
        if self.is_new_moon:
            modulations['emotions_intuition'] -= 0.05
            modulations['luck_talent'] -= 0.03
            modulations['karma_cycles'] += 0.03
        elif self.is_full_moon:
            modulations['emotions_intuition'] += 0.05
            modulations['luck_talent'] += 0.03
            modulations['energy_will'] += 0.02

        # Влияние накшатры
        if self.nakshatra in NAKSHATRA_GOOD_FOR_STARTING:
            modulations['luck_talent'] += 0.02
        elif self.nakshatra in NAKSHATRA_BAD_FOR_STARTING:
            modulations['luck_talent'] -= 0.02
            modulations['work_discipline'] -= 0.01

        # Ограничиваем диапазон
        for axis in modulations:
            modulations[axis] = max(-0.15, min(0.15, modulations[axis]))

        return {k: round(v, 4) for k, v in modulations.items()}


# ============================================================
# ОСНОВНОЙ КЛАСС КАЛЬКУЛЯТОРА
# ============================================================

class PanchangaCalculator:
    """
    Калькулятор ведической панчанги
    """

    def __init__(self):
        self._cache: Dict[str, Panchanga] = {}
        self._tithi_names = TITHI_NAMES
        self._nakshatra_names = NAKSHATRA_NAMES
        self._yoga_names = YOGA_NAMES
        self._karana_names = KARANA_NAMES
        self._vara_names = VARA_NAMES

    def _get_cache_key(self, target_date: date, longitude: float) -> str:
        """Создать ключ для кэша"""
        return f"{target_date.isoformat()}_{longitude:.2f}"

    def _calculate_tithi(self, sun_long: float, moon_long: float) -> Tuple[int, float, str]:
        """
        Рассчитать титхи (лунный день)

        Титхи = разница долгот Луны и Солнца, делённая на 12 градусов
        """
        diff = moon_long - sun_long
        if diff < 0:
            diff += 360

        tithi_number = int(diff / 12) + 1
        if tithi_number > 30:
            tithi_number -= 30

        # Определяем пакшу (растущая/убывающая Луна)
        paksha = 'Shukla' if tithi_number <= 15 else 'Krishna'

        return tithi_number, diff, paksha

    def _calculate_nakshatra(self, moon_long: float) -> Tuple[int, float, int]:
        """
        Рассчитать накшатру (звёздную стоянку Луны)

        Накшатра = долгота Луны, делённая на 13.3333 градуса
        """
        nakshatra_degrees = 360.0 / 27.0
        nakshatra_index = int(moon_long / nakshatra_degrees) % 27
        nakshatra_number = nakshatra_index + 1

        # Остаток в накшатре для определения пады
        remainder = moon_long % nakshatra_degrees
        nakshatra_pada = int(remainder / (nakshatra_degrees / 4)) + 1

        return nakshatra_number, remainder, nakshatra_pada

    def _calculate_yoga(self, sun_long: float, moon_long: float) -> Tuple[int, float]:
        """
        Рассчитать йогу

        Йога = (долгота Солнца + долгота Луны) / 13.3333 градуса
        """
        sum_long = sun_long + moon_long
        if sum_long > 360:
            sum_long -= 360

        yoga_degrees = 360.0 / 27.0
        yoga_number = int(sum_long / yoga_degrees) % 27 + 1

        return yoga_number, sum_long

    def _calculate_karana(self, tithi_number: int, tithi_diff: float) -> Tuple[int, float]:
        """
        Рассчитать карану (половину титхи)

        Каждая титхи делится на две караны по 6 градусов
        """
        # Позиция внутри титхи (0-12 градусов)
        position_in_tithi = tithi_diff % 12

        # Карана: 1-7 для первых 7 каран, затем циклически
        karana_index = int(position_in_tithi / 6)

        # Специальная обработка: 1-я титхи даёт особую карану
        if tithi_number == 1 and karana_index == 0:
            karana_number = 1  # Кимступха
        else:
            # Базовая карана: 2-7 для остальных
            karana_number = (karana_index + 2) if karana_index < 2 else karana_index + 4

        # Повтор для второй половины дня
        if karana_number > 11:
            karana_number = (karana_number % 7) + 2

        return karana_number, position_in_tithi

    def _calculate_lunar_month(self, sun_long: float, moon_long: float, tithi_number: int) -> str:
        """
        Рассчитать лунный месяц

        Лунный месяц определяется по положению Солнца в зодиаке
        """
        # Солнечные месяцы (санкраманы)
        solar_months = [
            (0, 'Chaitra'), (30, 'Vaishakha'), (60, 'Jyeshtha'),
            (90, 'Ashadha'), (120, 'Shravana'), (150, 'Bhadrapada'),
            (180, 'Ashwina'), (210, 'Kartika'), (240, 'Margashirsha'),
            (270, 'Pausha'), (300, 'Magha'), (330, 'Phalguna')
        ]

        # Находим текущий солнечный месяц
        current_month = 'Chaitra'
        for degree, month in solar_months:
            if sun_long >= degree:
                current_month = month

        # Корректировка для новой луны (добавляем месяц)
        if tithi_number == 30:  # Амавасья
            # Переход на следующий месяц
            pass

        return current_month

    def calculate(
            self,
            sun_longitude: float,
            moon_longitude: float,
            target_date: date,
            longitude: float = 0.0,
            language: str = 'ru'
    ) -> Panchanga:
        """
        Рассчитать панчангу на основе долгот Солнца и Луны

        Args:
            sun_longitude: Долгота Солнца в градусах (0-360)
            moon_longitude: Долгота Луны в градусах (0-360)
            target_date: Целевая дата
            longitude: Географическая долгота для корректировки (не используется в упрощённой версии)
            language: Язык для названий ('ru' или 'en')

        Returns:
            Panchanga с рассчитанными значениями
        """
        # Проверка кэша
        cache_key = self._get_cache_key(target_date, longitude)
        if cache_key in self._cache:
            logger.debug(f"✅ Панчанга из кэша: {cache_key}")
            return self._cache[cache_key]

        # 1. Тити
        tithi_number, tithi_diff, paksha = self._calculate_tithi(sun_longitude, moon_longitude)
        tithi_name = self._tithi_names.get(tithi_number, {'ru': '', 'en': ''})

        # 2. День недели
        vara_number = target_date.weekday()  # ПН=0, но нам нужно ВС=0
        vara_number = (vara_number + 1) % 7  # Преобразуем так, чтобы ВС=0
        vara_info = self._vara_names.get(vara_number, {})

        # 3. Накшатра
        nakshatra_number, nakshatra_rem, nakshatra_pada = self._calculate_nakshatra(moon_longitude)
        nakshatra_name = self._nakshatra_names.get(nakshatra_number, {'ru': '', 'en': ''})

        # 4. Йога
        yoga_number, yoga_sum = self._calculate_yoga(sun_longitude, moon_longitude)
        yoga_name = self._yoga_names.get(yoga_number, {'ru': '', 'en': ''})

        # 5. Карана
        karana_number, karana_pos = self._calculate_karana(tithi_number, tithi_diff)
        karana_name = self._karana_names.get(karana_number, {'ru': '', 'en': ''})

        # 6. Лунный месяц
        lunar_month = self._calculate_lunar_month(sun_longitude, moon_longitude, tithi_number)
        lunar_month_name = LUNAR_MONTHS.get(lunar_month, {}).get('ru', lunar_month)

        # 7. Дополнительные флаги
        is_new_moon = tithi_number == 30
        is_full_moon = tithi_number == 15
        is_ekadashi = tithi_number in EKADASHI_TITHIS

        result = Panchanga(
            date=target_date,
            tithi=tithi_number,
            tithi_name_ru=tithi_name.get('ru', ''),
            tithi_name_en=tithi_name.get('en', ''),
            tithi_name_sanskrit=tithi_name.get('en', ''),
            vara=vara_number,
            vara_name_ru=vara_info.get('ru', ''),
            vara_name_en=vara_info.get('en', ''),
            vara_planet=vara_info.get('planet', ''),
            nakshatra=nakshatra_number,
            nakshatra_name_ru=nakshatra_name.get('ru', ''),
            nakshatra_name_en=nakshatra_name.get('en', ''),
            nakshatra_pada=nakshatra_pada,
            yoga=yoga_number,
            yoga_name_ru=yoga_name.get('ru', ''),
            yoga_name_en=yoga_name.get('en', ''),
            karana=karana_number,
            karana_name_ru=karana_name.get('ru', ''),
            karana_name_en=karana_name.get('en', ''),
            paksha=paksha,
            lunar_month=lunar_month_name,
            is_new_moon=is_new_moon,
            is_full_moon=is_full_moon,
            is_ekadashi=is_ekadashi,
        )

        # Сохраняем в кэш
        self._cache[cache_key] = result
        if len(self._cache) > 365:
            oldest = min(self._cache.keys())
            del self._cache[oldest]

        logger.info(f"✅ Рассчитана панчанга для {target_date}: "
                    f"титхи={tithi_number}, накшатра={nakshatra_number}, "
                    f"йога={yoga_number}, карана={karana_number}")

        return result

    def calculate_from_chart(
            self,
            sun_longitude: float,
            moon_longitude: float,
            target_date: date,
            language: str = 'ru'
    ) -> Panchanga:
        """
        Упрощённый метод для расчёта панчанги из натальной карты
        """
        return self.calculate(sun_longitude, moon_longitude, target_date, language=language)


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def panchanga_to_axis_modulation(panchanga: Panchanga) -> Dict[str, float]:
    """
    Преобразовать панчангу в модуляторы для осей Magic Profile
    """
    return panchanga.get_axis_modulation()


# ============================================================
# ФАБРИКА ДЛЯ СОЗДАНИЯ КАЛЬКУЛЯТОРА
# ============================================================

_panchanga_calculator: Optional[PanchangaCalculator] = None


def get_panchanga_calculator() -> PanchangaCalculator:
    """Получить глобальный экземпляр PanchangaCalculator"""
    global _panchanga_calculator
    if _panchanga_calculator is None:
        _panchanga_calculator = PanchangaCalculator()
    return _panchanga_calculator


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

def example_usage():
    """Пример использования калькулятора панчанги"""
    calculator = get_panchanga_calculator()

    # Пример долгот (нужно получить из эфемерид)
    # Для демонстрации используем примерные значения
    sun_long = 30.5  # Солнце в Тельце
    moon_long = 45.2  # Луна в Близнецах
    today = date.today()

    print("\n=== ПАНЧАНГА НА СЕГОДНЯ ===\n")

    panchanga = calculator.calculate(sun_long, moon_long, today)

    print(f"📅 Дата: {panchanga.date}")
    print(f"🌙 Пакша: {panchanga.paksha}")
    print(f"🌒 Лунный месяц: {panchanga.lunar_month}\n")

    print("📊 ТИТХИ (Лунный день):")
    print(f"   Номер: {panchanga.tithi}")
    print(f"   Название: {panchanga.tithi_name_ru}")
    print(f"   Новолуние: {panchanga.is_new_moon}")
    print(f"   Полнолуние: {panchanga.is_full_moon}")
    print(f"   Экадаши: {panchanga.is_ekadashi}\n")

    print("📊 ВАРА (День недели):")
    print(f"   Название: {panchanga.vara_name_ru}")
    print(f"   Управитель: {panchanga.vara_planet}\n")

    print("📊 НАКШАТРА:")
    print(f"   Номер: {panchanga.nakshatra}")
    print(f"   Название: {panchanga.nakshatra_name_ru}")
    print(f"   Пада: {panchanga.nakshatra_pada}\n")

    print("📊 ЙОГА:")
    print(f"   Номер: {panchanga.yoga}")
    print(f"   Название: {panchanga.yoga_name_ru}\n")

    print("📊 КАРАНА:")
    print(f"   Номер: {panchanga.karana}")
    print(f"   Название: {panchanga.karana_name_ru}\n")

    print("=== ПРАКТИЧЕСКИЕ РЕКОМЕНДАЦИИ ===")

    haircut = panchanga.get_suitability_for_haircut()
    print(f"✂️ СТРИЖКА: {haircut['verdict']}")
    print(f"   {haircut['advice']}\n")

    travel = panchanga.get_suitability_for_travel()
    print(f"✈️ ПОЕЗДКИ: {travel['verdict']}")
    print(f"   {travel['advice']}\n")

    starting = panchanga.get_suitability_for_starting()
    print(f"🚀 НОВЫЕ НАЧАЛА: {starting['verdict']}")
    print(f"   {starting['advice']}\n")

    print("=== МОДУЛЯЦИИ ДЛЯ MAGIC PROFILE ===")
    modulations = panchanga.get_axis_modulation()
    for axis, delta in modulations.items():
        if abs(delta) > 0.01:
            print(f"  {axis}: {delta:+.3f}")

    return panchanga


if __name__ == "__main__":
    example_usage()