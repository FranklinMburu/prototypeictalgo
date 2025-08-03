from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.sql import func
import datetime
from config import settings

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
    entry_price = Column(Float)
    sl = Column(Float)
    tp = Column(Float)
    outcome = Column(String)
    pnl = Column(Float)
    notes = Column(Text)
    timestamp = Column(DateTime, default=func.now())
    signal = relationship("Signal", back_populates="trades")

class Setting(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True)
    value = Column(String)
    description = Column(Text)
    timestamp = Column(DateTime, default=func.now())



# SQLite/aiosqlite does not support connection pooling arguments
DATABASE_URL = settings.DATABASE_URL.replace('sqlite:///', 'sqlite+aiosqlite:///')
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
