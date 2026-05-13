"""Все модели базы данных"""
import json
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, BigInteger, Integer, SmallInteger, String, Date, Time,
    TIMESTAMP, Text, Boolean, Numeric, Float, DECIMAL, ForeignKey,
    UniqueConstraint, CheckConstraint, Index, func, Enum, text, Interval
)
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects.postgresql import JSONB, ARRAY, ENUM
from sqlalchemy.orm import relationship

from .core import Base
from .enums import *


# ============================================
# МОДЕЛИ БАЗЫ ДАННЫХ
# ============================================

class User(Base):
    """Основная таблица пользователей"""
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    #telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True)
    max_id = Column(String(255), unique=True, nullable=True)  # NEW
    udemy_id = Column(String(255), unique=True, nullable=True)  # NEW
    phone_hash = Column(String(128), nullable=True)
    email_hash = Column(String(128), nullable=True)
    primary_auth_method = Column(String(20), default='telegram')

    # Статус пользователя
    status = Column(
        String(20),
        default='active',
        nullable=False,
        server_default='active',
        index=True
    )
    is_verified = Column(Boolean, default=False, nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False, index=True)

    # Конфиденциальность
    privacy_level = Column(
        String(20),
        default='standard',
        nullable=False,
        server_default='standard'
    )
    
    # ПОЛЕ ДЛЯ ПАРОЛЯ
    password_hash = Column(String(128), nullable=True, comment="Bcrypt hash of password")

    # google and apple ID
    google_id = Column(String(255), unique=True, nullable=True)
    apple_id = Column(String(255), unique=True, nullable=True)

    # Временные метки
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    last_activity_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    premium_until = Column(TIMESTAMP(timezone=True), nullable=True)

    # Ограничения
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive', 'suspended', 'deleted')",
                        name='ck_users_status'),
        CheckConstraint("privacy_level IN ('minimal', 'standard', 'maximum')",
                        name='ck_users_privacy'),
        CheckConstraint("primary_auth_method IN ('telegram', 'max', 'udemy', 'phone', 'email', 'google', 'apple')",
                        name='ck_users_primary_auth'),
        UniqueConstraint('phone_hash', 'email_hash',
                         postgresql_nulls_not_distinct=True, name='uq_users_phone_email'),
        Index('idx_users_status', status,
              postgresql_where=status == 'active'),
        Index('idx_users_last_activity', last_activity_at.desc()),
    )

    # Relationships
    profile = relationship(
        "UserProfile",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )
    natal_charts = relationship(
        "NatalChart",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )
    psyho_matrix = relationship(
        "PsyhoMatrix",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )
    biorhythms = relationship(
        "Biorhythm",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )
    magic_profile = relationship(
        "MagicProfile",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )
    recommendations = relationship(
        "Recommendation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )
    optimal_activities = relationship(
        "OptimalActivity",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id})>"


class UserProfile(Base):
    """Профиль пользователя с данными для расчетов"""
    __tablename__ = 'user_profiles'

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        primary_key=True
    )

    # Основная информация
    full_name = Column(String(255), nullable=True)
    username = Column(String(100), nullable=True, index=True)
    language_code = Column(String(10), default='ru', nullable=False)
    timezone = Column(String(50), default='Europe/Moscow', nullable=False)

    # geocoder поля
    birth_country_code = Column(
        String(2),
        default='RU',
        server_default='RU',
        nullable=False
    )
    system_language = Column(
        String(10),
        default='ru',
        server_default='ru'
    )
    birth_timezone = Column(
        String(50),
        default='Europe/Moscow',
        server_default='Europe/Moscow'
    )

    # Данные для расчётов (ОБЯЗАТЕЛЬНЫЕ)
    birth_date = Column(Date, nullable=False)
    birth_time = Column(Time, nullable=False)
    birth_city = Column(String(100), nullable=False)
    birth_country = Column(String(100), default='Russia', nullable=False)

    # Координаты
    birth_lat = Column(DECIMAL(9, 6), nullable=True)
    birth_lng = Column(DECIMAL(9, 6), nullable=True)

    # Профессиональная информация
    profession = Column(String(100), nullable=True)
    job_position = Column(String(100), nullable=True)

    # Текущее местоположение
    current_city = Column(String(100), nullable=True)
    current_lat = Column(DECIMAL(9, 6), nullable=True)
    current_lng = Column(DECIMAL(9, 6), nullable=True)

    # Настройки
    notification_enabled = Column(Boolean, default=True, nullable=False)
    daily_recommendations_enabled = Column(Boolean, default=True, nullable=False)

    # Временные метки
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint(
            "birth_date >= '1900-01-01' AND birth_date <= CURRENT_DATE",
            name='ck_profile_birth_date'
        ),
        CheckConstraint(
            "birth_time >= '00:00:00' AND birth_time < '24:00:00'",
            name='ck_profile_birth_time'
        ),
        Index('idx_profiles_birth_date', 'birth_date'),
        Index('idx_profiles_birth_city_trgm', 'birth_city', postgresql_using='gin',
              postgresql_ops={'birth_city': 'gin_trgm_ops'})
    )

    # Relationship
    user = relationship("User", back_populates="profile", lazy="joined")

    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id}, username={self.username})>"


