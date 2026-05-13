-- ============================================
-- DAILY TUNER DATABASE 
-- ============================================

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET TIME ZONE 'UTC';

-- ============================================
-- 1. ОЧИСТКА СТАРЫХ ТИПОВ И ЗАВИСИМОСТЕЙ
-- ============================================

-- Удаляем старые ENUM типы если существуют (для идемпотентности)
DROP TYPE IF EXISTS activity_type CASCADE;
DROP TYPE IF EXISTS aspect_type CASCADE;
DROP TYPE IF EXISTS energy_level CASCADE;
DROP TYPE IF EXISTS test_type CASCADE;

-- ============================================
-- 2. СОЗДАНИЕ РАСШИРЕНИЙ
-- ============================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- 3. СОЗДАНИЕ ТИПОВ ДАННЫХ 
-- ============================================

-- Типы активности для рекомендаций (сохраняем ENUM для обратной совместимости)
CREATE TYPE activity_type AS ENUM (
    'physical',
    'spiritual', 
    'learning',
    'psychological',
    'career',
    'self_realization',
    'finances'
);

-- Типы астрологических аспектов (для натальных карт)
CREATE TYPE aspect_type AS ENUM (
    'conjunction',
    'sextile',
    'square',
    'trine',
    'opposition',
    'quincunx',
    'semi_sextile',
    'semi_square'
);

-- Уровни энергии для рекомендаций
CREATE TYPE energy_level AS ENUM (
    'very_low',
    'low',
    'medium',
    'high',
    'very_high'
);

-- Типы психологических тестов
CREATE TYPE test_type AS ENUM (
    'mbti',
    'big5',
    'values',
    'maslow'
);


-- После CREATE TYPE test_type AS ENUM ... ДОБАВИТЬ:
CREATE TYPE trend_type AS ENUM ('rising', 'falling', 'stable');

CREATE TYPE phase_type AS ENUM ('positive', 'negative', 'critical', 'neutral');


-- ============================================
-- 4. СОЗДАНИЕ РОЛИ ПРИЛОЖЕНИЯ 
-- ============================================

-- Пароль будет установлен после создания через ALTER
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'personal_assistant_app') THEN
        CREATE ROLE personal_assistant_app WITH LOGIN;
        COMMENT ON ROLE personal_assistant_app IS 'Роль приложения для основного доступа к БД';
    END IF;
END
$$;

-- ============================================
-- 5. ОСНОВНАЯ ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ 
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    
    -- Внешние идентификаторы
    telegram_id BIGINT UNIQUE,
    max_id VARCHAR(255) UNIQUE,
    udemy_id VARCHAR(255) UNIQUE,
    google_id VARCHAR(255) UNIQUE,
    apple_id VARCHAR(255) UNIQUE,
    
    -- Анонимизированные данные (хеши)
    phone_hash VARCHAR(128),
    email_hash VARCHAR(128),
    password_hash VARCHAR(255),
    
    -- Метод первичной авторизации
    primary_auth_method VARCHAR(20) DEFAULT 'telegram' 
        CHECK (primary_auth_method IN ('telegram', 'max', 'udemy', 'phone', 'email', 'google', 'apple')),
    
    -- Статус пользователя
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended', 'deleted')),
    is_verified BOOLEAN DEFAULT FALSE,
    is_premium BOOLEAN DEFAULT FALSE,
    
    -- Конфиденциальность
    privacy_level VARCHAR(20) DEFAULT 'standard' CHECK (privacy_level IN ('minimal', 'standard', 'maximum')),
    
    -- Временные метки
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    last_activity_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    premium_until TIMESTAMPTZ
);

-- =====================================================
-- ✅ ИНДЕКСЫ ДЛЯ ВНЕШНИХ ИДЕНТИФИКАТОРОВ (PARTIAL UNIQUE)
-- =====================================================

-- Telegram ID (уникальный, если не NULL)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_telegram 
ON users(telegram_id) WHERE telegram_id IS NOT NULL;

-- MAX ID (уникальный, если не NULL)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_max 
ON users(max_id) WHERE max_id IS NOT NULL;

-- Udemy ID (уникальный, если не NULL)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_udemy 
ON users(udemy_id) WHERE udemy_id IS NOT NULL;

-- Google ID (уникальный, если не NULL)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_google 
ON users(google_id) WHERE google_id IS NOT NULL;

-- Apple ID (уникальный, если не NULL)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_apple 
ON users(apple_id) WHERE apple_id IS NOT NULL;

-- =====================================================
-- ✅ ИНДЕКСЫ ДЛЯ ТЕЛЕФОНА И EMAIL (PARTIAL UNIQUE)
-- =====================================================

-- Уникальность комбинации телефон + email (только если оба NOT NULL)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_phone_email_unique 
ON users (phone_hash, email_hash) 
WHERE phone_hash IS NOT NULL AND email_hash IS NOT NULL;

-- Уникальность телефона (если указан)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_phone_unique 
ON users (phone_hash) 
WHERE phone_hash IS NOT NULL;

-- Уникальность email (если указан)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_unique 
ON users (email_hash) 
WHERE email_hash IS NOT NULL;

-- =====================================================
-- ✅ ВСПОМОГАТЕЛЬНЫЕ ИНДЕКСЫ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ
-- =====================================================

-- Поиск по методу авторизации (редко, но полезно)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_auth_method 
ON users(primary_auth_method) WHERE primary_auth_method IS NOT NULL;

-- Активные пользователи
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_status 
ON users(status) WHERE status = 'active';

-- Сортировка по последней активности (для аналитики)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_last_activity 
ON users(last_activity_at DESC);

-- Составной индекс для поиска по дате создания (для отчетов)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_at 
ON users(created_at DESC);

-- Индекс для премиум пользователей (часто запрашивается)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_premium 
ON users(premium_until) WHERE is_premium = true;

-- =====================================================
-- ✅ КОММЕНТАРИИ К ТАБЛИЦЕ И ПОЛЯМ (ОПЦИОНАЛЬНО)
-- =====================================================

