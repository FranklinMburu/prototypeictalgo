"""Tests for outcome policy checks."""

from reasoner_service.policy.outcome_policy import check_performance


def test_check_performance_pass_on_small_sample() -> None:
    key = ("ES", "MODEL", "London")
    snapshot = {key: {"count": 5, "expectancy": -1.0, "win_rate": 0.0}}
    result = check_performance(key, snapshot, min_sample_size=20)
    assert result["result"] == "pass"


def test_check_performance_veto_on_underperformance() -> None:
    key = ("ES", "MODEL", "London")
    snapshot = {key: {"count": 25, "expectancy": -0.1, "win_rate": 0.4}}
    result = check_performance(key, snapshot, min_sample_size=20, expectancy_threshold=-0.05, win_rate_threshold=0.45)
    assert result["result"] == "veto"
    assert result["reason"] == "outcome_underperformance"


def test_check_performance_pass_on_good_stats() -> None:
    key = ("ES", "MODEL", "London")
    snapshot = {key: {"count": 25, "expectancy": 0.2, "win_rate": 0.6}}
    result = check_performance(key, snapshot, min_sample_size=20)
    assert result["result"] == "pass"