class NatalChart(Base):
    """Натальные астрологические карты"""
    __tablename__ = 'natal_charts'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Метаданные расчёта
    calculation_date = Column(Date, nullable=False, server_default=func.current_date())
    calculation_timestamp = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    calculation_time_ms = Column(Integer, nullable=True)

    # Географические данные
    city_name = Column(String(100), nullable=False)
    birth_lat = Column(DECIMAL(9, 6), nullable=False)
    birth_lng = Column(DECIMAL(9, 6), nullable=False)
    birth_timezone = Column(String(50), nullable=False)

    # geocoder поля
    birth_country_code = Column(String(2), nullable=True)
    system_language = Column(String(10), default='ru', nullable=True)
    geocoder_cache_key = Column(String(64), nullable=True)
    geocoder_source = Column(
        String(20),
        default='manual',
        server_default='manual',
        nullable=False
    )

    # Временные метки (UTC и локальное)
    birth_datetime_local = Column(TIMESTAMP(timezone=True), nullable=True)
    birth_datetime_utc = Column(TIMESTAMP(timezone=True), nullable=True)
    julian_day = Column(DECIMAL(15, 6), nullable=True)

    # Астрология
    planets = Column(JSONB, nullable=False, default={})
    houses = Column(JSONB, nullable=False, default={})
    aspects = Column(JSONB, nullable=False, default=[])

    # Джйотиш
    panchanga = Column(JSONB, nullable=False, default={})
    dasha = Column(JSONB, nullable=False, default={})

    # Дополнительные расчеты
    arabic_parts = Column(JSONB, nullable=False, default={})
    fixed_stars = Column(JSONB, nullable=False, default=[])
    planetary_hour = Column(JSONB, nullable=False, default={})

    # Метаданные расчетов
    ayanamsa = Column(DECIMAL(10, 6), nullable=True)
    sidereal_time = Column(DECIMAL(8, 4), nullable=True)
    void_of_course_moon = Column(Boolean, default=False)
    moon_phase_degrees = Column(DECIMAL(6, 2), nullable=True)

    moon_data = Column(JSONB, nullable=False, default={})
    solar_data = Column(JSONB, nullable=False, default={})
    lunar_returns = Column(JSONB, nullable=False, default=[])
    solar_returns = Column(JSONB, nullable=False, default=[])

    critical_degrees = Column(JSONB, nullable=False, default=[])
    midpoints = Column(JSONB, nullable=False, default={})

    # Календарные данные
    weekday = Column(String(20), default='Monday')
    weekday_ruler = Column(String(20), nullable=True)

    # ML-признаки
    ml_features = Column(JSONB, nullable=False, default={})

    # Система домов
    house_system = Column(String(20), default='Placidus', nullable=False)

    aspect_qualities = Column(JSONB, nullable=False, default=[])
    patterns = Column(JSONB, nullable=False, default={})
    star_interpretations = Column(JSONB, nullable=False, default=[])
    arabic_connections = Column(JSONB, nullable=False, default={})
    calculation_metadata = Column(JSONB, nullable=False, default={})

    # Статус
    calculation_status = Column(
        String(20),
        default='success',
        nullable=False,
        server_default='success'
    )
    error_message = Column(Text, nullable=True)

    # Временные метки - БЕЗ ТРИГГЕРА, используем onupdate
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # SQLAlchemy обновляет автоматически
        nullable=False
    )

    # Индексы
    __table_args__ = (
        CheckConstraint(
            "calculation_status IN ('pending', 'success', 'failed', 'partial')",
            name='ck_natal_status'
        ),
        CheckConstraint(
            "geocoder_source IN ('manual','memory_cache','db_cache','api','nominatim','google','yandex')",
            name='ck_natal_geocoder_source'
        ),
        CheckConstraint(
            "weekday IN ('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')",
            name='ck_natal_weekday'
        ),

        # Индексы
        Index('idx_natal_planets_gin', 'planets', postgresql_using='gin'),
        Index('idx_natal_panchanga_gin', 'panchanga', postgresql_using='gin'),
        Index('idx_natal_arabic_parts_gin', 'arabic_parts', postgresql_using='gin'),
        Index('idx_natal_moon_data_gin', 'moon_data', postgresql_using='gin'),
        Index('idx_natal_solar_data_gin', 'solar_data', postgresql_using='gin'),
        Index('idx_natal_ml_features_gin', 'ml_features', postgresql_using='gin'),

        # Индексы для JSONB полей
        Index(
            'idx_natal_nakshatra',
            text("(panchanga->>'nakshatra_name')"),
            postgresql_ops={'panchanga': 'jsonb_path_ops'}
        ),
        Index(
            'idx_natal_dasha_current',
            text("(dasha->>'planet')"),
            postgresql_ops={'dasha': 'jsonb_path_ops'}
        ),

        # Обычные индексы
        Index('idx_natal_user_date', 'user_id', 'calculation_date'),
        Index('idx_natal_weekday', 'weekday'),
        Index('idx_natal_julian_day', 'julian_day'),
    )

    user = relationship("User", back_populates="natal_charts", lazy="joined")

    def __repr__(self):
        return f"<NatalChart(id={self.id}, user_id={self.user_id}, city={self.city_name})>"