COMMENT ON TABLE users IS 'Пользователи системы с поддержкой множественных методов авторизации';
COMMENT ON COLUMN users.telegram_id IS 'ID пользователя в Telegram (уникальный, если указан)';
COMMENT ON COLUMN users.max_id IS 'ID пользователя в MAX платформе';
COMMENT ON COLUMN users.udemy_id IS 'ID пользователя в Udemy';
COMMENT ON COLUMN users.google_id IS 'ID пользователя в Google';
COMMENT ON COLUMN users.apple_id IS 'ID пользователя в Apple';
COMMENT ON COLUMN users.phone_hash IS 'Хеш телефона для анонимизации';
COMMENT ON COLUMN users.email_hash IS 'Хеш email для анонимизации';
COMMENT ON COLUMN users.primary_auth_method IS 'Основной метод авторизации пользователя';
COMMENT ON COLUMN users.status IS 'Статус аккаунта: active, inactive, suspended, deleted';
COMMENT ON COLUMN users.is_verified IS 'Подтвержден ли аккаунт';
COMMENT ON COLUMN users.is_premium IS 'Есть ли премиум-доступ';
COMMENT ON COLUMN users.privacy_level IS 'Уровень конфиденциальности: minimal, standard, maximum';
COMMENT ON COLUMN users.premium_until IS 'Дата окончания премиум-доступа';

-- ============================================
-- 6. ПРОФИЛИ ПОЛЬЗОВАТЕЛЕЙ + GEOCODER
-- ============================================

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    
    -- Основная информация
    full_name VARCHAR(255),
    username VARCHAR(100),
    language_code VARCHAR(10) DEFAULT 'ru',
    timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
    
    -- Geocoder поля (сразу!)
    birth_country_code VARCHAR(2) DEFAULT 'RU' CHECK (birth_country_code ~ '^[A-Z]{2}$'),
    system_language VARCHAR(10) DEFAULT 'ru' CHECK (system_language IN ('ru','en','de','fr','es')),
    birth_timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
    
    -- Данные для расчётов
    birth_date DATE NOT NULL,
    birth_time TIME NOT NULL,
    birth_city VARCHAR(100) NOT NULL,
    birth_country VARCHAR(100) DEFAULT 'Russia',
    birth_lat DECIMAL(9,6),
    birth_lng DECIMAL(9,6),
    profession VARCHAR(100), 
    job_position VARCHAR(100), 
    
    -- Текущее местоположение
    current_city VARCHAR(100),
    current_lat DECIMAL(9,6),
    current_lng DECIMAL(9,6),
    
    -- Настройки
    notification_enabled BOOLEAN DEFAULT TRUE,
    daily_recommendations_enabled BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    CONSTRAINT valid_birth_date CHECK (birth_date >= '1900-01-01' AND birth_date <= CURRENT_DATE),
    CONSTRAINT valid_birth_time CHECK (birth_time >= '00:00:00' AND birth_time < '24:00:00')
);


-- Индексы
CREATE INDEX IF NOT EXISTS idx_profiles_birth_date ON user_profiles(birth_date);
CREATE INDEX IF NOT EXISTS idx_profiles_birth_city_trgm ON user_profiles USING GIN(birth_city gin_trgm_ops);



-- ============================================
-- 7. НАТАЛЬНЫЕ КАРТЫ + GEOCODER
-- ============================================

CREATE TABLE IF NOT EXISTS natal_charts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Метаданные расчёта
    calculation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    calculation_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    calculation_time_ms INTEGER,

    -- Географические данные
    city_name VARCHAR(100) NOT NULL,
    birth_lat DECIMAL(9,6) NOT NULL,
    birth_lng DECIMAL(9,6) NOT NULL,
    birth_timezone VARCHAR(50) NOT NULL,
    birth_country_code VARCHAR(2),
    system_language VARCHAR(10) DEFAULT 'ru',
    geocoder_cache_key VARCHAR(64),
    geocoder_source VARCHAR(20) DEFAULT 'manual'
        CHECK (geocoder_source IN ('manual','memory_cache','db_cache','api','nominatim','google','yandex')),

    -- Временные метки рождения
    birth_datetime_local TIMESTAMPTZ,
    birth_datetime_utc TIMESTAMPTZ,
    julian_day DECIMAL(15,6),

    -- Астрологические данные
    planets JSONB NOT NULL DEFAULT '{}',
    houses JSONB NOT NULL DEFAULT '{}',
    aspects JSONB NOT NULL DEFAULT '[]',

    -- Джйотиш
    panchanga JSONB NOT NULL DEFAULT '{}',
    dasha JSONB NOT NULL DEFAULT '{}',

    -- Дополнительные расчеты
    arabic_parts JSONB NOT NULL DEFAULT '{}',
    fixed_stars JSONB NOT NULL DEFAULT '[]',
    planetary_hour JSONB NOT NULL DEFAULT '{}',

    -- Метаданные расчетов
    ayanamsa DECIMAL(10,6),
    sidereal_time DECIMAL(8,4),
    void_of_course_moon BOOLEAN DEFAULT FALSE,
    moon_phase_degrees DECIMAL(6,2),

    -- Детальные данные Луны и Солнца
    moon_data JSONB NOT NULL DEFAULT '{}',
    solar_data JSONB NOT NULL DEFAULT '{}',
    lunar_returns JSONB NOT NULL DEFAULT '[]',
    solar_returns JSONB NOT NULL DEFAULT '[]',

    -- Дополнительные астрологические точки
    critical_degrees JSONB NOT NULL DEFAULT '[]',
    midpoints JSONB NOT NULL DEFAULT '{}',

    -- ✅ НОВЫЕ ПОЛЯ (психологические интерпретации)
    aspect_qualities JSONB NOT NULL DEFAULT '[]',
    patterns JSONB NOT NULL DEFAULT '{}',
    star_interpretations JSONB NOT NULL DEFAULT '[]',
    arabic_connections JSONB NOT NULL DEFAULT '{}',
    calculation_metadata JSONB NOT NULL DEFAULT '{}',

    -- Календарные данные
    weekday VARCHAR(20) DEFAULT 'Monday',
    weekday_ruler VARCHAR(20),

    -- ML-признаки
    ml_features JSONB NOT NULL DEFAULT '{}',

    -- Система домов
    house_system VARCHAR(20) DEFAULT 'Placidus',

    -- Статус
    calculation_status VARCHAR(20) DEFAULT 'success'
        CHECK (calculation_status IN ('pending','success','failed','partial')),
    error_message TEXT,

    -- Временные метки записи
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Индексы (все с IF NOT EXISTS)
CREATE INDEX IF NOT EXISTS idx_natal_user_date ON natal_charts(user_id, calculation_date DESC);
CREATE INDEX IF NOT EXISTS idx_natal_date ON natal_charts(calculation_date);
CREATE INDEX IF NOT EXISTS idx_natal_planets_gin ON natal_charts USING GIN(planets);
CREATE INDEX IF NOT EXISTS idx_natal_panchanga_gin ON natal_charts USING GIN(panchanga);
CREATE INDEX IF NOT EXISTS idx_natal_nakshatra ON natal_charts ((panchanga->>'nakshatra_name'));
CREATE INDEX IF NOT EXISTS idx_natal_arabic_parts_gin ON natal_charts USING GIN(arabic_parts);
CREATE INDEX IF NOT EXISTS idx_natal_dasha_current ON natal_charts ((dasha->>'planet'));
CREATE INDEX IF NOT EXISTS idx_natal_weekday ON natal_charts(weekday);
CREATE INDEX IF NOT EXISTS idx_natal_julian_day ON natal_charts(julian_day);
CREATE INDEX IF NOT EXISTS idx_natal_moon_data_gin ON natal_charts USING GIN(moon_data);
CREATE INDEX IF NOT EXISTS idx_natal_solar_data_gin ON natal_charts USING GIN(solar_data);
CREATE INDEX IF NOT EXISTS idx_natal_ml_features_gin ON natal_charts USING GIN(ml_features);
CREATE INDEX IF NOT EXISTS idx_natal_critical_degrees_gin ON natal_charts USING GIN(critical_degrees);
CREATE INDEX IF NOT EXISTS idx_natal_midpoints_gin ON natal_charts USING GIN(midpoints);

