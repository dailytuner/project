-- ============================================================
-- Psychometry Service Database Schema
-- Version: 3.4
-- Schema: psych
-- ============================================================

-- ============================================================
-- 1. CREATE SCHEMA
-- ============================================================
CREATE SCHEMA IF NOT EXISTS psych;

-- ============================================================
-- 2. CREATE TABLES
-- ============================================================

-- 2.1. MMPI RESULTS
CREATE TABLE IF NOT EXISTS psych.mmpi_results (
    -- Primary & Foreign Keys
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- Test Metadata
    taken_at TIMESTAMPTZ NOT NULL,
    test_version VARCHAR(20) DEFAULT 'MMPI-2',

    -- Clinical Scales (T-scores)
    hs_t_score FLOAT,
    d_t_score FLOAT,
    hy_t_score FLOAT,
    pd_t_score FLOAT,
    mf_t_score FLOAT,
    pa_t_score FLOAT,
    pt_t_score FLOAT,
    sc_t_score FLOAT,
    ma_t_score FLOAT,
    si_t_score FLOAT,

    -- Validity Scales (Raw scores)
    l_raw_score FLOAT,
    f_raw_score FLOAT,
    k_raw_score FLOAT,
    q_count INTEGER,
    is_valid BOOLEAN,

    -- Idempotency
    idempotency_key VARCHAR(64) UNIQUE,

    -- Astrological Context (NULL in fallback mode)
    dasha_maha VARCHAR(20),
    dasha_antar VARCHAR(20),
    dasha_pratyantar VARCHAR(20),
    transit_saturn_house INTEGER,
    transit_jupiter_house INTEGER,
    transit_rahu_house INTEGER,
    moon_sign VARCHAR(20),
    moon_house INTEGER,
    moon_phase VARCHAR(20),
    is_retro_mercury BOOLEAN,
    is_retro_venus BOOLEAN,
    is_retro_mars BOOLEAN,

    -- Data Lake Reference
    raw_data_uri TEXT,

    -- System Fields
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.2. IAT RESULTS
CREATE TABLE IF NOT EXISTS psych.iat_results (
    -- Primary & Foreign Keys
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- Test Metadata
    taken_at TIMESTAMPTZ NOT NULL,
    test_type VARCHAR(50) NOT NULL,

    -- Core Results
    d_score FLOAT NOT NULL,
    mean_rt_ms FLOAT,
    error_rate FLOAT,
    rt_std FLOAT,
    practice_effect_score FLOAT,

    -- Idempotency
    idempotency_key VARCHAR(64) UNIQUE,

    -- Session Seed (BIGINT to avoid overflow)
    session_seed BIGINT NOT NULL,

    -- Astrological Context (NULL in fallback mode)
    dasha_maha VARCHAR(20),
    dasha_antar VARCHAR(20),
    transit_moon_house INTEGER,
    moon_phase VARCHAR(20),
    is_retro_mercury BOOLEAN,
    is_retro_venus BOOLEAN,
    transit_saturn_house INTEGER,

    -- Data Lake Reference
    raw_data_uri TEXT,

    -- System Fields
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.3. TEST SCHEDULE
CREATE TABLE IF NOT EXISTS psych.test_schedule (
    -- Primary & Foreign Keys
    user_id BIGINT PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,

    -- Last Test Timestamps
    last_mmpi_at TIMESTAMPTZ,
    last_iat_at TIMESTAMPTZ,

    -- Next Available Dates (DATE only)
    next_mmpi_due DATE,
    next_iat_due DATE,

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- System Fields
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2.4. OUTBOX
CREATE TABLE IF NOT EXISTS psych.outbox (
    -- Primary Key
    id BIGSERIAL PRIMARY KEY,

    -- Event Metadata
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,

    -- Idempotency
    idempotency_key VARCHAR(64) UNIQUE,

    -- Status
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'sent', 'dead_letter')),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,

    -- Retry Management
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,

    -- System Fields
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. CREATE INDEXES
-- ============================================================

-- MMPI Results Indexes
CREATE INDEX IF NOT EXISTS idx_mmpi_user_date ON psych.mmpi_results(user_id, taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_mmpi_idempotency ON psych.mmpi_results(idempotency_key);

-- IAT Results Indexes
CREATE INDEX IF NOT EXISTS idx_iat_user_date ON psych.iat_results(user_id, taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_iat_idempotency ON psych.iat_results(idempotency_key);

-- Test Schedule Indexes
CREATE INDEX IF NOT EXISTS idx_schedule_next_mmpi ON psych.test_schedule(next_mmpi_due)
    WHERE next_mmpi_due IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_schedule_next_iat ON psych.test_schedule(next_iat_due)
    WHERE next_iat_due IS NOT NULL;

-- Outbox Indexes
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON psych.outbox(status, created_at)
    WHERE status IN ('pending', 'processing');

CREATE INDEX IF NOT EXISTS idx_outbox_dead_letter ON psych.outbox(status)
    WHERE status = 'dead_letter';

-- ============================================================
-- 4. CREATE TRIGGERS
-- ============================================================

-- 4.1. Update Function
CREATE OR REPLACE FUNCTION psych.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4.2. Apply Triggers
DROP TRIGGER IF EXISTS update_mmpi_results_updated_at ON psych.mmpi_results;
CREATE TRIGGER update_mmpi_results_updated_at
    BEFORE UPDATE ON psych.mmpi_results
    FOR EACH ROW EXECUTE FUNCTION psych.update_updated_at();

DROP TRIGGER IF EXISTS update_iat_results_updated_at ON psych.iat_results;
CREATE TRIGGER update_iat_results_updated_at
    BEFORE UPDATE ON psych.iat_results
    FOR EACH ROW EXECUTE FUNCTION psych.update_updated_at();

DROP TRIGGER IF EXISTS update_test_schedule_updated_at ON psych.test_schedule;
CREATE TRIGGER update_test_schedule_updated_at
    BEFORE UPDATE ON psych.test_schedule
    FOR EACH ROW EXECUTE FUNCTION psych.update_updated_at();

DROP TRIGGER IF EXISTS update_outbox_updated_at ON psych.outbox;
CREATE TRIGGER update_outbox_updated_at
    BEFORE UPDATE ON psych.outbox
    FOR EACH ROW EXECUTE FUNCTION psych.update_updated_at();

-- ============================================================
-- 5. CREATE ROLES AND PERMISSIONS
-- ============================================================

-- 5.1. Create Role (if not exists) - PostgreSQL 9.6+ compatible
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'psychometry_app') THEN
        CREATE ROLE psychometry_app;
    END IF;
END
$$;

-- 5.2. Grant Schema Permissions
GRANT USAGE ON SCHEMA psych TO psychometry_app;

-- 5.3. Grant Table Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA psych TO psychometry_app;

-- 5.4. Grant Sequence Permissions
GRANT USAGE ON ALL SEQUENCES IN SCHEMA psych TO psychometry_app;

-- 5.5. Grant Function Permissions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA psych TO psychometry_app;

-- 5.6. Set Default Permissions for Future Tables
ALTER DEFAULT PRIVILEGES IN SCHEMA psych
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO psychometry_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA psych
    GRANT USAGE ON SEQUENCES TO psychometry_app;

-- ============================================================
-- 6. ADD COMMENTS FOR DOCUMENTATION
-- ============================================================

COMMENT ON SCHEMA psych IS 'Psychometry Service schema for MMPI-2 and IAT testing';

-- MMPI Results Comments
COMMENT ON TABLE psych.mmpi_results IS 'MMPI-2 test results with T-scores, validity scales, and astrological context';
COMMENT ON COLUMN psych.mmpi_results.id IS 'Unique result identifier';
COMMENT ON COLUMN psych.mmpi_results.user_id IS 'Reference to users table';
COMMENT ON COLUMN psych.mmpi_results.taken_at IS 'Timestamp when test was completed';
COMMENT ON COLUMN psych.mmpi_results.test_version IS 'MMPI version (default: MMPI-2)';
COMMENT ON COLUMN psych.mmpi_results.hs_t_score IS 'Hypochondriasis T-score';
COMMENT ON COLUMN psych.mmpi_results.d_t_score IS 'Depression T-score';
COMMENT ON COLUMN psych.mmpi_results.hy_t_score IS 'Hysteria T-score';
COMMENT ON COLUMN psych.mmpi_results.pd_t_score IS 'Psychopathic Deviate T-score';
COMMENT ON COLUMN psych.mmpi_results.mf_t_score IS 'Masculinity/Femininity T-score';
COMMENT ON COLUMN psych.mmpi_results.pa_t_score IS 'Paranoia T-score';
COMMENT ON COLUMN psych.mmpi_results.pt_t_score IS 'Psychasthenia T-score';
COMMENT ON COLUMN psych.mmpi_results.sc_t_score IS 'Schizophrenia T-score';
COMMENT ON COLUMN psych.mmpi_results.ma_t_score IS 'Hypomania T-score';
COMMENT ON COLUMN psych.mmpi_results.si_t_score IS 'Social Introversion T-score';
COMMENT ON COLUMN psych.mmpi_results.l_raw_score IS 'Lie Scale raw score (validity)';
COMMENT ON COLUMN psych.mmpi_results.f_raw_score IS 'Infrequency Scale raw score (validity)';
COMMENT ON COLUMN psych.mmpi_results.k_raw_score IS 'Defensiveness Scale raw score (validity)';
COMMENT ON COLUMN psych.mmpi_results.q_count IS 'Number of omitted answers';
COMMENT ON COLUMN psych.mmpi_results.is_valid IS 'Whether test passed validity checks (L≤8, F≤16, K≤20)';
COMMENT ON COLUMN psych.mmpi_results.idempotency_key IS 'Deterministic hash for duplicate prevention';
COMMENT ON COLUMN psych.mmpi_results.raw_data_uri IS 'S3 URI for raw answers in Data Lake (NULL if upload failed)';

-- IAT Results Comments
COMMENT ON TABLE psych.iat_results IS 'IAT test results with D-score and session metadata';
COMMENT ON COLUMN psych.iat_results.d_score IS 'D-score calculated per Greenwald et al. (2003)';
COMMENT ON COLUMN psych.iat_results.session_seed IS 'Deterministic seed for stimulus generation (BIGINT)';

-- Outbox Comments
COMMENT ON TABLE psych.outbox IS 'Outbox pattern implementation for guaranteed event delivery';
COMMENT ON COLUMN psych.outbox.status IS 'pending | processing | sent | dead_letter';
COMMENT ON COLUMN psych.outbox.processing_started_at IS 'Used for stale recovery (processing > 5 min)';

-- ============================================================
-- 7. VERIFICATION (uncomment to run)
-- ============================================================

-- Verify schema exists:
-- SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'psych';

-- Verify tables:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'psych' ORDER BY table_name;

-- Verify indexes:
-- SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'psych' ORDER BY indexname;

-- Verify triggers:
-- SELECT trigger_name, event_manipulation FROM information_schema.triggers
-- WHERE trigger_schema = 'psych' ORDER BY trigger_name;

-- Verify role:
-- SELECT rolname FROM pg_roles WHERE rolname = 'psychometry_app';

-- ============================================================
-- END OF MIGRATION
-- ============================================================