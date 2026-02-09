"""
Unit tests for backtest_replay.metrics.
"""

from datetime import datetime
from typing import Optional

import pytest

from backtest_replay.schemas import ReplayOutcome
from backtest_replay import metrics


def build_outcome(signal_id: str, outcome: str, r: Optional[float]) -> ReplayOutcome:
    return ReplayOutcome(
        signal_id=signal_id,
        outcome=outcome,  # type: ignore
        r_multiple=r,
        mae=None,
        mfe=None,
        exit_price=None,
        exit_time=None,
        notes=None,
    )


def test_compute_metrics_basic() -> None:
    # Prepare a list of outcomes: WIN, LOSS, BE, UNKNOWN
    outcomes = [
        build_outcome("s1", "WIN", 2.0),
        build_outcome("s2", "LOSS", -1.0),
        build_outcome("s3", "BE", 0.0),
        build_outcome("s4", "UNKNOWN", None),
    ]
    # Expectancy: average of 2.0, -1.0 and 0.0 = 1/3
    assert pytest.approx(metrics.compute_expectancy(outcomes), rel=1e-6) == (2.0 - 1.0 + 0.0) / 3
    # Win rate: 1 win out of 3 evaluable
    assert pytest.approx(metrics.compute_win_rate(outcomes)) == 1 / 3
    # BE rate: 1 break-even out of 3 evaluable
    assert pytest.approx(metrics.compute_break_even_rate(outcomes)) == 1 / 3
    # Distribution should include only evaluable R values
    dist = metrics.distribution(outcomes)
    assert sorted(dist) == sorted([2.0, -1.0, 0.0])


def test_group_metrics() -> None:
    # Group outcomes by outcome type
    outcomes = [
        build_outcome("w", "WIN", 2.0),
        build_outcome("l", "LOSS", -1.0),
        build_outcome("b", "BE", 0.0),
        build_outcome("u", "UNKNOWN", None),
    ]
    grouped = metrics.group_metrics(outcomes, key_func=lambda o: o.outcome)
    # Check metrics for WIN group
    assert grouped["WIN"]["count"] == 1
    assert grouped["WIN"]["expectancy"] == 2.0
    assert grouped["WIN"]["win_rate"] == 1.0
    # Check LOSS group
    assert grouped["LOSS"]["expectancy"] == -1.0
    assert grouped["LOSS"]["win_rate"] == 0.0
    # Check BE group
    assert grouped["BE"]["expectancy"] == 0.0
    assert grouped["BE"]["be_rate"] == 1.0
