from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.sql import func
import datetime
from ict_trading_system.config import settings

Base = declarative_base()

class Signal(Base):
    __tablename__ = 'signals'
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    timeframe = Column(String)
    signal_type = Column(String)
    confidence = Column(Integer)
    raw_data = Column(Text)
    timestamp = Column(DateTime, default=func.now())
    analysis = relationship("Analysis", back_populates="signal", uselist=False)
    trades = relationship("Trade", back_populates="signal")

class Analysis(Base):
    __tablename__ = 'analysis'
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey('signals.id'))
    gpt_analysis = Column(Text)
    confidence_score = Column(Integer)
    recommendation = Column(Text)
    timestamp = Column(DateTime, default=func.now())
    signal = relationship("Signal", back_populates="analysis")

class Trade(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey('signals.id'))
    
    # Core trade fields (existing)
    entry_price = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    outcome = Column(String, nullable=True)  # "win", "loss", "breakeven" (nullable for backward compat)
    pnl = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=func.now())
    
    # Outcome-aware fields (new, optional)
    # These fields enable symmetry with reasoner_service.DecisionOutcome
    # and track when and how trades close.
    # FUTURE INTEGRATION: Link to ReasoningManager feedback, PolicyStore refinement
    decision_id = Column(String, nullable=True, index=True)  # UUID from reasoner_service.Decision
    exit_price = Column(Float, nullable=True)  # Price at actual exit (may differ from TP/SL)
    exit_reason = Column(String, nullable=True)  # "tp", "sl", "manual", "timeout"
    closed_at = Column(DateTime, nullable=True, index=True)  # When trade actually closed
    
    signal = relationship("Signal", back_populates="trades")

class Setting(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True)
    value = Column(String)
    description = Column(Text)
    timestamp = Column(DateTime, default=func.now())




# --- Database Engine Selection Logic ---
# Supports SQLite (aiosqlite), PostgreSQL (asyncpg), MySQL (aiomysql)
import re
raw_url = settings.DATABASE_URL
if raw_url.startswith('sqlite:///'):
    DATABASE_URL = raw_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
elif raw_url.startswith('postgresql://') or raw_url.startswith('postgres://'):
    # Convert to asyncpg driver if not already
    DATABASE_URL = re.sub(r'^postgresql://', 'postgresql+asyncpg://', raw_url)
    DATABASE_URL = re.sub(r'^postgres://', 'postgresql+asyncpg://', DATABASE_URL)
elif raw_url.startswith('mysql://'):
    DATABASE_URL = raw_url.replace('mysql://', 'mysql+aiomysql://')
else:
    raise ValueError(f"Unsupported DB URL: {raw_url}")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