-- ✅ НОВЫЕ ИНДЕКСЫ
CREATE INDEX IF NOT EXISTS idx_natal_aspect_qualities_gin ON natal_charts USING GIN(aspect_qualities);
CREATE INDEX IF NOT EXISTS idx_natal_patterns_gin ON natal_charts USING GIN(patterns);
CREATE INDEX IF NOT EXISTS idx_natal_star_interpretations_gin ON natal_charts USING GIN(star_interpretations);
CREATE INDEX IF NOT EXISTS idx_natal_arabic_connections_gin ON natal_charts USING GIN(arabic_connections);
-- ============================================
-- 8. ПСИХОМАТРИЦЫ 
-- ============================================
-- Таблица психоматриц v2.0
CREATE TABLE IF NOT EXISTS psyho_matrices (
    -- Первичный ключ (ссылка на пользователя)
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,

    -- ============ ОСНОВНЫЕ ЧИСЛА ============
    -- Первое число (сумма всех цифр даты) - может быть мастер-числом
    first_number INTEGER NOT NULL CHECK (first_number BETWEEN 1 AND 99),

    -- Второе число (сумма цифр первого) - всегда 1-9 или мастер-числа
    second_number INTEGER NOT NULL CHECK (
        (second_number BETWEEN 1 AND 99) OR
        (second_number IN (11, 22, 33))
    ),

    -- Третье число (первое - 2*день) - может быть мастер-числом
    third_number INTEGER NOT NULL CHECK (third_number BETWEEN 1 AND 99),

    -- Четвертое число (сумма цифр третьего) - всегда 1-9 или мастер-числа
    fourth_number INTEGER NOT NULL CHECK (
        (fourth_number BETWEEN 1 AND 9) OR
        (fourth_number IN (11, 22, 33))
    ),

    -- ============ МАТРИЦЫ И ХАРАКТЕРИСТИКИ ============
    -- Словарь количеств цифр (ключи "1".."9", значения - количества)
    matrix_digits JSONB NOT NULL DEFAULT '{}',

    matrix_3x3 JSONB NOT NULL DEFAULT '[[0,0,0],[0,0,0],[0,0,0]]',

    -- Детальные характеристики (все анализы)
    characteristics JSONB NOT NULL DEFAULT '{}',

    -- Массивы кодов талантов и сил
    talent_codes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    strength_codes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

    -- ============ АНАЛИТИЧЕСКИЕ ПОЛЯ ============
    -- Уровень энергии (enum)
    energy_level energy_level NOT NULL DEFAULT 'medium',

    -- Жизненное предназначение (текст)
    life_purpose TEXT,

    -- Подсказки по совместимости
    compatibility_hints JSONB NOT NULL DEFAULT '{}',

    -- Дополнительные расчеты
    additional JSONB NOT NULL DEFAULT '{}',

    -- Кармический анализ
    karmic_analysis JSONB NOT NULL DEFAULT '{}',

    -- Прогностические данные
    forecasting JSONB NOT NULL DEFAULT '{}',

    -- ============ МЕТАДАННЫЕ ============
    -- Версия расчета
    calculation_version VARCHAR(20) NOT NULL DEFAULT '3.1'
        CHECK (calculation_version IN ('1.0', '2.0', '3.0', '3.1')),

    -- Временные метки
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============ ИНДЕКСЫ ============

-- Индекс по user_id (для быстрого поиска)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_user_id
    ON psyho_matrices(user_id);

-- Индекс по energy_level (для фильтрации и статистики)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_energy
    ON psyho_matrices(energy_level);

-- GIN индекс для JSONB поля matrix_digits
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_digits_gin
    ON psyho_matrices USING GIN(matrix_digits);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_3x3_gin
    ON psyho_matrices USING GIN(matrix_3x3);

-- GIN индекс для JSONB поля characteristics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_characteristics_gin
    ON psyho_matrices USING GIN(characteristics);

-- GIN индекс для JSONB поля additional
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_additional_gin
    ON psyho_matrices USING GIN(additional);

-- GIN индекс для JSONB поля karmic_analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_karmic_gin
    ON psyho_matrices USING GIN(karmic_analysis);

-- GIN индекс для JSONB поля forecasting
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_forecasting_gin
    ON psyho_matrices USING GIN(forecasting);

-- Индекс по calculation_version (для версионирования)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_version
    ON psyho_matrices(calculation_version);

-- Композитный индекс для частых запросов
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psyho_matrices_user_energy
    ON psyho_matrices(user_id, energy_level);

-- ============ ТРИГГЕР ДЛЯ updated_at ============

-- Функция обновления timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Триггер на обновление
DROP TRIGGER IF EXISTS update_psyho_matrices_updated_at ON psyho_matrices;
CREATE TRIGGER update_psyho_matrices_updated_at
    BEFORE UPDATE ON psyho_matrices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============ КОММЕНТАРИИ ============

COMMENT ON TABLE psyho_matrices IS 'Психоматрицы (квадрат Пифагора) v3.1 - полные расчеты';

COMMENT ON COLUMN psyho_matrices.user_id IS 'ID пользователя (внешний ключ)';
COMMENT ON COLUMN psyho_matrices.first_number IS 'Первое число - сумма всех цифр даты рождения (1-99)';
COMMENT ON COLUMN psyho_matrices.second_number IS 'Второе число - редукция первого (1-9 или 11,22,33)';
COMMENT ON COLUMN psyho_matrices.third_number IS 'Третье число - первое минус удвоенный день (1-99)';
COMMENT ON COLUMN psyho_matrices.fourth_number IS 'Четвертое число - редукция третьего (1-9 или 11,22,33)';
COMMENT ON COLUMN psyho_matrices.matrix_digits IS 'JSON объект с количеством каждой цифры 1-9';
COMMENT ON COLUMN psyho_matrices.matrix_3x3 IS 'Матрица 3x3 для позиционного анализа';
COMMENT ON COLUMN psyho_matrices.characteristics IS 'Детальный анализ всех характеристик';
COMMENT ON COLUMN psyho_matrices.talent_codes IS 'Массив кодов талантов';
COMMENT ON COLUMN psyho_matrices.strength_codes IS 'Массив кодов сильных сторон';
COMMENT ON COLUMN psyho_matrices.energy_level IS 'Уровень энергии (very_low, low, medium, high, very_high)';
COMMENT ON COLUMN psyho_matrices.life_purpose IS 'Описание жизненного предназначения';
COMMENT ON COLUMN psyho_matrices.compatibility_hints IS 'Данные для анализа совместимости';
COMMENT ON COLUMN psyho_matrices.additional IS 'Дополнительные нумерологические расчеты';
COMMENT ON COLUMN psyho_matrices.karmic_analysis IS 'Кармический анализ (долги, задачи, прошлые жизни)';
COMMENT ON COLUMN psyho_matrices.forecasting IS 'Прогностические данные (годы, периоды, рекомендации)';
COMMENT ON COLUMN psyho_matrices.calculation_version IS 'Версия алгоритма расчета';
COMMENT ON COLUMN psyho_matrices.created_at IS 'Время создания записи';
COMMENT ON COLUMN psyho_matrices.updated_at IS 'Время последнего обновления';
-- ============================================
-- 9. БИОРИТМЫ 
-- ============================================
-- Создаем таблицу только для статического профиля
CREATE TABLE IF NOT EXISTS biorhythms (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    calculation_date DATE NOT NULL,

    -- ========== ПРОФИЛЬНЫЕ ПОЛЯ ==========
    profile_version VARCHAR(10) NOT NULL DEFAULT '1.0',
    profile_calculated_at DATE,
    days_analyzed INTEGER CHECK (days_analyzed > 0),

    -- Фазы при рождении (от -1.0 до 1.0)
    birth_physical FLOAT CHECK (birth_physical BETWEEN -1.0 AND 1.0),
    birth_emotional FLOAT CHECK (birth_emotional BETWEEN -1.0 AND 1.0),
    birth_intellectual FLOAT CHECK (birth_intellectual BETWEEN -1.0 AND 1.0),
    birth_intuitive FLOAT CHECK (birth_intuitive BETWEEN -1.0 AND 1.0),

    -- ML метрики (от 0 до 1)
    system_stability FLOAT CHECK (system_stability BETWEEN 0 AND 1),
    predictability FLOAT CHECK (predictability BETWEEN 0 AND 1),

    -- Полный профиль в JSONB (ВСЕ данные для Mistral)
    profile_data JSONB NOT NULL DEFAULT '{}',

    -- Временные метки
    calculated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Уникальность (один профиль на пользователя)
    UNIQUE(user_id)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_biorhythms_user ON biorhythms(user_id);
CREATE INDEX IF NOT EXISTS idx_biorhythms_profile_date ON biorhythms(profile_calculated_at);
CREATE INDEX IF NOT EXISTS idx_biorhythms_stability ON biorhythms(system_stability);

-- GIN индекс для JSONB
CREATE INDEX IF NOT EXISTS idx_biorhythms_profile_data_gin ON biorhythms USING gin(profile_data);

-- Комментарии
COMMENT ON TABLE biorhythms IS 'Статический профиль биоритмов пользователя';
COMMENT ON COLUMN biorhythms.profile_version IS 'Версия алгоритма расчета профиля';
COMMENT ON COLUMN biorhythms.profile_calculated_at IS 'Дата расчета профиля';
COMMENT ON COLUMN biorhythms.days_analyzed IS 'Количество дней для анализа (обычно 1825 = 5 лет)';
COMMENT ON COLUMN biorhythms.birth_physical IS 'Фаза физического цикла при рождении (-1..1)';
COMMENT ON COLUMN biorhythms.system_stability IS 'Стабильность системы (0-1)';
COMMENT ON COLUMN biorhythms.profile_data IS 'Полные данные профиля для Mistral';

-- ============================================
-- 10. MAGIC PROFILES 
-- ============================================

CREATE TABLE magic_profiles (
    -- Уникальный идентификатор записи
    id SERIAL PRIMARY KEY,

    -- Связь с пользователем (один к одному)
    user_id INTEGER NOT NULL UNIQUE
        REFERENCES users(id) ON DELETE CASCADE,

    -- ============ v2.0 ЯДРО ============
    -- 9 осей личности (заменяет все старые JSONB поля)
    axes JSONB NOT NULL DEFAULT '{}',
    
    axis_count INTEGER DEFAULT 9 NOT NULL,
    
    data_sources TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Интегрированный психологический портрет
    psychological_blueprint JSONB NOT NULL DEFAULT '{}',

    -- ML-признаки (raw_features + big_five + special_indicators)
    ml_features JSONB NOT NULL DEFAULT '{}',

    -- ============ ML ВЕКТОР ============
    -- Фиксированный вектор для поиска похожих (длина 26)
    feature_vector REAL[] NOT NULL DEFAULT ARRAY[]::REAL[],

    -- Кластеризация
    cluster_id INTEGER,
    anomaly_score REAL DEFAULT 0.0
        CHECK (anomaly_score >= 0 AND anomaly_score <= 1),

    -- ============ МЕТАДАННЫЕ ============
    -- Версия профиля
    profile_version VARCHAR(20) DEFAULT '2.0',

    -- Общая уверенность в данных
    confidence_score REAL DEFAULT 0.85
        CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Единый JSON с метаданными расчета
    -- Включает: axis_count, feature_count, calculation_time_ms, data_sources
    calculation_metadata JSONB NOT NULL DEFAULT '{}',

    -- ============ СТАТУС ============
    -- Флаг валидности
    is_valid BOOLEAN DEFAULT TRUE,

    -- Ошибки валидации
    validation_errors TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- ============ ВРЕМЕННЫЕ МЕТКИ ============
    calculated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- =====================================================
-- ИНДЕКСЫ
-- =====================================================

-- 1. Уникальный индекс для быстрого поиска по user_id
CREATE UNIQUE INDEX idx_magic_user_id
    ON magic_profiles(user_id);

-- 2. GIN индексы для JSONB полей (сложные запросы)
CREATE INDEX idx_magic_axes_gin
    ON magic_profiles USING GIN(axes);

CREATE INDEX idx_magic_blueprint_gin
    ON magic_profiles USING GIN(psychological_blueprint);

CREATE INDEX idx_magic_ml_features_gin
    ON magic_profiles USING GIN(ml_features);

CREATE INDEX idx_magic_metadata_gin
    ON magic_profiles USING GIN(calculation_metadata);

-- 3. Индекс для кластеризации
CREATE INDEX idx_magic_cluster_id
    ON magic_profiles(cluster_id);

-- 4. Индекс для confidence (часто используется в фильтрах)
CREATE INDEX idx_magic_confidence
    ON magic_profiles(confidence_score);

-- 5. Индекс для поиска по версиям
CREATE INDEX idx_magic_version
    ON magic_profiles(profile_version);

-- 6. GIN индекс для массива ошибок (опционально)
CREATE INDEX idx_magic_errors_gin
    ON magic_profiles USING GIN(validation_errors);

-- =====================================================
-- ТРИГГЕР для автоматического обновления updated_at
-- =====================================================

CREATE OR REPLACE FUNCTION update_magic_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_magic_updated_at
    BEFORE UPDATE ON magic_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_magic_updated_at();

-- =====================================================
-- КОММЕНТАРИИ (для документации)
-- =====================================================

COMMENT ON TABLE magic_profiles IS 'Magic Profile v2.0 - 9 осей личности (энергия, здоровье, интеллект, эмоции, труд, удача, социум, карма, миссия)';

COMMENT ON COLUMN magic_profiles.axes IS '9 осей личности с полной структурой: energy_will, health_physical, intellect_logic, emotions_intuition, work_discipline, luck_talent, social_relations, karma_cycles, destiny_mission';
COMMENT ON COLUMN magic_profiles.psychological_blueprint IS 'Интегрированный психологический портрет: core_personality, emotional_architecture, cognitive_style, social_dynamics, life_purpose_indicators';
COMMENT ON COLUMN magic_profiles.ml_features IS 'ML-признаки: raw_features (18+ метрик), big_five, special_indicators (has_spica, has_yod, destiny_intensity)';
COMMENT ON COLUMN magic_profiles.feature_vector IS 'Фиксированный вектор для ML моделей (27 признаков: 18 raw + 5 big5 + 3 special)';
COMMENT ON COLUMN magic_profiles.calculation_metadata IS 'Метаданные расчета: axis_count (9), feature_count (26), calculation_time_ms, data_sources';


-- ============================================
-- 11. ОПТИМАЛЬНЫЕ АКТИВНОСТИ 
-- ============================================

CREATE TABLE IF NOT EXISTS optimal_activities (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    calculation_date DATE NOT NULL,
    
    -- Оптимальные активности
    activity_indices SMALLINT[] NOT NULL DEFAULT '{}',
    activity_types activity_type[] NOT NULL DEFAULT '{}',
    
    -- Оценки активностей
    activity_scores REAL[] NOT NULL DEFAULT '{}',
    confidence_scores REAL[] NOT NULL DEFAULT '{}',
    
    -- Рекомендации
    recommendations TEXT[] NOT NULL DEFAULT '{}',
    time_slots JSONB NOT NULL DEFAULT '{}',
    priority_order SMALLINT[] NOT NULL DEFAULT '{}',
    
    -- Энергетические метрики
    energy_level REAL NOT NULL CHECK (energy_level >= 0 AND energy_level <= 1),
    energy_trend VARCHAR(10) CHECK (energy_trend IN ('rising', 'falling', 'stable')),
    focus_areas TEXT[] DEFAULT '{}',
    
    -- ML-данные
    ml_features JSONB NOT NULL DEFAULT '{}',
    feature_vector REAL[] NOT NULL DEFAULT '{}',
    model_version VARCHAR(20) DEFAULT '1.0',
    
    -- Статус
    is_generated BOOLEAN DEFAULT TRUE,
    is_approved BOOLEAN DEFAULT FALSE,
    user_feedback SMALLINT CHECK (user_feedback BETWEEN 1 AND 5),
    
    -- Временные метки
    generated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Уникальность
    UNIQUE(user_id, calculation_date)
);

CREATE INDEX IF NOT EXISTS idx_activities_user_date ON optimal_activities(user_id, calculation_date DESC);

-- ============================================
-- 12. РЕКОМЕНДАЦИИ 
-- ============================================

-- 1. Recommendations (упрощённая)
CREATE TABLE recommendations (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    calculation_date DATE NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    category VARCHAR(50) NOT NULL,
    priority SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    relevance_score REAL NOT NULL DEFAULT 0.5 CHECK (relevance_score BETWEEN 0 AND 1),
    data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, calculation_date, category)
);

-- 2. Daily Forecast Cache
CREATE TABLE daily_forecast_cache (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    forecast_date DATE NOT NULL,  -- ✅ Согласованное имя
    axes_deltas JSONB NOT NULL,
    daily_axes JSONB NOT NULL,
    recommendations JSONB,
    background_risks JSONB,
    subtle_signals JSONB,
    signal_categories JSONB,
    rules_version VARCHAR(20) DEFAULT 'v1.0',
    invalidated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    UNIQUE(user_id, forecast_date)
);

-- 3. Feedback
CREATE TABLE forecast_feedback (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    forecast_date DATE,
    axis_name VARCHAR(50),
    predicted_score REAL,
    user_rating REAL,
    delta REAL,
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. История пересчёта профиля (для анализа динамики)
CREATE TABLE profile_snapshots (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    axes JSONB NOT NULL,
    ml_features JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы (оптимизированные)
CREATE INDEX CONCURRENTLY idx_recommendations_user_date ON recommendations(user_id, calculation_date DESC);
CREATE INDEX CONCURRENTLY idx_daily_cache_date ON daily_forecast_cache(user_id, forecast_date);
CREATE INDEX CONCURRENTLY idx_feedback_accuracy ON forecast_feedback(delta) WHERE delta IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_daily_forecast_cache_user_date ON daily_forecast_cache(user_id, forecast_date);
-- Добавить для быстрых запросов фидбека по пользователю:
CREATE INDEX CONCURRENTLY idx_feedback_user_date ON forecast_feedback(user_id, forecast_date);


-- ============================================
-- 13. ПСИХОЛОГИЧЕСКИЕ ТЕСТЫ 
-- ============================================

CREATE TABLE IF NOT EXISTS psychological_tests (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Информация о тесте
    test_type test_type NOT NULL,
    test_version VARCHAR(20) NOT NULL,
    test_name VARCHAR(100) NOT NULL,
    
    -- Вопросы и ответы
    questions JSONB NOT NULL DEFAULT '[]',
    answers JSONB NOT NULL DEFAULT '{}',
    raw_responses JSONB NOT NULL DEFAULT '{}',
    
    -- Результаты
    scores JSONB NOT NULL DEFAULT '{}',
    profile_type VARCHAR(50),
    interpretation TEXT,
    insights JSONB NOT NULL DEFAULT '{}',
    
    -- Метаданные
    completion_percentage SMALLINT NOT NULL DEFAULT 100 CHECK (completion_percentage BETWEEN 0 AND 100),
    time_spent_seconds INTEGER,
    device_info JSONB DEFAULT '{}',
    
    -- Статус
    status VARCHAR(20) DEFAULT 'completed' CHECK (status IN ('started', 'in_progress', 'completed', 'abandoned')),
    
    -- Временные метки
    started_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Уникальность
    UNIQUE(user_id, test_type, test_version)
);

CREATE INDEX IF NOT EXISTS idx_tests_user ON psychological_tests(user_id);
CREATE INDEX IF NOT EXISTS idx_tests_type ON psychological_tests(test_type);

-- ============================================
-- 14. АСТРОЛОГИЧЕСКИЕ СОБЫТИЯ 
-- ============================================

CREATE TABLE IF NOT EXISTS astro_events (
    id BIGSERIAL PRIMARY KEY,
    
    -- Дата события
    event_date DATE NOT NULL,
    event_time TIMESTAMPTZ,
    
    -- Тип события
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'new_moon', 'full_moon', 'first_quarter', 'last_quarter',
        'mercury_retrograde', 'venus_retrograde', 'mars_retrograde',
        'jupiter_retrograde', 'saturn_retrograde', 'uranus_retrograde',
        'neptune_retrograde', 'pluto_retrograde',
        'eclipse_solar', 'eclipse_lunar',
        'planetary_transit'
    )),
    
    -- Детали события
    event_name VARCHAR(100) NOT NULL,
    description TEXT,
    significance_level VARCHAR(20) CHECK (significance_level IN ('low', 'medium', 'high', 'critical')),
    
    -- Астрологические данные
    zodiac_sign VARCHAR(20),
    degree DECIMAL(5,2),
    planetary_aspects JSONB DEFAULT '{}',
    
    -- Рекомендации
    general_recommendations TEXT[] DEFAULT '{}',
    caution_areas TEXT[] DEFAULT '{}',
    
    -- Метаданные
    source VARCHAR(50) DEFAULT 'calculated',
    confidence REAL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1),
    
    -- Временные метки
    calculated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_astro_events_date ON astro_events(event_date);
CREATE INDEX IF NOT EXISTS idx_astro_events_type ON astro_events(event_type);

-- ============================================
-- 15. СИСТЕМНЫЙ АУДИТ И ЛОГИ 
-- ============================================

CREATE TABLE IF NOT EXISTS system_audit_log (
    id BIGSERIAL PRIMARY KEY,
    
    -- Действие
    action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('create', 'read', 'update', 'delete', 'login', 'logout', 'error')),
    action_name VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    
    -- Пользователь
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    user_ip INET,
    user_agent TEXT,
    session_id UUID,
    
    -- Данные
    request_data JSONB,
    response_data JSONB,
    error_details TEXT,
    stack_trace TEXT,
    
    -- Статус
    status_code INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_code VARCHAR(50),
    
    -- Производительность
    duration_ms INTEGER CHECK (duration_ms >= 0),
    memory_usage_kb INTEGER,
    
    -- Метаданные
    service_name VARCHAR(50) NOT NULL,
    endpoint VARCHAR(255),
    http_method VARCHAR(10),
    
    -- Временные метки
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON system_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_date ON system_audit_log(created_at DESC);

-- ============================================
-- 16. КЭШ РАСЧЁТОВ 
-- ============================================

CREATE TABLE IF NOT EXISTS calculation_cache (
    id BIGSERIAL PRIMARY KEY,
    
    -- Ключ кэша
    cache_key VARCHAR(255) NOT NULL UNIQUE,
    cache_group VARCHAR(100) NOT NULL,
    
    -- Данные
    data JSONB NOT NULL,
    data_hash VARCHAR(64) NOT NULL,
    
    -- Метаданные
    calculation_type VARCHAR(50) NOT NULL,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    
    -- Время жизни
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Статистика использования
    access_count INTEGER DEFAULT 0,
    is_valid BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_cache_key ON calculation_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON calculation_cache(expires_at) WHERE is_valid = TRUE;

-- ============================================
-- 17. МЕТРИКИ И СТАТИСТИКА 
-- ============================================

CREATE TABLE IF NOT EXISTS system_metrics (
    id BIGSERIAL PRIMARY KEY,
    
    -- Идентификация метрики
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL CHECK (metric_type IN ('counter', 'gauge', 'histogram', 'summary')),
    
    -- Значение
    metric_value DOUBLE PRECISION NOT NULL,
    metric_labels JSONB DEFAULT '{}',
    
    -- Метаданные
    service_name VARCHAR(50) NOT NULL,
    hostname VARCHAR(100),
    
    -- Временные метки
    collected_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_name_date ON system_metrics(metric_name, collected_at DESC);

-- ============================================
-- 18. ML МЕТРИКИ 
-- ============================================

CREATE TABLE IF NOT EXISTS ml_model_metrics (
    id BIGSERIAL PRIMARY KEY,
    
    -- Идентификация модели
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    
    -- Метрики производительности
    inference_time_ms INTEGER NOT NULL,
    memory_usage_mb INTEGER NOT NULL,
    success_rate REAL NOT NULL CHECK (success_rate BETWEEN 0 AND 1),
    
    -- Метаданные запроса
    input_size_bytes INTEGER,
    output_size_bytes INTEGER,
    user_id BIGINT REFERENCES users(id),
    
    -- Временные метки
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ml_metrics_model ON ml_model_metrics(model_name, timestamp DESC);

-- ============================================
-- 19. ТРИГГЕРЫ И ФУНКЦИИ 
-- ============================================

-- Функция обновления updated_at 
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для обновления updated_at
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at 
    BEFORE UPDATE ON user_profiles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_natal_charts_updated_at 
    BEFORE UPDATE ON natal_charts 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_magic_profiles_updated_at 
    BEFORE UPDATE ON magic_profiles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_recommendations_updated_at 
    BEFORE UPDATE ON recommendations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_astro_events_updated_at 
    BEFORE UPDATE ON astro_events 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Функция для обновления активности пользователя 
CREATE OR REPLACE FUNCTION update_user_activity()
RETURNS TRIGGER AS $$
BEGIN
    -- Используем CTE для обновления без рекурсивного триггера
    WITH activity_update AS (
        UPDATE users 
        SET last_activity_at = NOW()
        WHERE id = NEW.user_id
        AND last_activity_at < NOW() - INTERVAL '5 minutes'
        RETURNING 1
    )
    SELECT 1 FROM activity_update;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры для обновления активности
CREATE TRIGGER update_activity_on_recommendation
    AFTER INSERT OR UPDATE ON recommendations
    FOR EACH ROW EXECUTE FUNCTION update_user_activity();

CREATE TRIGGER update_activity_on_test
    AFTER INSERT OR UPDATE ON psychological_tests
    FOR EACH ROW EXECUTE FUNCTION update_user_activity();

-- 1. Функция очистки expired прогнозов
CREATE OR REPLACE FUNCTION cleanup_old_forecasts()
RETURNS void AS $$
BEGIN
    DELETE FROM daily_forecast_cache
    WHERE expires_at < NOW();

    RAISE NOTICE 'Cleaned % expired forecasts at %',
        FOUND, NOW();
END;
$$ LANGUAGE plpgsql;

-- 2. Функция общей очистки БД (отдельно!)
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
BEGIN
    -- Удаляем старые метрики (90 дней)
    DELETE FROM system_metrics
    WHERE collected_at < NOW() - INTERVAL '90 days';

    -- Удаляем старые ML метрики (30 дней)
    DELETE FROM ml_model_metrics
    WHERE timestamp < NOW() - INTERVAL '30 days';

    -- Инвалидируем старый кэш (7 дней)
    UPDATE calculation_cache
    SET is_valid = FALSE
    WHERE expires_at < NOW() - INTERVAL '7 days';

    -- Архивируем старые аудит логи (1 год)
    DELETE FROM system_audit_log
    WHERE created_at < NOW() - INTERVAL '1 year';

    RAISE NOTICE 'Database cleanup completed at %', NOW();
END;
$$ LANGUAGE plpgsql;

-- 3. Планировщики (cron)
--SELECT cron.schedule('cleanup-forecasts-weekly', '0 2 * * 0', 'SELECT cleanup_old_forecasts();');
--SELECT cron.schedule('cleanup-data-monthly', '0 3 1 * *', 'SELECT cleanup_old_data();');



-- ============================================
-- 20. НАСТРОЙКА ПРАВ ДОСТУПА 
-- ============================================

-- Даем права на подключение
GRANT CONNECT ON DATABASE personalassistant TO personal_assistant_app;

-- Даем права на схему
GRANT USAGE ON SCHEMA public TO personal_assistant_app;

-- Права для приложения
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public 
TO personal_assistant_app;

GRANT USAGE ON ALL SEQUENCES IN SCHEMA public 
TO personal_assistant_app;

-- Права для выполнения функций
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public 
TO personal_assistant_app;

-- Настройка прав по умолчанию для будущих таблиц 
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES 
TO personal_assistant_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public 
GRANT USAGE ON SEQUENCES 
TO personal_assistant_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public 
GRANT EXECUTE ON FUNCTIONS 
TO personal_assistant_app;

-- ============================================
-- 21. ПРЕДСТАВЛЕНИЯ ДЛЯ МОНИТОРИНГА
-- ============================================

-- Полная информация о пользователе
CREATE OR REPLACE VIEW user_complete_info AS
SELECT 
    u.id,
    u.telegram_id,
    u.status,
    COALESCE(u.is_premium, FALSE) as is_premium,  --  Защита
    --u.is_premium,
    u.created_at as user_created,
    u.last_activity_at,
    
    up.full_name,
    up.username,
    up.language_code,
    up.birth_date,
    up.birth_city,
    up.profession,
    up.current_city,
    
    -- Статистика
    -- Безопасный подсчёт (игнорирует ошибки)
    COALESCE((SELECT COUNT(*) FROM natal_charts nc WHERE nc.user_id = u.id), 0) as natal_charts_count,
    COALESCE((SELECT COUNT(*) FROM biorhythms b WHERE b.user_id = u.id), 0) as biorhythms_count,
    COALESCE((SELECT COUNT(*) FROM recommendations r WHERE r.user_id = u.id), 0) as recommendations_count,
    COALESCE((SELECT COUNT(*) FROM psychological_tests pt WHERE pt.user_id = u.id), 0) as tests_count
    
FROM users u
LEFT JOIN user_profiles up ON u.id = up.user_id;

-- Ежедневная сводка
CREATE OR REPLACE VIEW daily_user_summary AS
SELECT 
    DATE(created_at) as date,
    COUNT(*) as new_users,
    COUNT(*) FILTER (WHERE is_premium = TRUE) as new_premium_users,
    COUNT(DISTINCT telegram_id) as active_users,
    
    -- Активность
    (SELECT COUNT(*) FROM recommendations 
     WHERE calculation_date = CURRENT_DATE) as daily_recommendations,
    
    (SELECT COUNT(*) FROM biorhythms 
     WHERE calculation_date = CURRENT_DATE) as daily_biorhythms,
    
    -- Конверсия
    ROUND(
        COUNT(*) FILTER (WHERE last_activity_at >= NOW() - INTERVAL '7 days') * 100.0 / 
        NULLIF(COUNT(*), 0), 2
    ) as weekly_retention_rate
    
FROM users
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Статистика рекомендаций
--
-- ML модели метрики
CREATE OR REPLACE VIEW ml_models_performance AS
SELECT 
    model_name,
    model_version,
    COUNT(*) as total_inferences,
    AVG(inference_time_ms) as avg_inference_time,
    AVG(success_rate) * 100 as avg_success_rate,
    AVG(memory_usage_mb) as avg_memory_mb,
    MIN(timestamp) as first_used,
    MAX(timestamp) as last_used
    
FROM ml_model_metrics
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY model_name, model_version
ORDER BY total_inferences DESC;

-- ============================================
-- 22. КОММЕНТАРИИ К ТАБЛИЦАМ
-- ============================================

COMMENT ON TABLE users IS 'Основная таблица пользователей системы';
COMMENT ON TABLE user_profiles IS 'Дополнительная информация о пользователях для расчётов';
COMMENT ON TABLE natal_charts IS 'Натальные астрологические карты';
COMMENT ON TABLE psyho_matrices IS 'Нумерологические психоматрицы по методу Пифагора';
COMMENT ON TABLE biorhythms IS 'Расчёты биоритмов пользователей';
COMMENT ON TABLE magic_profiles IS 'Интегрированные психологические и эзотерические профили';
COMMENT ON TABLE optimal_activities IS 'Рекомендации оптимальных активностей';
COMMENT ON TABLE recommendations IS 'Итоговые персонализированные рекомендации';
COMMENT ON TABLE psychological_tests IS 'Результаты психологических тестов пользователей';
COMMENT ON TABLE astro_events IS 'Астрологические события и лунные фазы';
COMMENT ON TABLE system_audit_log IS 'Логирование действий в системе';
COMMENT ON TABLE calculation_cache IS 'Кэш результатов расчётов для оптимизации';
COMMENT ON TABLE system_metrics IS 'Метрики производительности системы';
COMMENT ON TABLE ml_model_metrics IS 'Метрики производительности ML моделей';
COMMENT ON COLUMN daily_forecast_cache.background_risks IS 'Список фоновых рисков от слабых сигналов';
COMMENT ON COLUMN daily_forecast_cache.subtle_signals IS 'Детали слабых сигналов по осям';
COMMENT ON COLUMN daily_forecast_cache.signal_categories IS 'Категоризация всех сигналов (critical/strong/medium/weak)';

-- ============================================
-- 23. ВАЛИДАЦИЯ И ФИНАЛЬНАЯ НАСТРОЙКА
-- ============================================

DO $$
DECLARE
    table_count INTEGER;
    index_count INTEGER;
    view_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count FROM pg_tables WHERE schemaname = 'public';
    SELECT COUNT(*) INTO index_count FROM pg_indexes WHERE schemaname = 'public';
    SELECT COUNT(*) INTO view_count FROM pg_views WHERE schemaname = 'public';
    
    RAISE NOTICE '============================================';
    RAISE NOTICE 'PERSONAL ASSISTANT v4.1 - PRODUCTION READY';
    RAISE NOTICE 'Tables: % | Indexes: % | Views: %', table_count, index_count, view_count;
    RAISE NOTICE 'Ready for ML/Astrology at %', NOW();
    RAISE NOTICE '============================================';
END $$;

-- ============================================
-- 24. ПРОВЕРОЧНЫЙ ЗАПРОС (опционально)
-- ============================================

-- Проверяем создание таблиц (только для отладки)
DO $$
BEGIN
    RAISE NOTICE 'Database structure verification:';
    RAISE NOTICE '  Users table: %', (SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'users'));
    RAISE NOTICE '  Recommendations table: %', (SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'recommendations'));
    RAISE NOTICE '  ML metrics table: %', (SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'ml_model_metrics'));
    RAISE NOTICE '  Role exists: %', (SELECT EXISTS (SELECT FROM pg_roles WHERE rolname = 'personal_assistant_app'));
END
$$;
