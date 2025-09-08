async def get_decision_by_id(engine, id1):
    # Return a dummy decision dict
    return {
        "id": id1,
        "symbol": "TST",
        "decision_text": '{"ok": true}',
        "raw": {"a": 1, "b": "x"},
        "bias": "neutral",
        "confidence": 0.12,
        "recommendation": "do_nothing",
        "repair_used": False,
        "fallback_used": True,
        "duration_ms": 123
    }

async def get_recent_decisions(engine, limit=10):
    # Return a list of dummy decisions
    return [
        {
            "id": "dummy1",
            "symbol": "TST",
            "decision_text": '{"ok": true}',
            "raw": {"a": 1, "b": "x"},
            "bias": "neutral",
            "confidence": 0.12,
            "recommendation": "do_nothing",
            "repair_used": False,
            "fallback_used": True,
            "duration_ms": 123
        },
        {
            "id": "dummy2",
            "symbol": "TST2",
            "decision_text": '{"ok": true}',
            "raw": None,
            "bias": "bullish",
            "confidence": 0.9,
            "recommendation": "enter",
            "repair_used": False,
            "fallback_used": False,
            "duration_ms": 10
        }
    ]

async def log_notification(engine, decision_id, channel, status, http_status, error):
    # Return a dummy log id as string
    return "logid123"

import asyncio
from typing import Any, Optional, List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, JSON, DateTime, ForeignKey
from sqlalchemy.future import select
from sqlalchemy.sql import func
import uuid
import datetime

Base = declarative_base()

class Decision(Base):
    __tablename__ = "decisions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String)
    decision_text = Column(Text)
    raw = Column(JSON, nullable=True)
    bias = Column(String)
    confidence = Column(Float)
    recommendation = Column(String)
    repair_used = Column(Boolean)
    fallback_used = Column(Boolean)
    duration_ms = Column(Integer)
    created_at = Column(DateTime, default=func.now())

class NotificationLog(Base):
    __tablename__ = "notification_logs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=True)
    channel = Column(String)
    status = Column(String)
    http_status = Column(Integer)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


def get_engine_and_session(dsn=None):
    dsn = dsn or "sqlite+aiosqlite:///./decisions.db"
    engine = create_async_engine(dsn, echo=False, future=True)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, async_session

async def create_engine_and_sessionmaker(dsn=None):
    dsn = dsn or "sqlite+aiosqlite:///./decisions.db"
    engine = create_async_engine(dsn, echo=False, future=True)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, async_session

async def create_engine_from_env_or_dsn(dsn=None):
    engine, _ = await create_engine_and_sessionmaker(dsn)
    return engine

async def init_models(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def insert_decision(sessionmaker, **kwargs):
    async with sessionmaker() as session:
        dec = Decision(**kwargs)
        session.add(dec)
        await session.commit()
        await session.refresh(dec)
        return dec.id

async def get_decision_by_id(sessionmaker, id1):
    async with sessionmaker() as session:
        result = await session.execute(select(Decision).where(Decision.id == id1))
        dec = result.scalar_one_or_none()
        if not dec:
            return None
        return {c.name: getattr(dec, c.name) for c in Decision.__table__.columns}

async def get_recent_decisions(sessionmaker, limit=10):
    async with sessionmaker() as session:
        result = await session.execute(select(Decision).order_by(Decision.created_at.desc()).limit(limit))
        decs = result.scalars().all()
        return [{c.name: getattr(dec, c.name) for c in Decision.__table__.columns} for dec in decs]

async def log_notification(sessionmaker, decision_id, channel, status, http_status, error):
    async with sessionmaker() as session:
        log = NotificationLog(
            decision_id=decision_id,
            channel=channel,
            status=status,
            http_status=http_status,
            error=error,
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log.id

def compute_decision_hash(symbol, rec, conf, ts_ms):
    return f"{symbol}:{rec}:{conf}:{ts_ms}"

