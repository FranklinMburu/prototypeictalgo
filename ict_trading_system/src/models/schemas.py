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
    class Config:
        orm_mode = True

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
    class Config:
        orm_mode = True

class TradeBase(BaseModel):
    signal_id: int
    entry_price: float
    sl: float
    tp: float
    outcome: Optional[str]
    pnl: Optional[float]
    notes: Optional[str]
    timestamp: Optional[datetime]

class TradeCreate(TradeBase):
    pass

class Trade(TradeBase):
    id: int
    class Config:
        orm_mode = True

class SettingBase(BaseModel):
    key: str
    value: str
    description: Optional[str]
    timestamp: Optional[datetime]

class SettingCreate(SettingBase):
    pass

class Setting(SettingBase):
    id: int
    class Config:
        orm_mode = True