class PsyhoMatrix(Base):
    """
    Модель психоматрицы (квадрат Пифагора)

    Полная реализация с валидацией на уровне БД и ORM.
    Соответствует psyho_matrix.py v3.1
    """

    __tablename__ = 'psyho_matrices'
    __table_args__ = (
        # ============ CHECK CONSTRAINTS ============

        # Основные числа
        CheckConstraint(
            "first_number BETWEEN 1 AND 99",
            name='ck_first_number_range'
        ),
        CheckConstraint(
            "third_number BETWEEN 1 AND 99",
            name='ck_third_number_range'
        ),


        # Четвертое число: 1-9 ИЛИ мастер-числа 11,22,33
        CheckConstraint(
            "(fourth_number BETWEEN 1 AND 9) OR (fourth_number IN (11, 22, 33))",
            name='ck_fourth_number_valid'
        ),

        # Версия расчета
        CheckConstraint(
            "calculation_version IN ('1.0', '2.0', '3.0', '3.1')",
            name='ck_version_valid'
        ),

        # ============ ИНДЕКСЫ ============

        # Основные индексы
        Index('idx_psyho_matrices_user_id', 'user_id'),
        Index('idx_psyho_matrices_energy', 'energy_level'),
        Index('idx_psyho_matrices_version', 'calculation_version'),
        Index('idx_psyho_matrices_user_energy', 'user_id', 'energy_level'),

        # GIN индексы для JSONB полей
        Index(
            'idx_psyho_matrices_digits_gin',
            'matrix_digits',
            postgresql_using='gin'
        ),
        Index(
            'idx_psyho_matrices_characteristics_gin',
            'characteristics',
            postgresql_using='gin'
        ),
        Index(
            'idx_psyho_matrices_hints_gin',
            'compatibility_hints',
            postgresql_using='gin'
        ),
        Index(
            'idx_psyho_matrices_additional_gin',
            'additional',
            postgresql_using='gin'
        ),
        Index(
            'idx_psyho_matrices_karmic_gin',
            'karmic_analysis',
            postgresql_using='gin'
        ),
        Index(
            'idx_psyho_matrices_forecasting_gin',
            'forecasting',
            postgresql_using='gin'
        ),

        # Комментарий к таблице
        {
            'comment': 'Психоматрицы (квадрат Пифагора) v3.1 - полные расчеты'
        }
    )

    # ============ ПЕРВИЧНЫЙ КЛЮЧ ============

    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        primary_key=True,
        nullable=False,
        comment='ID пользователя (внешний ключ)'
    )

    # ============ ОСНОВНЫЕ ЧИСЛА ============

    first_number = Column(
        Integer,
        nullable=False,
        comment='Первое число - сумма всех цифр даты рождения (1-99)'
    )

    second_number = Column(
        Integer,
        nullable=False,
        comment='Второе число - редукция первого (1-9 или 11,22,33)'
    )

    third_number = Column(
        Integer,
        nullable=False,
        comment='Третье число - первое минус удвоенный день (1-99)'
    )

    fourth_number = Column(
        Integer,
        nullable=False,
        comment='Четвертое число - редукция третьего (1-9 или 11,22,33)'
    )

    # ============ МАТРИЦЫ И ХАРАКТЕРИСТИКИ ============

    matrix_digits = Column(
        JSONB,
        nullable=False,
        default={},
        server_default=text("'{}'"),
        comment='JSON объект с количеством каждой цифры 1-9'
    )

    matrix_3x3 = Column(
        JSONB,
        nullable=False,
        default=[[0, 0, 0], [0, 0, 0], [0, 0, 0]],
        server_default=text("'[[0,0,0],[0,0,0],[0,0,0]]'"),
        comment='Матрица 3x3 для позиционного анализа'
    )

    characteristics = Column(
        JSONB,
        nullable=False,
        default={},
        server_default=text("'{}'"),
        comment='Детальный анализ всех характеристик'
    )

    talent_codes = Column(
        ARRAY(Text),
        nullable=False,
        default=[],
        server_default=text("ARRAY[]::TEXT[]"),
        comment='Массив кодов талантов'
    )

    strength_codes = Column(
        ARRAY(Text),
        nullable=False,
        default=[],
        server_default=text("ARRAY[]::TEXT[]"),
        comment='Массив кодов сильных сторон'
    )

    # ============ АНАЛИТИЧЕСКИЕ ПОЛЯ ============

    energy_level = Column(
        Enum(EnergyLevel, name='energy_level', create_type=True),
        nullable=False,
        default=EnergyLevel.medium,
        server_default='medium',
        comment='Уровень энергии (very_low, low, medium, high, very_high)'
    )

    life_purpose = Column(
        Text,
        nullable=True,
        comment='Описание жизненного предназначения'
    )

    compatibility_hints = Column(
        JSONB,
        nullable=False,
        default={},
        server_default=text("'{}'"),
        comment='Данные для анализа совместимости'
    )

    additional = Column(
        JSONB,
        nullable=False,
        default={},
        server_default=text("'{}'"),
        comment='Дополнительные нумерологические расчеты'
    )

    karmic_analysis = Column(
        JSONB,
        nullable=False,
        default={},
        server_default=text("'{}'"),
        comment='Кармический анализ (долги, задачи, прошлые жизни)'
    )

    forecasting = Column(
        JSONB,
        nullable=False,
        default={},
        server_default=text("'{}'"),
        comment='Прогностические данные (годы, периоды, рекомендации)'
    )

    # ============ МЕТАДАННЫЕ ============

    calculated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment='Время расчета психоматрицы (из калькулятора)'
    )

    calculation_version = Column(
        String(20),
        nullable=False,
        default='3.1',
        server_default='3.1',
        comment='Версия алгоритма расчета'
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment='Время создания записи'
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment='Время последнего обновления'
    )

    # ============ СВЯЗИ ============

    user = relationship(
        "User",
        back_populates="psyho_matrix",
        lazy="select",
        foreign_keys=[user_id]
    )

    def __repr__(self):
        return f"<PsyhoMatrix(user_id={self.user_id}, version={self.calculation_version})>"

    def to_dict(self):
        """Преобразование в словарь для API"""
        return {
            'user_id': self.user_id,
            'first_number': self.first_number,
            'second_number': self.second_number,
            'third_number': self.third_number,
            'fourth_number': self.fourth_number,
            'matrix_digits': self.matrix_digits,
            'characteristics': self.characteristics,
            'talent_codes': self.talent_codes,
            'strength_codes': self.strength_codes,
            'energy_level': str(self.energy_level),
            'life_purpose': self.life_purpose,
            'compatibility_hints': self.compatibility_hints,
            'additional': self.additional,
            'karmic_analysis': self.karmic_analysis,
            'forecasting': self.forecasting,
            'calculation_version': self.calculation_version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def from_calculator_result(cls, user_id: int, calculator_result: dict):
        """
        Создание модели из результата калькулятора

        Args:
            user_id: ID пользователя
            calculator_result: Результат PsyhoMatrixCalculator.calculate_matrix()
        """
        return cls(
            user_id=user_id,
            first_number=calculator_result['first_number'],
            second_number=calculator_result['second_number'],
            third_number=calculator_result['third_number'],
            fourth_number=calculator_result['fourth_number'],
            matrix_digits=calculator_result['matrix_digits'],
            matrix_3x3=calculator_result.get('matrix_3x3', [[0, 0, 0], [0, 0, 0], [0, 0, 0]]),
            characteristics=calculator_result['characteristics'],
            talent_codes=calculator_result['talent_codes'],
            strength_codes=calculator_result['strength_codes'],
            energy_level=EnergyLevel(calculator_result['energy_level']),
            life_purpose=calculator_result['life_purpose'],
            compatibility_hints=calculator_result['compatibility_hints'],
            additional=calculator_result['additional'],
            karmic_analysis=calculator_result['karmic_analysis'],
            forecasting=calculator_result['forecasting'],
            calculation_version=calculator_result.get('calculation_version', '3.1')
        )


class Biorhythm(Base):
    """Статический профиль биоритмов пользователя"""
    __tablename__ = 'biorhythms'  # Имя не меняем

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    calculation_date = Column(Date, nullable=False, index=True)  # Дата создания профиля

    # ========== ПРОФИЛЬНЫЕ ПОЛЯ ==========
    profile_version = Column(String(10), nullable=False, default='1.0', server_default='1.0')
    profile_calculated_at = Column(Date, nullable=True)  # Дата расчета профиля
    days_analyzed = Column(Integer, nullable=True)  # Сколько дней анализировали

    # Фазы при рождении (для быстрых запросов)
    birth_physical = Column(Float(precision=4), nullable=True)
    birth_emotional = Column(Float(precision=4), nullable=True)
    birth_intellectual = Column(Float(precision=4), nullable=True)
    birth_intuitive = Column(Float(precision=4), nullable=True)

    # ML метрики (для быстрых запросов)
    system_stability = Column(Float(precision=4), nullable=True)
    predictability = Column(Float(precision=4), nullable=True)

    # Полный профиль в JSONB (ВСЕ данные для Mistral)
    profile_data = Column(JSONB, nullable=False, default={})

    # Временные метки
    calculated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # ========== ОГРАНИЧЕНИЯ ==========
    __table_args__ = (
        # Constraints для профильных полей
        CheckConstraint("birth_physical BETWEEN -1.0 AND 1.0", name='ck_bio_birth_physical'),
        CheckConstraint("birth_emotional BETWEEN -1.0 AND 1.0", name='ck_bio_birth_emotional'),
        CheckConstraint("birth_intellectual BETWEEN -1.0 AND 1.0", name='ck_bio_birth_intellectual'),
        CheckConstraint("birth_intuitive BETWEEN -1.0 AND 1.0", name='ck_bio_birth_intuitive'),
        CheckConstraint("system_stability BETWEEN 0 AND 1", name='ck_bio_system_stability'),
        CheckConstraint("predictability BETWEEN 0 AND 1", name='ck_bio_predictability'),
        CheckConstraint("days_analyzed > 0", name='ck_bio_days_analyzed'),

        # Уникальность (один профиль на пользователя)
        UniqueConstraint('user_id', name='uq_biorhythms_user'),

        # Индексы
        Index('idx_biorhythms_user', 'user_id'),
        Index('idx_biorhythms_profile_date', 'profile_calculated_at'),
        Index('idx_biorhythms_stability', 'system_stability'),

        # GIN индекс для JSONB
        Index('gin_biorhythms_profile_data', 'profile_data', postgresql_using='gin'),
    )

    # Relationship
    user = relationship("User", back_populates="biorhythms", lazy="joined")

    def __repr__(self):
        return f"<Biorhythm(user_id={self.user_id}, version={self.profile_version})>"


class MagicProfile(Base):
    """
    Интегрированные психологические и эзотерические профили v2.0.
    Основан на 9 осях личности из MagicProfileCalculator.
    """
    __tablename__ = 'magic_profiles'

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
        comment='ID пользователя (один профиль на пользователя)'
    )

    # ============ v2.0 ЯДРО ============
    axes = Column(
        JSONB,
        nullable=False,
        default={},
        comment='9 осей личности с полной структурой'
    )

    axis_count = Column(Integer, nullable=False, default=9)

    psychological_blueprint = Column(
        JSONB,
        nullable=False,
        default={},
        comment='Интегрированный психологический портрет'
    )

    ml_features = Column(
        JSONB,
        nullable=False,
        default={},
        comment='ML-признаки: raw_features, big_five, special_indicators'
    )

    # ============ ML ВЕКТОР ============
    feature_vector = Column(
        ARRAY(Float),
        nullable=True,
        comment='Фиксированный вектор признаков для ML моделей (27 признаков)'
    )

    cluster_id = Column(
        Integer,
        nullable=True,
        comment='ID кластера для группировки похожих профилей'
    )

    anomaly_score = Column(
        Float,
        default=0.0,
        comment='Оценка аномальности профиля (0-1)'
    )

    # ============ МЕТАДАННЫЕ ============
    profile_version = Column(
        String(20),
        default='2.0',
        comment='Версия профиля (2.0, 2.1, etc.)'
    )

    confidence_score = Column(
        Float,
        default=0.85,
        comment='Общая уверенность в данных (0-1)'
    )

    calculation_metadata = Column(
        JSONB,
        nullable=False,
        default={},
        comment='Метаданные расчета: axis_count, feature_count, calculation_time_ms, data_sources'
    )

    data_sources = Column(
        ARRAY(Text),
        default=lambda: ['astrology', 'numerology', 'biorhythms'],
        comment='Список использованных источников данных'
    )

    # ============ СТАТУС ============
    is_valid = Column(
        Boolean,
        default=True,
        comment='Флаг валидности профиля'
    )

    validation_errors = Column(
        ARRAY(Text),
        default=[],
        comment='Ошибки валидации, если есть'
    )

    # ============ ВРЕМЕННЫЕ МЕТКИ ============
    calculated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        comment='Время первого расчета'
    )

    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment='Время последнего обновления'
    )

    # ============ ИНДЕКСЫ И ОГРАНИЧЕНИЯ ============
    __table_args__ = (
        Index('ix_magic_profiles_user_id', 'user_id', unique=True),
        Index('ix_magic_profiles_feature_vec', 'feature_vector',
              postgresql_using='hnsw', postgresql_ops={'feature_vector': 'vector_cosine_ops'}),
        Index('ix_magic_profiles_cluster_id', 'cluster_id'),
        Index('ix_magic_profiles_confidence', 'confidence_score'),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name='ck_magic_confidence'
        ),
        CheckConstraint(
            "anomaly_score >= 0 AND anomaly_score <= 1",
            name='ck_magic_anomaly'
        ),
    )

    # Relationship
    user = relationship("User", back_populates="magic_profile", lazy="joined")

    def __repr__(self):
        return f"<MagicProfile(user_id={self.user_id}, version={self.profile_version})>"

    @property
    def axis_names(self) -> List[str]:
        """Получить список названий осей"""
        return list(self.axes.keys()) if self.axes else []

    @property
    def feature_count(self) -> int:
        """Длина feature vector"""
        vector = self.feature_vector

        if vector is None:
            return 0

        # Для PostgreSQL ARRAY
        if hasattr(vector, 'array'):
            return len(vector.array)

        # Для обычного списка
        try:
            return len(vector)
        except TypeError:
            return 0

    def get_axis(self, name: str) -> Dict:
        """Безопасное получение оси по имени"""
        return self.axes.get(name, {}) if self.axes else {}


