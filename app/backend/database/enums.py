from enum import Enum as PyEnum
from typing import Any


class ActivityType(str, PyEnum):
    PHYSICAL = 'physical'
    SPIRITUAL = 'spiritual'
    LEARNING = 'learning'
    PSYCHOLOGICAL = 'psychological'
    CAREER = 'career'
    SELF_REALIZATION = 'self_realization'
    FINANCES = 'finances'


class AspectType(str, PyEnum):
    CONJUNCTION = 'conjunction'
    SEXTILE = 'sextile'
    SQUARE = 'square'
    TRINE = 'trine'
    OPPOSITION = 'opposition'
    QUINCUNX = 'quincunx'
    SEMI_SEXTILE = 'semi_sextile'
    SEMI_SQUARE = 'semi_square'


class EnergyLevel(str, PyEnum):
    very_low = 'very_low'
    low = 'low'
    medium = 'medium'
    high = 'high'
    very_high = 'very_high'

    @classmethod
    def from_ui(cls, value: str) -> 'EnergyLevel':
        mapping = {
            'very_low': cls.very_low,
            'low': cls.low,
            'medium': cls.medium,
            'high': cls.high,
            'very_high': cls.very_high,
        }
        return mapping.get(str(value).lower(), cls.medium)


class TestType(str, PyEnum):
    MBTI = 'mbti'
    BIG5 = 'big5'
    VALUES = 'values'
    MASLOW = 'maslow'


class TrendEnum(str, PyEnum):
    rising = "rising"
    falling = "falling"
    stable = "stable"


class PhaseEnum(str, PyEnum):
    positive = "positive"
    negative = "negative"
    critical = "critical"
    neutral = "neutral"


def energy_level(value: Any) -> EnergyLevel:
    return EnergyLevel.from_ui(value)


__all__ = [
    'ActivityType', 'AspectType', 'EnergyLevel', 'TestType',
    'TrendEnum', 'PhaseEnum', 'energy_level'
]
