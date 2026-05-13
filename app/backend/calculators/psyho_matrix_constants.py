"""
psyho_matrix_constants.py - Константы для калькулятора психоматрицы
Англоязычные версии для модели данных
"""

from typing import Dict, List, Tuple, Any

# ==================== МАППИНГ ЦИФР В ХАРАКТЕРИСТИКИ ====================

DIGIT_TO_CHARACTERISTIC: Dict[int, str] = {
    1: "character",
    2: "energy",
    3: "interest",
    4: "health",
    5: "logic",
    6: "labor",
    7: "luck",
    8: "duty",
    9: "memory"
}

# ==================== ШАБЛОНЫ АНАЛИЗА ЦИФР (АНГЛИЙСКИЙ) ====================

ANALYSIS_TEMPLATES: Dict[int, Dict[int, str]] = {
    1: {  # Character
        0: "Flexible character, adaptability",
        1: "Balanced, stable character",
        2: "Strong character, leadership qualities",
        3: "Willful, purposeful character",
        4: "Transformational character, powerful will"
    },
    2: {  # Energy
        0: "Energy requires attention, conserve strength",
        1: "Balanced energy, stability",
        2: "High energy, activity",
        3: "Powerful energy, needs direction",
        4: "Colossal energy, gift of influence"
    },
    3: {  # Interest
        0: "Creative and humanitarian interests",
        1: "Diverse interests",
        2: "Deep interest in science and technology",
        3: "Analytical mind, researcher",
        4: "Genius in technical fields"
    },
    4: {  # Health
        0: "Attention to health, prevention",
        1: "Good health, resilience",
        2: "Strong health, endurance",
        3: "Excellent health, vitality",
        4: "Incredible health, recovery"
    },
    5: {  # Logic
        0: "Intuitive thinking, creativity",
        1: "Practical logic, common sense",
        2: "Analytical mind, strategic thinking",
        3: "Deep analyst, systemic thinking",
        4: "Genius logic, insights"
    },
    6: {  # Labor
        0: "Intellectual work, creativity",
        1: "Physical work brings satisfaction",
        2: "Master of craft, perfectionism",
        3: "Virtuoso of labor, highest mastery",
        4: "Incredible work capacity"
    },
    7: {  # Luck
        0: "Luck through work and persistence",
        1: "Luck in small things, favorable opportunities",
        2: "Fortune, support of higher powers",
        3: "Great luck, favor of fate",
        4: "Incredible luck, karmic bonuses"
    },
    8: {  # Duty
        0: "Freedom from obligations, flexibility",
        1: "Responsibility, reliability",
        2: "Strong sense of duty, commitment",
        3: "Karmic obligations, service",
        4: "Highest responsibility, mission"
    },
    9: {  # Memory
        0: "Practical memory, selectivity",
        1: "Good memory, learning ability",
        2: "Excellent memory, analytical skills",
        3: "Phenomenal memory, erudition",
        4: "Genius memory, encyclopedic knowledge"
    }
}

# ==================== ЖИЗНЕННОЕ ПРЕДНАЗНАЧЕНИЕ (АНГЛИЙСКИЙ) ====================

LIFE_PURPOSE_MAP: Dict[int, str] = {
    1: "Leadership and initiative - creating new and managing projects",
    2: "Harmony and diplomacy - establishing balance and partnerships",
    3: "Creativity and communication - self-expression through art and communication",
    4: "Stability and order - building reliable structures and systems",
    5: "Freedom and exploration - seeking new knowledge and adventures",
    6: "Family and care - nurturing, support, creating home comfort",
    7: "Analysis and wisdom - deep understanding, philosophy, spiritual search",
    8: "Material achievement - managing finances, resources, power",
    9: "Service and humanism - helping people, charity, healing",
    11: "Master teacher - spiritual enlightenment, teaching higher truths",
    22: "Master builder - implementing large-scale projects and architecture",
    33: "Master healer - healing on all levels: physical, emotional, spiritual"
}

# ==================== ТИПЫ ПАРТНЕРОВ ПО ЧИСЛАМ (АНГЛИЙСКИЙ) ====================

PARTNER_TYPES: Dict[int, List[str]] = {
    1: ["Creative natures", "Innovators"],
    2: ["Practical people", "Organizers"],
    3: ["Communicators", "Artists"],
    4: ["Builders", "Administrators"],
    5: ["Explorers", "Philosophers"],
    6: ["Educators", "Caring souls"],
    7: ["Analysts", "Sages"],
    8: ["Managers", "Financiers"],
    9: ["Humanitarians", "Healers"]
}

# ==================== МАППИНГ СОВМЕСТИМОСТИ ====================

COMPATIBILITY_MAP: Dict[int, List[int]] = {
    1: [2, 4, 7],
    2: [1, 5, 8],
    3: [6, 9],
    4: [1, 7],
    5: [2, 8],
    6: [3, 9],
    7: [1, 4],
    8: [2, 5],
    9: [3, 6],
    11: [22, 33, 4],
    22: [11, 33, 8],
    33: [11, 22, 9]
}

# ==================== ПОРОГИ ЭНЕРГИИ ====================

ENERGY_THRESHOLDS: List[Tuple[int, str]] = [
    (6, 'very_low'),
    (13, 'low'),
    (21, 'medium'),
    (28, 'high'),
    (99, 'very_high')
]

# ==================== МАСТЕР-ЧИСЛА ====================

MASTER_NUMBERS = frozenset({11, 22, 33})

# ==================== КАРМИЧЕСКИЙ ЦИКЛ ====================

KARMIC_CYCLE: int = 40
