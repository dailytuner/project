"""
psyho_matrix.py - Профессиональный калькулятор психоматрицы
Версия 3.2 - ПОЛНОСТЬЮ ПРИВЕДЕНА К МЕТОДОЛОГИИ АЛЕКСАНДРОВА
"""

from datetime import datetime, date
from typing import Dict, List, Any, Tuple, Optional, Union
import logging
from functools import lru_cache
import math

from .psyho_matrix_constants import (
    DIGIT_TO_CHARACTERISTIC,
    ANALYSIS_TEMPLATES,
    LIFE_PURPOSE_MAP,
    PARTNER_TYPES,
    COMPATIBILITY_MAP,
    MASTER_NUMBERS
)

logger = logging.getLogger(__name__)


class PsyhoMatrixCalculator:
    """
    Калькулятор психоматрицы по методике Александрова
    Все расчеты строго соответствуют классической методологии
    """

    def __init__(self):
        """Инициализация калькулятора с константами"""
        self.digit_to_characteristic = DIGIT_TO_CHARACTERISTIC
        self.analysis_templates = ANALYSIS_TEMPLATES
        self.life_purpose_map = LIFE_PURPOSE_MAP
        self.partner_types = PARTNER_TYPES
        self.compatibility_map = COMPATIBILITY_MAP
        self.master_numbers = MASTER_NUMBERS

    @lru_cache(maxsize=1024)
    def calculate_matrix(self, birth_date: date) -> Dict[str, Any]:
        """
        Основной метод расчета психоматрицы

        Args:
            birth_date: Дата рождения

        Returns:
            Dict с полными результатами расчета
        """
        # Валидация
        self._validate_birth_date(birth_date)

        day, month, year = birth_date.day, birth_date.month, birth_date.year

        # 1. Базовые числа (по Александрову)
        first_number = self._calculate_first_number(day, month, year)
        second_number = self._calculate_second_number(first_number)
        third_number = self._calculate_third_number(first_number, day)
        fourth_number = self._calculate_fourth_number(third_number)

        # 2. Построение матриц
        matrix_digits, matrix_3x3 = self._build_detailed_matrix(
            day, month, year,
            first_number, second_number, third_number, fourth_number,
        )

        # 3. Характеристики
        characteristics = self._get_professional_characteristics(
            matrix_digits, matrix_3x3
        )

        # 4. Энергетический уровень (только по двойкам)
        energy_level = self._get_energy_level(matrix_digits)

        # 5. Жизненное предназначение (по третьему числу)
        life_purpose = self._get_detailed_life_purpose(
            third_number, first_number
        )

        # 6. Коды талантов и сил
        talent_codes = self._get_detailed_talent_codes(
            matrix_digits, matrix_3x3
        )
        strength_codes = self._get_detailed_strength_codes(
            matrix_digits, matrix_3x3
        )

        # 7. Совместимость
        compatibility_hints = self._get_professional_compatibility_hints(
            first_number, fourth_number, matrix_digits
        )

        # 8. Дополнительные расчеты
        additional = self._get_additional_calculations(
            day, month, year,
            matrix_digits, matrix_3x3,
            first_number, fourth_number, third_number
        )

        # 9. Кармический анализ
        karmic_analysis = self._get_karmic_analysis(
            matrix_digits, first_number, third_number
        )

        # 10. Прогностика (с day, month для персональных годов)
        forecasting = self._get_forecasting_data(
            matrix_digits, first_number, fourth_number, day, month
        )

        return {
            # Основные числа
            'first_number': int(first_number),
            'second_number': int(second_number),
            'third_number': int(third_number),
            'fourth_number': int(fourth_number),

            # Матрицы
            'matrix_digits': matrix_digits,
            'matrix_3x3': matrix_3x3,

            # Характеристики
            'characteristics': characteristics,

            # Коды и уровни
            'talent_codes': talent_codes,
            'strength_codes': strength_codes,
            'energy_level': energy_level,

            # Предназначение и совместимость
            'life_purpose': life_purpose,
            'compatibility_hints': compatibility_hints,

            # Дополнительные данные
            'additional': additional,
            'karmic_analysis': karmic_analysis,
            'forecasting': forecasting,

            # Метаданные
            'calculation_version': '3.2',
            'calculated_at': datetime.now().isoformat(),
            'birth_date': birth_date.isoformat()
        }

    # ==================== ВАЛИДАЦИЯ ====================

    def _validate_birth_date(self, birth_date: date) -> None:
        """Полная валидация даты рождения"""
        if not isinstance(birth_date, date):
            raise TypeError(f"Expected date, got {type(birth_date)}")

        try:
            datetime(birth_date.year, birth_date.month, birth_date.day)
        except ValueError as e:
            raise ValueError(f"Invalid date: {e}")

        if birth_date.year < 1582:
            logger.warning(f"Date before Gregorian calendar: {birth_date}")

        if birth_date > date.today():
            logger.warning(f"Future date: {birth_date}")

    # ==================== БАЗОВЫЕ РАСЧЕТЫ (АЛЕКСАНДРОВ) ====================

    def _calculate_first_number(self, day: int, month: int, year: int) -> int:
        """
        Первое число = сумма всех цифр даты рождения
        НЕ РЕДУЦИРУЕТСЯ!
        """
        date_str = f"{day:02d}{month:02d}{year}"
        total = sum(int(d) for d in date_str)
        return total

    def _calculate_second_number(self, first_number: int) -> int:
        """Второе число = редукция первого числа"""
        return self._reduction_with_masters(first_number)

    def _calculate_third_number(self, first_number: int, day: int) -> int:
        """
        Третье число = первое число - 2 * первая цифра дня рождения
        НЕ РЕДУЦИРУЕТСЯ!
        """
        first_digit_of_day = int(str(day)[0])
        third_raw = first_number - (2 * first_digit_of_day)
        return third_raw

    def _calculate_fourth_number(self, third_number: int) -> int:
        """
        Четвертое число = редукция третьего числа
        """
        return self._reduction_with_masters(third_number)

    def _reduction_with_masters(self, number: int) -> int:
        """
        Редукция числа с сохранением мастер-чисел (11, 22, 33)
        """
        if number in self.master_numbers:
            return number

        result = number
        while result > 9:
            result = sum(int(d) for d in str(result))
            if result in self.master_numbers:
                return result

        return result

    # ==================== ПОСТРОЕНИЕ МАТРИЦ ====================

    def _build_detailed_matrix(self, day: int, month: int, year: int,
                               first: int, second: int, third: int, fourth: int) -> Tuple[
        Dict[str, int], List[List[int]]]:
        """
        Построение детальной матрицы из ВСЕХ цифр:
        - Дата рождения
        - 4 рабочих числа
        """
        # Валидация чисел
        for num in [first, second, third, fourth]:
            if num < 0:
                raise ValueError(f"Negative number in working numbers: {num}")

        # Собираем все цифры в одну строку
        working_numbers_str = ''.join(map(str, [first, second, third, fourth]))
        all_digits = f"{day:02d}{month:02d}{year}" + working_numbers_str

        # Подсчет количества каждой цифры
        matrix_digits = {str(i): all_digits.count(str(i)) for i in range(1, 10)}

        # Заполнение матрицы 3x3
        matrix_3x3 = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        for digit in all_digits:
            d = int(digit)
            if 1 <= d <= 9:
                row = (d - 1) // 3
                col = (d - 1) % 3
                matrix_3x3[row][col] += 1

        logger.debug(f"All digits: {all_digits}")
        logger.debug(f"Matrix digits: {matrix_digits}")
        logger.debug(f"Matrix 3x3: {matrix_3x3}")

        return matrix_digits, matrix_3x3

    # ==================== ХАРАКТЕРИСТИКИ ====================

    def _get_professional_characteristics(self, matrix_digits: Dict[str, int],
                                          matrix_3x3: List[List[int]]) -> Dict[str, Any]:
        """Профессиональный анализ характеристик"""
        characteristics = {}

        for digit, char_name in self.digit_to_characteristic.items():
            count = matrix_digits.get(str(digit), 0)
            characteristics[char_name] = self._analyze_digit_professional(digit, count)
            characteristics[f'{char_name}_score'] = self._count_to_score(count)
            characteristics[f'{char_name}_count'] = count

        characteristics['matrix_analysis'] = self._analyze_matrix_structure(matrix_digits)
        characteristics['positional'] = self._analyze_positions(matrix_3x3)
        characteristics['indices'] = self._calculate_indices(matrix_digits)

        return characteristics

    def _analyze_digit_professional(self, digit: int, count: int) -> str:
        """Профессиональный анализ отдельной цифры"""
        template = self.analysis_templates.get(digit, {})
        adjusted_count = min(count, 4)
        return template.get(adjusted_count, "Balanced development")

    def _count_to_score(self, count: int) -> int:
        """Конвертация количества в баллы (0-100)"""
        score_map = {0: 10, 1: 40, 2: 70, 3: 90, 4: 100}
        return score_map.get(min(count, 4), 50)

    def _analyze_matrix_structure(self, matrix_digits: Dict[str, int]) -> Dict[str, Any]:
        """Анализ структуры матрицы"""
        total_digits = sum(matrix_digits.values())
        unique_digits = sum(1 for v in matrix_digits.values() if v > 0)

        dominant_digit = None
        max_count = 0
        for digit, count in matrix_digits.items():
            if count > max_count:
                max_count = count
                dominant_digit = digit

        empty_cells = [d for d in range(1, 10) if matrix_digits.get(str(d), 0) == 0]
        filled_cells = [d for d in range(1, 10) if matrix_digits.get(str(d), 0) > 0]
        density = (unique_digits / 9) * 100

        return {
            'total_digits': total_digits,
            'unique_digits': unique_digits,
            'dominant_digit': dominant_digit,
            'dominant_count': max_count,
            'empty_cells': empty_cells,
            'filled_cells': filled_cells,
            'density': round(density, 2),
            'is_dense': density > 50,
            'is_sparse': density < 30
        }

    def _analyze_positions(self, matrix_3x3: List[List[int]]) -> Dict[str, Any]:
        """Анализ позиций в матрице 3x3"""
        row_strength = [sum(row) for row in matrix_3x3]

        col_strength = [
            sum(matrix_3x3[i][0] for i in range(3)),
            sum(matrix_3x3[i][1] for i in range(3)),
            sum(matrix_3x3[i][2] for i in range(3))
        ]

        main_diag = matrix_3x3[0][0] + matrix_3x3[1][1] + matrix_3x3[2][2]
        anti_diag = matrix_3x3[0][2] + matrix_3x3[1][1] + matrix_3x3[2][0]

        corners = (
                matrix_3x3[0][0] + matrix_3x3[0][2] +
                matrix_3x3[2][0] + matrix_3x3[2][2]
        )

        center = matrix_3x3[1][1]

        return {
            'row_strength': row_strength,
            'column_strength': col_strength,
            'main_diagonal': main_diag,
            'anti_diagonal': anti_diag,
            'corners': corners,
            'center': center,
            'balance_score': self._calculate_balance_score(matrix_3x3)
        }

    def _calculate_balance_score(self, matrix_3x3: List[List[int]]) -> int:
        """Расчет баланса матрицы (0-100)"""
        all_values = [cell for row in matrix_3x3 for cell in row]
        if not all_values:
            return 100

        mean = sum(all_values) / len(all_values)
        variance = sum((x - mean) ** 2 for x in all_values) / len(all_values)
        std_dev = math.sqrt(variance) if variance > 0 else 0

        max_possible = max(all_values) if all_values else 1
        if max_possible == 0:
            return 100

        balance = max(0, 100 - (std_dev / max_possible * 100))
        return int(balance)

    def _calculate_indices(self, matrix_digits: Dict[str, int]) -> Dict[str, float]:
        """
        Расчет дополнительных индексов
        Индексы - это авторская метрика, не входящая в методологию Александрова
        """
        # Используем веса из предыдущей версии для совместимости с БД
        purpose_index = matrix_digits.get('1', 0) * 15
        energy_index = matrix_digits.get('2', 0) * 10
        interest_index = matrix_digits.get('3', 0) * 12
        health_index = matrix_digits.get('4', 0) * 12
        logic_index = matrix_digits.get('5', 0) * 15
        labor_index = matrix_digits.get('6', 0) * 10
        luck_index = matrix_digits.get('7', 0) * 18
        duty_index = matrix_digits.get('8', 0) * 10
        memory_index = matrix_digits.get('9', 0) * 10

        total_digits = sum(matrix_digits.values())
        development_index = (total_digits / 27) * 100 if total_digits else 0

        return {
            'purpose_index': min(purpose_index, 100),
            'energy_index': min(energy_index, 100),
            'interest_index': min(interest_index, 100),
            'health_index': min(health_index, 100),
            'logic_index': min(logic_index, 100),
            'labor_index': min(labor_index, 100),
            'luck_index': min(luck_index, 100),
            'duty_index': min(duty_index, 100),
            'memory_index': min(memory_index, 100),
            'development_index': round(development_index, 2)
        }

    # ==================== ЭНЕРГЕТИЧЕСКИЙ УРОВЕНЬ (АЛЕКСАНДРОВ) ====================

    def _get_energy_level(self, matrix_digits: Dict[str, int]) -> str:
        """
        Энергетический уровень по методике Александрова
        Определяется ТОЛЬКО по количеству двоек
        """
        twos = matrix_digits.get('2', 0)
        if twos >= 3:
            return "very_high"
        elif twos == 2:
            return "high"
        elif twos == 1:
            return "medium"
        else:
            return "low"

    # ==================== КОДЫ ТАЛАНТОВ ====================

    def _get_detailed_talent_codes(self, matrix_digits: Dict[str, int],
                                   matrix_3x3: List[List[int]]) -> List[str]:
        """Получение детальных кодов талантов"""
        talents = set()

        # Таланты по цифрам
        for digit in range(1, 10):
            count = matrix_digits.get(str(digit), 0)
            if count >= 2:
                char_name = self.digit_to_characteristic[digit]
                talents.add(f"TALENT_{char_name.upper()}")

                if count >= 3:
                    talents.add(f"MASTER_TALENT_{char_name.upper()}")

        # Составные таланты
        if matrix_digits.get('3', 0) >= 2 and matrix_digits.get('5', 0) >= 1:
            talents.add("TALENT_TECHNICAL_ANALYTICAL")

        if matrix_digits.get('2', 0) >= 2 and matrix_digits.get('7', 0) >= 1:
            talents.add("TALENT_ENERGY_CREATIVE")

        if matrix_digits.get('1', 0) >= 2 and matrix_digits.get('8', 0) >= 1:
            talents.add("TALENT_LEADERSHIP_MANAGEMENT")

        if matrix_digits.get('4', 0) >= 2 and matrix_digits.get('6', 0) >= 1:
            talents.add("TALENT_HEALTH_HEALING")

        if matrix_digits.get('9', 0) >= 2 and matrix_digits.get('3', 0) >= 1:
            talents.add("TALENT_MEMORY_LEARNING")

        # Диагональные таланты
        main_diag = matrix_3x3[0][0] + matrix_3x3[1][1] + matrix_3x3[2][2]
        if main_diag >= 3:
            talents.add("TALENT_HOLISTIC_THINKING")
        if main_diag >= 5:
            talents.add("TALENT_SYSTEMIC_VISION")

        anti_diag = matrix_3x3[0][2] + matrix_3x3[1][1] + matrix_3x3[2][0]
        if anti_diag >= 3:
            talents.add("TALENT_CREATIVE_INTUITION")

        # Сила строк
        for i, row in enumerate(matrix_3x3):
            if sum(row) >= 4:
                talents.add(f"TALENT_ROW_{i + 1}_STRENGTH")

        if not talents:
            talents.update(["TALENT_ADAPTABILITY", "TALENT_LEARNING"])

        return sorted(talents)

    def _get_detailed_strength_codes(self, matrix_digits: Dict[str, int],
                                     matrix_3x3: List[List[int]]) -> List[str]:
        """
        Силы = подмножество талантов
        """
        talents = self._get_detailed_talent_codes(matrix_digits, matrix_3x3)

        strengths = set()

        # Маппинг: талант → сила
        mapping = {
            "TALENT_CHARACTER": "STRENGTH_CHARACTER",
            "MASTER_TALENT_CHARACTER": "MASTER_STRENGTH_CHARACTER",
            "TALENT_ENERGY": "STRENGTH_ENERGY",
            "MASTER_TALENT_ENERGY": "MASTER_STRENGTH_ENERGY",
            "TALENT_INTEREST": "STRENGTH_INTEREST",
            "MASTER_TALENT_INTEREST": "MASTER_STRENGTH_INTEREST",
            "TALENT_HEALTH": "STRENGTH_HEALTH",
            "MASTER_TALENT_HEALTH": "MASTER_STRENGTH_HEALTH",
            "TALENT_LOGIC": "STRENGTH_LOGIC",
            "MASTER_TALENT_LOGIC": "MASTER_STRENGTH_LOGIC",
            "TALENT_LABOR": "STRENGTH_LABOR",
            "MASTER_TALENT_LABOR": "MASTER_STRENGTH_LABOR",
            "TALENT_LUCK": "STRENGTH_LUCK",
            "MASTER_TALENT_LUCK": "MASTER_STRENGTH_LUCK",
            "TALENT_DUTY": "STRENGTH_DUTY",
            "MASTER_TALENT_DUTY": "MASTER_STRENGTH_DUTY",
            "TALENT_MEMORY": "STRENGTH_MEMORY",
            "MASTER_TALENT_MEMORY": "MASTER_STRENGTH_MEMORY",
            "TALENT_LEADERSHIP_MANAGEMENT": "STRENGTH_LEADERSHIP_MANAGEMENT",
            "TALENT_ENERGY_CREATIVE": "STRENGTH_ENERGY_CREATIVE",
            "TALENT_TECHNICAL_ANALYTICAL": "STRENGTH_TECHNICAL_ANALYTICAL",
            "TALENT_HEALTH_HEALING": "STRENGTH_HEALTH_HEALING",
            "TALENT_MEMORY_LEARNING": "STRENGTH_MEMORY_LEARNING",
            "TALENT_HOLISTIC_THINKING": "STRENGTH_HOLISTIC_THINKING",
            "TALENT_SYSTEMIC_VISION": "STRENGTH_SYSTEMIC_VISION",
            "TALENT_CREATIVE_INTUITION": "STRENGTH_CREATIVE_INTUITION",
            "TALENT_ROW_1_STRENGTH": "STRENGTH_ROW_1",
            "TALENT_ROW_2_STRENGTH": "STRENGTH_ROW_2",
            "TALENT_ROW_3_STRENGTH": "STRENGTH_ROW_3",
        }

        for talent in talents:
            if talent in mapping:
                strengths.add(mapping[talent])

        if not strengths:
            strengths.update(["STRENGTH_RESILIENCE", "STRENGTH_POTENTIAL"])

        return sorted(strengths)

    # ==================== ЖИЗНЕННОЕ ПРЕДНАЗНАЧЕНИЕ (АЛЕКСАНДРОВ) ====================

    def _get_detailed_life_purpose(self, third_number: int,
                                   first_number: int) -> str:
        """
        Жизненное предназначение по методике Александрова
        Определяется по ТРЕТЬЕМУ числу (не редуцированному)

        Если точного совпадения нет в маппинге, генерирует описание
        на основе редуцированного числа с указанием пути.
        """
        # Пытаемся найти по третьему числу
        if third_number in self.life_purpose_map:
            purpose = self.life_purpose_map[third_number]
        else:
            # Если нет в маппинге, редуцируем и используем базовое описание
            reduced = self._reduction_with_masters(third_number)
            base_purpose = self.life_purpose_map.get(
                reduced,
                "Personal development and growth"
            )
            purpose = f"{base_purpose} (realized through the unique path of number {third_number})"

        # Усиление мастер-числом в первом числе
        if first_number in self.master_numbers:
            purpose += f" (amplified and intensified by master number {first_number})"

            if first_number == 11:
                purpose += " - spiritual teacher and illuminator"
            elif first_number == 22:
                purpose += " - master builder and architect"
            elif first_number == 33:
                purpose += " - master healer and teacher"

        if len(purpose) > 800:
            purpose = purpose[:797] + "..."

        return purpose

    # ==================== СОВМЕСТИМОСТЬ ====================

    def _get_professional_compatibility_hints(self, first_number: int,
                                              fourth_number: int,
                                              matrix_digits: Dict[str, int]) -> Dict[str, Any]:
        """Профессиональный анализ совместимости"""
        hints = {
            'compatible_numbers': [],
            'challenging_numbers': [],
            'ideal_partners': [],
            'energy_compatibility': 'medium',
            'communication_compatibility': 'medium',
            'relationship_score': 70,
            'recommendations': [],
            'partner_types': []
        }

        # Совместимые числа по редуцированному первому числу
        reduced_first = self._reduction_with_masters(first_number)
        if reduced_first in self.compatibility_map:
            hints['compatible_numbers'] = self.compatibility_map[reduced_first]
        else:
            hints['compatible_numbers'] = [1, 2, 3]

        # Проблемные числа (только если не в compatible_numbers)
        if matrix_digits.get('1', 0) >= 3:
            if 1 not in hints['compatible_numbers']:
                hints['challenging_numbers'].append(1)
            hints['recommendations'].append("Learn compromise and flexibility in relationships")

        if matrix_digits.get('8', 0) >= 3:
            if 8 not in hints['compatible_numbers']:
                hints['challenging_numbers'].append(8)
            hints['recommendations'].append("Balance responsibility with personal freedom")

        if matrix_digits.get('4', 0) == 0:
            if 4 not in hints['compatible_numbers']:
                hints['challenging_numbers'].append(4)
            hints['recommendations'].append("Develop stability and patience")

        # Идеальные партнеры
        if fourth_number in self.partner_types:
            hints['ideal_partners'] = self.partner_types[fourth_number]
        else:
            hints['ideal_partners'] = ["Versatile personalities"]

        if first_number in self.partner_types:
            hints['partner_types'] = self.partner_types[first_number]

        # Энергетическая совместимость
        energy_count = matrix_digits.get('2', 0)
        if energy_count >= 3:
            hints['energy_compatibility'] = 'very_high'
            hints['relationship_score'] += 15
            hints['recommendations'].append("Your high energy attracts many partners")
        elif energy_count == 0:
            hints['energy_compatibility'] = 'low'
            hints['relationship_score'] -= 10
            hints['recommendations'].append("Need to develop energy exchange in relationships")
        elif energy_count == 1:
            hints['energy_compatibility'] = 'medium'
        else:
            hints['energy_compatibility'] = 'high'
            hints['relationship_score'] += 5

        # Коммуникативная совместимость
        interest_count = matrix_digits.get('3', 0)
        if interest_count >= 2:
            hints['communication_compatibility'] = 'high'
            hints['relationship_score'] += 10
        elif interest_count == 0:
            hints['communication_compatibility'] = 'low'
            hints['relationship_score'] -= 5

        # Дополнительные бонусы
        if matrix_digits.get('5', 0) >= 2:
            hints['relationship_score'] += 5

        if matrix_digits.get('6', 0) >= 2:
            hints['relationship_score'] += 10

        hints['relationship_score'] = max(30, min(95, hints['relationship_score']))

        return hints

    # ==================== ДОПОЛНИТЕЛЬНЫЕ РАСЧЕТЫ ====================

    def _get_additional_calculations(self, day: int, month: int, year: int,
                                     matrix_digits: Dict[str, int],
                                     matrix_3x3: List[List[int]],
                                     first_number: int,
                                     fourth_number: int,
                                     third_number: int) -> Dict[str, Any]:
        """
        Дополнительные нумерологические расчеты
        """
        # Число судьбы (по Александрову: редукция первого числа)
        destiny_number = self._reduction_with_masters(first_number)

        # Четвертое число (редуцированное третье)
        # Внимание: это НЕ число личности в классическом смысле!
        # Число личности рассчитывается из имени, но мы его не вычисляем
        personality_number = fourth_number

        # Число души (по Александрову: редукция дня рождения)
        soul_number = self._reduction_with_masters(day)

        # Число зрелости (по Александрову: судьба + четвертое число)
        maturity_number = self._reduction_with_masters(
            destiny_number + personality_number
        )

        # Пики жизни
        life_peaks = self._calculate_life_peaks(day, month, year)

        # Вызовы
        challenges = self._calculate_challenges(matrix_digits)

        # Кармические числа
        karmic_numbers = {13, 14, 16, 19}
        has_karmic = (first_number in karmic_numbers) or (third_number in karmic_numbers)

        return {
            'destiny_number': destiny_number,
            'personality_number': personality_number,
            'soul_number': soul_number,
            'maturity_number': maturity_number,
            'life_peaks': life_peaks,
            'challenges': challenges,
            'master_number_present': first_number in self.master_numbers,
            'karmic_number_present': has_karmic
        }

    def _calculate_life_peaks(self, day: int, month: int, year: int) -> List[Dict[str, Any]]:
        """
        Расчет 4 пиков жизни по методике Александрова:
        - Пик 1 (0-27 лет): месяц + день
        - Пик 2 (28-55 лет): день + год
        - Пик 3 (56-83 года): пик1 + пик2
        - Пик 4 (84+ лет): месяц + год
        """
        m = self._reduction_with_masters(month)
        d = self._reduction_with_masters(day)
        y = self._reduction_with_masters(year)

        peaks = []

        p1 = self._reduction_with_masters(m + d)
        peaks.append({
            'peak_number': p1,
            'period': '0-27 years',
            'description': self._get_peak_description(p1, 0)
        })

        p2 = self._reduction_with_masters(d + y)
        peaks.append({
            'peak_number': p2,
            'period': '28-55 years',
            'description': self._get_peak_description(p2, 1)
        })

        p3 = self._reduction_with_masters(p1 + p2)
        peaks.append({
            'peak_number': p3,
            'period': '56-83 years',
            'description': self._get_peak_description(p3, 2)
        })

        p4 = self._reduction_with_masters(m + y)
        peaks.append({
            'peak_number': p4,
            'period': '84+ years',
            'description': self._get_peak_description(p4, 3)
        })

        return peaks

    def _get_peak_description(self, peak_number: int, peak_index: int) -> str:
        """Получение описания пика"""
        descriptions = {
            1: "Leadership and independence",
            2: "Cooperation and relationships",
            3: "Creativity and expression",
            4: "Work and building foundations",
            5: "Freedom and change",
            6: "Responsibility and service",
            7: "Analysis and introspection",
            8: "Power and achievement",
            9: "Completion and transformation"
        }

        base_desc = descriptions.get(peak_number, "Growth and development")
        phases = ["Early", "Middle", "Late", "Final"]
        return f"{phases[peak_index]} peak: {base_desc}"

    def _calculate_challenges(self, matrix_digits: Dict[str, int]) -> List[Dict[str, Any]]:
        """Расчет жизненных вызовов (отсутствующие качества)"""
        challenges = []

        for digit in range(1, 10):
            if matrix_digits.get(str(digit), 0) == 0:
                char_name = self.digit_to_characteristic.get(digit, 'unknown')
                challenges.append({
                    'challenge_number': digit,
                    'challenge_area': char_name,
                    'challenge_description': self._get_challenge_description(digit)
                })

        return challenges

    def _get_challenge_description(self, digit: int) -> str:
        """Получение описания вызова"""
        descriptions = {
            1: "Develop independence and self-confidence",
            2: "Cultivate patience and cooperation",
            3: "Express creativity and communicate",
            4: "Build stability and discipline",
            5: "Embrace change and freedom",
            6: "Take responsibility and serve",
            7: "Trust intuition and seek wisdom",
            8: "Balance material and spiritual",
            9: "Let go and transform"
        }

        return descriptions.get(digit, "Integrate missing quality")

    # ==================== КАРМИЧЕСКИЙ АНАЛИЗ (АЛЕКСАНДРОВ) ====================

    def _get_karmic_analysis(self, matrix_digits: Dict[str, int],
                             first_number: int,
                             third_number: int) -> Dict[str, Any]:
        """
        Кармический анализ по методике Александрова
        """
        karmic_debt = self._calculate_karmic_debt(first_number, third_number)
        karmic_tasks = self._calculate_karmic_tasks(matrix_digits)
        past_lives = self._analyze_past_lives(matrix_digits)

        return {
            'karmic_debt': karmic_debt,
            'karmic_tasks': karmic_tasks,
            'past_lives': past_lives,
            'karmic_maturity': self._calculate_karmic_maturity(matrix_digits),
            'soul_age': self._calculate_soul_age(matrix_digits)
        }

    def _calculate_karmic_debt(self, first_number: int, third_number: int) -> List[Dict[str, Any]]:
        """
        Расчет кармического долга по Александрову
        Проверяем числа 13, 14, 16, 19 в первом и третьем числе
        """
        debts = []

        karmic_numbers = {
            13: "Overcoming laziness and developing discipline",
            14: "Learning balance and avoiding extremes",
            16: "Healing ego and practicing humility",
            19: "Developing independence with integrity"
        }

        if first_number in karmic_numbers:
            debts.append({
                'number': first_number,
                'source': 'first_number',
                'description': karmic_numbers[first_number],
                'severity': 'high'
            })

        if third_number in karmic_numbers:
            debts.append({
                'number': third_number,
                'source': 'third_number',
                'description': karmic_numbers[third_number],
                'severity': 'high'
            })

        return debts

    def _calculate_karmic_tasks(self, matrix_digits: Dict[str, int]) -> List[Dict[str, Any]]:
        """
        Расчет кармических задач по Александрову:
        - count = 0: качество отсутствует → нужно развить (кармически важно)
        - count = 1: качество слабое → зона роста (добавлено для практического использования)

        Примечание: в классической методологии Александрова кармическими
        задачами считаются только count=0. count=1 добавлены как зоны роста
        для более полного практического анализа.
        """
        tasks = []

        for digit in range(1, 10):
            count = matrix_digits.get(str(digit), 0)
            char_name = self.digit_to_characteristic.get(digit, 'quality')

            if count == 0:
                tasks.append({
                    'digit': digit,
                    'task': f"Develop {char_name}",
                    'priority': 'high',
                    'type': 'development'
                })
            elif count == 1:
                tasks.append({
                    'digit': digit,
                    'task': f"Strengthen {char_name}",
                    'priority': 'medium',
                    'type': 'strengthening'
                })

        return tasks

    def _analyze_past_lives(self, matrix_digits: Dict[str, int]) -> Dict[str, Any]:
        """Анализ прошлых жизней по Александрову"""
        total = sum(int(d) * count for d, count in matrix_digits.items())
        experience = total % 9 + 1

        past_life_archetypes = {
            1: "Leader, pioneer, innovator",
            2: "Diplomat, partner, mediator",
            3: "Artist, creator, communicator",
            4: "Builder, worker, organizer",
            5: "Explorer, adventurer, teacher",
            6: "Healer, caretaker, servant",
            7: "Mystic, scholar, recluse",
            8: "Executive, manager, power holder",
            9: "Humanitarian, philosopher, guide"
        }

        return {
            'archetype': past_life_archetypes.get(experience, "Diverse experiences"),
            'experience_level': self._get_experience_level(total),
            'past_life_number': experience
        }

    def _get_experience_level(self, total: int) -> str:
        """
        Уровень опыта души по Александрову
        """
        if total < 18:
            return "Young soul, new experiences"
        elif total < 22:
            return "Developing soul, learning"
        elif total < 26:
            return "Experienced soul, teaching"
        else:
            return "Old soul, wisdom keeper"

    def _calculate_karmic_maturity(self, matrix_digits: Dict[str, int]) -> int:
        """
        Кармическая зрелость по Александрову
        Формула: (total_digits / 27) * 100
        """
        total_digits = sum(matrix_digits.values())
        maturity = (total_digits / 27) * 100
        return int(round(min(max(maturity, 10), 100)))

    def _calculate_soul_age(self, matrix_digits: Dict[str, int]) -> str:
        """
        Возраст души по Александрову
        Определяется по сумме всех цифр матрицы
        """
        total_digits = sum(matrix_digits.values())

        if total_digits <= 7:
            return "Infant soul (0-7)"
        elif total_digits <= 13:
            return "Young soul (8-13)"
        elif total_digits <= 18:
            return "Mature soul (14-18)"
        elif total_digits <= 23:
            return "Advanced soul (19-23)"
        else:
            return "Ancient soul (24+)"

    # ==================== ПРОГНОСТИКА ====================

    def _get_forecasting_data(self, matrix_digits: Dict[str, int],
                              first_number: int,
                              fourth_number: int,
                              day: int,
                              month: int) -> Dict[str, Any]:
        """
        Прогностические данные

        Args:
            day: День рождения (для персональных годов)
            month: Месяц рождения (для персональных годов)
        """
        personal_years = self._calculate_personal_years(day, month)
        favorable_periods = self._calculate_favorable_periods(matrix_digits)
        growth_areas = self._identify_growth_areas(matrix_digits)

        return {
            'personal_years': personal_years,
            'favorable_periods': favorable_periods,
            'growth_areas': growth_areas,
            'current_cycle': self._determine_current_cycle(fourth_number),
            'recommendations': self._generate_recommendations(matrix_digits)
        }

    def _calculate_personal_years(self, day: int, month: int) -> List[Dict[str, Any]]:
        """
        Расчет персональных годов по методике Александрова
        Формула: день + месяц + год (все редуцируются)
        """
        current_year = datetime.now().year
        years = []

        for i in range(-2, 3):
            target_year = current_year + i
            # По Александрову: день + месяц + год
            year_num = self._reduction_with_masters(day + month + target_year)

            years.append({
                'year': target_year,
                'personal_year': year_num,
                'description': self._get_personal_year_description(year_num)
            })

        return years

    def _get_personal_year_description(self, year_num: int) -> str:
        """Описание персонального года"""
        descriptions = {
            1: "New beginnings, opportunities, independence",
            2: "Patience, cooperation, relationships",
            3: "Creativity, socializing, expression",
            4: "Work, building foundations, discipline",
            5: "Change, freedom, adventure",
            6: "Responsibility, family, service",
            7: "Rest, reflection, analysis",
            8: "Power, achievement, abundance",
            9: "Completion, release, transformation"
        }

        return descriptions.get(year_num, "Growth and learning")

    def _calculate_favorable_periods(self, matrix_digits: Dict[str, int]) -> List[Dict[str, Any]]:
        """Расчет благоприятных периодов"""
        periods = []

        if matrix_digits.get('1', 0) >= 2:
            periods.append({
                'area': 'Career and leadership',
                'favorable': True,
                'advice': 'Take initiative, start new projects'
            })

        if matrix_digits.get('2', 0) >= 2:
            periods.append({
                'area': 'Relationships and partnerships',
                'favorable': True,
                'advice': 'Build connections, collaborate'
            })

        if matrix_digits.get('3', 0) >= 2:
            periods.append({
                'area': 'Creativity and communication',
                'favorable': True,
                'advice': 'Express yourself, share ideas'
            })

        if matrix_digits.get('4', 0) >= 2:
            periods.append({
                'area': 'Health and stability',
                'favorable': True,
                'advice': 'Build routines, focus on wellness'
            })

        if matrix_digits.get('5', 0) >= 2:
            periods.append({
                'area': 'Travel and learning',
                'favorable': True,
                'advice': 'Explore, study, expand horizons'
            })

        return periods

    def _identify_growth_areas(self, matrix_digits: Dict[str, int]) -> List[Dict[str, Any]]:
        """Определение зон роста"""
        growth_areas = []

        for digit in range(1, 10):
            count = matrix_digits.get(str(digit), 0)
            if count == 0:
                growth_areas.append({
                    'digit': digit,
                    'area': self.digit_to_characteristic.get(digit, 'unknown'),
                    'potential': 'To be developed',
                    'suggestion': f'Focus on developing {self.digit_to_characteristic.get(digit, "this quality")}'
                })
            elif count == 1:
                growth_areas.append({
                    'digit': digit,
                    'area': self.digit_to_characteristic.get(digit, 'unknown'),
                    'potential': 'Strengthening',
                    'suggestion': f'Practice and reinforce {self.digit_to_characteristic.get(digit, "this quality")}'
                })

        return sorted(growth_areas, key=lambda x: x['digit'])

    def _determine_current_cycle(self, fourth_number: int) -> Dict[str, Any]:
        """Определение текущего жизненного цикла"""
        cycles = {
            1: "Cycle of Leadership and Innovation",
            2: "Cycle of Partnership and Harmony",
            3: "Cycle of Creativity and Expression",
            4: "Cycle of Building and Stability",
            5: "Cycle of Change and Freedom",
            6: "Cycle of Service and Responsibility",
            7: "Cycle of Analysis and Wisdom",
            8: "Cycle of Power and Achievement",
            9: "Cycle of Completion and Transformation"
        }

        return {
            'cycle_number': fourth_number,
            'cycle_name': cycles.get(fourth_number, "Growth Cycle"),
            'duration': '9 years',
            'focus': self.life_purpose_map.get(fourth_number, "Personal development")
        }

    def _generate_recommendations(self, matrix_digits: Dict[str, int]) -> List[str]:
        """Генерация рекомендаций"""
        recommendations = []

        missing = [d for d in range(1, 10) if matrix_digits.get(str(d), 0) == 0]
        if missing:
            missing_names = [self.digit_to_characteristic.get(d, 'quality') for d in missing]
            recommendations.append(
                f"Develop missing qualities: {', '.join(missing_names)}"
            )

        weak = [d for d in range(1, 10) if matrix_digits.get(str(d), 0) == 1]
        if weak:
            weak_names = [self.digit_to_characteristic.get(d, 'quality') for d in weak]
            recommendations.append(
                f"Strengthen developing qualities: {', '.join(weak_names)}"
            )

        strong = [d for d in range(1, 10) if matrix_digits.get(str(d), 0) >= 3]
        if strong:
            strong_names = [self.digit_to_characteristic.get(d, 'quality') for d in strong]
            recommendations.append(
                f"Balance overused qualities: {', '.join(strong_names)}"
            )

        total_digits = sum(matrix_digits.values())
        if total_digits < 10:
            recommendations.append("Focus on personal development and self-discovery")
        elif total_digits > 20:
            recommendations.append("Share your wisdom and experience with others")

        return recommendations[:5]

    @staticmethod
    @lru_cache(maxsize=1024)
    def calculate_matrix_static(birth_date: date) -> Dict[str, Any]:
        """
        Статический метод для вызова из сервисов без создания экземпляра
        """
        calculator = PsyhoMatrixCalculator()
        return calculator.calculate_matrix(birth_date)