class OptimalActivity(Base):
    """Оптимальные активности"""
    __tablename__ = 'optimal_activities'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    calculation_date = Column(Date, nullable=False, index=True)

    # Оптимальные активности
    activity_indices = Column(ARRAY(SmallInteger), nullable=False, default=[])

    activity_types = Column(
        ARRAY(Enum(ActivityType, name='activity_type')),
        nullable=False,
        default=[]
    )

    # Оценки активностей
    activity_scores = Column(ARRAY(Float), nullable=False, default=[])
    confidence_scores = Column(ARRAY(Float), nullable=False, default=[])

    # Рекомендации
    recommendations = Column(ARRAY(Text), nullable=False, default=[])
    time_slots = Column(JSONB, nullable=False, default={})
    priority_order = Column(ARRAY(SmallInteger), nullable=False, default=[])

    # Энергетические метрики
    energy_level = Column(Float, nullable=False)
    energy_trend = Column(String(10), nullable=True)
    focus_areas = Column(ARRAY(Text), nullable=False, default=[])

    # ML-данные
    ml_features = Column(JSONB, nullable=False, default={})
    feature_vector = Column(ARRAY(Float), nullable=False, default=[])
    model_version = Column(String(20), default='1.0', nullable=False)

    # Статус
    is_generated = Column(Boolean, default=True, nullable=False)
    is_approved = Column(Boolean, default=False, nullable=False)
    user_feedback = Column(SmallInteger, nullable=True)

    # Временные метки
    generated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint(
            "energy_level >= 0 AND energy_level <= 1",
            name='ck_activity_energy'
        ),
        CheckConstraint(
            "energy_trend IS NULL OR energy_trend IN ('rising', 'falling', 'stable')",
            name='ck_activity_trend'
        ),
        CheckConstraint(
            "user_feedback IS NULL OR user_feedback BETWEEN 1 AND 5",
            name='ck_activity_feedback'
        ),
        UniqueConstraint('user_id', 'calculation_date', name='uq_optimal_activities_user_date'),
    )

    # Relationship
    user = relationship("User", back_populates="optimal_activities", lazy="joined")

    def __repr__(self):
        return f"<OptimalActivity(user_id={self.user_id}, date={self.calculation_date})>"


