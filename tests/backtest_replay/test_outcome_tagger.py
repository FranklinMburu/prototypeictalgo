"""
Unit tests for backtest_replay.outcome_tagger.
"""

from datetime import datetime, timedelta
from typing import Optional

import pytest

from backtest_replay.schemas import ReplaySignal
from backtest_replay.outcome_tagger import tag_from_candles


def make_signal(
    signal_id: str,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    timestamp: Optional[datetime] = None,
) -> ReplaySignal:
    return ReplaySignal(
        signal_id=signal_id,
        timestamp=timestamp or datetime.utcnow(),
        symbol="TEST",
        timeframe="1m",
        direction=direction,  # type: ignore
        model="TEST",
        session="London",
        regime=None,
        entry=entry,
        sl=sl,
        tp=tp,
        meta={},
    )


def test_long_sl_first_tie_break() -> None:
    ts = datetime(2023, 1, 1, 0, 0, 0)
    signal = make_signal("s1", "LONG", entry=100.0, sl=99.0, tp=102.0, timestamp=ts)
    # Candle hits both TP and SL; should be LOSS due to SL-first tie-break
    candles = [
        {
            "timestamp": ts + timedelta(minutes=1),
            "open": 100.0,
            "high": 102.5,
            "low": 98.5,
            "close": 101.0,
        }
    ]
    outcomes = tag_from_candles([signal], candles)
    assert outcomes[0].outcome == "LOSS"
    assert outcomes[0].r_multiple == -1.0


def test_long_tp_hit_first() -> None:
    ts = datetime(2023, 1, 1, 0, 0, 0)
    signal = make_signal("s2", "LONG", entry=100.0, sl=99.0, tp=102.0, timestamp=ts)
    # Candle hits TP only
    candles = [
        {
            "timestamp": ts + timedelta(minutes=1),
            "open": 100.0,
            "high": 102.1,
            "low": 100.0,
            "close": 102.0,
        }
    ]
    outcomes = tag_from_candles([signal], candles)
    assert outcomes[0].outcome == "WIN"
    # Risk = 1; profit = 2; R = 2.0
    assert outcomes[0].r_multiple == pytest.approx(2.0)


def test_long_no_exit() -> None:
    ts = datetime(2023, 1, 1, 0, 0, 0)
    signal = make_signal("s3", "LONG", entry=100.0, sl=99.0, tp=102.0, timestamp=ts)
    # Candle does not hit SL or TP
    candles = [
        {
            "timestamp": ts + timedelta(minutes=1),
            "open": 100.0,
            "high": 101.0,
            "low": 99.1,
            "close": 100.5,
        },
        {
            "timestamp": ts + timedelta(minutes=2),
            "open": 100.5,
            "high": 101.2,
            "low": 99.2,
            "close": 100.7,
        },
    ]
    outcomes = tag_from_candles([signal], candles)
    assert outcomes[0].outcome == "UNKNOWN"
    assert outcomes[0].r_multiple is None


def test_short_tp_hit_first() -> None:
    ts = datetime(2023, 1, 1, 0, 0, 0)
    signal = make_signal("s4", "SHORT", entry=100.0, sl=101.0, tp=98.0, timestamp=ts)
    # Candle hits TP (low below TP), does not hit SL
    candles = [
        {
            "timestamp": ts + timedelta(minutes=1),
            "open": 100.0,
            "high": 100.5,
            "low": 97.9,
            "close": 98.5,
        }
    ]
    outcomes = tag_from_candles([signal], candles)
    assert outcomes[0].outcome == "WIN"
    # risk = sl - entry = 1; profit = entry - tp = 2; r_multiple = 2.0
    assert outcomes[0].r_multiple == pytest.approx(2.0)


def test_short_sl_first_tie_break() -> None:
    ts = datetime(2023, 1, 1, 0, 0, 0)
    signal = make_signal("s5", "SHORT", entry=100.0, sl=101.0, tp=98.0, timestamp=ts)
    # Candle hits both SL and TP; should be LOSS due to SL-first tie-break
    candles = [
        {
            "timestamp": ts + timedelta(minutes=1),
            "open": 100.0,
            "high": 101.5,
            "low": 97.5,
            "close": 100.0,
        }
    ]
    outcomes = tag_from_candles([signal], candles)
    assert outcomes[0].outcome == "LOSS"
    assert outcomes[0].r_multiple == -1.0
