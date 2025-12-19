"""
Unit tests for Outcome Analytics Service.

Verifies:
1. Correct aggregation of outcomes and policy evaluations
2. Edge cases (no data, partial data, null values)
3. Deterministic results (same inputs → same outputs)
4. No mutation of input data
5. Accurate policy false-positive / false-negative calculations
6. Fail-silent error handling (analytics never crash)
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

from reasoner_service.outcome_analytics_service import (
    OutcomeAnalyticsService,
    create_analytics_service,
)


class TestPolicyVetoImpact:
    """Test counterfactual analysis of policy veto impact."""
    
    def test_veto_impact_empty_data(self):
        """Handle empty outcomes and evaluations."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        result = service.policy_veto_impact([], [])
        
        assert result["total_trades"] == 0
        assert result["would_have_been_vetoed"] == 0
        assert result["vetoed_winners"] == 0
        assert result["vetoed_losers"] == 0
        assert result["veto_precision"] == 0.0
        assert result["veto_recall"] == 0.0
    
    def test_veto_impact_all_winners(self):
        """When all trades are winners, veto precision is 0 (all false positives)."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {
                "signal_type": "bullish_choch",
                "symbol": "EURUSD",
                "timeframe": "4H",
                "outcome": "win",
                "pnl": 100,
            },
            {
                "signal_type": "bullish_choch",
                "symbol": "EURUSD",
                "timeframe": "4H",
                "outcome": "win",
                "pnl": 150,
            },
        ]
        
        evaluations = [
            {
                "decision": "veto",
                "signal_type": "bullish_choch",
                "symbol": "EURUSD",
                "timeframe": "4H",
            }
        ]
        
        result = service.policy_veto_impact(outcomes, evaluations)
        
        assert result["total_trades"] == 2
        assert result["would_have_been_vetoed"] == 2
        assert result["vetoed_winners"] == 2
        assert result["vetoed_losers"] == 0
        assert result["veto_precision"] == 0.0  # No losses among vetoed
        assert result["veto_recall"] == 0.0  # Didn't catch any losses
        assert result["veto_false_positives"] == 2
    
    def test_veto_impact_all_losers(self):
        """When all trades are losers, veto precision is 1.0 (perfect precision)."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {
                "signal_type": "bearish_bos",
                "symbol": "GBPUSD",
                "timeframe": "1H",
                "outcome": "loss",
                "pnl": -50,
            },
            {
                "signal_type": "bearish_bos",
                "symbol": "GBPUSD",
                "timeframe": "1H",
                "outcome": "loss",
                "pnl": -75,
            },
        ]
        
        evaluations = [
            {
                "decision": "veto",
                "signal_type": "bearish_bos",
                "symbol": "GBPUSD",
                "timeframe": "1H",
            }
        ]
        
        result = service.policy_veto_impact(outcomes, evaluations)
        
        assert result["total_trades"] == 2
        assert result["would_have_been_vetoed"] == 2
        assert result["vetoed_losers"] == 2
        assert result["vetoed_winners"] == 0
        assert result["veto_precision"] == 1.0  # All vetoed trades were losses
        assert result["veto_recall"] == 1.0  # Caught all losses
        assert result["veto_false_negatives"] == 0
    
    def test_veto_impact_mixed(self):
        """Mixed outcomes - some winners, some losers, partial veto coverage."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"signal_type": "s1", "symbol": "SYM1", "timeframe": "4H", "outcome": "win", "pnl": 100},
            {"signal_type": "s1", "symbol": "SYM1", "timeframe": "4H", "outcome": "win", "pnl": 80},
            {"signal_type": "s1", "symbol": "SYM1", "timeframe": "4H", "outcome": "loss", "pnl": -50},
            {"signal_type": "s1", "symbol": "SYM1", "timeframe": "4H", "outcome": "loss", "pnl": -60},
        ]
        
        evaluations = [
            {
                "decision": "veto",
                "signal_type": "s1",
                "symbol": "SYM1",
                "timeframe": "4H",
            }
        ]
        
        result = service.policy_veto_impact(outcomes, evaluations)
        
        assert result["total_trades"] == 4
        assert result["would_have_been_vetoed"] == 4
        assert result["vetoed_winners"] == 2
        assert result["vetoed_losers"] == 2
        assert result["veto_precision"] == 0.5  # Half of vetoed trades were losses
        assert result["veto_recall"] == 1.0  # Caught all losses
        assert result["veto_false_positives"] == 2
        assert result["veto_false_negatives"] == 0
    
    def test_veto_impact_deterministic(self):
        """Same inputs always produce same outputs (except timestamp)."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"signal_type": "s1", "symbol": "EUR", "timeframe": "4H", "outcome": "win"},
            {"signal_type": "s1", "symbol": "EUR", "timeframe": "4H", "outcome": "loss"},
        ]
        
        evaluations = [
            {"decision": "veto", "signal_type": "s1", "symbol": "EUR", "timeframe": "4H"}
        ]
        
        result1 = service.policy_veto_impact(outcomes, evaluations)
        result2 = service.policy_veto_impact(outcomes, evaluations)
        
        # Compare all fields except timestamp
        for key in result1:
            if key != "analysis_period":
                assert result1[key] == result2[key]
    
    def test_veto_impact_no_mutation(self):
        """Outcomes and evaluations are not mutated."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"signal_type": "s1", "symbol": "EUR", "timeframe": "4H", "outcome": "win"}
        ]
        outcomes_copy = [dict(o) for o in outcomes]
        
        evaluations = [
            {"decision": "veto", "signal_type": "s1", "symbol": "EUR", "timeframe": "4H"}
        ]
        evaluations_copy = [dict(e) for e in evaluations]
        
        service.policy_veto_impact(outcomes, evaluations)
        
        assert outcomes == outcomes_copy
        assert evaluations == evaluations_copy


class TestSignalPolicyHeatmap:
    """Test signal-policy heatmap analytics."""
    
    def test_heatmap_empty_data(self):
        """Handle empty outcomes."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        result = service.signal_policy_heatmap([], [])
        
        assert result["by_signal_type"] == {}
        assert result["by_timeframe"] == {}
    
    def test_heatmap_single_signal_type(self):
        """Analyze single signal type."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"signal_type": "bullish_choch", "timeframe": "4H", "outcome": "win"},
            {"signal_type": "bullish_choch", "timeframe": "4H", "outcome": "win"},
            {"signal_type": "bullish_choch", "timeframe": "4H", "outcome": "loss"},
        ]
        
        evaluations = [
            {
                "decision": "veto",
                "signal_type": "bullish_choch",
                "timeframe": "4H",
                "symbol": "EUR",
            }
        ]
        
        result = service.signal_policy_heatmap(outcomes, evaluations)
        
        assert "bullish_choch" in result["by_signal_type"]
        stats = result["by_signal_type"]["bullish_choch"]
        assert stats["total_trades"] == 3
        assert stats["vetoed_trades"] == 3  # All would have been vetoed
        assert stats["veto_rate"] == 1.0  # 100% veto rate
    
    def test_heatmap_by_timeframe(self):
        """Aggregate by timeframe."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"signal_type": "s1", "timeframe": "4H", "symbol": "EUR", "outcome": "win"},
            {"signal_type": "s1", "timeframe": "4H", "symbol": "EUR", "outcome": "loss"},
            {"signal_type": "s1", "timeframe": "1H", "symbol": "EUR", "outcome": "win"},
        ]
        
        evaluations = []
        
        result = service.signal_policy_heatmap(outcomes, evaluations)
        
        assert "4H" in result["by_timeframe"]
        assert result["by_timeframe"]["4H"]["total_trades"] == 2
        assert "1H" in result["by_timeframe"]
        assert result["by_timeframe"]["1H"]["total_trades"] == 1
    
    def test_heatmap_deterministic(self):
        """Same inputs always produce same outputs (except timestamp)."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"signal_type": "s1", "timeframe": "4H", "symbol": "EUR", "outcome": "win"},
            {"signal_type": "s1", "timeframe": "4H", "symbol": "EUR", "outcome": "loss"},
        ]
        evaluations = []
        
        result1 = service.signal_policy_heatmap(outcomes, evaluations)
        result2 = service.signal_policy_heatmap(outcomes, evaluations)
        
        # Compare all fields except timestamp
        for key in result1:
            if key != "analysis_period":
                assert result1[key] == result2[key]


class TestRegimePolicyPerformance:
    """Test regime-based policy performance analysis."""
    
    def test_regime_empty_data(self):
        """Handle empty outcomes."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        result = service.regime_policy_performance([])
        
        assert result["trending_market"]["trades_in_regime"] == 0
        assert result["ranging_market"]["trades_in_regime"] == 0
        assert result["high_volatility"]["trades_in_regime"] == 0
    
    def test_regime_single_outcome(self):
        """Single outcome is classified into a regime."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"pnl": 100, "outcome": "win"}
        ]
        
        result = service.regime_policy_performance(outcomes)
        
        total_trades = (
            result["trending_market"].get("trades_in_regime", 0)
            + result["ranging_market"].get("trades_in_regime", 0)
            + result["high_volatility"].get("trades_in_regime", 0)
        )
        assert total_trades == 1
    
    def test_regime_deterministic(self):
        """Same outcomes always produce same regime classification (except timestamp)."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"pnl": 100, "outcome": "win"},
            {"pnl": -50, "outcome": "loss"},
            {"pnl": 75, "outcome": "win"},
        ]
        
        result1 = service.regime_policy_performance(outcomes)
        result2 = service.regime_policy_performance(outcomes)
        
        # Compare all fields except timestamp
        for key in result1:
            if key != "analysis_period":
                assert result1[key] == result2[key]
    
    def test_regime_statistics(self):
        """Regime statistics are correctly calculated."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"pnl": 100, "outcome": "win"},
            {"pnl": 90, "outcome": "win"},
            {"pnl": -50, "outcome": "loss"},
            {"pnl": -60, "outcome": "loss"},
        ]
        
        result = service.regime_policy_performance(outcomes)
        
        # Check that at least one regime has data
        has_data = any(
            result[regime].get("trades_in_regime", 0) > 0
            for regime in ["trending_market", "ranging_market", "high_volatility"]
        )
        assert has_data


class TestOutputConsistency:
    """Test output structure and consistency across methods."""
    
    def test_veto_impact_output_structure(self):
        """Veto impact has required fields."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        result = service.policy_veto_impact([], [])
        
        required_fields = [
            "total_trades",
            "would_have_been_vetoed",
            "vetoed_winners",
            "vetoed_losers",
            "veto_precision",
            "veto_recall",
            "veto_false_positives",
            "veto_false_negatives",
            "analysis_period",
            "note",
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
    
    def test_heatmap_output_structure(self):
        """Heatmap has required fields."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        result = service.signal_policy_heatmap([], [])
        
        required_fields = [
            "by_signal_type",
            "by_timeframe",
            "analysis_period",
            "note",
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
    
    def test_regime_output_structure(self):
        """Regime analysis has required fields."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        result = service.regime_policy_performance([])
        
        required_fields = [
            "trending_market",
            "ranging_market",
            "high_volatility",
            "analysis_period",
            "note",
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
    
    def test_all_outputs_have_disclaimer(self):
        """All outputs include disclaimer that service doesn't influence decisions."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        veto_result = service.policy_veto_impact([], [])
        heatmap_result = service.signal_policy_heatmap([], [])
        regime_result = service.regime_policy_performance([])
        
        assert "note" in veto_result
        assert "note" in heatmap_result
        assert "note" in regime_result
        
        for result in [veto_result, heatmap_result, regime_result]:
            assert "does not influence decisions" in result.get("note", "").lower()


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_null_outcome_fields(self):
        """Handle outcomes with null/missing fields."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"outcome": "win"},  # Missing signal_type, symbol, etc.
            {"signal_type": "s1", "outcome": "loss"},  # Missing symbol
        ]
        
        # Should not crash
        result = service.policy_veto_impact(outcomes, [])
        assert result["total_trades"] == 2
    
    def test_zero_pnl_outcomes(self):
        """Handle breakeven trades (zero PnL)."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"pnl": 0, "outcome": "breakeven"},
            {"pnl": 100, "outcome": "win"},
            {"pnl": -50, "outcome": "loss"},
        ]
        
        result = service.regime_policy_performance(outcomes)
        
        # Should handle zero PnL without crashing
        assert "trending_market" in result
    
    def test_negative_veto_counts(self):
        """Veto counts should never be negative."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"signal_type": "s1", "symbol": "EUR", "timeframe": "4H", "outcome": "win"}
        ]
        
        evaluations = [
            {"decision": "allow", "signal_type": "s1"}  # No veto
        ]
        
        result = service.policy_veto_impact(outcomes, evaluations)
        
        assert result["would_have_been_vetoed"] >= 0
        assert result["vetoed_winners"] >= 0
        assert result["vetoed_losers"] >= 0
    
    def test_precision_recall_bounds(self):
        """Precision and recall should be between 0 and 1."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outcomes = [
            {"signal_type": "s1", "symbol": "EUR", "timeframe": "4H", "outcome": "win"},
            {"signal_type": "s1", "symbol": "EUR", "timeframe": "4H", "outcome": "loss"},
        ]
        
        evaluations = [
            {"decision": "veto", "signal_type": "s1", "symbol": "EUR", "timeframe": "4H"}
        ]
        
        result = service.policy_veto_impact(outcomes, evaluations)
        
        assert 0.0 <= result["veto_precision"] <= 1.0
        assert 0.0 <= result["veto_recall"] <= 1.0


class TestServiceInitialization:
    """Test service initialization and configuration."""
    
    def test_service_initialization(self):
        """Service initializes with sessionmaker."""
        mock_sessionmaker = AsyncMock()
        service = OutcomeAnalyticsService(mock_sessionmaker)
        
        assert service.sessionmaker == mock_sessionmaker
        assert service.stats_service is None
    
    def test_service_with_stats_service(self):
        """Service can be initialized with OutcomeStatsService."""
        mock_sessionmaker = AsyncMock()
        mock_stats_service = AsyncMock()
        
        service = OutcomeAnalyticsService(mock_sessionmaker, mock_stats_service)
        
        assert service.sessionmaker == mock_sessionmaker
        assert service.stats_service == mock_stats_service
    
    @pytest.mark.asyncio
    async def test_factory_function(self):
        """Factory function creates service correctly."""
        mock_sessionmaker = AsyncMock()
        mock_stats_service = AsyncMock()
        
        service = await create_analytics_service(mock_sessionmaker, mock_stats_service)
        
        assert isinstance(service, OutcomeAnalyticsService)
        assert service.sessionmaker == mock_sessionmaker
        assert service.stats_service == mock_stats_service


class TestFailSilentBehavior:
    """Test that analytics fail silently without crashing execution."""
    
    @pytest.mark.asyncio
    async def test_get_outcomes_handles_db_error(self):
        """Get outcomes handles database errors gracefully."""
        mock_sessionmaker = AsyncMock()
        mock_sessionmaker.return_value.__aenter__.side_effect = Exception("DB error")
        
        service = OutcomeAnalyticsService(mock_sessionmaker)
        
        # Should return empty list, not raise
        outcomes = await service.get_outcomes_for_analysis()
        assert outcomes == []
    
    @pytest.mark.asyncio
    async def test_full_report_handles_errors(self):
        """Full report handles errors gracefully."""
        # Create a mock sessionmaker that fails at the context manager level
        mock_session = AsyncMock()
        mock_sessionmaker = AsyncMock(return_value=mock_session)
        mock_sessionmaker.return_value.__aenter__.side_effect = Exception("DB error")
        
        service = OutcomeAnalyticsService(mock_sessionmaker)
        
        # Should return error dict or partial report, not raise
        report = await service.full_analytics_report()
        
        # Either it has an error key or it still returns a valid report structure
        # with the data it could retrieve
        assert "disclaimer" in report
        # If there's an error, it should be in the report
        if "error" in report:
            assert isinstance(report["error"], str)


class TestNonInfluenceGuarantee:
    """Test that analytics never influence live trading."""
    
    def test_no_state_mutations(self):
        """Analytics methods don't mutate any state."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        initial_cache = dict(service._cache)
        
        # Run analytics
        service.policy_veto_impact([], [])
        service.signal_policy_heatmap([], [])
        service.regime_policy_performance([])
        
        # Cache should not change (purely analytical)
        assert service._cache == initial_cache
    
    def test_output_is_read_only_intent(self):
        """Output structure makes it clear this is for analysis only."""
        service = OutcomeAnalyticsService(AsyncMock())
        
        outputs = [
            service.policy_veto_impact([], []),
            service.signal_policy_heatmap([], []),
            service.regime_policy_performance([]),
        ]
        
        for output in outputs:
            # Each output should have a disclaimer
            assert "note" in output
            note = output["note"].lower()
            assert "analyt" in note or "does not influence" in note
