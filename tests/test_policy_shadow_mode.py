"""
Unit tests for Policy Shadow Mode integration.

Verifies:
1. Shadow mode initializes correctly
2. Evaluator is called on each decision
3. Results are logged to audit trail
4. Execution always proceeds regardless of VETO
5. Non-blocking behavior (errors don't interrupt flow)
6. All metadata is captured correctly
"""

import pytest
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch, Mock

from reasoner_service.policy_shadow_mode import (
    PolicyShadowModeManager,
    get_shadow_mode_manager,
    initialize_shadow_mode,
    evaluate_decision_shadow,
    get_shadow_audit_trail,
    get_shadow_stats,
)


class TestPolicyShadowModeManagerInitialization:
    """Test shadow mode manager initialization."""
    
    def test_initialization_creates_manager(self):
        """Manager is created with no evaluator initially."""
        manager = PolicyShadowModeManager()
        assert manager is not None
        assert manager._evaluator is None
        assert manager._initialized is False
        assert manager._audit_trail == []
    
    @pytest.mark.asyncio
    async def test_initialize_success(self):
        """Initialize with valid stats service creates evaluator."""
        manager = PolicyShadowModeManager()
        
        # Mock stats service
        mock_stats_service = AsyncMock()
        
        # Mock create_policy_evaluator
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        
        with patch(
            "reasoner_service.outcome_policy_evaluator.create_policy_evaluator",
            return_value=mock_evaluator,
        ):
            success = await manager.initialize(mock_stats_service, {})
            assert success is True
            assert manager._evaluator is not None
            assert manager._initialized is True
    
    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Initialize is idempotent - multiple calls are safe."""
        manager = PolicyShadowModeManager()
        
        mock_stats_service = AsyncMock()
        mock_evaluator = AsyncMock()
        
        with patch(
            "reasoner_service.outcome_policy_evaluator.create_policy_evaluator",
            return_value=mock_evaluator,
        ):
            # First call
            result1 = await manager.initialize(mock_stats_service, {})
            assert result1 is True
            
            # Second call - should return immediately
            result2 = await manager.initialize(mock_stats_service, {})
            assert result2 is True
    
    @pytest.mark.asyncio
    async def test_initialize_with_config(self):
        """Initialize passes config to factory function."""
        manager = PolicyShadowModeManager()
        
        mock_stats_service = AsyncMock()
        mock_evaluator = AsyncMock()
        
        config = {
            "win_rate_threshold": 0.50,
            "max_loss_streak": 3,
        }
        
        with patch(
            "reasoner_service.outcome_policy_evaluator.create_policy_evaluator",
            return_value=mock_evaluator,
        ) as mock_factory:
            await manager.initialize(mock_stats_service, config)
            mock_factory.assert_called_once_with(mock_stats_service, config)
    
    @pytest.mark.asyncio
    async def test_initialize_graceful_failure(self):
        """Initialize catches exceptions gracefully."""
        manager = PolicyShadowModeManager()
        
        mock_stats_service = AsyncMock()
        
        with patch(
            "reasoner_service.outcome_policy_evaluator.create_policy_evaluator",
            side_effect=Exception("Factory failed"),
        ):
            success = await manager.initialize(mock_stats_service)
            assert success is False
            assert manager._evaluator is None
            assert manager._initialized is True
            assert "Factory failed" in manager._init_error


class TestShadowModeEvaluation:
    """Test decision evaluation in shadow mode."""
    
    @pytest.mark.asyncio
    async def test_evaluate_decision_allow(self):
        """Evaluates decision and returns ALLOW result."""
        manager = PolicyShadowModeManager()
        
        # Create mock evaluator that returns None (ALLOW)
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        decision = {
            "signal_type": "bullish_choch",
            "symbol": "EURUSD",
            "timeframe": "4H",
            "recommendation": "buy",
            "confidence": 0.85,
        }
        
        result = await manager.evaluate_decision(decision)
        
        assert result["evaluated"] is True
        assert result["decision"] == "allow"
        assert result["rule_name"] is None
        assert result["reason"] is None
        assert result["error"] is None
        assert result["audit_entry"] is not None
        assert result["audit_entry"]["decision"] == "allow"
    
    @pytest.mark.asyncio
    async def test_evaluate_decision_veto(self):
        """Evaluates decision and returns VETO result with reason."""
        manager = PolicyShadowModeManager()
        
        # Create mock PolicyEvaluation result (VETO)
        from reasoner_service.outcome_policy_evaluator import PolicyDecision
        
        mock_eval_result = MagicMock()
        mock_eval_result.decision = PolicyDecision.VETO
        mock_eval_result.rule_name = "WinRateThresholdRule"
        mock_eval_result.reason = "bullish_choch win rate 0.35 below threshold 0.45"
        mock_eval_result.metrics_snapshot = {"win_rate": 0.35, "total_trades": 20}
        mock_eval_result.timestamp = datetime.now(timezone.utc).isoformat()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=mock_eval_result)
        manager._evaluator = mock_evaluator
        
        decision = {
            "signal_type": "bullish_choch",
            "symbol": "EURUSD",
            "recommendation": "buy",
            "confidence": 0.85,
        }
        
        result = await manager.evaluate_decision(decision)
        
        assert result["evaluated"] is True
        assert result["decision"] == "veto"
        assert result["rule_name"] == "WinRateThresholdRule"
        assert "win rate" in result["reason"]
        assert result["error"] is None
        assert result["audit_entry"]["decision"] == "veto"
    
    @pytest.mark.asyncio
    async def test_evaluate_decision_not_initialized(self):
        """Handles evaluation when evaluator not initialized."""
        manager = PolicyShadowModeManager()
        
        decision = {"signal_type": "test", "symbol": "TEST"}
        
        result = await manager.evaluate_decision(decision)
        
        assert result["evaluated"] is False
        assert result["decision"] is None
        assert result["error"] == "evaluator_not_initialized"
    
    @pytest.mark.asyncio
    async def test_evaluate_decision_error_handling(self):
        """Handles evaluation errors gracefully (non-blocking)."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(side_effect=Exception("Evaluation failed"))
        manager._evaluator = mock_evaluator
        
        decision = {"signal_type": "test", "symbol": "TEST"}
        
        result = await manager.evaluate_decision(decision)
        
        # IMPORTANT: Non-blocking - error is captured but doesn't crash
        assert result["evaluated"] is False
        assert result["decision"] is None
        assert "Evaluation failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_evaluate_extracts_metadata_from_decision(self):
        """Extracts signal_type, symbol, timeframe from decision dict."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        decision = {
            "signal_type": "bullish_engulfing",
            "symbol": "GBPUSD",
            "timeframe": "1H",
        }
        
        await manager.evaluate_decision(decision)
        
        # Verify evaluator was called with extracted metadata
        mock_evaluator.evaluate.assert_called_once_with(
            "bullish_engulfing", "GBPUSD", "1H"
        )
    
    @pytest.mark.asyncio
    async def test_evaluate_uses_provided_metadata(self):
        """Uses provided metadata parameters over decision dict."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        decision = {
            "signal_type": "from_decision",
            "symbol": "from_decision",
            "timeframe": "from_decision",
        }
        
        await manager.evaluate_decision(
            decision,
            signal_type="provided_signal",
            symbol="PROVIDED",
            timeframe="4H",
        )
        
        # Should use provided parameters, not decision dict
        mock_evaluator.evaluate.assert_called_once_with(
            "provided_signal", "PROVIDED", "4H"
        )


