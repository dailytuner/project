# src/core/models.py

from sqlalchemy import (
    Column, BigInteger, String, Float, Integer, Boolean,
    DateTime, Text, JSON, ForeignKey, CheckConstraint
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..infrastructure.database import Base


class MMPIResult(Base):
    __tablename__ = "mmpi_results"
    __table_args__ = {"schema": "psych"}

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)

    taken_at = Column(TIMESTAMP(timezone=True), nullable=False)
    test_version = Column(String(20), default="MMPI-2")

    # Clinical Scales (T-scores)
    hs_t_score = Column(Float)
    d_t_score = Column(Float)
    hy_t_score = Column(Float)
    pd_t_score = Column(Float)
    mf_t_score = Column(Float)
    pa_t_score = Column(Float)
    pt_t_score = Column(Float)
    sc_t_score = Column(Float)
    ma_t_score = Column(Float)
    si_t_score = Column(Float)

    # Validity Scales (Raw scores)
    l_raw_score = Column(Float)
    f_raw_score = Column(Float)
    k_raw_score = Column(Float)
    q_count = Column(Integer)
    is_valid = Column(Boolean)

    # Idempotency
    idempotency_key = Column(String(64), unique=True, index=True)

    # Astrological Context
    dasha_maha = Column(String(20))
    dasha_antar = Column(String(20))
    dasha_pratyantar = Column(String(20))
    transit_saturn_house = Column(Integer)
    transit_jupiter_house = Column(Integer)
    transit_rahu_house = Column(Integer)
    moon_sign = Column(String(20))
    moon_house = Column(Integer)
    moon_phase = Column(String(20))
    is_retro_mercury = Column(Boolean)
    is_retro_venus = Column(Boolean)
    is_retro_mars = Column(Boolean)

    # Data Lake Reference
    raw_data_uri = Column(Text)

    # System Fields
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class IATResult(Base):
    __tablename__ = "iat_results"
    __table_args__ = {"schema": "psych"}

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)

    taken_at = Column(TIMESTAMP(timezone=True), nullable=False)
    test_type = Column(String(50), nullable=False)

    # Core Results
    d_score = Column(Float, nullable=False)
    mean_rt_ms = Column(Float)
    error_rate = Column(Float)
    rt_std = Column(Float)
    practice_effect_score = Column(Float)

    # Idempotency
    idempotency_key = Column(String(64), unique=True, index=True)

    # Session Seed
    session_seed = Column(BigInteger, nullable=False)

    # Astrological Context
    dasha_maha = Column(String(20))
    dasha_antar = Column(String(20))
    transit_moon_house = Column(Integer)
    moon_phase = Column(String(20))
    is_retro_mercury = Column(Boolean)
    is_retro_venus = Column(Boolean)
    transit_saturn_house = Column(Integer)

    # Data Lake Reference
    raw_data_uri = Column(Text)

    # System Fields
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class TestSchedule(Base):
    __tablename__ = "test_schedule"
    __table_args__ = {"schema": "psych"}

    user_id = Column(BigInteger, ForeignKey("public.users.id", ondelete="CASCADE"), primary_key=True)

    last_mmpi_at = Column(TIMESTAMP(timezone=True))
    last_iat_at = Column(TIMESTAMP(timezone=True))
    next_mmpi_due = Column(DateTime)  # DATE only, but DateTime works with date comparisons
    next_iat_due = Column(DateTime)  # DATE only

    is_active = Column(Boolean, default=True)

    # System Fields
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class Outbox(Base):
    __tablename__ = "outbox"
    __table_args__ = {"schema": "psych"}

    id = Column(BigInteger, primary_key=True, index=True)

    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)

    idempotency_key = Column(String(64), unique=True, index=True)

    status = Column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False
    )
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'dead_letter')",
            name="check_outbox_status"
        ),
    )

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    processing_started_at = Column(TIMESTAMP(timezone=True))
    processed_at = Column(TIMESTAMP(timezone=True))

    retry_count = Column(Integer, default=0, server_default="0")
    last_error = Column(Text)

    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())