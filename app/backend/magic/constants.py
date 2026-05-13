"""
Константы для MagicProfileCalculator.
"""

# Версия профиля
PROFILE_VERSION = "2.0"

# Названия 9 осей
AXIS_NAMES = [
    'energy_will',
    'health_physical',
    'intellect_logic',
    'emotions_intuition',
    'work_discipline',
    'luck_talent',
    'social_relations',
    'karma_cycles',
    'destiny_mission'
]

# Планеты для каждой оси (для справки)
AXIS_PLANETS = {
    'energy_will': ['Sun', 'Mars'],
    'health_physical': ['Moon', 'Saturn'],
    'intellect_logic': ['Mercury', 'Uranus'],
    'emotions_intuition': ['Moon', 'Neptune'],
    'work_discipline': ['Saturn', 'Mars'],
    'luck_talent': ['Jupiter', 'Venus'],
    'social_relations': ['Venus', 'Moon'],
    'karma_cycles': ['Saturn', 'Pluto', 'True_Node'],
    'destiny_mission': ['Sun', 'Pluto', 'Uranus']
}

# Веса планет (0-1)
PLANET_WEIGHTS = {
    'Sun': 1.0,
    'Moon': 0.9,
    'Mercury': 0.8,
    'Venus': 0.8,
    'Mars': 0.9,
    'Jupiter': 0.9,
    'Saturn': 1.0,
    'Uranus': 0.7,
    'Neptune': 0.7,
    'Pluto': 0.8,
    'True_Node': 0.6,
    'Mean_Node': 0.5,
    'Chiron': 0.5,
    'Lilith': 0.4
}

# Веса домов (1-12)
HOUSE_WEIGHTS = {
    1: 1.0,   # Личность
    2: 0.7,   # Финансы
    3: 0.6,   # Коммуникация
    4: 0.8,   # Дом, семья
    5: 0.7,   # Творчество
    6: 0.6,   # Работа, здоровье
    7: 0.9,   # Партнерство
    8: 0.8,   # Трансформация
    9: 0.7,   # Философия
    10: 1.0,  # Карьера
    11: 0.7,  # Друзья
    12: 0.6   # Подсознание
}

# Модификаторы элементов
ELEMENT_MODIFIERS = {
    'fire': 1.2,
    'earth': 1.1,
    'air': 1.0,
    'water': 0.9
}

# Типы аспектов
ASPECT_TYPES = {
    'conjunction': {'angle': 0, 'nature': 'synthesis'},
    'sextile': {'angle': 60, 'nature': 'opportunity'},
    'square': {'angle': 90, 'nature': 'tension'},
    'trine': {'angle': 120, 'nature': 'harmony'},
    'opposition': {'angle': 180, 'nature': 'projection'},
    'quincunx': {'angle': 150, 'nature': 'adjustment'},
    'semisextile': {'angle': 30, 'nature': 'development'},
    'semisquare': {'angle': 45, 'nature': 'friction'},
    'sesquiquadrate': {'angle': 135, 'nature': 'crisis'}
}

# Кармические интерпретации
KARMIC_INTERPRETATIONS = {
    'Aries': {'base': 'Научиться проявлять инициативу без эгоизма'},
    'Taurus': {'base': 'Развить стабильность без упрямства'},
    'Gemini': {'base': 'Обрести глубину без поверхностности'},
    'Cancer': {'base': 'Научиться заботиться, не растворяясь'},
    'Leo': {'base': 'Сиять, не затмевая других'},
    'Virgo': {'base': 'Совершенствовать, не критикуя'},
    'Libra': {'base': 'Стремиться к гармонии, избегая конфликтов'},
    'Scorpio': {'base': 'Трансформироваться, не разрушая'},
    'Sagittarius': {'base': 'Искать истину, не осуждая'},
    'Capricorn': {'base': 'Достигать целей, не застывая'},
    'Aquarius': {'base': 'Быть уникальным, не отвергая'},
    'Pisces': {'base': 'Сливаться, не теряя себя'},
    'houses': {
        '1': 'в самовыражении',
        '2': 'в материальной сфере',
        '3': 'в общении',
        '4': 'в семье и доме',
        '5': 'в творчестве',
        '6': 'в работе и здоровье',
        '7': 'в партнерстве',
        '8': 'в трансформациях',
        '9': 'в поиске смысла',
        '10': 'в карьере',
        '11': 'в дружбе',
        '12': 'в духовности'
    }
}

house_meanings = {
            1: "через развитие личности и самовыражение",
            2: "через формирование ценностей и финансов",
            3: "через общение и обучение",
            4: "через работу с родом и домом",
            5: "через творчество и детей",
            6: "через служение и здоровье",
            7: "через партнерские отношения",
            8: "через кризисы и трансформации",
            9: "через поиск смысла и путешествия",
            10: "через карьеру и социальную реализацию",
            11: "через дружбу и коллективы",
            12: "через уединение и духовность"
        }


PROFILE_VERSION = '1.0'