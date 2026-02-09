"""
Outcome-Aware Policy.

This deterministic helper evaluates whether a trade should pass or be vetoed
based on aggregated metrics (expectancy, win rate, sample size).
"""
from typing import Any, Dict, Tuple


def check_performance(
    key: Tuple[str, str, str],
    metrics_snapshot: Dict[Tuple[str, str, str], Dict[str, Any]],
    *,
    min_sample_size: int = 20,
    expectancy_threshold: float = -0.05,
    win_rate_threshold: float = 0.45,
) -> Dict[str, Any]:
    stats = metrics_snapshot.get(key)
    if not stats:
        return {"result": "pass"}
    count = int(stats.get("count", 0) or 0)
    expectancy = float(stats.get("expectancy", 0.0) or 0.0)
    win_rate = float(stats.get("win_rate", 0.0) or 0.0)
    if count < min_sample_size:
        return {"result": "pass"}
    if expectancy < expectancy_threshold or win_rate < win_rate_threshold:
        return {
            "result": "veto",
            "reason": "outcome_underperformance",
            "count": count,
            "expectancy": expectancy,
            "win_rate": win_rate,
        }
    return {"result": "pass"}