class TestAuditTrailTracking:
    """Test audit trail logging and retrieval."""
    
    @pytest.mark.asyncio
    async def test_audit_trail_records_all_evaluations(self):
        """All evaluations are recorded in audit trail."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        decision1 = {"signal_type": "test1", "symbol": "EUR"}
        decision2 = {"signal_type": "test2", "symbol": "GBP"}
        
        await manager.evaluate_decision(decision1)
        await manager.evaluate_decision(decision2)
        
        assert len(manager._audit_trail) == 2
        assert manager._audit_trail[0]["signal_type"] == "test1"
        assert manager._audit_trail[1]["signal_type"] == "test2"
    
    @pytest.mark.asyncio
    async def test_get_audit_trail_with_limit(self):
        """Get audit trail respects limit parameter."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        # Add 5 evaluations
        for i in range(5):
            await manager.evaluate_decision({"signal_type": f"test{i}", "symbol": f"SYM{i}"})
        
        # Get limited audit trail
        trail = await manager.get_audit_trail(limit=2)
        
        assert len(trail) == 2
        # Most recent first
        assert trail[0]["signal_type"] == "test4"
        assert trail[1]["signal_type"] == "test3"
    
    @pytest.mark.asyncio
    async def test_get_audit_trail_no_limit(self):
        """Get audit trail without limit returns all entries."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        for i in range(5):
            await manager.evaluate_decision({"signal_type": f"test{i}"})
        
        trail = await manager.get_audit_trail(limit=None)
        
        assert len(trail) == 5
    
    @pytest.mark.asyncio
    async def test_clear_audit_trail(self):
        """Clear audit trail removes all entries."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        for i in range(3):
            await manager.evaluate_decision({"signal_type": f"test{i}"})
        
        assert len(manager._audit_trail) == 3
        
        cleared = await manager.clear_audit_trail()
        
        assert cleared == 3
        assert len(manager._audit_trail) == 0


