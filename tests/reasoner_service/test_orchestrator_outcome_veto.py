"""Tests for orchestrator outcome-aware veto path."""

import pytest

from reasoner_service import config as rs_config
from reasoner_service.orchestrator import DecisionOrchestrator


@pytest.mark.asyncio
async def test_pre_reasoning_policy_outcome_veto(monkeypatch) -> None:
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_veto": {
            "min_sample_size": 20,
            "expectancy_threshold": -0.05,
            "win_rate_threshold": 0.45,
        }
    }
    orch._metrics_snapshot = {
        ("ES", "MODEL", "London"): {"count": 25, "expectancy": -0.1, "win_rate": 0.4}
    }

    decision = {"id": "d1", "symbol": "ES", "model": "MODEL", "session": "London"}
    result = await orch.pre_reasoning_policy_check(decision)

    assert result["result"] == "veto"
    assert result["reason"] == "outcome_underperformance"
