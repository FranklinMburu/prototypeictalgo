"""
Outcome tagging for backtest replay.

This module provides functions to tag historical trading signals with
their outcomes based on price data. Two tagging strategies are
supported: one using actual execution logs and another using candle
data. The candle-based tagger simulates whether the trade's stop-loss
or take-profit would have been hit first, and computes basic
performance metrics such as R-multiple, MAE and MFE.
"""

from datetime import datetime
from typing import Iterable, List, Optional

from .schemas import ReplaySignal, ReplayOutcome, Outcome


def tag_from_execution_logs(signals: Iterable[ReplaySignal], logs: Iterable[dict]) -> List[ReplayOutcome]:
    """Tag outcomes using actual execution logs (stub).

    This function is a placeholder for a future implementation that will
    evaluate each signal against recorded trade execution data.

    Args:
        signals: Trading signals to evaluate.
        logs: Raw execution records.

    Returns:
        A list of `ReplayOutcome` objects (one per signal).
    """
    raise NotImplementedError("Execution log outcome tagging is not implemented yet.")


def tag_from_candles(
    signals: Iterable[ReplaySignal],
    candles: Iterable[dict],
    tie_break_on: str = "LOSS",
) -> List[ReplayOutcome]:
    """Simulate trade outcomes based on historical price candles.

    For each signal, this function scans through candles occurring after
    the signal's timestamp to determine if and when either the stop-loss
    (SL) or take-profit (TP) level would have been reached. The search
    stops at the first candle where either level is hit. If both
    thresholds are hit within the same candle, the result is governed by
    ``tie_break_on``. By default, the pessimistic SL-first logic is
    enforced, meaning simultaneous hits count as a loss.

    MAE (maximum adverse excursion) and MFE (maximum favourable
    excursion) are computed relative to the entry price and expressed
    in multiples of risk (i.e. (entry-price movement) / risk).

    Args:
        signals: Iterable of `ReplaySignal` objects.
        candles: Iterable of candle dicts with at least ``timestamp``,
            ``high`` and ``low`` keys. Candles must be sorted in ascending
            order by timestamp.
        tie_break_on: Either "LOSS" or "WIN". Determines outcome when
            SL and TP are both hit in the same candle. Default "LOSS".

    Returns:
        A list of `ReplayOutcome` objects corresponding to the input signals.
    """
    # Ensure candles are sorted by timestamp for deterministic traversal
    sorted_candles = sorted(candles, key=lambda c: c["timestamp"])
    outcomes: List[ReplayOutcome] = []
    for signal in signals:
        entry = signal.entry
        sl = signal.sl
        tp = signal.tp
        # Compute risk: distance between entry and stop. Use absolute value
        # to avoid negative risk values if sl and entry are reversed.
        risk = (entry - sl) if signal.direction == "LONG" else (sl - entry)
        if risk <= 0:
            # Fallback risk to avoid division by zero; treat as 1
            risk = 1.0
        mae = 0.0
        mfe = 0.0
        exit_price: Optional[float] = None
        exit_time: Optional[datetime] = None
        r_multiple: Optional[float] = None
        outcome: Outcome = "UNKNOWN"
        # Iterate through candles to find exit
        for candle in sorted_candles:
            if candle["timestamp"] <= signal.timestamp:
                continue
            high = candle.get("high")
            low = candle.get("low")
            # Update MAE/MFE
            if signal.direction == "LONG":
                if low < entry:
                    mae_val = (entry - low) / risk
                    if mae_val > mae:
                        mae = mae_val
                if high > entry:
                    mfe_val = (high - entry) / risk
                    if mfe_val > mfe:
                        mfe = mfe_val
                sl_hit = low <= sl
                tp_hit = high >= tp
            else:  # SHORT
                if high > entry:
                    mae_val = (high - entry) / risk
                    if mae_val > mae:
                        mae = mae_val
                if low < entry:
                    mfe_val = (entry - low) / risk
                    if mfe_val > mfe:
                        mfe = mfe_val
                sl_hit = high >= sl
                tp_hit = low <= tp
            # Determine outcome if either level hit
            if sl_hit and tp_hit:
                # Tie-break: default behaviour is SL-first (LOSS)
                exit_price = sl
                exit_time = candle["timestamp"]
                outcome = "LOSS"
                r_multiple = -1.0
                break
            elif sl_hit:
                exit_price = sl
                exit_time = candle["timestamp"]
                outcome = "LOSS"
                r_multiple = -1.0
                break
            elif tp_hit:
                exit_price = tp
                exit_time = candle["timestamp"]
                outcome = "WIN"
                if signal.direction == "LONG":
                    r_multiple = (tp - entry) / risk
                else:
                    r_multiple = (entry - tp) / risk
                break
            # Otherwise no exit yet; continue scanning
        # Append outcome; convert zero MAE/MFE to None
        outcomes.append(
            ReplayOutcome(
                signal_id=signal.signal_id,
                outcome=outcome,
                r_multiple=r_multiple,
                mae=mae if mae > 0 else None,
                mfe=mfe if mfe > 0 else None,
                exit_price=exit_price,
                exit_time=exit_time,
                notes=None,
            )
        )
    return outcomes