class Recommendation(Base):
    __tablename__ = 'recommendations'

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    calculation_date = Column(Date, nullable=False, index=True)

    # Контент
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text)

    # Метаданные
    category = Column(String(50), nullable=False, index=True)
    priority = Column(SmallInteger, default=3, index=True)
    relevance_score = Column(Float, default=0.5)

    # JSON для гибкости
    data = Column(JSONB, nullable=False, default=dict)  # Всё остальное

    # Временные метки
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                        onupdate=func.now())

    user = relationship(
        "User",
        back_populates="recommendations",
        lazy="select"
    )

    __table_args__ = (
        UniqueConstraint('user_id', 'calculation_date', 'category'),
        CheckConstraint('priority BETWEEN 1 AND 5'),
        CheckConstraint('relevance_score BETWEEN 0 AND 1'),
    )


class DailyForecastCache(Base):
    __tablename__ = 'daily_forecast_cache'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    forecast_date = Column(Date, nullable=False, index=True)  #  ЕДИНОЕ ИМЯ
    axes_deltas = Column(JSONB, nullable=False)
    daily_axes = Column(JSONB, nullable=False)
    background_risks = Column(JSONB, nullable=True, comment="Список фоновых рисков от слабых сигналов")
    subtle_signals = Column(JSONB, nullable=True, comment="Детали слабых сигналов по осям")
    signal_categories = Column(JSONB, nullable=True, comment="Категоризация всех сигналов")
    recommendations = Column(JSONB)

    rules_version = Column(String(20), default='v1.0')
    invalidated_at = Column(TIMESTAMP(timezone=True))

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True),
                        server_default=func.now() + Interval('31 days'))

    __table_args__ = (
        UniqueConstraint('user_id', 'forecast_date'),
        Index('ix_forecast_date_range', 'user_id', 'forecast_date'),
        Index('ix_expires_active', 'expires_at',
              postgresql_where=text("expires_at > NOW()")),
    )

