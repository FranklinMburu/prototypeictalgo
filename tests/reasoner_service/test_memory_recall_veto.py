"""Tests for DB-backed memory recall veto in orchestrator (fixed version).

Focus:
1. Uses r_multiple directly from DecisionOutcome (not pnl-derived)
2. Tests session/direction isolation
3. Tests invalid/missing r_multiple handling
4. Tests expanded grouping key (symbol + signal_type + model + session + direction)
"""

import pytest
from datetime import datetime, timezone
from reasoner_service import config as rs_config
from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.storage import DecisionOutcome


@pytest.mark.asyncio
async def test_memory_recall_veto_uses_r_multiple_directly(monkeypatch):
    """Test that veto uses r_multiple directly (not pnl-derived)."""
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

    # Outcomes with r_multiple already set (not derived from pnl)
    poor_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "ES", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 4500.0, "exit_price": 4495.0,
            "pnl": -50.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": -0.5,  # Already computed, not pnl/10
            "model": "v1", "session": "London", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o2", "decision_id": "d2", "symbol": "ES", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 4510.0, "exit_price": 4500.0,
            "pnl": -100.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": -1.0,  # Already computed
            "model": "v1", "session": "London", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o3", "decision_id": "d3", "symbol": "ES", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 4520.0, "exit_price": 4510.0,
            "pnl": -100.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": -0.75,  # Already computed
            "model": "v1", "session": "London", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit, model=None, session_id=None, direction=None):
        if symbol == "ES" and signal_type == "bullish_choch":
            return poor_outcomes
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d4", "symbol": "ES", "signal_type": "bullish_choch",
            "model": "v1", "session": "London", "direction": "long"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "veto"
        assert result["reason"] == "memory_underperformance"
        # Average r_multiple: (-0.5 + -1.0 + -0.75) / 3 = -0.75 < 0.0 threshold
        assert result["details"]["expectancy"] < 0.0
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_session_direction_isolation(monkeypatch):
    """Test that London losses do NOT veto NY trades (session/direction isolation)."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 2,  # Low threshold
            "suppress_if": {
                "expectancy_r": 0.0,  # Veto if expectancy < 0
                "win_rate": 0.45,
            }
        }
    }

    # London short trades had poor performance
    london_short_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "EURUSD", "timeframe": "4H",
            "signal_type": "bearish_bos", "entry_price": 1.0900, "exit_price": 1.0895,
            "pnl": -50.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": -0.5,
            "model": "v1", "session": "London", "direction": "short",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o2", "decision_id": "d2", "symbol": "EURUSD", "timeframe": "4H",
            "signal_type": "bearish_bos", "entry_price": 1.0910, "exit_price": 1.0920,
            "pnl": -100.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": -1.0,
            "model": "v1", "session": "London", "direction": "short",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    # But New York long trades have great performance
    ny_long_outcomes = [
        {
            "id": "o3", "decision_id": "d3", "symbol": "EURUSD", "timeframe": "4H",
            "signal_type": "bearish_bos", "entry_price": 1.0850, "exit_price": 1.0900,
            "pnl": 500.0, "outcome": "win", "exit_reason": "tp",
            "r_multiple": 5.0,
            "model": "v1", "session": "NewYork", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o4", "decision_id": "d4", "symbol": "EURUSD", "timeframe": "4H",
            "signal_type": "bearish_bos", "entry_price": 1.0860, "exit_price": 1.0920,
            "pnl": 600.0, "outcome": "win", "exit_reason": "tp",
            "r_multiple": 6.0,
            "model": "v1", "session": "NewYork", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit, model=None, session_id=None, direction=None):
        # Return different outcomes based on session + direction filters
        if session_id == "London" and direction == "short":
            return london_short_outcomes
        elif session_id == "NewYork" and direction == "long":
            return ny_long_outcomes
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        # Test 1: London short should VETO (poor outcomes)
        decision_london = {
            "id": "d_test", "symbol": "EURUSD", "signal_type": "bearish_bos",
            "model": "v1", "session": "London", "direction": "short"
        }
        result_london = await orch.pre_reasoning_policy_check(decision_london)
        assert result_london["result"] == "veto", "London short should veto due to poor performance"
        assert result_london["details"]["expectancy"] < 0.0
        
        # Test 2: New York long should PASS (good outcomes)
        decision_ny = {
            "id": "d_test2", "symbol": "EURUSD", "signal_type": "bearish_bos",
            "model": "v1", "session": "NewYork", "direction": "long"
        }
        result_ny = await orch.pre_reasoning_policy_check(decision_ny)
        assert result_ny["result"] == "pass", "New York long should pass due to good performance"
        assert result_ny["details"]["expectancy"] > 5.0
        
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_ignores_invalid_r_multiple(monkeypatch):
    """Test that invalid/missing r_multiple is excluded from calculations (not counted in sample_size)."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 2,  # Need 2 valid outcomes
            "suppress_if": {
                "expectancy_r": 0.0,
                "win_rate": 0.45,
            }
        }
    }

    # Mix of valid and invalid r_multiple
    mixed_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "GBPUSD", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 1.2700, "exit_price": 1.2750,
            "pnl": 50.0, "outcome": "win", "exit_reason": "tp",
            "r_multiple": 2.5,  # Valid
            "model": "v1", "session": "London", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o2", "decision_id": "d2", "symbol": "GBPUSD", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 1.2800, "exit_price": 1.2750,
            "pnl": -50.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": None,  # MISSING - should be excluded
            "model": "v1", "session": "London", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o3", "decision_id": "d3", "symbol": "GBPUSD", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 1.2750, "exit_price": 1.2800,
            "pnl": 50.0, "outcome": "win", "exit_reason": "tp",
            "r_multiple": 3.0,  # Valid
            "model": "v1", "session": "London", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit, model=None, session_id=None, direction=None):
        if symbol == "GBPUSD" and signal_type == "bullish_choch":
            return mixed_outcomes
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d_test", "symbol": "GBPUSD", "signal_type": "bullish_choch",
            "model": "v1", "session": "London", "direction": "long"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        # Should PASS because:
        # - Only 2 valid r_multiple values: [2.5, 3.0]
        # - The missing r_multiple (o2) is excluded, doesn't count toward sample
        # - Expectancy = (2.5 + 3.0) / 2 = 2.75 > 0.0 threshold
        # - Win rate = 2/2 = 1.0 > 0.45 threshold
        assert result["result"] == "pass"
        assert result["details"]["sample_size"] == 2  # Only 2 valid outcomes
        assert result["details"]["expectancy"] > 2.0  # 2.75
        assert result["details"]["win_rate"] == 1.0  # 2 wins out of 2
        
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_insufficient_valid_sample(monkeypatch):
    """Test that insufficient valid outcomes (with r_multiple) does NOT trigger veto."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 3,  # Need 3 valid outcomes
            "suppress_if": {
                "expectancy_r": 0.0,
                "win_rate": 0.45,
            }
        }
    }

    # Only 1 outcome with valid r_multiple (rest are None)
    sparse_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "AUDUSD", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 0.6700, "exit_price": 0.6750,
            "pnl": 50.0, "outcome": "win", "exit_reason": "tp",
            "r_multiple": 2.0,  # Valid
            "model": "v1", "session": "Tokyo", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o2", "decision_id": "d2", "symbol": "AUDUSD", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 0.6800, "exit_price": 0.6750,
            "pnl": -50.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": None,  # Missing
            "model": "v1", "session": "Tokyo", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
        {
            "id": "o3", "decision_id": "d3", "symbol": "AUDUSD", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 0.6750, "exit_price": 0.6700,
            "pnl": -50.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": None,  # Missing
            "model": "v1", "session": "Tokyo", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit, model=None, session_id=None, direction=None):
        if symbol == "AUDUSD" and signal_type == "bullish_choch":
            return sparse_outcomes
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d_test", "symbol": "AUDUSD", "signal_type": "bullish_choch",
            "model": "v1", "session": "Tokyo", "direction": "long"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        # Should PASS because we only have 1 valid outcome < min_sample_size of 3
        assert result["result"] == "pass"
        assert result["details"]["sample_size"] == 1
        
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_pass_feature_disabled(monkeypatch):
    """Test that feature disabled (enabled=false) skips veto entirely."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": False,  # DISABLED
            "window_last_n_trades": 50,
            "min_sample_size": 1,
            "suppress_if": {
                "expectancy_r": 100.0,  # Extremely strict
                "win_rate": 1.0,
            }
        }
    }

    # Even with terrible outcomes, should not veto if feature is disabled
    terrible_outcomes = [
        {
            "id": "o1", "decision_id": "d1", "symbol": "NZDUSD", "timeframe": "4H",
            "signal_type": "bullish_choch", "entry_price": 0.6000, "exit_price": 0.5900,
            "pnl": -1000.0, "outcome": "loss", "exit_reason": "sl",
            "r_multiple": -10.0,
            "model": "v1", "session": "Sydney", "direction": "long",
            "closed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        },
    ]

    async def mock_get_outcomes(sessionmaker, symbol, signal_type, limit, model=None, session_id=None, direction=None):
        if symbol == "NZDUSD" and signal_type == "bullish_choch":
            return terrible_outcomes
        return []

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d_test", "symbol": "NZDUSD", "signal_type": "bullish_choch",
            "model": "v1", "session": "Sydney", "direction": "long"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        # Should PASS because feature is disabled
        assert result["result"] == "pass"
        
    finally:
        orch_module.get_outcomes_by_signal_type = original_get


@pytest.mark.asyncio
async def test_memory_recall_fail_open_on_db_error(monkeypatch):
    """Test fail-open on DB error: returns PASS and logs warning."""
    monkeypatch.setattr(rs_config.Settings, "ENABLE_PERMISSIVE_POLICY", False)

    orch = DecisionOrchestrator()
    orch._constraints = {
        "outcome_adaptation": {
            "enabled": True,
            "window_last_n_trades": 50,
            "min_sample_size": 1,
            "suppress_if": {
                "expectancy_r": 0.0,
                "win_rate": 0.45,
            }
        }
    }

    async def mock_get_outcomes_error(sessionmaker, symbol, signal_type, limit, model=None, session_id=None, direction=None):
        # Simulate DB error
        raise Exception("Database connection failed")

    import reasoner_service.orchestrator as orch_module
    original_get = orch_module.get_outcomes_by_signal_type
    orch_module.get_outcomes_by_signal_type = mock_get_outcomes_error
    
    try:
        orch._sessionmaker = "mock_sessionmaker"
        
        decision = {
            "id": "d_test", "symbol": "USDJPY", "signal_type": "bullish_choch",
            "model": "v1", "session": "Tokyo", "direction": "long"
        }
        result = await orch.pre_reasoning_policy_check(decision)

        # Should PASS (fail-open) even though DB error occurred
        assert result["result"] == "pass"
        
    finally:
        orch_module.get_outcomes_by_signal_type = original_get
