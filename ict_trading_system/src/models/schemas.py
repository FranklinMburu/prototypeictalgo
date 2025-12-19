from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SignalBase(BaseModel):
    symbol: str
    timeframe: str
    signal_type: str
    confidence: int
    raw_data: Optional[str]
    timestamp: Optional[datetime]

class SignalCreate(SignalBase):
    pass

class Signal(SignalBase):
    id: int
    model_config = {
        "from_attributes": True
    }

class AnalysisBase(BaseModel):
    signal_id: int
    gpt_analysis: str
    confidence_score: int
    recommendation: str
    timestamp: Optional[datetime]

class AnalysisCreate(AnalysisBase):
    pass

class Analysis(AnalysisBase):
    id: int
    model_config = {
        "from_attributes": True
    }

class TradeBase(BaseModel):
    signal_id: int
    entry_price: float
    sl: float
    tp: float
    outcome: Optional[str] = None  # "win", "loss", "breakeven"
    pnl: Optional[float] = None
    notes: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    # Outcome-aware fields (new, optional)
    # Enable symmetry with reasoner_service.DecisionOutcome
    decision_id: Optional[str] = None  # UUID from reasoner_service.Decision
    exit_price: Optional[float] = None  # Actual exit price (may differ from TP/SL)
    exit_reason: Optional[str] = None  # "tp", "sl", "manual", "timeout"
    closed_at: Optional[datetime] = None  # When trade closed

class TradeCreate(TradeBase):
    pass

class Trade(TradeBase):
    id: int
    model_config = {
        "from_attributes": True
    }

class SettingBase(BaseModel):
    key: str
    value: str
    description: Optional[str]
    timestamp: Optional[datetime]

class SettingCreate(SettingBase):
    pass

class Setting(SettingBase):
    id: int
    model_config = {
        "from_attributes": True
    }
