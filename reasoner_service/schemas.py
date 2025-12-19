


class Triggers:
    def __init__(self, entry_condition=None, take_profits=None, stop_loss=None):
        self.entry_condition = entry_condition
        self.take_profits = [float(x) for x in (take_profits or [])]
        self.stop_loss = float(stop_loss) if stop_loss is not None else None

class Versions:
    def __init__(self, reasoner_version=None, strategy_version=None):
        self.reasoner_version = reasoner_version
        self.strategy_version = strategy_version


from pydantic import BaseModel, field_validator, ValidationError, Field
from typing import List, Any, Optional

class Decision(BaseModel):
    symbol: str
    snapshot_ts_ms: Any
    bias: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommendation: str
    triggers: Triggers
    drivers: List[Any]
    caveats: List[Any]
    summary: str
    versions: Any

    @field_validator('confidence', mode='before')
    @classmethod
    def clip_confidence(cls, v):
        try:
            v = float(v)
        except Exception:
            raise ValueError("Invalid confidence value")
        return min(max(v, 0.0), 1.0)

    @field_validator('drivers')
    @classmethod
    def drivers_non_empty(cls, v):
        if not v:
            raise ValueError("drivers must be non-empty")
        return v

    @field_validator('triggers', mode='before')
    @classmethod
    def coerce_triggers(cls, v):
        if isinstance(v, Triggers):
            return v
        return Triggers(**v)

    @field_validator('versions', mode='before')
    @classmethod
    def coerce_versions(cls, v):
        if isinstance(v, Versions):
            return v
        return Versions(**v)

    model_config = {
        "arbitrary_types_allowed": True
    }

    def model_dump(self):
        return self.dict()
class Versions:
    def __init__(self, reasoner_version=None, strategy_version=None):
        self.reasoner_version = reasoner_version
        self.strategy_version = strategy_version


decision_schema = {}

# Explicitly export for test imports
__all__ = ["Decision", "Triggers", "Versions"]

# ============================================================================
# DECISION OUTCOME SCHEMAS
# ============================================================================
# Pydantic models for decision outcome validation and serialization.
# ============================================================================

from datetime import datetime

class DecisionOutcomeBase(BaseModel):
    """Base schema for decision outcomes."""
    decision_id: str
    symbol: str
    timeframe: str
    signal_type: str
    entry_price: float
    exit_price: float
    pnl: float
    outcome: str  # "win", "loss", "breakeven"
    exit_reason: str  # "tp", "sl", "manual", "timeout"
    closed_at: datetime

    @field_validator('outcome', mode='before')
    @classmethod
    def validate_outcome(cls, v):
        if v not in ("win", "loss", "breakeven"):
            raise ValueError(f"outcome must be 'win', 'loss', or 'breakeven', got '{v}'")
        return v

    @field_validator('exit_reason', mode='before')
    @classmethod
    def validate_exit_reason(cls, v):
        if v not in ("tp", "sl", "manual", "timeout"):
            raise ValueError(f"exit_reason must be 'tp', 'sl', 'manual', or 'timeout', got '{v}'")
        return v

    @field_validator('entry_price', 'exit_price', 'pnl', mode='before')
    @classmethod
    def validate_float_fields(cls, v):
        try:
            return float(v)
        except Exception:
            raise ValueError(f"Invalid float value: {v}")


class DecisionOutcomeCreate(DecisionOutcomeBase):
    """Schema for creating a new decision outcome."""
    pass


class DecisionOutcome(DecisionOutcomeBase):
    """Schema for retrieving a decision outcome from storage."""
    id: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


__all__ = ["Decision", "Triggers", "Versions", "DecisionOutcomeBase", "DecisionOutcomeCreate", "DecisionOutcome"]