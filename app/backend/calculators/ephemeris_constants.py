
ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira",
    "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra",
    "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula",
    "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

YOGAS = [
    "Vishkumbha", "Preeti", "Ayushman", "Saubhagya", "Shobhana",
    "Atiganda", "Sukarman", "Dhriti", "Shoola", "Ganda",
    "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyan", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma",
    "Indra", "Vaidhriti"
]

TITHIS = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Purnima",
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami",
    "Shashthi", "Saptami", "Ashtami", "Navami", "Dashami",
    "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi", "Amavasya"
]

KARANAS = [
    "Kimstughna", "Bava", "Balava", "Kaulava", "Taitila",
    "Gara", "Vanija", "Vishti", "Shakuni", "Chatushpada", "Naga"
]

# Константы орбов для аспектов
ASPECT_ORBS = {
    'conjunction': {'Sun': 10, 'Moon': 10, 'default': 8},
    'opposition': {'Sun': 10, 'Moon': 10, 'default': 8},
    'square': {'default': 6},
    'trine': {'default': 6},
    'sextile': {'default': 4},
    'semisextile': {'default': 2},
    'semisquare': {'default': 2},
    'sesquiquadrate': {'default': 2},
    'quincunx': {'default': 3}
}

# Углы аспектов
ASPECT_ANGLES = {
    0: "conjunction",
    30: "semisextile",
    45: "semisquare",
    60: "sextile",
    90: "square",
    120: "trine",
    135: "sesquiquadrate",
    150: "quincunx",
    180: "opposition"
}

# Психологическая интерпретация звезд
FIXED_STARS_PSYCHOLOGY = {
    'Regulus': {
        'meaning': 'царственность, лидерство',
        'positive': 'благородство, успех',
        'negative': 'высокомерие, тирания',
        'with_sun': 'прирожденный лидер',
        'with_moon': 'эмоциональная власть',
        'with_mercury': 'царство мысли'
    },
    'Spica': {
        'meaning': 'дар, удача, талант',
        'positive': 'гениальность, помощь',
        'negative': 'лень от избытка даров',
        'with_sun': 'яркий талант',
        'with_moon': 'эмоциональная щедрость'
    },
    'Antares': {
        'meaning': 'воин, защитник',
        'positive': 'мужество, защита',
        'negative': 'агрессия, разрушение'
    },
    'Sirius': {
        'meaning': 'духовный учитель, защитник',
        'positive': 'мудрость, защита',
        'negative': 'фанатизм, догматизм'
    },
    'Vega': {
        'meaning': 'музыкальность, гармония',
        'positive': 'творчество, вдохновение',
        'negative': 'рассеянность, иллюзии'
    },
    'Aldebaran': {
        'meaning': 'хранитель врат, честь',
        'positive': 'целостность, лидерство',
        'negative': 'упрямство, гнев'
    },
    'Rigel': {
        'meaning': 'технический гений',
        'positive': 'изобретательность',
        'negative': 'холодность, расчет'
    },
    'Betelgeuse': {
        'meaning': 'харизма, успех',
        'positive': 'удача, слава',
        'negative': 'эгоцентризм, расточительность'
    },
    'Procyon': {
        'meaning': 'быстрый ум, адаптивность',
        'positive': 'сообразительность',
        'negative': 'поверхностность'
    },
    'Achernar': {
        'meaning': 'конец пути, завершение',
        'positive': 'мудрость, глубина',
        'negative': 'депрессия, изоляция'
    },
    'Hadar': {
        'meaning': 'корни, традиции',
        'positive': 'стабильность, опора',
        'negative': 'косность, консерватизм'
    },
    'Altair': {
        'meaning': 'полет, свобода',
        'positive': 'независимость, смелость',
        'negative': 'безрассудство'
    },
    'Acrux': {
        'meaning': 'мистицизм, вера',
        'positive': 'духовность',
        'negative': 'догматизм'
    },
    'Fomalhaut': {
        'meaning': 'миссия, предназначение',
        'positive': 'глубина, поиск смысла',
        'negative': 'одержимость'
    }
}

