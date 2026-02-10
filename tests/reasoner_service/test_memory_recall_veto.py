"""Tests for DB-backed memory recall veto in orchestrator."""

import pytest
from datetime import datetime, timezone
from reasoner_service import config as rs_config
from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.storage import DecisionOutcome


@pytest.mark.asyncio
async def test_memory_recall_veto_on_poor_expectancy(monkeypatch):
    """Test that poor expectancy triggers memory recall veto."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 3,
            "suppress_if": {
                "expectancy_r": 0.0,  # Veto if expectancy < 0
                "win_rate": 0.45,
            }
        }
    }

    # Mock sessionmaker to return poor outcomes (all losses)
    poor_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "ES", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 4500.0, "exit_price": 4495.0,
            "pnl": -50.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o2", "decision_id": "d2", "symbol": "ES", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 4510.0, "exit_price": 4500.0,
            "pnl": -100.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o3", "decision_id": "d3", "symbol": "ES", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 4520.0, "exit_price": 4510.0,
            "pnl": -100.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit):
        if symbol == "ES" and signal_type == "bullish_choch":
            return poor_outcomes
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"  # Non-None to trigger DB query
        
        decision = {
            "id": "d4", "symbol": "ES", "signal_type": "bullish_choch",
            "model": "MODEL", "session": "London"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "veto"
        assert result["reason"] == "memory_underperformance"
        assert "details" in result
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_veto_on_poor_win_rate(monkeypatch):
    """Test that poor win rate triggers memory recall veto."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 3,
            "suppress_if": {
                "expectancy_r": -0.5,  # Lenient on expectancy
                "win_rate": 0.6,  # Strict on win rate
            }
        }
    }

    # Mixed outcomes but poor win rate (1/3 = 0.33 < 0.6)
    mixed_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "NQ", "timeframe": "1H",
            "signal_type": "bearish_bos", "entry_price": 15000.0, "exit_price": 14990.0,
            "pnl": -100.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o2", "decision_id": "d2", "symbol": "NQ", "timeframe": "1H",
            "signal_type": "bearish_bos", "entry_price": 15020.0, "exit_price": 15010.0,
            "pnl": -100.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o3", "decision_id": "d3", "symbol": "NQ", "timeframe": "1H",
            "signal_type": "bearish_bos", "entry_price": 15100.0, "exit_price": 15150.0,
            "pnl": 50.0, "outcome": "win", "exit_reason": "tp", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit):
        if symbol == "NQ" and signal_type == "bearish_bos":
            return mixed_outcomes
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d4", "symbol": "NQ", "signal_type": "bearish_bos",
            "model": "MODEL", "session": "NewYork"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "veto"
        assert result["reason"] == "memory_underperformance"
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_pass_on_good_performance(monkeypatch):
    """Test that good performance passes memory recall check."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 3,
            "suppress_if": {
                "expectancy_r": -0.05,
                "win_rate": 0.45,
            }
        }
    }

    # Good outcomes: 2/3 wins = 0.67 > 0.45
    good_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "GC", "timeframe": "4H",
            "signal_type": "reversal", "entry_price": 2050.0, "exit_price": 2100.0,
            "pnl": 50.0, "outcome": "win", "exit_reason": "tp", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o2", "decision_id": "d2", "symbol": "GC", "timeframe": "4H",
            "signal_type": "reversal", "entry_price": 2080.0, "exit_price": 2120.0,
            "pnl": 40.0, "outcome": "win", "exit_reason": "tp", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o3", "decision_id": "d3", "symbol": "GC", "timeframe": "4H",
            "signal_type": "reversal", "entry_price": 2070.0, "exit_price": 2050.0,
            "pnl": -20.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit):
        if symbol == "GC" and signal_type == "reversal":
            return good_outcomes
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d4", "symbol": "GC", "signal_type": "reversal",
            "model": "MODEL", "session": "London"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "pass"
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_pass_insufficient_sample(monkeypatch):
    """Test that insufficient sample size results in pass."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 10,  # Require 10, but we only have 2
            "suppress_if": {
                "expectancy_r": -0.05,
                "win_rate": 0.45,
            }
        }
    }

    # Only 2 outcomes - below min_sample_size of 10
    small_sample = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "CL", "timeframe": "1D",
            "signal_type": "trend", "entry_price": 75.0, "exit_price": 70.0,
            "pnl": -50.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o2", "decision_id": "d2", "symbol": "CL", "timeframe": "1D",
            "signal_type": "trend", "entry_price": 76.0, "exit_price": 74.0,
            "pnl": -20.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit):
        if symbol == "CL" and signal_type == "trend":
            return small_sample
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d3", "symbol": "CL", "signal_type": "trend",
            "model": "MODEL", "session": "London"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "pass"
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_pass_no_history(monkeypatch):
    """Test that no history results in pass."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 5,
            "suppress_if": {
                "expectancy_r": -0.05,
                "win_rate": 0.45,
            }
        }
    }

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit):
        return []  # No outcomes for this signal_type

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d1", "symbol": "UNKNOWN", "signal_type": "new_pattern",
            "model": "MODEL", "session": "London"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "pass"
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_pass_feature_disabled(monkeypatch):
    """Test that disabled outcome_adaptation skips memory recall check."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": False,  # Feature disabled
            "window_last_n_trades": 50,
            "min_sample_size": 5,
            "suppress_if": {
                "expectancy_r": -0.05,
                "win_rate": 0.45,
            }
        }
    }

    # Even with poor outcomes, memory recall should not trigger
    poor_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "ES", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 4500.0, "exit_price": 4450.0,
            "pnl": -500.0, "outcome": "loss", "exit_reason": "sl", "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit):
        return poor_outcomes

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        # Don't set sessionmaker - this ensures DB query won't run
        orch._sessionmaker = None
        
        decision = {
            "id": "d2", "symbol": "ES", "signal_type": "bullish_choch",
            "model": "MODEL", "session": "London"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        # Should pass because feature is disabled and no sessionmaker
        assert result["result"] == "pass"
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_fail_open_on_db_error(monkeypatch, caplog):
    """Test that DB errors result in fail-open (pass) with warning logged."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 5,
            "suppress_if": {
                "expectancy_r": -0.05,
                "win_rate": 0.45,
            }
        }
    }

    async def mock_get_outcomes_error(sessionmaker, symbol, signal_type, limit):
        raise Exception("DB connection failed")

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes_error
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d1", "symbol": "ES", "signal_type": "bullish_choch",
            "model": "MODEL", "session": "London"
        }
        
        with caplog.at_level("WARNING"):
            result = await orch.pre_reasoning_policy_check(decision)

        # Should pass despite DB error (fail-open)
        assert result["result"] == "pass"
        # Should have logged a warning
        assert "Memory recall veto check failed" in caplog.text
    finally:
        orch_module.get_outcomes_by_signal_type = original_get
