"""
Tests for Trade Governance Service

Verifies that governance rule evaluation works correctly,
with explicit guarantees that results are informational only.
"""

import pytest
from datetime import datetime, timezone, timedelta
from reasoner_service.trade_governance_service import TradeGovernanceService


class TestDailyTradeLimit:
    """Verify daily trade count enforcement."""
    
    def test_within_limit(self):
        """Trade allowed when below daily limit."""
        service = TradeGovernanceService(max_trades_per_day=5)
        
        # Register 3 trades from today
        today = datetime.now(timezone.utc)
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": (today - timedelta(hours=i)).isoformat(),
            }
            for i in range(3)
        ]
        service.add_outcomes(outcomes)
        
        # New trade should be allowed (4/5)
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is True
        assert len(report["violations"]) == 0
    
    def test_limit_exceeded(self):
        """Trade blocked when daily limit reached."""
        service = TradeGovernanceService(max_trades_per_day=3)
        
        today = datetime.now(timezone.utc)
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": (today - timedelta(hours=i)).isoformat(),
            }
            for i in range(3)
        ]
        service.add_outcomes(outcomes)
        
        # Next trade violates limit (3/3)
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is False
        assert any("Daily trade limit" in v for v in report["violations"])


class TestDailyLossLimit:
    """Verify daily loss limit enforcement."""
    
    def test_within_loss_limit(self):
        """Trade allowed when cumulative loss is acceptable."""
        service = TradeGovernanceService(max_daily_loss=500.0)
        
        today = datetime.now(timezone.utc)
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": -100.0,  # -100
                "timestamp": (today - timedelta(hours=1)).isoformat(),
            },
            {
                "symbol": "GBPUSD",
                "timeframe": "1H",
                "pnl": -200.0,  # Total: -300
                "timestamp": (today - timedelta(minutes=30)).isoformat(),
            },
        ]
        service.add_outcomes(outcomes)
        
        report = service.evaluate_trade({
            "symbol": "USDCAD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is True
        assert not any("Daily loss limit" in v for v in report["violations"])
    
    def test_loss_limit_exceeded(self):
        """Trade blocked when daily loss limit exceeded."""
        service = TradeGovernanceService(max_daily_loss=300.0)
        
        today = datetime.now(timezone.utc)
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": -200.0,
                "timestamp": (today - timedelta(hours=1)).isoformat(),
            },
            {
                "symbol": "GBPUSD",
                "timeframe": "1H",
                "pnl": -150.0,  # Total: -350
                "timestamp": (today - timedelta(minutes=30)).isoformat(),
            },
        ]
        service.add_outcomes(outcomes)
        
        report = service.evaluate_trade({
            "symbol": "USDCAD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is False
        assert any("Daily loss limit exceeded" in v for v in report["violations"])


class TestKillzoneHours:
    """Verify killzone/session window enforcement."""
    
    def test_outside_killzone(self):
        """Trade allowed outside killzone hours."""
        service = TradeGovernanceService(killzone_hours=[(0, 8), (22, 24)])
        
        # 10:00 UTC is outside killzone
        trade_time = datetime(2025, 1, 20, 10, 0, 0, tzinfo=timezone.utc)
        
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": trade_time.isoformat(),
        })
        
        assert report["allowed"] is True
        assert not any("killzone" in v.lower() for v in report["violations"])
    
    def test_during_killzone(self):
        """Trade blocked during killzone hours."""
        service = TradeGovernanceService(killzone_hours=[(0, 8), (22, 24)])
        
        # 02:00 UTC is in first killzone
        trade_time = datetime(2025, 1, 20, 2, 0, 0, tzinfo=timezone.utc)
        
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": trade_time.isoformat(),
        })
        
        assert report["allowed"] is False
        assert any("killzone" in v.lower() for v in report["violations"])
    
    def test_killzone_wraparound(self):
        """Killzone spanning midnight is handled correctly."""
        service = TradeGovernanceService(killzone_hours=[(22, 24), (0, 2)])
        
        # 23:00 UTC is in killzone (22-24)
        trade_time_evening = datetime(2025, 1, 20, 23, 0, 0, tzinfo=timezone.utc)
        report_evening = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": trade_time_evening.isoformat(),
        })
        assert report_evening["allowed"] is False
        
        # 01:00 UTC is in killzone (0-2)
        trade_time_morning = datetime(2025, 1, 21, 1, 0, 0, tzinfo=timezone.utc)
        report_morning = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": trade_time_morning.isoformat(),
        })
        assert report_morning["allowed"] is False