# Неподвижные звезды (основные)
FIXED_STARS = [
    {"name": "Regulus", "swe_name": "Regulus", "mag": 1.35, "const": "Leo"},
    {"name": "Spica", "swe_name": "Spica", "mag": 0.98, "const": "Virgo"},
    {"name": "Antares", "swe_name": "Antares", "mag": 0.96, "const": "Scorpio"},
    {"name": "Sirius", "swe_name": "Sirius", "mag": -1.46, "const": "Canis Major"},
    {"name": "Vega", "swe_name": "Vega", "mag": 0.03, "const": "Lyra"},
    {"name": "Aldebaran", "swe_name": "Aldebaran", "mag": 0.87, "const": "Taurus"},
    {"name": "Rigel", "swe_name": "Rigel", "mag": 0.18, "const": "Orion"},
    {"name": "Betelgeuse", "swe_name": "Betelgeuse", "mag": 0.45, "const": "Orion"},
    {"name": "Procyon", "swe_name": "Procyon", "mag": 0.34, "const": "Canis Minor"},
    {"name": "Achernar", "swe_name": "Achernar", "mag": 0.46, "const": "Eridanus"},
    {"name": "Hadar", "swe_name": "Hadar", "mag": 0.61, "const": "Centaurus"},
    {"name": "Altair", "swe_name": "Altair", "mag": 0.77, "const": "Aquila"},
    {"name": "Acrux", "swe_name": "Acrux", "mag": 0.77, "const": "Crux"},
    {"name": "Fomalhaut", "swe_name": "Fomalhaut", "mag": 1.17, "const": "Piscis Austrinus"}
]


# Вимшоттари Даша (порядок планет и годы)
DASHA_ORDER = ['Ketu', 'Venus', 'Sun', 'Moon', 'Mars', 'Rahu', 'Jupiter', 'Saturn', 'Mercury']
DASHA_YEARS = [7, 20, 6, 10, 7, 18, 16, 19, 17]  # Годы для каждой планеты

# Достоинства планет (essential dignities)
RULERS = {
    'Aries': 'Mars', 'Taurus': 'Venus', 'Gemini': 'Mercury',
    'Cancer': 'Moon', 'Leo': 'Sun', 'Virgo': 'Mercury',
    'Libra': 'Venus', 'Scorpio': 'Mars', 'Sagittarius': 'Jupiter',
    'Capricorn': 'Saturn', 'Aquarius': 'Saturn', 'Pisces': 'Jupiter'
}

EXALTATIONS = {
    'Sun': 19, 'Moon': 3, 'Mercury': 15, 'Venus': 27,
    'Mars': 28, 'Jupiter': 15, 'Saturn': 21
}

DETRIMENT_SIGNS = {
    'Mars': 'Libra', 'Venus': 'Scorpio', 'Mercury': 'Sagittarius',
    'Moon': 'Capricorn', 'Sun': 'Aquarius', 'Jupiter': 'Gemini',
    'Saturn': 'Cancer'
}

FALL_SIGNS = {
    'Sun': 'Libra', 'Moon': 'Scorpio', 'Mercury': 'Pisces',
    'Venus': 'Virgo', 'Mars': 'Cancer', 'Jupiter': 'Capricorn',
    'Saturn': 'Aries'
}

# Триплицитеты (дневные/ночные)
TRIPLICITIES = {
    ('Fire', 'day'): ('Sun', 'Jupiter'),
    ('Fire', 'night'): ('Jupiter', 'Sun'),
    ('Earth', 'day'): ('Venus', 'Moon'),
    ('Earth', 'night'): ('Moon', 'Venus'),
    ('Air', 'day'): ('Saturn', 'Mercury'),
    ('Air', 'night'): ('Mercury', 'Saturn'),
    ('Water', 'day'): ('Mars', 'Venus'),
    ('Water', 'night'): ('Venus', 'Mars')
}

# Элементы знаков
SIGN_ELEMENTS = {
    'Aries': 'Fire', 'Leo': 'Fire', 'Sagittarius': 'Fire',
    'Taurus': 'Earth', 'Virgo': 'Earth', 'Capricorn': 'Earth',
    'Gemini': 'Air', 'Libra': 'Air', 'Aquarius': 'Air',
    'Cancer': 'Water', 'Scorpio': 'Water', 'Pisces': 'Water'
}