class ForecastFeedback(Base):
    __tablename__ = 'forecast_feedback'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    forecast_date = Column(Date, index=True)
    axis_name = Column(String(50), index=True)

    predicted_score = Column(Float)
    user_rating = Column(Float)
    delta = Column(Float)  # Вычислять в сервисе

    comment = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class ProfileSnapshot(Base):
    __tablename__ = "profile_snapshots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    snapshot_date = Column(Date, nullable=False)
    axes = Column(JSONB, nullable=False)
    ml_features = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class PsychologicalTest(Base):
    """Психологические тесты"""
    __tablename__ = 'psychological_tests'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Информация о тесте
    test_type = Column(
        Enum(TestType, name='test_type'),
        nullable=False
    )
    test_version = Column(String(20), nullable=False)
    test_name = Column(String(100), nullable=False)

    # Вопросы и ответы
    questions = Column(JSONB, nullable=False, default=[])
    answers = Column(JSONB, nullable=False, default={})
    raw_responses = Column(JSONB, nullable=False, default={})

    # Результаты
    scores = Column(JSONB, nullable=False, default={})
    profile_type = Column(String(50), nullable=True)
    interpretation = Column(Text, nullable=True)
    insights = Column(JSONB, nullable=False, default={})

    # Метаданные
    completion_percentage = Column(
        SmallInteger,
        default=100,
        nullable=False,
        server_default='100'
    )
    time_spent_seconds = Column(Integer, nullable=True)
    device_info = Column(JSONB, nullable=False, default={})

    # Статус
    status = Column(
        String(20),
        default='completed',
        nullable=False,
        server_default='completed'
    )

    # Временные метки
    started_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Ограничения
    __table_args__ = (
        CheckConstraint(
            "completion_percentage BETWEEN 0 AND 100",
            name='ck_test_completion'
        ),
        CheckConstraint(
            "status IN ('started', 'in_progress', 'completed', 'abandoned')",
            name='ck_test_status'
        ),
        UniqueConstraint('user_id', 'test_type', 'test_version', name='uq_tests_user_type_version'),
    )

    def __repr__(self):
        return f"<PsychologicalTest(id={self.id}, user_id={self.user_id}, test_type={self.test_type})>"