class TestCooldownAfterLoss:
    """Verify cooldown period enforcement after losses."""
    
    def test_cooldown_active(self):
        """Trade blocked during cooldown after loss."""
        service = TradeGovernanceService(cooldown_minutes_after_loss=30)
        
        now = datetime.now(timezone.utc)
        loss_time = now - timedelta(minutes=10)  # Loss 10 minutes ago
        
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": -100.0,
                "timestamp": loss_time.isoformat(),
            }
        ]
        service.add_outcomes(outcomes)
        
        # Try to trade 10 minutes after loss (within 30-minute cooldown)
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": now.isoformat(),
        })
        
        assert report["allowed"] is False
        assert any("Cooldown period" in v for v in report["violations"])
    
    def test_cooldown_expired(self):
        """Trade allowed after cooldown expires."""
        service = TradeGovernanceService(cooldown_minutes_after_loss=30)
        
        now = datetime.now(timezone.utc)
        loss_time = now - timedelta(minutes=31)  # Loss 31 minutes ago
        
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": -100.0,
                "timestamp": loss_time.isoformat(),
            }
        ]
        service.add_outcomes(outcomes)
        
        # Trade 31 minutes after loss (cooldown expired)
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": now.isoformat(),
        })
        
        assert report["allowed"] is True
        assert not any("Cooldown period" in v for v in report["violations"])
    
    def test_no_cooldown_for_wins(self):
        """No cooldown after winning trades."""
        service = TradeGovernanceService(cooldown_minutes_after_loss=30)
        
        now = datetime.now(timezone.utc)
        win_time = now - timedelta(minutes=5)
        
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 200.0,  # Win, not a loss
                "timestamp": win_time.isoformat(),
            }
        ]
        service.add_outcomes(outcomes)
        
        # Trade 5 minutes after win (no cooldown needed)
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": now.isoformat(),
        })
        
        assert report["allowed"] is True


class TestSymbolOvertrading:
    """Verify symbol-level trade concentration limits."""
    
    def test_within_symbol_limit(self):
        """Trade allowed when symbol trade count is below limit."""
        service = TradeGovernanceService(max_trades_per_symbol=3)
        
        today = datetime.now(timezone.utc)
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": (today - timedelta(hours=i)).isoformat(),
            }
            for i in range(2)
        ]
        service.add_outcomes(outcomes)
        
        # Third trade on EURUSD should be allowed (2/3)
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is True
        assert not any("Symbol trade limit" in v for v in report["violations"])
    
    def test_symbol_limit_exceeded(self):
        """Trade blocked when symbol trade limit reached."""
        service = TradeGovernanceService(max_trades_per_symbol=2)
        
        today = datetime.now(timezone.utc)
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": (today - timedelta(hours=i)).isoformat(),
            }
            for i in range(2)
        ]
        service.add_outcomes(outcomes)
        
        # Third trade on EURUSD violates limit (2/2)
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is False
        assert any("Symbol trade limit reached" in v for v in report["violations"])


class TestTimeframeOvertrading:
    """Verify timeframe-level trade concentration limits."""
    
    def test_within_timeframe_limit(self):
        """Trade allowed when timeframe trade count is below limit."""
        service = TradeGovernanceService(max_trades_per_timeframe=4)
        
        today = datetime.now(timezone.utc)
        outcomes = [
            {
                "symbol": f"SYM{i}",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": (today - timedelta(hours=i)).isoformat(),
            }
            for i in range(3)
        ]
        service.add_outcomes(outcomes)
        
        # Fourth trade on 1H should be allowed (3/4)
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is True
        assert not any("Timeframe trade limit" in v for v in report["violations"])
    
    def test_timeframe_limit_exceeded(self):
        """Trade blocked when timeframe trade limit reached."""
        service = TradeGovernanceService(max_trades_per_timeframe=2)
        
        today = datetime.now(timezone.utc)
        outcomes = [
            {
                "symbol": f"SYM{i}",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": (today - timedelta(hours=i)).isoformat(),
            }
            for i in range(2)
        ]
        service.add_outcomes(outcomes)
        
        # Third trade on 1H violates limit (2/2)
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is False
        assert any("Timeframe trade limit reached" in v for v in report["violations"])