# Египетские термы (границы)
TERMS = {
    'Aries': [
        (0, 6, 'Jupiter'), (6, 12, 'Venus'), (12, 20, 'Mercury'),
        (20, 25, 'Mars'), (25, 30, 'Saturn')
    ],
    'Taurus': [
        (0, 8, 'Venus'), (8, 14, 'Mercury'), (14, 22, 'Jupiter'),
        (22, 27, 'Saturn'), (27, 30, 'Mars')
    ],
    'Gemini': [
        (0, 6, 'Mercury'), (6, 12, 'Jupiter'), (12, 17, 'Venus'),
        (17, 24, 'Mars'), (24, 30, 'Saturn')
    ],
    'Cancer': [
        (0, 7, 'Mars'), (7, 13, 'Venus'), (13, 19, 'Mercury'),
        (19, 26, 'Jupiter'), (26, 30, 'Saturn')
    ],
    'Leo': [
        (0, 6, 'Jupiter'), (6, 13, 'Venus'), (13, 19, 'Saturn'),
        (19, 25, 'Mercury'), (25, 30, 'Mars')
    ],
    'Virgo': [
        (0, 7, 'Mars'), (7, 13, 'Venus'), (13, 18, 'Mercury'),
        (18, 24, 'Jupiter'), (24, 30, 'Saturn')
    ],
    'Libra': [
        (0, 6, 'Saturn'), (6, 14, 'Mercury'), (14, 21, 'Jupiter'),
        (21, 28, 'Venus'), (28, 30, 'Mars')
    ],
    'Scorpio': [
        (0, 7, 'Mars'), (7, 11, 'Venus'), (11, 19, 'Mercury'),
        (19, 24, 'Jupiter'), (24, 30, 'Saturn')
    ],
    'Sagittarius': [
        (0, 8, 'Jupiter'), (8, 14, 'Venus'), (14, 19, 'Mercury'),
        (19, 25, 'Saturn'), (25, 30, 'Mars')
    ],
    'Capricorn': [
        (0, 7, 'Mars'), (7, 14, 'Venus'), (14, 22, 'Mercury'),
        (22, 26, 'Jupiter'), (26, 30, 'Saturn')
    ],
    'Aquarius': [
        (0, 7, 'Mercury'), (7, 13, 'Venus'), (13, 20, 'Jupiter'),
        (20, 25, 'Mars'), (25, 30, 'Saturn')
    ],
    'Pisces': [
        (0, 12, 'Venus'), (12, 16, 'Jupiter'), (16, 19, 'Mercury'),
        (19, 28, 'Mars'), (28, 30, 'Saturn')
    ]
}

# Халдейские фейсы (деканы)
FACES = {
    'Aries': {0: 'Mars', 10: 'Sun', 20: 'Venus'},
    'Taurus': {0: 'Mercury', 10: 'Moon', 20: 'Saturn'},
    'Gemini': {0: 'Jupiter', 10: 'Mars', 20: 'Sun'},
    'Cancer': {0: 'Venus', 10: 'Mercury', 20: 'Moon'},
    'Leo': {0: 'Saturn', 10: 'Jupiter', 20: 'Mars'},
    'Virgo': {0: 'Sun', 10: 'Venus', 20: 'Mercury'},
    'Libra': {0: 'Moon', 10: 'Saturn', 20: 'Jupiter'},
    'Scorpio': {0: 'Mars', 10: 'Sun', 20: 'Venus'},
    'Sagittarius': {0: 'Mercury', 10: 'Moon', 20: 'Saturn'},
    'Capricorn': {0: 'Jupiter', 10: 'Mars', 20: 'Sun'},
    'Aquarius': {0: 'Venus', 10: 'Mercury', 20: 'Moon'},
    'Pisces': {0: 'Saturn', 10: 'Jupiter', 20: 'Mars'}
}


# ==================== АРАБСКИЕ ЧАСТИ (ОСНОВНЫЕ) ====================