class AstroEvent(Base):
    """Астрологические события"""
    __tablename__ = 'astro_events'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_date = Column(Date, nullable=False, index=True)
    event_time = Column(TIMESTAMP(timezone=True), nullable=True)

    event_type = Column(String(50), nullable=False)
    event_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    significance_level = Column(String(20), nullable=True)

    zodiac_sign = Column(String(20), nullable=True)
    degree = Column(DECIMAL(5, 2), nullable=True)
    planetary_aspects = Column(JSONB, default={}, nullable=False)

    general_recommendations = Column(ARRAY(Text), default=[], nullable=False)
    caution_areas = Column(ARRAY(Text), default=[], nullable=False)

    source = Column(String(50), default='calculated', nullable=False)
    confidence = Column(Float, default=1.0, nullable=False)

    calculated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('new_moon', 'full_moon', 'first_quarter', 'last_quarter',"
            "'mercury_retrograde', 'venus_retrograde', 'mars_retrograde',"
            "'jupiter_retrograde', 'saturn_retrograde', 'uranus_retrograde',"
            "'neptune_retrograde', 'pluto_retrograde', 'eclipse_solar',"
            "'eclipse_lunar', 'planetary_transit')",
            name='ck_astro_event_type'
        ),
        CheckConstraint(
            "significance_level IN ('low', 'medium', 'high', 'critical')",
            name='ck_astro_significance'
        ),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name='ck_astro_confidence'
        ),
    )

    def __repr__(self):
        return f"<AstroEvent(id={self.id}, event_name={self.event_name}, date={self.event_date})>"


def parse_json_field(field):
    """Единая функция для парсинга JSON полей"""
    if field is None:
        return {}
    if isinstance(field, dict):
        return field
    if isinstance(field, str):
        try:
            return json.loads(field)
        except:
            return {}
    return {}


__all__ = [
    'User', 'UserProfile', 'NatalChart', 'PsyhoMatrix', 'Biorhythm',
    'MagicProfile', 'OptimalActivity', 'Recommendation',
    'PsychologicalTest', 'AstroEvent', 'parse_json_field',
    'DailyForecastCache',
    'ForecastFeedback',
    'ProfileSnapshot'
]


