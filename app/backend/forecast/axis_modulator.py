"""
axis_modulator.py - Модулятор 9 осей Magic Profile на основе транзитов
Версия 1.0 - Production Ready

Преобразует транзитные аспекты и другие астрологические факторы
в коэффициенты изменения для девяти осей личности.

Вход: транзитные аспекты, биоритмы, даша-период, панчанга
Выход: словарь {axis_name: delta} где delta от -0.3 до +0.3
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, date, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from .biorhythm_calculator import get_biorhythm_calculator, biorhythms_to_axis_modulation
from .dasha_calculator import get_dasha_calculator, dasha_to_axis_modulation
from .panchanga_calculator import get_panchanga_calculator, panchanga_to_axis_modulation

logger = logging.getLogger(__name__)


# ============================================================
# КОНСТАНТЫ ОСЕЙ
# ============================================================

class AxisName(str, Enum):
    """Названия 9 осей Magic Profile"""
    ENERGY_WILL = "energy_will"
    HEALTH_PHYSICAL = "health_physical"
    INTELLECT_LOGIC = "intellect_logic"
    EMOTIONS_INTUITION = "emotions_intuition"
    WORK_DISCIPLINE = "work_discipline"
    LUCK_TALENT = "luck_talent"
    SOCIAL_RELATIONS = "social_relations"
    KARMA_CYCLES = "karma_cycles"
    DESTINY_MISSION = "destiny_mission"


# ============================================================
# ТИПЫ МОДУЛЯТОРОВ
# ============================================================

@dataclass
class TransitEffect:
    """Эффект от одного транзитного аспекта"""
    axis: AxisName
    delta: float
    strength: float  # 0-1, насколько уверены в эффекте
    description: str


@dataclass
class BiorhythmEffect:
    """Эффект от биоритмов"""
    axis: AxisName
    delta: float
    cycle_type: str  # physical, emotional, intellectual


@dataclass
class DashaEffect:
    """Эффект от даша-периода"""
    axis: AxisName
    delta: float
    planet: str
    sub_planet: Optional[str]


# ============================================================
# БАЗА ПРАВИЛ ДЛЯ ТРАНЗИТОВ
# ============================================================

# Структура: (транзитная_планета, аспект, натальная_планета) -> (ось, дельта_базовая, множитель_силы)
TRANSIT_RULES = {
    # ========== ЭНЕРГИЯ И ВОЛЯ (energy_will) ==========
    # Солнце — жизненная сила
    ('Sun', 'conjunction', 'Sun'): (AxisName.ENERGY_WILL, 0.12, 1.0),
    ('Sun', 'trine', 'Sun'): (AxisName.ENERGY_WILL, 0.08, 0.8),
    ('Sun', 'sextile', 'Sun'): (AxisName.ENERGY_WILL, 0.06, 0.7),
    ('Sun', 'square', 'Sun'): (AxisName.ENERGY_WILL, -0.06, 0.9),
    ('Sun', 'opposition', 'Sun'): (AxisName.ENERGY_WILL, -0.04, 0.8),

    # Марс — активность, инициатива
    ('Mars', 'conjunction', 'Mars'): (AxisName.ENERGY_WILL, 0.15, 1.0),
    ('Mars', 'trine', 'Mars'): (AxisName.ENERGY_WILL, 0.10, 0.8),
    ('Mars', 'sextile', 'Mars'): (AxisName.ENERGY_WILL, 0.08, 0.7),
    ('Mars', 'square', 'Mars'): (AxisName.ENERGY_WILL, -0.08, 0.9),
    ('Mars', 'opposition', 'Mars'): (AxisName.ENERGY_WILL, -0.05, 0.8),
    ('Mars', 'conjunction', 'Sun'): (AxisName.ENERGY_WILL, 0.12, 1.0),
    ('Mars', 'trine', 'Sun'): (AxisName.ENERGY_WILL, 0.08, 0.8),
    ('Mars', 'square', 'Moon'): (AxisName.ENERGY_WILL, -0.06, 0.9),

    # Уран — энергетические всплески
    ('Uranus', 'conjunction', 'Sun'): (AxisName.ENERGY_WILL, 0.10, 0.9),
    ('Uranus', 'trine', 'Sun'): (AxisName.ENERGY_WILL, 0.06, 0.8),
    ('Uranus', 'square', 'Mars'): (AxisName.ENERGY_WILL, -0.05, 0.8),
    ('Uranus', 'trine', 'Mars'): (AxisName.ENERGY_WILL, 0.08, 0.7),

    # Плутон — трансформационная энергия
    ('Pluto', 'conjunction', 'Mars'): (AxisName.ENERGY_WILL, 0.08, 0.9),
    ('Pluto', 'square', 'Mars'): (AxisName.ENERGY_WILL, -0.07, 0.9),
    ('Pluto', 'conjunction', 'Sun'): (AxisName.ENERGY_WILL, 0.06, 0.8),

    # ========== ЗДОРОВЬЕ И ФИЗИКА (health_physical) ==========
    # Сатурн — выносливость
    ('Saturn', 'conjunction', 'Saturn'): (AxisName.HEALTH_PHYSICAL, 0.10, 1.0),
    ('Saturn', 'trine', 'Saturn'): (AxisName.HEALTH_PHYSICAL, 0.08, 0.8),
    ('Saturn', 'square', 'Saturn'): (AxisName.HEALTH_PHYSICAL, -0.10, 0.9),
    ('Saturn', 'opposition', 'Saturn'): (AxisName.HEALTH_PHYSICAL, -0.06, 0.8),

    # Луна — восстановление
    ('Moon', 'conjunction', 'Moon'): (AxisName.HEALTH_PHYSICAL, 0.08, 1.0),
    ('Moon', 'trine', 'Moon'): (AxisName.HEALTH_PHYSICAL, 0.06, 0.8),
    ('Moon', 'square', 'Saturn'): (AxisName.HEALTH_PHYSICAL, -0.08, 0.9),

    # 6 дом — здоровье
    ('Mars', 'conjunction', 'SixthHouse'): (AxisName.HEALTH_PHYSICAL, -0.10, 0.9),
    ('Mars', 'square', 'SixthHouse'): (AxisName.HEALTH_PHYSICAL, -0.06, 0.8),
    ('Jupiter', 'trine', 'SixthHouse'): (AxisName.HEALTH_PHYSICAL, 0.08, 0.8),
    ('Venus', 'trine', 'SixthHouse'): (AxisName.HEALTH_PHYSICAL, 0.06, 0.7),

    # ========== ИНТЕЛЛЕКТ И ЛОГИКА (intellect_logic) ==========
    # Меркурий — мышление
    ('Mercury', 'conjunction', 'Mercury'): (AxisName.INTELLECT_LOGIC, 0.15, 1.0),
    ('Mercury', 'trine', 'Mercury'): (AxisName.INTELLECT_LOGIC, 0.10, 0.8),
    ('Mercury', 'sextile', 'Mercury'): (AxisName.INTELLECT_LOGIC, 0.08, 0.7),
    ('Mercury', 'square', 'Mercury'): (AxisName.INTELLECT_LOGIC, -0.10, 0.9),
    ('Mercury', 'opposition', 'Mercury'): (AxisName.INTELLECT_LOGIC, -0.06, 0.8),
    ('Mercury', 'retrograde', 'any'): (AxisName.INTELLECT_LOGIC, -0.08, 0.8),

    # Уран — инсайты
    ('Uranus', 'conjunction', 'Mercury'): (AxisName.INTELLECT_LOGIC, 0.12, 0.9),
    ('Uranus', 'trine', 'Mercury'): (AxisName.INTELLECT_LOGIC, 0.08, 0.8),
    ('Uranus', 'square', 'Mercury'): (AxisName.INTELLECT_LOGIC, -0.05, 0.8),

    # Сатурн — структурирование мысли
    ('Saturn', 'conjunction', 'Mercury'): (AxisName.INTELLECT_LOGIC, 0.06, 0.8),
    ('Saturn', 'square', 'Mercury'): (AxisName.INTELLECT_LOGIC, -0.12, 0.9),
    ('Saturn', 'opposition', 'Mercury'): (AxisName.INTELLECT_LOGIC, -0.08, 0.8),

    # Нептун — рассеянность
    ('Neptune', 'conjunction', 'Mercury'): (AxisName.INTELLECT_LOGIC, -0.06, 0.7),
    ('Neptune', 'square', 'Mercury'): (AxisName.INTELLECT_LOGIC, -0.10, 0.8),

    # 3 и 9 дома — обучение и познание
    ('Jupiter', 'conjunction', 'NinthHouse'): (AxisName.INTELLECT_LOGIC, 0.10, 0.8),
    ('Mercury', 'trine', 'ThirdHouse'): (AxisName.INTELLECT_LOGIC, 0.08, 0.7),
    ('Saturn', 'square', 'NinthHouse'): (AxisName.INTELLECT_LOGIC, -0.06, 0.8),

    # ========== ЭМОЦИИ И ИНТУИЦИЯ (emotions_intuition) ==========
    # Луна — эмоции
    ('Moon', 'conjunction', 'Moon'): (AxisName.EMOTIONS_INTUITION, 0.15, 1.0),
    ('Moon', 'trine', 'Moon'): (AxisName.EMOTIONS_INTUITION, 0.10, 0.8),
    ('Moon', 'sextile', 'Moon'): (AxisName.EMOTIONS_INTUITION, 0.08, 0.7),
    ('Moon', 'square', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.12, 0.9),
    ('Moon', 'opposition', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.08, 0.8),

    # Нептун — интуиция
    ('Neptune', 'conjunction', 'Moon'): (AxisName.EMOTIONS_INTUITION, 0.12, 0.9),
    ('Neptune', 'trine', 'Moon'): (AxisName.EMOTIONS_INTUITION, 0.08, 0.8),
    ('Neptune', 'sextile', 'Moon'): (AxisName.EMOTIONS_INTUITION, 0.06, 0.7),
    ('Neptune', 'square', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.06, 0.8),

    # Венера — гармония
    ('Venus', 'conjunction', 'Moon'): (AxisName.EMOTIONS_INTUITION, 0.10, 0.8),
    ('Venus', 'trine', 'Moon'): (AxisName.EMOTIONS_INTUITION, 0.08, 0.7),

    # Марс — раздражительность
    ('Mars', 'square', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.10, 0.9),
    ('Mars', 'opposition', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.06, 0.8),
    ('Mars', 'conjunction', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.05, 0.8),

    # Сатурн — эмоциональная холодность
    ('Saturn', 'square', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.10, 0.8),
    ('Saturn', 'opposition', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.08, 0.8),
    ('Saturn', 'conjunction', 'Moon'): (AxisName.EMOTIONS_INTUITION, -0.06, 0.7),

    # 4 дом — эмоциональная база
    ('Moon', 'conjunction', 'FourthHouse'): (AxisName.EMOTIONS_INTUITION, 0.08, 0.7),
    ('Moon', 'square', 'FourthHouse'): (AxisName.EMOTIONS_INTUITION, -0.06, 0.7),

    # 12 дом — подсознание
    ('Neptune', 'conjunction', 'TwelfthHouse'): (AxisName.EMOTIONS_INTUITION, 0.10, 0.8),
    ('Moon', 'conjunction', 'TwelfthHouse'): (AxisName.EMOTIONS_INTUITION, -0.06, 0.7),

    # ========== ТРУД И ДИСЦИПЛИНА (work_discipline) ==========
    # Сатурн — дисциплина
    ('Saturn', 'conjunction', 'Saturn'): (AxisName.WORK_DISCIPLINE, 0.15, 1.0),
    ('Saturn', 'trine', 'Saturn'): (AxisName.WORK_DISCIPLINE, 0.10, 0.8),
    ('Saturn', 'sextile', 'Saturn'): (AxisName.WORK_DISCIPLINE, 0.08, 0.7),
    ('Saturn', 'square', 'Saturn'): (AxisName.WORK_DISCIPLINE, -0.08, 0.9),
    ('Saturn', 'opposition', 'Saturn'): (AxisName.WORK_DISCIPLINE, -0.06, 0.8),

    # Марс — трудоспособность
    ('Mars', 'conjunction', 'Saturn'): (AxisName.WORK_DISCIPLINE, 0.10, 0.8),
    ('Mars', 'trine', 'Saturn'): (AxisName.WORK_DISCIPLINE, 0.08, 0.7),
    ('Mars', 'square', 'Saturn'): (AxisName.WORK_DISCIPLINE, -0.06, 0.8),

    # 6 дом — работа
    ('Saturn', 'conjunction', 'SixthHouse'): (AxisName.WORK_DISCIPLINE, 0.12, 0.8),
    ('Saturn', 'trine', 'SixthHouse'): (AxisName.WORK_DISCIPLINE, 0.08, 0.7),
    ('Saturn', 'square', 'SixthHouse'): (AxisName.WORK_DISCIPLINE, -0.08, 0.8),
    ('Mars', 'conjunction', 'SixthHouse'): (AxisName.WORK_DISCIPLINE, 0.08, 0.7),
    ('Mars', 'square', 'SixthHouse'): (AxisName.WORK_DISCIPLINE, -0.06, 0.7),

    # 10 дом — карьера
    ('Saturn', 'conjunction', 'TenthHouse'): (AxisName.WORK_DISCIPLINE, 0.10, 0.8),
    ('Jupiter', 'conjunction', 'TenthHouse'): (AxisName.WORK_DISCIPLINE, 0.08, 0.7),
    ('Saturn', 'square', 'TenthHouse'): (AxisName.WORK_DISCIPLINE, -0.06, 0.7),

    # Уран — нестабильность в работе
    ('Uranus', 'conjunction', 'TenthHouse'): (AxisName.WORK_DISCIPLINE, -0.06, 0.7),
    ('Uranus', 'square', 'Saturn'): (AxisName.WORK_DISCIPLINE, -0.08, 0.7),

    # ========== СОЦИАЛЬНЫЕ ОТНОШЕНИЯ (social_relations) ==========
    # Венера — дипломатия
    ('Venus', 'conjunction', 'Venus'): (AxisName.SOCIAL_RELATIONS, 0.15, 1.0),
    ('Venus', 'trine', 'Venus'): (AxisName.SOCIAL_RELATIONS, 0.10, 0.8),
    ('Venus', 'sextile', 'Venus'): (AxisName.SOCIAL_RELATIONS, 0.08, 0.7),
    ('Venus', 'square', 'Venus'): (AxisName.SOCIAL_RELATIONS, -0.08, 0.9),
    ('Venus', 'opposition', 'Venus'): (AxisName.SOCIAL_RELATIONS, -0.06, 0.8),

    # Луна — эмпатия
    ('Moon', 'conjunction', 'Venus'): (AxisName.SOCIAL_RELATIONS, 0.10, 0.8),
    ('Moon', 'trine', 'Venus'): (AxisName.SOCIAL_RELATIONS, 0.08, 0.7),
    ('Moon', 'square', 'Venus'): (AxisName.SOCIAL_RELATIONS, -0.06, 0.8),

    # Марс — конфликтность
    ('Mars', 'square', 'Venus'): (AxisName.SOCIAL_RELATIONS, -0.10, 0.9),
    ('Mars', 'opposition', 'Venus'): (AxisName.SOCIAL_RELATIONS, -0.08, 0.8),
    ('Mars', 'conjunction', 'Venus'): (AxisName.SOCIAL_RELATIONS, -0.05, 0.7),

    # Сатурн — сдержанность
    ('Saturn', 'conjunction', 'Venus'): (AxisName.SOCIAL_RELATIONS, -0.06, 0.7),
    ('Saturn', 'square', 'Venus'): (AxisName.SOCIAL_RELATIONS, -0.10, 0.8),

    # 7 дом — партнёрство
    ('Venus', 'conjunction', 'SeventhHouse'): (AxisName.SOCIAL_RELATIONS, 0.12, 0.8),
    ('Venus', 'trine', 'SeventhHouse'): (AxisName.SOCIAL_RELATIONS, 0.08, 0.7),
    ('Mars', 'square', 'SeventhHouse'): (AxisName.SOCIAL_RELATIONS, -0.08, 0.8),
    ('Saturn', 'square', 'SeventhHouse'): (AxisName.SOCIAL_RELATIONS, -0.06, 0.7),

    # 11 дом — дружба
    ('Uranus', 'conjunction', 'EleventhHouse'): (AxisName.SOCIAL_RELATIONS, 0.08, 0.7),
    ('Jupiter', 'trine', 'EleventhHouse'): (AxisName.SOCIAL_RELATIONS, 0.08, 0.7),

    # ========== УДАЧА И ТАЛАНТЫ (luck_talent) ==========
    # Юпитер — удача
    ('Jupiter', 'conjunction', 'Jupiter'): (AxisName.LUCK_TALENT, 0.15, 1.0),
    ('Jupiter', 'trine', 'Jupiter'): (AxisName.LUCK_TALENT, 0.10, 0.8),
    ('Jupiter', 'sextile', 'Jupiter'): (AxisName.LUCK_TALENT, 0.08, 0.7),
    ('Jupiter', 'square', 'Jupiter'): (AxisName.LUCK_TALENT, -0.06, 0.8),
    ('Jupiter', 'opposition', 'Jupiter'): (AxisName.LUCK_TALENT, -0.04, 0.7),

    # Венера — творчество
    ('Venus', 'conjunction', 'Jupiter'): (AxisName.LUCK_TALENT, 0.10, 0.8),
    ('Venus', 'trine', 'Jupiter'): (AxisName.LUCK_TALENT, 0.08, 0.7),

    # Солнце — самовыражение
    ('Sun', 'conjunction', 'Jupiter'): (AxisName.LUCK_TALENT, 0.10, 0.8),
    ('Sun', 'trine', 'Jupiter'): (AxisName.LUCK_TALENT, 0.08, 0.7),

    # 5 дом — творчество
    ('Jupiter', 'conjunction', 'FifthHouse'): (AxisName.LUCK_TALENT, 0.12, 0.8),
    ('Jupiter', 'trine', 'FifthHouse'): (AxisName.LUCK_TALENT, 0.08, 0.7),
    ('Venus', 'conjunction', 'FifthHouse'): (AxisName.LUCK_TALENT, 0.10, 0.7),
    ('Saturn', 'square', 'FifthHouse'): (AxisName.LUCK_TALENT, -0.08, 0.7),

    # Сатурн — ограничения удачи
    ('Saturn', 'square', 'Jupiter'): (AxisName.LUCK_TALENT, -0.10, 0.8),
    ('Saturn', 'opposition', 'Jupiter'): (AxisName.LUCK_TALENT, -0.08, 0.7),
    ('Saturn', 'conjunction', 'Jupiter'): (AxisName.LUCK_TALENT, -0.06, 0.7),

    # ========== КАРМИЧЕСКИЕ ЦИКЛЫ (karma_cycles) ==========
    # Сатурн — кармический учитель
    ('Saturn', 'conjunction', 'Saturn'): (AxisName.KARMA_CYCLES, 0.12, 1.0),
    ('Saturn', 'square', 'Saturn'): (AxisName.KARMA_CYCLES, -0.08, 0.9),
    ('Saturn', 'opposition', 'Saturn'): (AxisName.KARMA_CYCLES, -0.06, 0.8),

    # Плутон — трансформация
    ('Pluto', 'conjunction', 'Pluto'): (AxisName.KARMA_CYCLES, 0.15, 0.9),
    ('Pluto', 'square', 'Pluto'): (AxisName.KARMA_CYCLES, -0.10, 0.9),
    ('Pluto', 'trine', 'Pluto'): (AxisName.KARMA_CYCLES, 0.08, 0.8),

    # Узлы — кармические точки
    ('True_Node', 'conjunction', 'True_Node'): (AxisName.KARMA_CYCLES, 0.12, 0.9),
    ('True_Node', 'conjunction', 'South_Node'): (AxisName.KARMA_CYCLES, 0.10, 0.8),
    ('Saturn', 'conjunction', 'True_Node'): (AxisName.KARMA_CYCLES, 0.10, 0.8),
    ('Saturn', 'square', 'True_Node'): (AxisName.KARMA_CYCLES, -0.08, 0.8),

    # 8 дом — трансформация
    ('Pluto', 'conjunction', 'EighthHouse'): (AxisName.KARMA_CYCLES, 0.12, 0.8),
    ('Pluto', 'square', 'EighthHouse'): (AxisName.KARMA_CYCLES, -0.08, 0.8),
    ('Saturn', 'conjunction', 'EighthHouse'): (AxisName.KARMA_CYCLES, 0.08, 0.7),

    # ========== СУДЬБА И МИССИЯ (destiny_mission) ==========
    # Солнце — миссия
    ('Sun', 'conjunction', 'Sun'): (AxisName.DESTINY_MISSION, 0.10, 1.0),
    ('Sun', 'trine', 'Sun'): (AxisName.DESTINY_MISSION, 0.08, 0.8),

    # Плутон — трансформация судьбы
    ('Pluto', 'conjunction', 'Sun'): (AxisName.DESTINY_MISSION, 0.12, 0.9),
    ('Pluto', 'trine', 'Sun'): (AxisName.DESTINY_MISSION, 0.08, 0.8),
    ('Pluto', 'square', 'Sun'): (AxisName.DESTINY_MISSION, -0.06, 0.8),

    # Уран — неожиданные повороты
    ('Uranus', 'conjunction', 'Sun'): (AxisName.DESTINY_MISSION, 0.10, 0.8),
    ('Uranus', 'trine', 'Sun'): (AxisName.DESTINY_MISSION, 0.08, 0.7),
    ('Uranus', 'square', 'Sun'): (AxisName.DESTINY_MISSION, -0.06, 0.7),

    # 10 дом — социальная реализация
    ('Sun', 'conjunction', 'TenthHouse'): (AxisName.DESTINY_MISSION, 0.12, 0.8),
    ('Sun', 'trine', 'TenthHouse'): (AxisName.DESTINY_MISSION, 0.08, 0.7),
    ('Saturn', 'conjunction', 'TenthHouse'): (AxisName.DESTINY_MISSION, 0.08, 0.7),
    ('Saturn', 'square', 'TenthHouse'): (AxisName.DESTINY_MISSION, -0.08, 0.7),

    # MC (Midheaven) — предназначение
    ('Sun', 'conjunction', 'MC'): (AxisName.DESTINY_MISSION, 0.15, 0.9),
    ('Jupiter', 'conjunction', 'MC'): (AxisName.DESTINY_MISSION, 0.10, 0.8),
    ('Saturn', 'conjunction', 'MC'): (AxisName.DESTINY_MISSION, -0.06, 0.7),

    # Узлы — кармическая миссия
    ('True_Node', 'conjunction', 'Sun'): (AxisName.DESTINY_MISSION, 0.12, 0.8),
    ('True_Node', 'conjunction', 'MC'): (AxisName.DESTINY_MISSION, 0.10, 0.8),
}

# ============================================================
# ПРАВИЛА ДЛЯ БИОРИТМОВ
# ============================================================

BIORHYTHM_RULES = {
    'physical': {
        AxisName.ENERGY_WILL: 0.08,
        AxisName.HEALTH_PHYSICAL: 0.10,
        AxisName.WORK_DISCIPLINE: 0.06,
    },
    'emotional': {
        AxisName.EMOTIONS_INTUITION: 0.12,
        AxisName.SOCIAL_RELATIONS: 0.08,
        AxisName.ENERGY_WILL: 0.04,
    },
    'intellectual': {
        AxisName.INTELLECT_LOGIC: 0.12,
        AxisName.LUCK_TALENT: 0.04,
        AxisName.WORK_DISCIPLINE: 0.04,
    },
}

# Пороги для определения "высокого" и "низкого" состояния биоритмов
BIORHYTHM_THRESHOLDS = {
    'high': 0.7,  # >0.7 → положительный эффект
    'low': -0.7,  # <-0.7 → отрицательный эффект
    'critical': 0.9,  # >0.9 или <-0.9 → сильный эффект
}

# ============================================================
# ПРАВИЛА ДЛЯ ДАША-ПЕРИОДА
# ============================================================

# Влияние планет в даша-периоде на оси
DASHA_RULES = {
    'Sun': {
        AxisName.ENERGY_WILL: 0.08,
        AxisName.DESTINY_MISSION: 0.10,
        AxisName.LUCK_TALENT: 0.06,
    },
    'Moon': {
        AxisName.EMOTIONS_INTUITION: 0.10,
        AxisName.SOCIAL_RELATIONS: 0.06,
        AxisName.HEALTH_PHYSICAL: 0.04,
    },
    'Mars': {
        AxisName.ENERGY_WILL: 0.10,
        AxisName.WORK_DISCIPLINE: 0.06,
        AxisName.SOCIAL_RELATIONS: -0.04,
    },
    'Mercury': {
        AxisName.INTELLECT_LOGIC: 0.10,
        AxisName.SOCIAL_RELATIONS: 0.06,
        AxisName.WORK_DISCIPLINE: 0.04,
    },
    'Jupiter': {
        AxisName.LUCK_TALENT: 0.12,
        AxisName.DESTINY_MISSION: 0.08,
        AxisName.SOCIAL_RELATIONS: 0.06,
    },
    'Venus': {
        AxisName.SOCIAL_RELATIONS: 0.10,
        AxisName.LUCK_TALENT: 0.08,
        AxisName.EMOTIONS_INTUITION: 0.06,
    },
    'Saturn': {
        AxisName.WORK_DISCIPLINE: 0.10,
        AxisName.KARMA_CYCLES: 0.10,
        AxisName.HEALTH_PHYSICAL: -0.06,
    },
    'Rahu': {
        AxisName.KARMA_CYCLES: 0.08,
        AxisName.ENERGY_WILL: 0.06,
        AxisName.INTELLECT_LOGIC: -0.06,
    },
    'Ketu': {
        AxisName.KARMA_CYCLES: 0.08,
        AxisName.EMOTIONS_INTUITION: 0.06,
        AxisName.SOCIAL_RELATIONS: -0.06,
    },
}

# Множитель для антардаши (подпериода)
ANTARDASHA_MULTIPLIER = 0.6

# ============================================================
# ПРАВИЛА ДЛЯ ЛУННЫХ ФАЗ И ПАНЧАНГИ
# ============================================================

# Влияние фаз Луны
MOON_PHASE_RULES = {
    'new': {
        AxisName.EMOTIONS_INTUITION: -0.06,
        AxisName.ENERGY_WILL: -0.04,
        AxisName.INTELLECT_LOGIC: -0.04,
    },
    'first_quarter': {
        AxisName.ENERGY_WILL: 0.08,
        AxisName.WORK_DISCIPLINE: 0.06,
    },
    'full': {
        AxisName.EMOTIONS_INTUITION: 0.10,
        AxisName.SOCIAL_RELATIONS: 0.08,
        AxisName.INTELLECT_LOGIC: -0.04,
    },
    'last_quarter': {
        AxisName.WORK_DISCIPLINE: 0.06,
        AxisName.KARMA_CYCLES: 0.06,
        AxisName.ENERGY_WILL: -0.04,
    },
}

# Void of course Moon
VOID_MOON_EFFECTS = {
    AxisName.WORK_DISCIPLINE: -0.08,
    AxisName.INTELLECT_LOGIC: -0.06,
    AxisName.EMOTIONS_INTUITION: -0.06,
    AxisName.LUCK_TALENT: -0.04,
    AxisName.SOCIAL_RELATIONS: -0.04,
}

# Накшатры для стрижки и бытовых дел (оставим для отдельного модуля)
NAKSHATRA_GOOD_FOR_HAIRCUT = {
    'Ashwini', 'Mrigashira', 'Pushya', 'Uttara Phalguni',
    'Hasta', 'Swati', 'Anuradha', 'Uttara Ashadha', 'Shravana', 'Revati'
}


# ============================================================
# ОСНОВНОЙ КЛАСС МОДУЛЯТОРА
# ============================================================

class AxisModulator:
    """
    Преобразует все астрологические факторы в модуляторы для 9 осей
    """

    def __init__(self):
        self._transit_rules = TRANSIT_RULES
        self._biorhythm_rules = BIORHYTHM_RULES
        self._dasha_rules = DASHA_RULES
        self._moon_phase_rules = MOON_PHASE_RULES
        self._void_moon_effects = VOID_MOON_EFFECTS

    def calculate_axis_modulators(
            self,
            transit_aspects: List[Dict],  # список аспектов от TransitCalculator
            biorhythms: Dict[str, float],  # {'physical': 0.3, 'emotional': -0.2, 'intellectual': 0.5}
            dasha_period: Optional[Dict] = None,  # {'planet': 'Jupiter', 'sub_planet': 'Venus'}
            moon_phase: Optional[str] = None,  # 'new', 'first_quarter', 'full', 'last_quarter'
            void_of_course_moon: bool = False,
    ) -> Dict[AxisName, float]:
        """
        Рассчитать коэффициенты модуляции для всех осей

        Returns:
            Словарь {AxisName: delta} где delta от -0.3 до +0.3
        """
        # Инициализация
        deltas: Dict[AxisName, float] = {}

        for axis in AxisName:
            deltas[axis] = 0.0

        # 1. Обрабатываем транзитные аспекты
        for aspect in transit_aspects:
            axis_delta = self._process_transit_aspect(aspect)
            if axis_delta:
                axis, delta = axis_delta
                deltas[axis] = max(-0.3, min(0.3, deltas[axis] + delta))

        # 2. Обрабатываем биоритмы
        for cycle_type, cycle_value in biorhythms.items():
            axis_deltas = self._process_biorhythms(cycle_type, cycle_value)
            for axis, delta in axis_deltas.items():
                deltas[axis] = max(-0.3, min(0.3, deltas[axis] + delta))

        # 3. Обрабатываем даша-период
        if dasha_period:
            axis_deltas = self._process_dasha(dasha_period)
            for axis, delta in axis_deltas.items():
                deltas[axis] = max(-0.3, min(0.3, deltas[axis] + delta))

        # 4. Обрабатываем фазу Луны
        if moon_phase:
            axis_deltas = self._process_moon_phase(moon_phase)
            for axis, delta in axis_deltas.items():
                deltas[axis] = max(-0.3, min(0.3, deltas[axis] + delta))

        # 5. Обрабатываем void of course Moon
        if void_of_course_moon:
            for axis, delta in self._void_moon_effects.items():
                deltas[axis] = max(-0.3, min(0.3, deltas[axis] + delta))

        # Округляем до 4 знаков
        result = {}
        for axis, delta in deltas.items():
            result[axis] = round(delta, 4)

        return result

    def _process_transit_aspect(self, aspect: Dict) -> Optional[Tuple[AxisName, float]]:
        """
        Обработать один транзитный аспект

        aspect = {
            'transit_planet': 'Mars',
            'natal_planet': 'Sun',
            'aspect_type': 'conjunction',
            'orb': 1.2,
            'strength': 0.25,
            'applying': True
        }
        """
        transit_planet = aspect.get('transit_planet')
        natal_planet = aspect.get('natal_planet')
        aspect_type = aspect.get('aspect_type')
        strength = aspect.get('strength', 0.15)

        # Ограничиваем силу аспекта
        strength = min(0.35, max(0.05, strength))

        # Проверяем, есть ли правило для этого аспекта
        rule_key = (transit_planet, aspect_type, natal_planet)

        if rule_key in self._transit_rules:
            axis, base_delta, strength_multiplier = self._transit_rules[rule_key]
            delta = base_delta * strength * strength_multiplier
            return (axis, delta)

        # Проверяем обобщённые правила
        if aspect_type == 'retrograde' and transit_planet in ['Mercury', 'Venus', 'Mars']:
            rule_key = (transit_planet, 'retrograde', 'any')
            if rule_key in self._transit_rules:
                axis, base_delta, strength_multiplier = self._transit_rules[rule_key]
                delta = base_delta * strength_multiplier
                return (axis, delta)

        return None

    def _process_biorhythms(self, cycle_type: str, cycle_value: float) -> Dict[AxisName, float]:
        """
        Обработать биоритмы

        cycle_type: 'physical', 'emotional', 'intellectual'
        cycle_value: от -1 до 1
        """
        result = {}

        # Определяем модуль эффекта в зависимости от значения
        if abs(cycle_value) > BIORHYTHM_THRESHOLDS['critical']:
            intensity = 1.0  # максимальный эффект
        elif cycle_value > BIORHYTHM_THRESHOLDS['high']:
            intensity = 0.7
        elif cycle_value < BIORHYTHM_THRESHOLDS['low']:
            intensity = 0.7
        else:
            return result  # нейтральное состояние, эффекта нет

        # Направление эффекта (знак)
        sign = 1 if cycle_value > 0 else -1

        # Применяем правила
        rules = self._biorhythm_rules.get(cycle_type, {})
        for axis, base_delta in rules.items():
            delta = sign * base_delta * intensity
            result[axis] = max(-0.15, min(0.15, delta))

        return result

    def _process_dasha(self, dasha_period: Dict) -> Dict[AxisName, float]:
        """
        Обработать даша-период

        dasha_period = {
            'planet': 'Jupiter',
            'sub_planet': 'Venus',  # опционально
            'progress': 0.65  # 0-1, насколько период продвинулся
        }
        """
        result = {}

        planet = dasha_period.get('planet')
        sub_planet = dasha_period.get('sub_planet')
        progress = dasha_period.get('progress', 0.5)

        # Учитываем прогресс периода (в начале и конце влияние слабее)
        progress_factor = 1.0 - abs(progress - 0.5) * 2  # 0.5 → 1.0, 0 или 1 → 0
        progress_factor = max(0.3, min(1.0, progress_factor))

        # Влияние основной планеты
        if planet in self._dasha_rules:
            for axis, base_delta in self._dasha_rules[planet].items():
                delta = base_delta * progress_factor
                result[axis] = result.get(axis, 0) + delta

        # Влияние подпериода (слабее)
        if sub_planet and sub_planet in self._dasha_rules:
            for axis, base_delta in self._dasha_rules[sub_planet].items():
                delta = base_delta * ANTARDASHA_MULTIPLIER * progress_factor
                result[axis] = result.get(axis, 0) + delta

        # Ограничиваем
        for axis in result:
            result[axis] = max(-0.15, min(0.15, result[axis]))

        return result

    def _process_moon_phase(self, moon_phase: str) -> Dict[AxisName, float]:
        """Обработать фазу Луны"""
        result = {}

        if moon_phase in self._moon_phase_rules:
            for axis, delta in self._moon_phase_rules[moon_phase].items():
                result[axis] = delta

        return result

    def get_trend_description(self, delta: float, axis_name: AxisName) -> str:
        """Получить текстовое описание тренда для оси"""
        if delta > 0.08:
            return "резко повышен"
        elif delta > 0.03:
            return "повышен"
        elif delta > -0.03:
            return "стабилен"
        elif delta > -0.08:
            return "понижен"
        else:
            return "резко понижен"

    def get_advice_for_axis(self, axis: AxisName, daily_value: float) -> str:
        """Получить совет для оси на основе её значения"""
        advice_map = {
            AxisName.ENERGY_WILL: {
                'high': "Занимайся спортом, берись за сложные проекты, проявляй инициативу",
                'medium': "Энергия в норме, можно работать в обычном режиме",
                'low': "Отдыхай, избегай конфликтов, не начинай новое"
            },
            AxisName.INTELLECT_LOGIC: {
                'high': "Учись, решай сложные задачи, планируй стратегию",
                'medium': "Мозг работает в штатном режиме",
                'low': "Не берись за сложные умственные задачи, перепроверяй информацию"
            },
            AxisName.EMOTIONS_INTUITION: {
                'high': "Доверяй интуиции, занимайся творчеством, общайся",
                'medium': "Эмоциональное состояние в норме",
                'low': "Медитируй, избегай важных решений, береги нервы"
            },
            AxisName.WORK_DISCIPLINE: {
                'high': "Отличное время для рутинной работы, закрывай долги",
                'medium': "Работоспособность в норме",
                'low': "Не планируй много дел, делегируй, отдыхай"
            },
            AxisName.SOCIAL_RELATIONS: {
                'high': "Общайся, встречайся с друзьями, иди на переговоры",
                'medium': "Социальные контакты в обычном режиме",
                'low': "Побудь один, не начинай конфликтов, избегай новых знакомств"
            },
            AxisName.LUCK_TALENT: {
                'high': "Рискуй, пробуй новое, проявляй таланты",
                'medium': "Удача в обычном режиме",
                'low': "Не рискуй, перепроверяй решения, не вкладывай крупные суммы"
            },
            AxisName.HEALTH_PHYSICAL: {
                'high': "Отличное здоровье, занимайся спортом, закаляйся",
                'medium': "Здоровье в норме",
                'low': "Береги себя, избегай перегрузок, профилактика"
            },
            AxisName.KARMA_CYCLES: {
                'high': "Завершай старые дела, анализируй прошлое",
                'medium': "Кармический период нейтрален",
                'low': "Не начинай важное, будь внимателен к знакам"
            },
            AxisName.DESTINY_MISSION: {
                'high': "Действуй по предназначению, следуй зову сердца",
                'medium': "Нейтральный период для миссии",
                'low': "Анализируй, не форсируй, копи энергию"
            },
        }

        axis_advice = advice_map.get(axis, {})

        if daily_value >= 0.7:
            level = 'high'
        elif daily_value >= 0.4:
            level = 'medium'
        else:
            level = 'low'

        return axis_advice.get(level, "Рекомендаций нет")

    async def calculate_axis_modulators_full(
            self,
            user_id: int,
            target_date: date,
            session: AsyncSession,
            transit_aspects: List[Dict],
            sun_longitude: float,
            moon_longitude: float,
            birth_datetime: datetime,
            nakshatra: str
    ) -> Dict[AxisName, float]:
        """Полный расчёт модуляторов со всеми источниками"""

        deltas = {}
        for axis in AxisName:
            deltas[axis] = 0.0

        # 1. Транзитные аспекты (уже есть)
        transit_deltas = self.calculate_axis_modulators(transit_aspects, {}, {}, None, False)
        for axis, delta in transit_deltas.items():
            deltas[axis] += delta

        # 2. Биоритмы
        biorhythm_calc = get_biorhythm_calculator()
        biorhythms = await biorhythm_calc.calculate_for_user_async(birth_datetime.date(), target_date)
        biorhythm_deltas = biorhythms_to_axis_modulation(biorhythms)
        for axis, delta in biorhythm_deltas.items():
            deltas[axis] = max(-0.3, min(0.3, deltas.get(axis, 0) + delta))

        # 3. Даша
        dasha_calc = get_dasha_calculator()
        dasha_info = dasha_calc.calculate_for_user(birth_datetime, nakshatra, target_date)
        dasha_deltas = dasha_to_axis_modulation(dasha_info)
        for axis, delta in dasha_deltas.items():
            deltas[axis] = max(-0.3, min(0.3, deltas.get(axis, 0) + delta))

        # 4. Панчанга
        panchanga_calc = get_panchanga_calculator()
        panchanga = panchanga_calc.calculate(sun_longitude, moon_longitude, target_date)
        panchanga_deltas = panchanga_to_axis_modulation(panchanga)
        for axis, delta in panchanga_deltas.items():
            deltas[axis] = max(-0.3, min(0.3, deltas.get(axis, 0) + delta))

        return {k: round(v, 4) for k, v in deltas.items()}


# ============================================================
# ФАБРИКА ДЛЯ СОЗДАНИЯ МОДУЛЯТОРА
# ============================================================

_axis_modulator: Optional[AxisModulator] = None


def get_axis_modulator() -> AxisModulator:
    """Получить глобальный экземпляр AxisModulator"""
    global _axis_modulator
    if _axis_modulator is None:
        _axis_modulator = AxisModulator()
    return _axis_modulator


# ============================================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================================

if __name__ == "__main__":
    # Пример использования
    modulator = get_axis_modulator()

    # Пример входных данных
    transit_aspects = [
        {'transit_planet': 'Mars', 'natal_planet': 'Sun', 'aspect_type': 'conjunction',
         'orb': 1.2, 'strength': 0.25, 'applying': True},
        {'transit_planet': 'Mercury', 'natal_planet': 'Mercury', 'aspect_type': 'square',
         'orb': 2.5, 'strength': 0.18, 'applying': False},
        {'transit_planet': 'Jupiter', 'natal_planet': 'Jupiter', 'aspect_type': 'trine',
         'orb': 3.0, 'strength': 0.20, 'applying': True},
    ]

    biorhythms = {
        'physical': 0.75,
        'emotional': -0.30,
        'intellectual': 0.60
    }

    dasha_period = {
        'planet': 'Jupiter',
        'sub_planet': 'Venus',
        'progress': 0.45
    }

    # Расчёт модуляторов
    deltas = modulator.calculate_axis_modulators(
        transit_aspects=transit_aspects,
        biorhythms=biorhythms,
        dasha_period=dasha_period,
        moon_phase='first_quarter',
        void_of_course_moon=False
    )

    print("\n=== МОДУЛЯТОРЫ ОСЕЙ ===")
    for axis, delta in deltas.items():
        if abs(delta) > 0.01:
            trend = "⬆️" if delta > 0 else "⬇️"
            print(f"  {axis.value}: {trend} {delta:+.3f}")