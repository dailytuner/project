"""Database package - полный экспорт для обратной совместимости"""
from .core import async_engine, async_session, Base, get_db, close_db
from .enums import ActivityType, AspectType, EnergyLevel, TestType, TrendEnum, PhaseEnum, energy_level
from .models import (
    User, UserProfile, NatalChart, PsyhoMatrix, Biorhythm, MagicProfile,
    OptimalActivity, Recommendation, PsychologicalTest, AstroEvent, parse_json_field
)


__all__ = [
    'async_engine', 'async_session', 'Base', 'get_db', 'close_db',
    'User', 'UserProfile', 'NatalChart', 'PsyhoMatrix', 'Biorhythm',
    'MagicProfile', 'OptimalActivity', 'Recommendation',
    'PsychologicalTest', 'AstroEvent', 'parse_json_field',
    'ActivityType', 'AspectType', 'EnergyLevel', 'TestType',
    'TrendEnum', 'PhaseEnum', 'energy_level'
]