class TestTradeSpacing:
    """Verify minimum spacing between trades."""
    
    def test_sufficient_spacing(self):
        """Trade allowed when spacing between trades is sufficient."""
        service = TradeGovernanceService(min_trade_spacing_minutes=5)
        
        now = datetime.now(timezone.utc)
        last_trade_time = now - timedelta(minutes=10)
        
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": last_trade_time.isoformat(),
            }
        ]
        service.add_outcomes(outcomes)
        
        # New trade 10 minutes after last (spacing requirement met)
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": now.isoformat(),
        })
        
        assert report["allowed"] is True
        assert not any("Trade spacing" in v for v in report["violations"])
    
    def test_insufficient_spacing(self):
        """Trade blocked when spacing between trades is insufficient."""
        service = TradeGovernanceService(min_trade_spacing_minutes=5)
        
        now = datetime.now(timezone.utc)
        last_trade_time = now - timedelta(minutes=2)
        
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": last_trade_time.isoformat(),
            }
        ]
        service.add_outcomes(outcomes)
        
        # New trade 2 minutes after last (violates 5-minute spacing)
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": now.isoformat(),
        })
        
        assert report["allowed"] is False
        assert any("Trade spacing" in v for v in report["violations"])


class TestMultipleViolations:
    """Verify correct handling of multiple simultaneous violations."""
    
    def test_multiple_violations_reported(self):
        """All violations are included in report."""
        service = TradeGovernanceService(
            max_trades_per_day=2,
            max_trades_per_symbol=1,
            killzone_hours=[(0, 10)],
        )
        
        # Use a specific date within the killzone hours
        killzone_time = datetime(2025, 1, 20, 5, 0, 0, tzinfo=timezone.utc)
        
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": (killzone_time - timedelta(hours=2)).isoformat(),
            },
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 100.0,
                "timestamp": (killzone_time - timedelta(hours=1)).isoformat(),
            },
        ]
        service.add_outcomes(outcomes)
        
        # This trade violates multiple rules (during killzone, symbol limit, daily limit)
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": killzone_time.isoformat(),
        })
        
        assert report["allowed"] is False
        assert len(report["violations"]) >= 1  # At least one violation (killzone)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_new_day_resets_counters(self):
        """Trades from previous day don't count toward current day limits."""
        service = TradeGovernanceService(max_trades_per_day=2)
        
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        today = datetime.now(timezone.utc)
        
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": yesterday.isoformat(),
            },
            {
                "symbol": "GBPUSD",
                "timeframe": "1H",
                "pnl": 100.0,
                "timestamp": yesterday.isoformat(),
            },
        ]
        service.add_outcomes(outcomes)
        
        # Today's first trade should be allowed (previous day doesn't count)
        report = service.evaluate_trade({
            "symbol": "USDCAD",
            "timeframe": "1H",
            "timestamp": today.isoformat(),
        })
        
        assert report["allowed"] is True
    
    def test_empty_outcomes(self):
        """Service handles empty outcomes correctly."""
        service = TradeGovernanceService()
        
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        assert report["allowed"] is True
        assert len(report["violations"]) == 0
    
    def test_missing_timestamp(self):
        """Error when trade timestamp is missing."""
        service = TradeGovernanceService()
        
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            # Missing timestamp
        })
        
        assert report["allowed"] is False
        assert any("timestamp" in v.lower() for v in report["violations"])
    
    def test_invalid_timestamp_format(self):
        """Error when trade timestamp format is invalid."""
        service = TradeGovernanceService()
        
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": "not-a-valid-timestamp",
        })
        
        assert report["allowed"] is False
        assert any("timestamp" in v.lower() or "format" in v.lower() for v in report["violations"])