ARABIC_PARTS = {
    "Fortune": {
        "day": lambda c: (c['ASC'] + c['Moon'] - c['Sun']) % 360,
        "night": lambda c: (c['ASC'] + c['Sun'] - c['Moon']) % 360,
        "interpretation": "Материальное благополучие, успех, удача"
    },
    "Spirit": {
        "day": lambda c: (c['ASC'] + c['Sun'] - c['Moon']) % 360,
        "night": lambda c: (c['ASC'] + c['Moon'] - c['Sun']) % 360,
        "interpretation": "Духовность, внутренний мир, философия"
    },
    "Love": {
        "formula": lambda c: (c['ASC'] + c['Venus'] - c['Sun']) % 360,
        "interpretation": "Любовные отношения, романтика"
    },
    "Passion": {
        "formula": lambda c: (c['ASC'] + c['Mars'] - c['Venus']) % 360,
        "interpretation": "Страсть, творческая энергия"
    },
    "Commerce": {
        "formula": lambda c: (c['ASC'] + c['Mercury'] - c['Sun']) % 360,
        "interpretation": "Бизнес, торговля, коммуникации"
    },
    "Faith": {
        "formula": lambda c: (c['ASC'] + c['Jupiter'] - c['Sun']) % 360,
        "interpretation": "Религия, вера, убеждения"
    },
    "Victory": {
        "formula": lambda c: (c['ASC'] + c['Jupiter'] - c['Saturn']) % 360,
        "interpretation": "Победа, достижения, триумф"
    },
    "Marriage": {
        "formula": lambda c: (c['ASC'] + c['Venus'] - c['Saturn']) % 360,
        "interpretation": "Брак, партнерство"
    },
    "Children": {
        "formula": lambda c: (c['ASC'] + c['Jupiter'] - c['Venus']) % 360,
        "interpretation": "Дети, творчество"
    },
    "Sickness": {
        "formula": lambda c: (c['ASC'] + c['Mars'] - c['Saturn']) % 360,
        "interpretation": "Здоровье, болезни"
    },
    "Death": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Moon']) % 360,
        "interpretation": "Трансформация, потери"
    },
    "Father": {
        "formula": lambda c: (c['Sun'] + c['Saturn'] - c['Moon']) % 360,
        "interpretation": "Отношения с отцом"
    },
    "Mother": {
        "formula": lambda c: (c['Moon'] + c['Venus'] - c['Saturn']) % 360,
        "interpretation": "Отношения с матерью"
    },
    "Soul": {
        "formula": lambda c: (c['ASC'] + c['Sun'] - c['Moon']) % 360,
        "interpretation": "Душа, внутренняя сущность, истинное Я"
    },
    "Necessity": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Sun']) % 360,
        "interpretation": "Необходимость, обязательства, кармические долги"
    },
    "Courage": {
        "formula": lambda c: (c['ASC'] + c['Mars'] - c['Mercury']) % 360,
        "interpretation": "Смелость, решительность, сила духа"
    },
    "Reason": {
        "formula": lambda c: (c['ASC'] + c['Mercury'] - c['Moon']) % 360,
        "interpretation": "Разум, логика, рациональное мышление"
    },
    "Intuition": {
        "formula": lambda c: (c['ASC'] + c['Moon'] - c['Mercury']) % 360,
        "interpretation": "Интуиция, предчувствия, подсознание"
    }
}


# ==================== АРАБСКИЕ ЧАСТИ (РАСШИРЕННЫЕ) ====================

