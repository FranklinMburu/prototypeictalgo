from typing import List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict

# Checklist item schema
class ChecklistItem(BaseModel):
    key: Literal[
        "htf_bias",
        "session_killzone",
        "liquidity_context",
        "poi",
        "ltf_confirmation",
        "risk_execution",
        "discipline"
    ]
    status: Literal["met", "partial", "not_met"]
    rationale: str

# Risk info schema
class RiskInfo(BaseModel):
    stop_loss: float
    take_profit: float
    rr_min: float
    risk_per_trade: float

# Metadata schema
class Metadata(BaseModel):
    symbol: str
    timeframe_context: List[str]
    timestamp: str

# Main SMC Decision schema
class SMCDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metadata: Metadata
    checklist: List[ChecklistItem]
    confidence_score: int = Field(ge=0, le=100)
    opportunity_tier: Literal["strong", "moderate", "weak"]
    action: Literal["long", "short", "wait"]
    risk: RiskInfo
    tier_rationale: Optional[str] = None
    checklist_score: Optional[float] = None
