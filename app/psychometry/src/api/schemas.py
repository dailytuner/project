# src/api/schemas.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List

# ============================================================
# MMPI SCHEMAS
# ============================================================

class MMPIValidity(BaseModel):
    l_raw_score: float
    f_raw_score: float
    k_raw_score: float
    is_valid: bool

class MMPITScoreResponse(BaseModel):
    hs_t_score: Optional[float] = None
    d_t_score: Optional[float] = None
    hy_t_score: Optional[float] = None
    pd_t_score: Optional[float] = None
    mf_t_score: Optional[float] = None
    pa_t_score: Optional[float] = None
    pt_t_score: Optional[float] = None
    sc_t_score: Optional[float] = None
    ma_t_score: Optional[float] = None
    si_t_score: Optional[float] = None

class MMPIStartResponse(BaseModel):
    success: bool = True
    test_id: str
    questions: List[Dict[int, str]]  # [{"id": 1, "text": "..."}]
    total_questions: int = 566
    estimated_time_seconds: int = 1800

class MMPISubmitRequest(BaseModel):
    answers: Dict[int, bool]  # {1: True, 2: False, ...}

class MMPISubmitResponse(BaseModel):
    success: bool = True
    result_id: int
    t_scores: MMPITScoreResponse
    validity: MMPIValidity
    astro_context: Optional[Dict] = None
    taken_at: datetime

# ============================================================
# IAT SCHEMAS
# ============================================================

class IATTrial(BaseModel):
    stimulus: str
    category: str

class IATBlock(BaseModel):
    block_id: int
    block_type: str  # 'practice', 'test', 'compatible', 'incompatible'
    trials: List[IATTrial]

class IATStartResponse(BaseModel):
    success: bool = True
    test_id: str
    session_seed: int
    blocks: List[IATBlock]

class IATTrialResult(BaseModel):
    stimulus: str
    rt_ms: int
    correct: bool

class IATBlockResult(BaseModel):
    block_id: int
    block_type: str
    trials: List[IATTrialResult]

class IATSubmitRequest(BaseModel):
    test_type: str
    blocks: List[IATBlockResult]

class IATSubmitResponse(BaseModel):
    success: bool = True
    result_id: int
    d_score: float
    mean_rt_ms: Optional[float] = None
    error_rate: Optional[float] = None
    astro_context: Optional[Dict] = None
    taken_at: datetime

# ============================================================
# TEST STATUS SCHEMAS
# ============================================================

class TestStatusResponse(BaseModel):
    can_take_mmpi: bool
    can_take_iat: bool
    next_mmpi_due: Optional[datetime] = None
    next_iat_due: Optional[datetime] = None

# ============================================================
# HISTORY SCHEMAS
# ============================================================

class MMPIHistoryItem(BaseModel):
    id: int
    taken_at: datetime
    d_t_score: float  # Primary metric for history view
    is_valid: bool

class IATHistoryItem(BaseModel):
    id: int
    taken_at: datetime
    d_score: float

class HistoryResponse(BaseModel):
    mmpi: List[MMPIHistoryItem]
    iat: List[IATHistoryItem]

# ============================================================
# HEALTH SCHEMA
# ============================================================

class ComponentHealth(BaseModel):
    database: str = "healthy"
    lake: str = "healthy"
    astro: str = "degraded"

class HealthResponse(BaseModel):
    status: str = "healthy"
    components: ComponentHealth