class TestShadowModeStatistics:
    """Test shadow mode statistics collection."""
    
    def test_stats_empty_audit_trail(self):
        """Stats for empty audit trail."""
        manager = PolicyShadowModeManager()
        
        stats = manager.get_stats()
        
        assert stats["total_evaluations"] == 0
        assert stats["allow_count"] == 0
        assert stats["veto_count"] == 0
        # veto_rate not present when audit trail is empty
    
    @pytest.mark.asyncio
    async def test_stats_tracks_allow_count(self):
        """Stats tracks ALLOW decisions."""
        manager = PolicyShadowModeManager()
        
        # Manually add ALLOW entries to audit trail
        manager._audit_trail = [
            {"decision": "allow", "signal_type": "test1"},
            {"decision": "allow", "signal_type": "test2"},
        ]
        
        stats = manager.get_stats()
        
        assert stats["total_evaluations"] == 2
        assert stats["allow_count"] == 2
        assert stats["veto_count"] == 0
        assert stats["veto_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_stats_tracks_veto_count(self):
        """Stats tracks VETO decisions and reasons."""
        manager = PolicyShadowModeManager()
        
        manager._audit_trail = [
            {"decision": "veto", "rule_name": "WinRateThresholdRule", "signal_type": "test1"},
            {"decision": "veto", "rule_name": "LossStreakRule", "signal_type": "test2"},
            {"decision": "veto", "rule_name": "WinRateThresholdRule", "signal_type": "test3"},
            {"decision": "allow"},
        ]
        
        stats = manager.get_stats()
        
        assert stats["total_evaluations"] == 4
        assert stats["allow_count"] == 1
        assert stats["veto_count"] == 3
        assert stats["veto_rate"] == 0.75
        assert stats["veto_by_rule"]["WinRateThresholdRule"] == 2
        assert stats["veto_by_rule"]["LossStreakRule"] == 1
    
    @pytest.mark.asyncio
    async def test_stats_tracks_veto_by_signal_type(self):
        """Stats aggregates VETO by signal type."""
        manager = PolicyShadowModeManager()
        
        manager._audit_trail = [
            {"decision": "veto", "signal_type": "bullish_choch"},
            {"decision": "veto", "signal_type": "bullish_choch"},
            {"decision": "veto", "signal_type": "bearish_engulfing"},
        ]
        
        stats = manager.get_stats()
        
        assert stats["veto_by_signal_type"]["bullish_choch"] == 2
        assert stats["veto_by_signal_type"]["bearish_engulfing"] == 1


class TestGlobalShadowModeInterface:
    """Test global singleton shadow mode functions."""
    
    def test_get_shadow_mode_manager_returns_singleton(self):
        """get_shadow_mode_manager returns same instance."""
        mgr1 = get_shadow_mode_manager()
        mgr2 = get_shadow_mode_manager()
        
        assert mgr1 is mgr2
    
    @pytest.mark.asyncio
    async def test_initialize_shadow_mode_global(self):
        """initialize_shadow_mode initializes global manager."""
        mock_stats_service = AsyncMock()
        mock_evaluator = AsyncMock()
        
        with patch(
            "reasoner_service.outcome_policy_evaluator.create_policy_evaluator",
            return_value=mock_evaluator,
        ):
            success = await initialize_shadow_mode(mock_stats_service, {})
            assert success is True
    
    @pytest.mark.asyncio
    async def test_evaluate_decision_shadow_global(self):
        """evaluate_decision_shadow uses global manager."""
        mgr = get_shadow_mode_manager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        mgr._evaluator = mock_evaluator
        
        decision = {"signal_type": "test", "symbol": "TEST"}
        
        result = await evaluate_decision_shadow(decision)
        
        assert result["evaluated"] is True
        assert result["decision"] == "allow"
    
    @pytest.mark.asyncio
    async def test_get_shadow_audit_trail_global(self):
        """get_shadow_audit_trail retrieves from global manager."""
        mgr = get_shadow_mode_manager()
        mgr._audit_trail = [
            {"decision": "allow", "signal_type": "test1"},
            {"decision": "veto", "signal_type": "test2"},
        ]
        
        trail = await get_shadow_audit_trail(limit=10)
        
        assert len(trail) == 2
        assert trail[0]["signal_type"] == "test2"  # Most recent first


class TestNonBlockingBehavior:
    """Test that shadow mode never blocks decision execution."""
    
    @pytest.mark.asyncio
    async def test_veto_does_not_block_execution(self):
        """VETO decision does NOT block execution (shadow mode)."""
        manager = PolicyShadowModeManager()
        
        from reasoner_service.outcome_policy_evaluator import PolicyDecision
        
        # Create VETO result
        mock_eval_result = MagicMock()
        mock_eval_result.decision = PolicyDecision.VETO
        mock_eval_result.rule_name = "LossStreakRule"
        mock_eval_result.reason = "Streak too high"
        mock_eval_result.metrics_snapshot = {}
        mock_eval_result.timestamp = datetime.now(timezone.utc).isoformat()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=mock_eval_result)
        manager._evaluator = mock_evaluator
        
        decision = {"signal_type": "test", "symbol": "TEST"}
        
        # Should not raise exception
        result = await manager.evaluate_decision(decision)
        
        # Result should be returned successfully
        assert result["evaluated"] is True
        assert result["decision"] == "veto"
        # But execution continues (no exception)
    
    @pytest.mark.asyncio
    async def test_evaluator_exception_does_not_block(self):
        """Evaluator exception does NOT block decision execution."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(
            side_effect=RuntimeError("Evaluator crashed")
        )
        manager._evaluator = mock_evaluator
        
        decision = {"signal_type": "test", "symbol": "TEST"}
        
        # Should not raise exception
        result = await manager.evaluate_decision(decision)
        
        # Error is captured but execution continues
        assert result["evaluated"] is False
        assert "Evaluator crashed" in result["error"]


class TestExecutionFlowIntegration:
    """Test that shadow mode integrates without breaking orchestration."""
    
    @pytest.mark.asyncio
    async def test_decision_metadata_preserved(self):
        """Decision metadata is preserved through shadow evaluation."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        decision = {
            "id": "dec_123",
            "signal_type": "test",
            "symbol": "EUR",
            "recommendation": "buy",
            "confidence": 0.9,
            "custom_field": "preserved",
        }
        
        result = await manager.evaluate_decision(decision)
        
        # Audit entry should include all metadata
        audit = result["audit_entry"]
        assert audit["decision_id"] == "dec_123"
        assert audit["recommendation"] == "buy"
        assert audit["confidence"] == 0.9
    
    @pytest.mark.asyncio
    async def test_shadow_result_structure(self):
        """Shadow result has expected structure for logging."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        mock_evaluator.evaluate = AsyncMock(return_value=None)
        manager._evaluator = mock_evaluator
        
        decision = {"signal_type": "test", "symbol": "TEST"}
        
        result = await manager.evaluate_decision(decision)
        
        # Result should have required fields for orchestrator attachment
        assert "evaluated" in result
        assert "decision" in result
        assert "rule_name" in result
        assert "reason" in result
        assert "metrics_snapshot" in result
        assert "timestamp" in result
        assert "error" in result
        assert "audit_entry" in result


class TestConcurrentAccess:
    """Test shadow mode thread-safety."""
    
    @pytest.mark.asyncio
    async def test_concurrent_evaluations(self):
        """Multiple concurrent evaluations are safe."""
        manager = PolicyShadowModeManager()
        
        mock_evaluator = AsyncMock()
        
        async def mock_eval(*args, **kwargs):
            await asyncio.sleep(0.001)  # Simulate some work
            return None
        
        mock_evaluator.evaluate = mock_eval
        manager._evaluator = mock_evaluator
        
        # Run multiple evaluations concurrently
        tasks = [
            manager.evaluate_decision({"signal_type": f"test{i}", "symbol": f"SYM{i}"})
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 10
        assert all(r["evaluated"] is True for r in results)
        
        # Audit trail should have all entries
        assert len(manager._audit_trail) == 10