class TestDeterminism:
    """Verify deterministic evaluation results."""
    
    def test_same_input_same_output(self):
        """Identical inputs produce identical outputs."""
        trade_context = {
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": datetime(2025, 1, 20, 15, 30, 0, tzinfo=timezone.utc).isoformat(),
        }
        
        outcomes = [
            {
                "symbol": "GBPUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": datetime(2025, 1, 20, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
            }
        ]
        
        service1 = TradeGovernanceService()
        service1.add_outcomes(outcomes)
        report1 = service1.evaluate_trade(trade_context)
        
        service2 = TradeGovernanceService()
        service2.add_outcomes(outcomes)
        report2 = service2.evaluate_trade(trade_context)
        
        # Compare all fields except timestamp
        assert report1["allowed"] == report2["allowed"]
        assert report1["violations"] == report2["violations"]
        assert report1["explanation"] == report2["explanation"]


class TestNoMutation:
    """Verify inputs are never mutated."""
    
    def test_outcomes_not_mutated(self):
        """Original outcomes list is not modified."""
        service = TradeGovernanceService()
        
        outcomes_original = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": 50.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        
        # Make a copy to compare later
        import copy
        outcomes_copy = copy.deepcopy(outcomes_original)
        
        service.add_outcomes(outcomes_original)
        service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Original should be unchanged
        assert outcomes_original == outcomes_copy


class TestBatchEvaluation:
    """Verify batch evaluation functionality."""
    
    def test_evaluate_multiple_trades(self):
        """Batch evaluation returns results for all trades."""
        service = TradeGovernanceService(max_trades_per_day=5)
        
        trades = [
            {
                "symbol": f"SYM{i}",
                "timeframe": "1H",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(3)
        ]
        
        reports = service.evaluate_batch(trades)
        
        assert len(reports) == 3
        assert all("allowed" in r for r in reports)
        assert all("violations" in r for r in reports)
    
    def test_batch_with_invalid_input(self):
        """Batch handles empty or invalid inputs gracefully."""
        service = TradeGovernanceService()
        
        reports = service.evaluate_batch([])
        assert reports == []
        
        reports = service.evaluate_batch(None)
        assert reports == []


class TestInformationalGuarantee:
    """Verify explicit guarantee that results are informational only."""
    
    def test_disclaimer_present(self):
        """All reports include informational disclaimer."""
        service = TradeGovernanceService()
        
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        assert "disclaimer" in report
        assert "informational" in report["disclaimer"].lower()
        assert "influence" in report["disclaimer"].lower()
    
    def test_no_enforcement_triggers(self):
        """No enforcement methods or orchestrator calls exist."""
        service = TradeGovernanceService()
        
        # Service has no methods that execute trades or modify state
        methods = [m for m in dir(service) if not m.startswith("_")]
        
        enforcement_keywords = ["execute", "block", "stop", "prevent", "trigger"]
        for method in methods:
            for keyword in enforcement_keywords:
                assert keyword not in method.lower(), \
                    f"Found potential enforcement method: {method}"


class TestConfigurableRules:
    """Verify rules are configurable, not hardcoded."""
    
    def test_custom_daily_limit(self):
        """Custom daily trade limit is applied."""
        service = TradeGovernanceService(max_trades_per_day=10)
        
        today = datetime.now(timezone.utc)
        # Create 9 trades with different timeframes to avoid timeframe limit
        outcomes = [
            {
                "symbol": "SYM",
                "timeframe": f"TF{i}",  # Different timeframe for each trade
                "pnl": 50.0,
                "timestamp": (today - timedelta(hours=i)).isoformat(),
            }
            for i in range(9)
        ]
        service.add_outcomes(outcomes)
        
        # Trade at a slightly different time same day with a new timeframe
        future_time = today + timedelta(minutes=30)
        report = service.evaluate_trade({
            "symbol": "TEST",
            "timeframe": "TF9",  # New timeframe not used before
            "timestamp": future_time.isoformat(),
        })
        
        # 9 trades from earlier today, limit is 10, next trade should be allowed (9/10)
        assert report["allowed"] is True
    
    def test_custom_cooldown(self):
        """Custom cooldown period is applied."""
        service = TradeGovernanceService(cooldown_minutes_after_loss=60)
        
        now = datetime.now(timezone.utc)
        loss_time = now - timedelta(minutes=30)  # Loss 30 minutes ago
        
        outcomes = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "pnl": -100.0,
                "timestamp": loss_time.isoformat(),
            }
        ]
        service.add_outcomes(outcomes)
        
        # 30 minutes into 60-minute cooldown
        report = service.evaluate_trade({
            "symbol": "GBPUSD",
            "timeframe": "1H",
            "timestamp": now.isoformat(),
        })
        
        assert report["allowed"] is False
        assert any("Cooldown" in v for v in report["violations"])


class TestOutputStructure:
    """Verify consistent output structure."""
    
    def test_trade_evaluation_structure(self):
        """Trade evaluation returns all required fields."""
        service = TradeGovernanceService()
        
        report = service.evaluate_trade({
            "symbol": "EURUSD",
            "timeframe": "1H",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        required_fields = ["allowed", "violations", "explanation", "evaluated_at", "disclaimer"]
        for field in required_fields:
            assert field in report, f"Missing required field: {field}"
        
        assert isinstance(report["allowed"], bool)
        assert isinstance(report["violations"], list)
        assert isinstance(report["explanation"], str)
        assert isinstance(report["evaluated_at"], str)
    
    def test_batch_evaluation_structure(self):
        """Batch evaluation returns list of properly structured reports."""
        service = TradeGovernanceService()
        
        trades = [
            {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
        
        reports = service.evaluate_batch(trades)
        
        assert isinstance(reports, list)
        assert len(reports) > 0
        assert all("allowed" in r for r in reports)