# ==================== УТИЛИТЫ ДЛЯ РАБОТЫ С БД ====================

def validate_for_database(matrix_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Валидация данных перед вставкой в БД"""
    errors = []

    required_fields = [
        'first_number', 'second_number', 'third_number', 'fourth_number',
        'matrix_digits', 'characteristics', 'talent_codes', 'strength_codes',
        'energy_level', 'life_purpose', 'compatibility_hints',
        'additional', 'karmic_analysis', 'forecasting'
    ]

    for field in required_fields:
        if field not in matrix_data:
            errors.append(f"Missing required field: {field}")

    if 'first_number' in matrix_data:
        if not isinstance(matrix_data['first_number'], int):
            errors.append("first_number must be int")
        elif not (1 <= matrix_data['first_number'] <= 99):
            errors.append("first_number must be between 1 and 99")

    if 'matrix_digits' in matrix_data:
        if not isinstance(matrix_data['matrix_digits'], dict):
            errors.append("matrix_digits must be dict")
        else:
            for i in range(1, 10):
                key = str(i)
                if key not in matrix_data['matrix_digits']:
                    errors.append(f"matrix_digits missing key {key}")
                elif not isinstance(matrix_data['matrix_digits'][key], int):
                    errors.append(f"matrix_digits[{key}] must be int")
                elif matrix_data['matrix_digits'][key] < 0:
                    errors.append(f"matrix_digits[{key}] cannot be negative")

    if 'energy_level' in matrix_data:
        valid_levels = {'very_low', 'low', 'medium', 'high', 'very_high'}
        if matrix_data['energy_level'] not in valid_levels:
            errors.append(f"energy_level must be one of: {sorted(valid_levels)}")

    if 'talent_codes' in matrix_data:
        if not isinstance(matrix_data['talent_codes'], list):
            errors.append("talent_codes must be list")
        elif not matrix_data['talent_codes']:
            errors.append("talent_codes cannot be empty")
        elif not all(isinstance(t, str) for t in matrix_data['talent_codes']):
            errors.append("All talent_codes must be str")

    if 'life_purpose' in matrix_data:
        if not isinstance(matrix_data['life_purpose'], str):
            errors.append("life_purpose must be str")
        elif len(matrix_data['life_purpose']) > 1000:
            errors.append("life_purpose too long (max 1000 chars)")

    return len(errors) == 0, errors


def prepare_for_db_insert(matrix_data: Dict[str, Any]) -> Dict[str, Any]:
    """Подготовка данных для вставки в БД через SQLAlchemy"""
    prepared = matrix_data.copy()

    prepared['first_number'] = int(prepared['first_number'])
    prepared['second_number'] = int(prepared['second_number'])
    prepared['third_number'] = int(prepared['third_number'])
    prepared['fourth_number'] = int(prepared['fourth_number'])

    prepared['talent_codes'] = [str(t) for t in prepared['talent_codes']]
    prepared['strength_codes'] = [str(s) for s in prepared['strength_codes']]

    if 'matrix_3x3' in prepared:
        prepared['matrix_3x3'] = [
            [int(cell) for cell in row]
            for row in prepared['matrix_3x3']
        ]

    return prepared


# ==================== ФУНКЦИЯ ДЛЯ ПРЯМОГО ИСПОЛЬЗОВАНИЯ ====================

@lru_cache(maxsize=1024)
def calculate_psyho_matrix(birth_date: date) -> Dict[str, Any]:
    """
    Удобная функция для прямых вызовов с кэшированием
    """
    calculator = PsyhoMatrixCalculator()
    return calculator.calculate_matrix(birth_date)


# ==================== ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ ====================

def compare_matrices(matrix1: Dict[str, Any],
                     matrix2: Dict[str, Any]) -> Dict[str, Any]:
    """Сравнение двух матриц для анализа совместимости"""
    compatibility = {
        'overall_score': 0,
        'strengths': [],
        'challenges': [],
        'recommendations': []
    }

    calc = PsyhoMatrixCalculator()
    reduced1 = calc._reduction_with_masters(matrix1['first_number'])
    reduced2 = calc._reduction_with_masters(matrix2['first_number'])

    compat_map = COMPATIBILITY_MAP.get(reduced1, [])
    if reduced2 in compat_map:
        compatibility['overall_score'] += 30
        compatibility['strengths'].append("Natural compatibility")

    energy1 = matrix1['energy_level']
    energy2 = matrix2['energy_level']
    energy_levels = ['very_low', 'low', 'medium', 'high', 'very_high']

    try:
        energy_diff = abs(energy_levels.index(energy1) - energy_levels.index(energy2))
        if energy_diff <= 1:
            compatibility['overall_score'] += 20
            compatibility['strengths'].append("Balanced energy exchange")
        elif energy_diff >= 3:
            compatibility['overall_score'] -= 10
            compatibility['challenges'].append("Energy imbalance")
    except ValueError:
        pass

    purpose1 = matrix1['fourth_number']
    purpose2 = matrix2['fourth_number']

    if purpose1 == purpose2:
        compatibility['overall_score'] += 20
        compatibility['strengths'].append("Shared life purpose")
    elif abs(purpose1 - purpose2) in [1, 8]:
        compatibility['overall_score'] += 10
        compatibility['strengths'].append("Complementary paths")

    talents1 = set(matrix1['talent_codes'])
    talents2 = set(matrix2['talent_codes'])

    common_talents = talents1.intersection(talents2)
    if common_talents:
        compatibility['overall_score'] += len(common_talents) * 5
        compatibility['strengths'].append(f"Shared talents: {len(common_talents)} areas")

    compatibility['overall_score'] = max(0, min(100, compatibility['overall_score']))

    if compatibility['overall_score'] >= 70:
        compatibility['recommendations'].append("Strong potential for harmonious relationship")
    elif compatibility['overall_score'] >= 50:
        compatibility['recommendations'].append("Good foundation, requires work")
    else:
        compatibility['recommendations'].append("Need understanding and compromise")

    return compatibility


# ==================== UNIT-ТЕСТЫ ====================

def run_tests():
    """Запуск тестов для проверки ключевых кейсов"""
    calculator = PsyhoMatrixCalculator()
    test_results = []

    # Тест 1: Базовые числа для 1973-10-16
    result = calculator.calculate_matrix(date(1973, 10, 16))
    test_results.append({
        'test': 'Base numbers for 1973-10-16',
        'passed': (
                result['first_number'] == 28 and
                result['second_number'] == 10 and
                result['third_number'] == 26 and
                result['fourth_number'] == 8
        ),
        'note': f"first={result['first_number']}, second={result['second_number']}, third={result['third_number']}, fourth={result['fourth_number']}"
    })

    # Тест 2: Кармический долг
    test_results.append({
        'test': 'Karmic debt check',
        'passed': result['karmic_analysis']['karmic_debt'] == [],
        'note': 'No karmic debt for 28/26'
    })

    # Тест 3: Энергетический уровень (только по двойкам)
    test_results.append({
        'test': 'Energy level (only by twos)',
        'passed': result['energy_level'] == 'high',
        'note': f"Energy level: {result['energy_level']}"
    })

    # Тест 4: Кармическая зрелость (формула Александрова)
    test_results.append({
        'test': 'Karmic maturity (total_digits/27*100)',
        'passed': result['karmic_analysis']['karmic_maturity'] == 48,
        'note': f"Maturity: {result['karmic_analysis']['karmic_maturity']}"
    })

    # Тест 5: Предназначение по третьему числу
    test_results.append({
        'test': 'Life purpose by third_number',
        'passed': 'Material achievement' in result['life_purpose'],
        'note': f"Purpose: {result['life_purpose'][:50]}..."
    })

    # Тест 6: Число души = день рождения
    test_results.append({
        'test': 'Soul number = birth day',
        'passed': result['additional']['soul_number'] == 7,
        'note': f"Soul number: {result['additional']['soul_number']}"
    })

    # Тест 7: Персональные годы (формула Александрова)
    test_results.append({
        'test': 'Personal years formula (day+month+year)',
        'passed': result['forecasting']['personal_years'][0]['personal_year'] == 7,
        'note': f"2024 personal year: {result['forecasting']['personal_years'][0]['personal_year']}"
    })

    # Вывод результатов
    print("\n=== TEST RESULTS ===")
    all_passed = True
    for i, test in enumerate(test_results, 1):
        status = "✅ PASSED" if test['passed'] else "❌ FAILED"
        print(f"{i}. {status} | {test['test']}")
        print(f"   Note: {test['note']}")
        if not test['passed']:
            all_passed = False

    print(f"\n{'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    return all_passed


if __name__ == "__main__":
    run_tests()