ARABIC_PARTS_EXTENDED = {
    "Art": {
        "formula": lambda c: (c['ASC'] + c['Venus'] - c['Mercury']) % 360,
        "interpretation": "Искусство, творчество, эстетика, гармония"
    },
    "Science": {
        "formula": lambda c: (c['ASC'] + c['Mercury'] - c['Saturn']) % 360,
        "interpretation": "Наука, исследования, методология, открытия"
    },
    "Friendship": {
        "formula": lambda c: (c['ASC'] + c['Moon'] - c['Venus']) % 360,
        "interpretation": "Дружба, социальные связи, единомышленники"
    },
    "Enmity": {
        "formula": lambda c: (c['ASC'] + c['Mars'] - c['Saturn']) % 360,
        "interpretation": "Вражда, конфликты, соперничество, борьба"
    },
    "Imprisonment": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Mars']) % 360,
        "interpretation": "Ограничения, тюрьма, изоляция, заточение"
    },
    "Travel": {
        "formula": lambda c: (c['ASC'] + c['Jupiter'] - c['Moon']) % 360,
        "interpretation": "Путешествия, перемещения, экспансия, дальние поездки"
    },
    "Home": {
        "formula": lambda c: (c['ASC'] + c['Moon'] - c['Saturn']) % 360,
        "interpretation": "Дом, семья, корни, недвижимость"
    },
    "Career": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Jupiter']) % 360,
        "interpretation": "Карьера, призвание, социальный статус, достижения"
    },
    "Destiny": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Sun']) % 360,
        "interpretation": "Судьба, предназначение, рок, фатум"
    },
    "Karma": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Moon']) % 360,
        "interpretation": "Карма, долги, уроки прошлого"
    },
    "Genius": {
        "formula": lambda c: (c['ASC'] + c['Mercury'] - c['Uranus']) % 360,
        "interpretation": "Гениальность, озарения, инсайты"
    },
    "Magic": {
        "formula": lambda c: (c['ASC'] + c['Neptune'] - c['Moon']) % 360,
        "interpretation": "Магия, мистика, оккультные способности"
    },
    "Power": {
        "formula": lambda c: (c['ASC'] + c['Pluto'] - c['Sun']) % 360,
        "interpretation": "Власть, влияние, трансформация"
    },
    "Wisdom": {
        "formula": lambda c: (c['ASC'] + c['Jupiter'] - c['Mercury']) % 360,
        "interpretation": "Мудрость, знание, философия"
    },
    "Communication": {
        "formula": lambda c: (c['ASC'] + c['Mercury'] - c['Venus']) % 360,
        "interpretation": "Коммуникация, общение, связь"
    },
    "Secrets": {
        "formula": lambda c: (c['ASC'] + c['Pluto'] - c['Mercury']) % 360,
        "interpretation": "Тайны, секреты, скрытая информация"
    },
    "Healing": {
        "formula": lambda c: (c['ASC'] + c['Chiron'] - c['Moon']) % 360,
        "interpretation": "Исцеление, целительство, восстановление"
    },
    "Teaching": {
        "formula": lambda c: (c['ASC'] + c['Jupiter'] - c['Saturn']) % 360,
        "interpretation": "Учительство, наставничество, передача знаний"
    },
    "Learning": {
        "formula": lambda c: (c['ASC'] + c['Mercury'] - c['Jupiter']) % 360,
        "interpretation": "Обучение, образование, познание"
    },
    "Creativity": {
        "formula": lambda c: (c['ASC'] + c['Venus'] - c['Mars']) % 360,
        "interpretation": "Творчество, креативность, самовыражение"
    },
    "Leadership": {
        "formula": lambda c: (c['ASC'] + c['Sun'] - c['Saturn']) % 360,
        "interpretation": "Лидерство, управление, руководство"
    },
    "Service": {
        "formula": lambda c: (c['ASC'] + c['Moon'] - c['Mercury']) % 360,
        "interpretation": "Служение, помощь, альтруизм"
    },
    "Abundance": {
        "formula": lambda c: (c['ASC'] + c['Jupiter'] - c['Venus']) % 360,
        "interpretation": "Изобилие, процветание, богатство"
    },
    "Loss": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Venus']) % 360,
        "interpretation": "Потери, утраты, расставания"
    },
    "Gain": {
        "formula": lambda c: (c['ASC'] + c['Jupiter'] - c['Mars']) % 360,
        "interpretation": "Прибыль, приобретения, выгода"
    },
    "Risk": {
        "formula": lambda c: (c['ASC'] + c['Mars'] - c['Jupiter']) % 360,
        "interpretation": "Риск, авантюра, опасность"
    },
    "Stability": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Moon']) % 360,
        "interpretation": "Стабильность, устойчивость, надежность"
    },
    "Change": {
        "formula": lambda c: (c['ASC'] + c['Uranus'] - c['Moon']) % 360,
        "interpretation": "Перемены, изменения, трансформация"
    },
    "Inspiration": {
        "formula": lambda c: (c['ASC'] + c['Neptune'] - c['Venus']) % 360,
        "interpretation": "Вдохновение, идеалы, мечты"
    },
    "Illusion": {
        "formula": lambda c: (c['ASC'] + c['Neptune'] - c['Mercury']) % 360,
        "interpretation": "Иллюзии, заблуждения, обман"
    },
    "Truth": {
        "formula": lambda c: (c['ASC'] + c['Sun'] - c['Neptune']) % 360,
        "interpretation": "Истина, правда, реальность"
    },
    "Freedom": {
        "formula": lambda c: (c['ASC'] + c['Uranus'] - c['Saturn']) % 360,
        "interpretation": "Свобода, независимость, освобождение"
    },
    "Discipline": {
        "formula": lambda c: (c['ASC'] + c['Saturn'] - c['Mars']) % 360,
        "interpretation": "Дисциплина, порядок, структура"
    }
}


# ==================== ОБЪЕДИНЕННЫЙ СЛОВАРЬ ====================

ALL_ARABIC_PARTS = {}
ALL_ARABIC_PARTS.update(ARABIC_PARTS)
ALL_ARABIC_PARTS.update(ARABIC_PARTS_EXTENDED)