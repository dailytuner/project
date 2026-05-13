"""
recommendation_generator.py - Генератор персонализированных рекомендаций
Версия 1.0 - Production Ready

На основе дневного прогноза (9 осей) и дополнительных факторов генерирует:
1. Персональные советы по активности (что делать / чего избегать)
2. Финансовые рекомендации
3. Бытовые рекомендации (стрижка, поездки, документы)
4. Рекомендации по здоровью и отдыху
5. Социальные рекомендации

Выход: структурированный набор рекомендаций для пользователя
"""

import logging
from datetime import date, datetime, time, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================
# ТИПЫ РЕКОМЕНДАЦИЙ
# ============================================================

class RecommendationCategory(str, Enum):
    """Категории рекомендаций"""
    ACTIVITY = "activity"
    FINANCE = "finance"
    HEALTH = "health"
    SOCIAL = "social"
    HOUSEHOLD = "household"
    WORK = "work"
    REST = "rest"
    SPIRITUAL = "spiritual"


class RecommendationPriority(int, Enum):
    """Приоритет рекомендации"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Recommendation:
    """Одна рекомендация"""
    category: RecommendationCategory
    priority: RecommendationPriority
    title: str
    content: str
    action_items: List[str] = field(default_factory=list)
    avoid_items: List[str] = field(default_factory=list)
    best_time: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'category': self.category.value,
            'priority': self.priority.value,
            'title': self.title,
            'content': self.content,
            'action_items': self.action_items,
            'avoid_items': self.avoid_items,
            'best_time': self.best_time
        }


@dataclass
class RecommendationSet:
    """Набор рекомендаций на день"""
    date: date
    user_id: int
    recommendations: List[Recommendation]
    summary: str
    daily_motto: str

    def to_dict(self) -> Dict:
        return {
            'date': self.date.isoformat(),
            'user_id': self.user_id,
            'recommendations': [r.to_dict() for r in self.recommendations],
            'summary': self.summary,
            'daily_motto': self.daily_motto
        }


# ============================================================
# БАЗА ПРАВИЛ ДЛЯ РЕКОМЕНДАЦИЙ
# ============================================================

# Правила для рекомендаций на основе значений осей
# Структура: (ось, порог, тип_изменения) -> рекомендация
AXIS_RECOMMENDATIONS = {
    # ЭНЕРГИЯ
    ('energy_will', 0.7, 'high'): {
        'title': '🔥 Высокая энергия — действуй!',
        'content': 'Сегодня ты полон сил и энергии. Это отличное время для активных действий.',
        'action': ['Начни новый проект', 'Займись спортом', 'Сделай то, что давно откладывал'],
        'avoid': ['Сиди без дела', 'Трать время на бесполезные занятия']
    },
    ('energy_will', 0.4, 'low'): {
        'title': '😴 Энергия на спаде — отдохни',
        'content': 'Сегодня энергия ниже обычного. Не перегружай себя, дай организму восстановиться.',
        'action': ['Отдохни', 'Поспи днём', 'Займись спокойными делами'],
        'avoid': ['Берись за сложные проекты', 'Конфликтуй', 'Переутомляйся']
    },

    # ИНТЕЛЛЕКТ
    ('intellect_logic', 0.7, 'high'): {
        'title': '🧠 Интеллект на пике — учись и решай!',
        'content': 'Сегодня твой ум работает особенно хорошо. Используй это для сложных задач.',
        'action': ['Учись новому', 'Решай сложные задачи', 'Планируй стратегию'],
        'avoid': ['Занимайся рутиной', 'Откладывай важные решения']
    },
    ('intellect_logic', 0.4, 'low'): {
        'title': '📚 Интеллект снижен — не берись за сложное',
        'content': 'Сегодня концентрация ниже обычного. Отложи сложные умственные задачи.',
        'action': ['Занимайся привычными делами', 'Отдыхай', 'Перепроверяй информацию'],
        'avoid': ['Принимай важные решения', 'Учись новому', 'Работай с цифрами']
    },

    # ЭМОЦИИ
    ('emotions_intuition', 0.7, 'high'): {
        'title': '💖 Эмоции на подъёме — твори и общайся!',
        'content': 'Сегодня ты особенно чувствителен и восприимчив. Доверяй своей интуиции.',
        'action': ['Занимайся творчеством', 'Общайся с близкими', 'Доверяй интуиции'],
        'avoid': ['Принимай холодные решения', 'Игнорируй свои чувства']
    },
    ('emotions_intuition', 0.4, 'low'): {
        'title': '🌊 Эмоциональный спад — береги нервы',
        'content': 'Сегодня эмоциональный фон снижен. Не принимай важных решений на эмоциях.',
        'action': ['Медитируй', 'Побудь в тишине', 'Занимайся дыхательными практиками'],
        'avoid': ['Ссоры и конфликты', 'Важные разговоры', 'Спонтанные решения']
    },

    # ДИСЦИПЛИНА
    ('work_discipline', 0.7, 'high'): {
        'title': '📋 Дисциплина на высоте — разгребай долги!',
        'content': 'Сегодня ты особенно организован. Отличное время для рутинных дел.',
        'action': ['Закрывай долги', 'Наводи порядок', 'Завершай начатое'],
        'avoid': ['Прокрастинируй', 'Откладывай дела на потом']
    },
    ('work_discipline', 0.4, 'low'): {
        'title': '😌 Дисциплина снижена — не планируй много',
        'content': 'Сегодня сложно заставить себя делать то, что нужно. Не планируй много дел.',
        'action': ['Делай только самое необходимое', 'Делегируй', 'Отдыхай'],
        'avoid': ['Берись за много дел', 'Ставь жёсткие дедлайны']
    },

    # СОЦИУМ
    ('social_relations', 0.7, 'high'): {
        'title': '👥 Социум настроен на общение — заводи знакомства!',
        'content': 'Сегодня ты особенно привлекателен для окружающих. Используй это.',
        'action': ['Общайся', 'Заводи новые знакомства', 'Иди на встречи'],
        'avoid': ['Изолируй себя', 'Отказывайся от приглашений']
    },
    ('social_relations', 0.4, 'low'): {
        'title': '🏠 Социальная активность снижена — побудь один',
        'content': 'Сегодня лучше побыть в одиночестве. Не форсируй общение.',
        'action': ['Побудь один', 'Займись собой', 'Избегай шумных мероприятий'],
        'avoid': ['Конфликты', 'Важные переговоры', 'Шумные компании']
    },

    # УДАЧА
    ('luck_talent', 0.7, 'high'): {
        'title': '🍀 Удача на твоей стороне — рискуй!',
        'content': 'Сегодня звёзды благоволят тебе. Можно рисковать и пробовать новое.',
        'action': ['Начинай новые проекты', 'Пробуй что-то новое', 'Рискуй в разумных пределах'],
        'avoid': ['Бойся перемен', 'Упускай возможности']
    },
    ('luck_talent', 0.4, 'low'): {
        'title': '⚠️ Удача не на твоей стороне — не рискуй',
        'content': 'Сегодня лучше не рисковать. Отложи важные решения и инвестиции.',
        'action': ['Будь осторожен', 'Перепроверяй информацию', 'Не торопись'],
        'avoid': ['Крупные траты', 'Азартные игры', 'Спонтанные решения']
    },

    # ЗДОРОВЬЕ
    ('health_physical', 0.7, 'high'): {
        'title': '💪 Здоровье отличное — занимайся спортом!',
        'content': 'Сегодня ты в хорошей физической форме. Используй это для активности.',
        'action': ['Занимайся спортом', 'Закаляйся', 'Больше двигайся'],
        'avoid': ['Лежи на диване', 'Переедай']
    },
    ('health_physical', 0.4, 'low'): {
        'title': '🩺 Здоровье требует внимания — береги себя',
        'content': 'Сегодня организм уязвимее обычного. Удели внимание профилактике.',
        'action': ['Отдыхай', 'Больше спи', 'Пей воду', 'Ешь здоровую пищу'],
        'avoid': ['Переутомляйся', 'Алкоголь', 'Вредную еду']
    },

    # КАРМА
    ('karma_cycles', 0.7, 'high'): {
        'title': '🪷 Кармический период — завершай старое',
        'content': 'Сегодня благоприятное время для завершения долгов и кармических задач.',
        'action': ['Завершай старые дела', 'Прощай обиды', 'Анализируй прошлое'],
        'avoid': ['Начинай важное', 'Забывай о прошлом']
    },
    ('karma_cycles', 0.4, 'low'): {
        'title': '🌀 Кармический кризис — будь внимателен',
        'content': 'Сегодня могут проявляться кармические уроки. Будь внимателен к знакам.',
        'action': ['Анализируй ситуации', 'Будь честен с собой', 'Не избегай проблем'],
        'avoid': ['Игнорируй знаки', 'Повторяй старые ошибки']
    },

    # МИССИЯ
    ('destiny_mission', 0.7, 'high'): {
        'title': '⭐ Время предназначения — действуй!',
        'content': 'Сегодня ты чувствуешь свою миссию особенно ярко. Следуй за зовом сердца.',
        'action': ['Следуй своей мечте', 'Делай то, что предназначено', 'Доверяй себе'],
        'avoid': ['Игнорируй своё призвание', 'Делай что-то против воли']
    },
    ('destiny_mission', 0.4, 'low'): {
        'title': '🗺️ Поиск пути — анализируй, не форсируй',
        'content': 'Сегодня неясно, куда двигаться. Не форсируй поиск миссии.',
        'action': ['Анализируй', 'Наблюдай', 'Копи энергию'],
        'avoid': ['Принимай судьбоносные решения', 'Паникуй']
    },
}

# Финансовые рекомендации
FINANCIAL_RECOMMENDATIONS = {
    'very_favorable': {
        'title': '💰 Отличный день для финансов',
        'content': 'Транзиты благоприятствуют финансовым операциям.',
        'action': ['Инвестируй', 'Открывай депозиты', 'Ведди переговоры о зарплате'],
        'avoid': ['Храни деньги под матрасом']
    },
    'favorable': {
        'title': '💵 Хороший день для финансов',
        'content': 'Сегодня можно заниматься финансовыми вопросами, но осторожно.',
        'action': ['Планируй бюджет', 'Оплачивай счета', 'Делай умеренные покупки'],
        'avoid': ['Крупные вложения', 'Рискованные инвестиции']
    },
    'neutral': {
        'title': '📊 Нейтральный день для финансов',
        'content': 'Ничего особенного в финансах сегодня не ожидается.',
        'action': ['Веди обычные расходы', 'Не рискуй'],
        'avoid': ['Крупные финансовые операции']
    },
    'unfavorable': {
        'title': '⚠️ Неблагоприятный день для финансов',
        'content': 'Сегодня лучше воздержаться от серьёзных финансовых решений.',
        'action': ['Контролируй расходы', 'Планируй, но не действуй'],
        'avoid': ['Траты', 'Инвестиции', 'Кредиты']
    },
}

# Лунные дни для стрижки
MOON_PHASE_FOR_HAIRCUT = {
    'new': {
        'verdict': '🛑 НЕ БЛАГОПРИЯТНО',
        'advice': 'В новолуние лучше не стричься — волосы могут расти медленно'
    },
    'first_quarter': {
        'verdict': '✅ БЛАГОПРИЯТНО',
        'advice': 'Стрижка на растущей Луне ускорит рост волос'
    },
    'full': {
        'verdict': '⚠️ НЕЙТРАЛЬНО',
        'advice': 'В полнолуние стрижка не повредит, но и пользы особой не будет'
    },
    'last_quarter': {
        'verdict': '✅ ХОРОШО',
        'advice': 'Стрижка на убывающей Луне укрепит корни волос'
    },
}

# Накшатры для стрижки (благоприятные)
GOOD_NAKSHATRAS_FOR_HAIRCUT = {
    'Ashwini', 'Mrigashira', 'Pushya', 'Uttara Phalguni',
    'Hasta', 'Swati', 'Anuradha', 'Uttara Ashadha', 'Shravana', 'Revati'
}

# Накшатры для поездок
GOOD_NAKSHATRAS_FOR_TRAVEL = {
    'Ashwini', 'Mrigashira', 'Pushya', 'Uttara Phalguni',
    'Hasta', 'Swati', 'Anuradha', 'Uttara Ashadha', 'Shravana', 'Revati',
    'Punarvasu', 'Vishakha'
}

# Благоприятные титхи для дел
GOOD_TITHIS = [2, 3, 5, 7, 10, 11, 13]  # 2-й, 3-й, 5-й, 7-й, 10-й, 11-й, 13-й

# ============================================================
# РЕКОМЕНДАЦИИ ДЛЯ VOID MOON
# ============================================================

VOID_MOON_ADVICE = {
    'action': ['Завершай текущие дела', 'Занимайся рутиной', 'Отдыхай'],
    'avoid': ['Начинай новые проекты', 'Важные переговоры', 'Покупай что-то важное'],
    'note': 'Луна без курса — время не для начинаний, а для завершений'
}

# ============================================================
# ЕЖЕДНЕВНЫЕ ДЕВИЗЫ
# ============================================================

DAILY_MOTTOS = [
    "Сегодня лучший день, чтобы начать!",
    "Маленькие шаги ведут к большим целям.",
    "Будь настоящим здесь и сейчас.",
    "Доверяй своей интуиции.",
    "Действуй, даже если страшно.",
    "Улыбнись новому дню!",
    "Ты сильнее, чем думаешь.",
    "Сделай то, что делает тебя счастливым.",
    "Сегодня ты можешь всё!",
    "Просто начни, а продолжение придёт само.",
]


# ============================================================
# ОСНОВНОЙ КЛАСС ГЕНЕРАТОРА
# ============================================================

class RecommendationGenerator:
    """
    Генератор персонализированных рекомендаций на основе прогноза
    """

    def __init__(self):
        self._axis_recommendations = AXIS_RECOMMENDATIONS
        self._financial_recs = FINANCIAL_RECOMMENDATIONS
        self._daily_mottos = DAILY_MOTTOS

    def _generate_dasha_recommendation(self, dasha_info: Dict) -> Optional[Recommendation]:
        """Генерирует рекомендацию на основе даша-периода"""
        mahadasha = dasha_info.get('mahadasha')

        if not mahadasha:
            return None

        dasha_advice = {
            'Sun': {'title': '☀️ Период Солнца', 'advice': 'Время лидерства и самореализации. Проявляй инициативу.'},
            'Moon': {'title': '🌙 Период Луны', 'advice': 'Время эмоций и заботы. Удели внимание семье и дому.'},
            'Mars': {'title': '🔥 Период Марса',
                     'advice': 'Время энергии и действия. Занимайся спортом, берись за сложное.'},
            'Mercury': {'title': '📝 Период Меркурия',
                        'advice': 'Время обучения и общения. Учись, общайся, веди переговоры.'},
            'Jupiter': {'title': '⭐ Период Юпитера',
                        'advice': 'Время удачи и расширения. Начинай новые проекты, инвестируй.'},
            'Venus': {'title': '💖 Период Венеры', 'advice': 'Время любви и творчества. Удели внимание отношениям.'},
            'Saturn': {'title': '⛰️ Период Сатурна',
                       'advice': 'Время дисциплины и работы. Будь терпелив, выполняй обязанности.'},
            'Rahu': {'title': '🌀 Период Раху', 'advice': 'Время неожиданностей. Будь внимателен, избегай риска.'},
            'Ketu': {'title': '🌀 Период Кету', 'advice': 'Время духовного поиска. Медитируй, анализируй прошлое.'},
        }

        advice = dasha_advice.get(mahadasha)
        if not advice:
            return None

        return Recommendation(
            category=RecommendationCategory.SPIRITUAL,
            priority=RecommendationPriority.MEDIUM,
            title=advice['title'],
            content=advice['advice'],
            action_items=[],
            avoid_items=[]
        )

    def generate_recommendations(
            self,
            user_id: int,
            forecast_date: date,
            axes_values: Dict[str, Dict[str, float]],  # {axis_name: {'daily': value, 'delta': delta}}
            moon_info: Optional[Dict] = None,
            financial_score: Optional[float] = None,
            #panchanga: Optional[Panchanga] = None,
            panchanga: Optional[Dict] = None,
            dasha_info: Optional[Dict] = None,
            void_moon: bool = False,
            user_language: str = 'ru'
    ) -> RecommendationSet:
        """
        Сгенерировать полный набор рекомендаций

        Args:
            user_id: ID пользователя
            forecast_date: Дата прогноза
            axes_values: Значения осей (daily, delta)
            moon_info: Информация о Луне (фаза, накшатра)
            financial_score: Финансовый балл (0-1)
            panchanga: Информация о панчанге (титхи, накшатра)
            void_moon: Признак "Луны без курса"
            user_language: Язык рекомендаций ('ru' или 'en')

        Returns:
            RecommendationSet с рекомендациями
        """
        recommendations = []

        # 1. Рекомендации по осям (основные)
        axis_recs = self._generate_axis_recommendations(axes_values)
        recommendations.extend(axis_recs)

        # 2. Финансовые рекомендации
        financial_rec = self._generate_financial_recommendation(financial_score)
        if financial_rec:
            recommendations.append(financial_rec)

        # 3. Рекомендации при Void Moon
        if void_moon:
            void_rec = self._generate_void_moon_recommendation()
            recommendations.append(void_rec)

        # Добавить рекомендации на основе даша
        if dasha_info and dasha_info.get('mahadasha'):
            dasha_rec = self._generate_dasha_recommendation(dasha_info)
            if dasha_rec:
                recommendations.append(dasha_rec)

        # 4. Рекомендации по стрижке (бытовые)
        if panchanga:
            # Используем уже существующие методы панчанги
            starting_rec = panchanga.get_suitability_for_starting()
            if starting_rec['level'] in ['excellent', 'good']:
                recommendations.append(Recommendation(
                    category=RecommendationCategory.ACTIVITY,
                    priority=RecommendationPriority.HIGH if starting_rec[
                                                                'level'] == 'excellent' else RecommendationPriority.MEDIUM,
                    title="✨ Благоприятный день для начинаний",
                    content=starting_rec['advice'],
                    action_items=["Начинай новые проекты", "Принимай важные решения"],
                    avoid_items=[]
                ))

        # 5. Общие рекомендации по здоровью
        health_rec = self._generate_health_recommendation(axes_values)
        if health_rec:
            recommendations.append(health_rec)

        # 6. Социальные рекомендации
        social_rec = self._generate_social_recommendation(axes_values)
        if social_rec:
            recommendations.append(social_rec)

        # 7. Рекомендации по отдыху
        rest_rec = self._generate_rest_recommendation(axes_values)
        if rest_rec:
            recommendations.append(rest_rec)

        # Сортируем по приоритету
        recommendations.sort(key=lambda x: x.priority.value, reverse=True)

        # Генерируем сводку и девиз
        summary = self._generate_summary(axes_values, moon_info, void_moon)
        motto = self._get_daily_motto()

        return RecommendationSet(
            date=forecast_date,
            user_id=user_id,
            recommendations=recommendations,
            summary=summary,
            daily_motto=motto
        )

    def _generate_axis_recommendations(
            self,
            axes_values: Dict[str, Dict[str, float]]
    ) -> List[Recommendation]:
        """Генерирует рекомендации на основе значений осей"""
        recommendations = []

        for axis_name, data in axes_values.items():
            daily_value = data.get('daily', 0.5)
            delta = data.get('delta', 0.0)

            # Определяем состояние
            if daily_value >= 0.7:
                state = 'high'
            elif daily_value <= 0.4:
                state = 'low'
            else:
                continue  # Нейтральное состояние — не добавляем рекомендацию

            # Ищем правило
            rule_key = (axis_name, 0.7 if state == 'high' else 0.4, state)
            rule = self._axis_recommendations.get(rule_key)

            if rule:
                recommendations.append(Recommendation(
                    category=RecommendationCategory.ACTIVITY,
                    priority=RecommendationPriority.HIGH if state == 'low' else RecommendationPriority.MEDIUM,
                    title=rule['title'],
                    content=rule['content'],
                    action_items=rule.get('action', []),
                    avoid_items=rule.get('avoid', [])
                ))

        return recommendations

    def _generate_financial_recommendation(
            self,
            financial_score: Optional[float] = None
    ) -> Optional[Recommendation]:
        """Генерирует финансовую рекомендацию"""
        if financial_score is None:
            return None

        if financial_score >= 0.8:
            level = 'very_favorable'
        elif financial_score >= 0.6:
            level = 'favorable'
        elif financial_score >= 0.4:
            level = 'neutral'
        else:
            level = 'unfavorable'

        rule = self._financial_recs.get(level)
        if not rule:
            return None

        return Recommendation(
            category=RecommendationCategory.FINANCE,
            priority=RecommendationPriority.HIGH if level == 'very_favorable' else RecommendationPriority.MEDIUM,
            title=rule['title'],
            content=rule['content'],
            action_items=rule.get('action', []),
            avoid_items=rule.get('avoid', [])
        )

    def _generate_void_moon_recommendation(self) -> Recommendation:
        """Генерирует рекомендацию при пустой Луне"""
        return Recommendation(
            category=RecommendationCategory.ACTIVITY,
            priority=RecommendationPriority.HIGH,
            title="🌙 Луна без курса — время завершений",
            content=VOID_MOON_ADVICE['note'],
            action_items=VOID_MOON_ADVICE.get('action', []),
            avoid_items=VOID_MOON_ADVICE.get('avoid', [])
        )

    def _generate_haircut_recommendation(
            self,
            panchanga: Dict
    ) -> Optional[Recommendation]:
        """Генерирует рекомендацию по стрижке"""
        # Получаем информацию о Луне и накшатре
        moon_phase = panchanga.get('moon_phase', '')
        nakshatra = panchanga.get('nakshatra', '')

        if not moon_phase:
            return None

        # Благоприятность накшатры
        nakshatra_good = nakshatra in GOOD_NAKSHATRAS_FOR_HAIRCUT

        # Определяем рекомендацию
        phase_advice = MOON_PHASE_FOR_HAIRCUT.get(moon_phase, MOON_PHASE_FOR_HAIRCUT.get('full'))

        if nakshatra_good and moon_phase in ['first_quarter', 'last_quarter']:
            title = "✂️ Отличный день для стрижки!"
            content = f"{phase_advice['advice']} Накшатра {nakshatra} также благоприятна."
            action_items = ["Смело иди к парикмахеру"]
            priority = RecommendationPriority.HIGH
        elif nakshatra_good or moon_phase in ['first_quarter', 'last_quarter']:
            title = "✂️ Стрижка возможна"
            content = f"{phase_advice['advice']} Накшатра {nakshatra} {'благоприятна' if nakshatra_good else 'нейтральна'}."
            action_items = ["Стрижка допустима, но не обязательна"]
            priority = RecommendationPriority.MEDIUM
        else:
            title = "✂️ Стрижку лучше отложить"
            content = phase_advice['advice']
            action_items = ["Подожди более благоприятного дня"]
            priority = RecommendationPriority.MEDIUM

        return Recommendation(
            category=RecommendationCategory.HOUSEHOLD,
            priority=priority,
            title=title,
            content=content,
            action_items=action_items,
            avoid_items=[] if "отложить" not in title else ["Стрижка сегодня не рекомендуется"]
        )

    def _generate_travel_recommendation(
            self,
            panchanga: Dict
    ) -> Optional[Recommendation]:
        """Генерирует рекомендацию по поездкам"""
        nakshatra = panchanga.get('nakshatra', '')
        tithi = panchanga.get('tithi', 0)

        if not nakshatra:
            return None

        # Проверяем благоприятность
        travel_good = nakshatra in GOOD_NAKSHATRAS_FOR_TRAVEL
        tithi_good = tithi in GOOD_TITHIS

        if travel_good and tithi_good:
            return Recommendation(
                category=RecommendationCategory.HOUSEHOLD,
                priority=RecommendationPriority.HIGH,
                title="✈️ Благоприятный день для поездок",
                content="Накшатра и лунный день благоприятствуют путешествиям.",
                action_items=["Можно планировать поездки", "Дорога будет удачной"],
                avoid_items=[]
            )
        elif travel_good or tithi_good:
            return Recommendation(
                category=RecommendationCategory.HOUSEHOLD,
                priority=RecommendationPriority.MEDIUM,
                title="🚗 Поездки возможны",
                content="День нейтрален для поездок. Будь внимателен на дороге.",
                action_items=["Поездки допустимы, но без спешки"],
                avoid_items=["Не планируй важные переезды"]
            )
        else:
            return Recommendation(
                category=RecommendationCategory.HOUSEHOLD,
                priority=RecommendationPriority.MEDIUM,
                title="🚫 Поездки не рекомендуются",
                content="Сегодня не лучший день для путешествий.",
                action_items=["Отложи поездки", "Будь особенно внимателен на дороге"],
                avoid_items=["Дальние поездки", "Командировки"]
            )

    def _generate_health_recommendation(
            self,
            axes_values: Dict[str, Dict[str, float]]
    ) -> Optional[Recommendation]:
        """Генерирует рекомендацию по здоровью на основе оси health_physical"""
        health_data = axes_values.get('health_physical', {})
        health_value = health_data.get('daily', 0.5)

        if health_value <= 0.4:
            return Recommendation(
                category=RecommendationCategory.HEALTH,
                priority=RecommendationPriority.HIGH,
                title="🩺 Здоровье требует внимания",
                content="Сегодня организм более уязвим. Удели внимание профилактике.",
                action_items=["Больше отдыхай", "Пей больше воды", "Ешь лёгкую пищу"],
                avoid_items=["Переутомляйся", "Алкоголь", "Острую и тяжёлую пищу"]
            )
        elif health_value >= 0.7:
            return Recommendation(
                category=RecommendationCategory.HEALTH,
                priority=RecommendationPriority.LOW,
                title="💪 Здоровье отличное",
                content="Сегодня ты в хорошей форме. Можно заниматься спортом.",
                action_items=["Спорт", "Прогулка на свежем воздухе", "Закаливание"],
                avoid_items=[]
            )

        return None

    def _generate_social_recommendation(
            self,
            axes_values: Dict[str, Dict[str, float]]
    ) -> Optional[Recommendation]:
        """Генерирует социальную рекомендацию"""
        social_data = axes_values.get('social_relations', {})
        social_value = social_data.get('daily', 0.5)

        if social_value >= 0.7:
            return Recommendation(
                category=RecommendationCategory.SOCIAL,
                priority=RecommendationPriority.MEDIUM,
                title="👥 Отличный день для общения",
                content="Твоя социальная привлекательность на высоте. Заводи новые знакомства.",
                action_items=["Встречайся с друзьями", "Посети мероприятие", "Заведи новые знакомства"],
                avoid_items=["Сиди дома в одиночестве"]
            )
        elif social_value <= 0.4:
            return Recommendation(
                category=RecommendationCategory.SOCIAL,
                priority=RecommendationPriority.MEDIUM,
                title="🏠 День для одиночества",
                content="Лучше провести время наедине с собой или с самыми близкими.",
                action_items=["Займись собой", "Читай", "Медитируй"],
                avoid_items=["Большие компании", "Конфликты", "Шумные мероприятия"]
            )

        return None

    def _generate_rest_recommendation(
            self,
            axes_values: Dict[str, Dict[str, float]]
    ) -> Optional[Recommendation]:
        """Генерирует рекомендацию по отдыху"""
        energy_data = axes_values.get('energy_will', {})
        energy_value = energy_data.get('daily', 0.5)

        work_data = axes_values.get('work_discipline', {})
        work_value = work_data.get('daily', 0.5)

        if energy_value <= 0.4 or work_value <= 0.4:
            return Recommendation(
                category=RecommendationCategory.REST,
                priority=RecommendationPriority.MEDIUM,
                title="😴 Сегодня лучше отдохнуть",
                content="Организм сигнализирует о необходимости восстановления.",
                action_items=["Поспи днём", "Прими ванну", "Гуляй в парке"],
                avoid_items=["Перерабатывай", "Игнорируй усталость"]
            )

        return None

    def _generate_summary(
            self,
            axes_values: Dict[str, Dict[str, float]],
            moon_info: Optional[Dict],
            void_moon: bool
    ) -> str:
        """Генерирует краткую сводку дня"""
        # Находим самые высокие и низкие оси
        axes_list = []
        for name, data in axes_values.items():
            axes_list.append((name, data.get('daily', 0.5)))

        axes_list.sort(key=lambda x: x[1], reverse=True)

        top_axis = axes_list[0][0] if axes_list else None
        bottom_axis = axes_list[-1][0] if axes_list else None

        # Переводим названия осей на русский
        axis_names_ru = {
            'energy_will': 'энергия',
            'health_physical': 'здоровье',
            'intellect_logic': 'интеллект',
            'emotions_intuition': 'эмоции',
            'work_discipline': 'дисциплина',
            'luck_talent': 'удача',
            'social_relations': 'социум',
            'karma_cycles': 'карма',
            'destiny_mission': 'миссия',
        }

        top_name = axis_names_ru.get(top_axis, top_axis) if top_axis else ''
        bottom_name = axis_names_ru.get(bottom_axis, bottom_axis) if bottom_axis else ''

        # Формируем сводку
        if top_axis and bottom_axis and top_axis != bottom_axis:
            summary = f"Сегодня пик {top_name} ({axes_list[0][1]:.0%}), но понижена {bottom_name} ({axes_list[-1][1]:.0%})"
        elif top_axis:
            summary = f"Сегодня особенно высока {top_name} ({axes_list[0][1]:.0%})"
        else:
            summary = "Сегодня все системы в балансе"

        # Добавляем про Луну
        if moon_info and moon_info.get('phase'):
            phase_ru = {
                'new': 'новолуние',
                'first_quarter': 'растущая Луна',
                'full': 'полнолуние',
                'last_quarter': 'убывающая Луна'
            }.get(moon_info.get('phase', ''), '')
            if phase_ru:
                summary += f", {phase_ru}"

        if void_moon:
            summary += " (Луна без курса — не начинай важного)"

        return summary

    def _get_daily_motto(self) -> str:
        """Возвращает случайный девиз дня"""
        import random
        return random.choice(self._daily_mottos)

    def calculate_financial_score(
            self,
            axes_values: Dict[str, Dict[str, float]],
            transits: Optional[List[Dict]] = None
    ) -> float:
        """
        Рассчитывает финансовый балл на основе осей и транзитов

        Returns:
            Float от 0 до 1
        """
        base_score = 0.5

        # Учитываем ось удачи
        luck_data = axes_values.get('luck_talent', {})
        luck_value = luck_data.get('daily', 0.5)
        base_score += (luck_value - 0.5) * 0.3

        # Учитываем интеллект для принятия решений
        intellect_data = axes_values.get('intellect_logic', {})
        intellect_value = intellect_data.get('daily', 0.5)
        base_score += (intellect_value - 0.5) * 0.2

        # Учитываем дисциплину для долгосрочных вложений
        discipline_data = axes_values.get('work_discipline', {})
        discipline_value = discipline_data.get('daily', 0.5)
        base_score += (discipline_value - 0.5) * 0.2

        # Ограничиваем диапазон
        return max(0.2, min(0.9, base_score))


# ============================================================
# ФАБРИКА ДЛЯ СОЗДАНИЯ ГЕНЕРАТОРА
# ============================================================

_recommendation_generator: Optional[RecommendationGenerator] = None


def get_recommendation_generator() -> RecommendationGenerator:
    """Получить глобальный экземпляр RecommendationGenerator"""
    global _recommendation_generator
    if _recommendation_generator is None:
        _recommendation_generator = RecommendationGenerator()
    return _recommendation_generator


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

async def example_usage():
    """Пример использования генератора"""
    generator = get_recommendation_generator()

    # Пример значений осей
    axes_values = {
        'energy_will': {'daily': 0.75, 'delta': 0.12},
        'intellect_logic': {'daily': 0.85, 'delta': 0.15},
        'emotions_intuition': {'daily': 0.35, 'delta': -0.10},
        'work_discipline': {'daily': 0.68, 'delta': 0.05},
        'social_relations': {'daily': 0.72, 'delta': 0.08},
        'luck_talent': {'daily': 0.82, 'delta': 0.12},
        'health_physical': {'daily': 0.55, 'delta': -0.02},
        'karma_cycles': {'daily': 0.45, 'delta': -0.05},
        'destiny_mission': {'daily': 0.65, 'delta': 0.03},
    }

    moon_info = {'phase': 'first_quarter', 'nakshatra': 'Pushya'}
    panchanga = {'moon_phase': 'first_quarter', 'nakshatra': 'Pushya', 'tithi': 5}

    # Генерируем рекомендации
    recommendations = generator.generate_recommendations(
        user_id=1,
        forecast_date=date.today(),
        axes_values=axes_values,
        moon_info=moon_info,
        financial_score=0.75,
        panchanga=panchanga,
        void_moon=False
    )

    print("\n=== ЕЖЕДНЕВНЫЕ РЕКОМЕНДАЦИИ ===\n")
    print(f"📅 {recommendations.date}")
    print(f"✨ {recommendations.daily_motto}\n")
    print(f"📊 {recommendations.summary}\n")

    for rec in recommendations.recommendations:
        print(f"【{rec.title}】")
        print(f"  {rec.content}")
        if rec.action_items:
            print(f"  ✅ Что делать: {', '.join(rec.action_items)}")
        if rec.avoid_items:
            print(f"  ❌ Чего избегать: {', '.join(rec.avoid_items)}")
        print()

    return recommendations


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())