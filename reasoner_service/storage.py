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


class DecisionOutcome(Base):
    """
    Outcome-aware decision tracking model.
    
    Captures the trade outcome linked to a decision when the trade closes.
    This data is used for decision feedback, policy refinement, and performance analysis.
    
    Future Integration Points:
    - PolicyStore: Refine policies based on outcome patterns
    - ReasoningManager: Feed outcomes back for learning/improvement
    - Observability: Track win rate, PnL distribution by signal type/symbol
    
    Fields:
    - decision_id: Foreign key to Decision (which triggered the entry)
    - symbol: Trading pair symbol (e.g., "EURUSD")
    - timeframe: Timeframe of the signal (e.g., "4H", "1D")
    - signal_type: Type of signal (e.g., "bullish_choch", "bearish_bos")
    - entry_price: Price at which trade was entered
    - exit_price: Price at which trade was exited (when closed_at is recorded)
    - pnl: Profit/loss in currency or pips
    - outcome: Trade result - "win" (pnl > 0), "loss" (pnl < 0), "breakeven" (pnl == 0)
    - exit_reason: Why trade closed - "tp" (take profit), "sl" (stop loss), "manual", "timeout"
    - closed_at: UTC timestamp when the trade was closed
    """
    __tablename__ = "decision_outcomes"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    decision_id = Column(String, ForeignKey("decisions.id"), nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    timeframe = Column(String, nullable=False)
    signal_type = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)
    outcome = Column(String, nullable=False)  # "win", "loss", "breakeven"
    exit_reason = Column(String, nullable=False)  # "tp", "sl", "manual", "timeout"
    closed_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now(), index=True)


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


# ============================================================================
# DECISION OUTCOME PERSISTENCE FUNCTIONS
# ============================================================================
# These functions manage DecisionOutcome records, enabling outcome-aware
# decision tracking without learning logic yet.
# ============================================================================

async def insert_decision_outcome(
    sessionmaker,
    decision_id: str,
    symbol: str,
    timeframe: str,
    signal_type: str,
    entry_price: float,
    exit_price: float,
    pnl: float,
    outcome: str,  # "win" | "loss" | "breakeven"
    exit_reason: str,  # "tp" | "sl" | "manual" | "timeout"
    closed_at: datetime.datetime,
) -> str:
    """
    Insert a trade outcome record linked to a decision.
    
    Args:
        sessionmaker: Async session factory
        decision_id: UUID of the decision that triggered the entry
        symbol: Trading pair (e.g., "EURUSD")
        timeframe: Signal timeframe (e.g., "4H")
        signal_type: Type of signal (e.g., "bullish_choch")
        entry_price: Entry price
        exit_price: Exit price
        pnl: Profit/loss amount
        outcome: Result classification ("win", "loss", "breakeven")
        exit_reason: Exit reason ("tp", "sl", "manual", "timeout")
        closed_at: Trade close timestamp (UTC)
    
    Returns:
        outcome_id: UUID string of inserted DecisionOutcome record
    
    Raises:
        ValueError: If outcome or exit_reason invalid
    """
    # Validate outcome
    if outcome not in ("win", "loss", "breakeven"):
        raise ValueError(f"Invalid outcome '{outcome}'; must be 'win', 'loss', or 'breakeven'")
    
    # Validate exit_reason
    if exit_reason not in ("tp", "sl", "manual", "timeout"):
        raise ValueError(f"Invalid exit_reason '{exit_reason}'; must be 'tp', 'sl', 'manual', or 'timeout'")
    
    async with sessionmaker() as session:
        outcome_rec = DecisionOutcome(
            decision_id=decision_id,
            symbol=symbol,
            timeframe=timeframe,
            signal_type=signal_type,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl=pnl,
            outcome=outcome,
            exit_reason=exit_reason,
            closed_at=closed_at,
        )
        session.add(outcome_rec)
        await session.commit()
        await session.refresh(outcome_rec)
        return outcome_rec.id


async def get_decision_outcome_by_id(sessionmaker, outcome_id: str) -> Optional[dict]:
    """
    Retrieve a decision outcome by ID.
    
    Returns:
        dict with outcome fields or None if not found
    """
    async with sessionmaker() as session:
        result = await session.execute(
            select(DecisionOutcome).where(DecisionOutcome.id == outcome_id)
        )
        outcome = result.scalar_one_or_none()
        if not outcome:
            return None
        return {c.name: getattr(outcome, c.name) for c in DecisionOutcome.__table__.columns}


async def get_recent_decision_outcomes(
    sessionmaker,
    limit: int = 10,
    symbol: Optional[str] = None,
) -> List[dict]:
    """
    Retrieve recent decision outcomes, optionally filtered by symbol.
    
    Args:
        sessionmaker: Async session factory
        limit: Max number of outcomes to return
        symbol: Optional symbol filter
    
    Returns:
        List of outcome dicts, ordered by created_at DESC
    """
    async with sessionmaker() as session:
        query = select(DecisionOutcome)
        if symbol:
            query = query.where(DecisionOutcome.symbol == symbol)
        query = query.order_by(DecisionOutcome.created_at.desc()).limit(limit)
        result = await session.execute(query)
        outcomes = result.scalars().all()
        return [
            {c.name: getattr(outcome, c.name) for c in DecisionOutcome.__table__.columns}
            for outcome in outcomes
        ]


async def get_outcomes_by_decision_id(sessionmaker, decision_id: str) -> List[dict]:
    """
    Retrieve all outcomes linked to a specific decision.
    
    Useful for tracking multiple trade legs from a single decision.
    """
    async with sessionmaker() as session:
        result = await session.execute(
            select(DecisionOutcome)
            .where(DecisionOutcome.decision_id == decision_id)
            .order_by(DecisionOutcome.created_at.asc())
        )
        outcomes = result.scalars().all()
        return [
            {c.name: getattr(outcome, c.name) for c in DecisionOutcome.__table__.columns}
            for outcome in outcomes
        ]


async def get_outcomes_by_symbol(
    sessionmaker,
    symbol: str,
    limit: int = 100,
) -> List[dict]:
    """
    Retrieve outcomes for a symbol, ordered by closed_at DESC.
    
    Useful for analyzing per-symbol performance.
    """
    async with sessionmaker() as session:
        result = await session.execute(
            select(DecisionOutcome)
            .where(DecisionOutcome.symbol == symbol)
            .order_by(DecisionOutcome.closed_at.desc())
            .limit(limit)
        )
        outcomes = result.scalars().all()
        return [
            {c.name: getattr(outcome, c.name) for c in DecisionOutcome.__table__.columns}
            for outcome in outcomes
        ]