"""
Data models used by the backtest replay system.

The dataclasses in this module define the structure of trading signals
and their replayed outcomes. They are designed to be immutable and
simple to serialise.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Literal

# Possible outcome states for a replayed trade
Outcome = Literal["WIN", "LOSS", "BE", "UNKNOWN"]


@dataclass(frozen=True)
class ReplaySignal:
    """Represents a trading signal for backtesting.

    Attributes:
        signal_id: Unique identifier for the signal.
        timestamp: Time the signal was generated (UTC).
        symbol: Trading symbol (e.g. "ES").
        timeframe: Chart timeframe (e.g. "1m").
        direction: "LONG" or "SHORT".
        model: Name of the ICT model used.
        session: Session classification (e.g. "London").
        regime: Optional market regime (e.g. "TREND").
        entry: Planned entry price.
        sl: Stop-loss price.
        tp: Take-profit price.
        meta: Arbitrary metadata dictionary.
    """

    signal_id: str
    timestamp: datetime
    symbol: str
    timeframe: str
    direction: Literal["LONG", "SHORT"]
    model: str
    session: str
    regime: Optional[str]
    entry: float
    sl: float
    tp: float
    meta: Dict[str, Any]


@dataclass(frozen=True)
class ReplayOutcome:
    """Outcome of a replayed trading signal.

    Attributes:
        signal_id: Identifier of the corresponding ReplaySignal.
        outcome: One of "WIN", "LOSS", "BE" or "UNKNOWN".
        r_multiple: Profit or loss in multiples of risk. Negative values
            represent losses, positive represent wins. None if unknown.
        mae: Maximum adverse excursion in multiples of risk. None if not
            computed or no adverse movement.
        mfe: Maximum favourable excursion in multiples of risk. None if not
            computed or no favourable movement.
        exit_price: Price at which the trade would have closed. None if
            unknown.
        exit_time: Timestamp of trade closure. None if unknown.
        notes: Optional notes.
    """

    signal_id: str
    outcome: Outcome
    r_multiple: Optional[float]
    mae: Optional[float]
    mfe: Optional[float]
    exit_price: Optional[float]
    exit_time: Optional[datetime]
    notes: Optional[str] = None
