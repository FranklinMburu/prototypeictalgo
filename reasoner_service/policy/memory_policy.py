"""
Memory-Based Policy.

This asynchronous helper evaluates trades by recalling similar past signals.
It accepts a lookup function that returns a list of dicts with an 'r_multiple'.
If the average expectancy of recalled signals falls below negative_threshold,
the trade is vetoed; if above positive_threshold, the trade is promoted.
"""
from typing import Any, Callable, Dict, Sequence, Tuple


async def check_similarity(
    key: Tuple[str, str, str],
    lookup_fn: Callable[[Tuple[str, str, str], int], Sequence[Dict[str, Any]]],
    *,
    top_n: int = 10,
    negative_threshold: float = -0.05,
    positive_threshold: float = 0.10,
) -> Dict[str, Any]:
    try:
        res = lookup_fn(key, top_n)
        if hasattr(res, "__await__"):
            res = await res
    except Exception:
        return {"result": "pass"}
    valid = [o for o in res if isinstance(o, dict) and isinstance(o.get("r_multiple"), (int, float))]
    if not valid:
        return {"result": "pass"}
    expectancy = sum(o["r_multiple"] for o in valid) / len(valid)
    if expectancy < negative_threshold:
        return {
            "result": "veto",
            "reason": "memory_underperformance",
            "expectancy": expectancy,
            "sample_size": len(valid),
        }
    if expectancy > positive_threshold:
        return {
            "result": "promote",
            "expectancy": expectancy,
            "sample_size": len(valid),
        }
    return {"result": "pass"}
