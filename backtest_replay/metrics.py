"""
Performance metrics for backtest replay.

This module defines functions for computing standard performance metrics
from sequences of `ReplayOutcome` instances. Metrics include expectancy
(average R-multiple), win rate, break-even rate, and grouping of these
metrics by arbitrary keys.

Example usage:

    outcomes = [ReplayOutcome(...), ...]
    exp = compute_expectancy(outcomes)
    win = compute_win_rate(outcomes)
    metrics_by_session = group_metrics(outcomes, key_func=lambda o: o.session)
"""

from collections import defaultdict
from typing import Iterable, Dict, Any, Callable, List

from .schemas import ReplayOutcome


def compute_expectancy(outcomes: Iterable[ReplayOutcome]) -> float:
    """Calculate the average R-multiple (expectancy) across outcomes.

    Outcomes with ``r_multiple`` equal to None or with the outcome type
    "UNKNOWN" are ignored. If there are no valid outcomes, returns 0.0.

    Args:
        outcomes: An iterable of `ReplayOutcome` objects.

    Returns:
        The mean R-multiple across all valid trades.
    """
    total = 0.0
    count = 0
    for outcome in outcomes:
        if outcome.outcome == "UNKNOWN" or outcome.r_multiple is None:
            continue
        total += outcome.r_multiple
        count += 1
    return total / count if count > 0 else 0.0


def compute_win_rate(outcomes: Iterable[ReplayOutcome]) -> float:
    """Compute the fraction of winning trades.

    Only considers outcomes with a definitive result (neither UNKNOWN
    nor None r_multiple). Returns 0.0 if there are no evaluable trades.
    """
    wins = 0
    total = 0
    for outcome in outcomes:
        if outcome.outcome in ("WIN", "LOSS", "BE") and outcome.r_multiple is not None:
            total += 1
            if outcome.outcome == "WIN":
                wins += 1
    return wins / total if total > 0 else 0.0


def compute_break_even_rate(outcomes: Iterable[ReplayOutcome]) -> float:
    """Compute the fraction of break-even trades among evaluable trades.
    """
    bes = 0
    total = 0
    for outcome in outcomes:
        if outcome.outcome in ("WIN", "LOSS", "BE") and outcome.r_multiple is not None:
            total += 1
            if outcome.outcome == "BE":
                bes += 1
    return bes / total if total > 0 else 0.0


def distribution(outcomes: Iterable[ReplayOutcome]) -> List[float]:
    """Return a list of R-multiples from evaluable trades.

    Trades with None ``r_multiple`` or UNKNOWN outcome are excluded.
    """
    return [o.r_multiple for o in outcomes if o.outcome != "UNKNOWN" and o.r_multiple is not None]


def group_metrics(
    outcomes: Iterable[ReplayOutcome],
    key_func: Callable[[ReplayOutcome], Any],
) -> Dict[Any, Dict[str, float]]:
    """Compute metrics grouped by the provided key function.

    The returned dictionary maps each group key to a dictionary of
    ``expectancy``, ``win_rate``, ``be_rate`` and ``count``. The count
    represents the number of evaluable trades in the group (excluding
    UNKNOWN or None r_multiple outcomes).

    Args:
        outcomes: Iterable of outcomes to group.
        key_func: Function taking a `ReplayOutcome` and returning a group key.

    Returns:
        A mapping of group key -> metrics dict.
    """
    groups: Dict[Any, List[ReplayOutcome]] = defaultdict(list)
    for outcome in outcomes:
        groups[key_func(outcome)].append(outcome)
    result: Dict[Any, Dict[str, float]] = {}
    for group_key, items in groups.items():
        evaluable = [o for o in items if o.outcome != "UNKNOWN" and o.r_multiple is not None]
        result[group_key] = {
            "count": len(evaluable),
            "expectancy": compute_expectancy(items),
            "win_rate": compute_win_rate(items),
            "be_rate": compute_break_even_rate(items),
        }
    return result
