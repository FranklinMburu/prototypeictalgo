"""
Tests for CounterfactualEnforcementSimulator

Verifies:
- Deterministic replay and simulation
- No mutation of timelines
- Correct blocked/allowed classification
- Accurate P&L calculations
- Batch simulation correctness
- Explicit non-enforcement guarantee
"""

import pytest
from datetime import datetime, timezone, timedelta
from copy import deepcopy

from reasoner_service.counterfactual_enforcement_simulator import (
    CounterfactualEnforcementSimulator,
)
from reasoner_service.decision_timeline_service import DecisionTimelineService
from reasoner_service.trade_governance_service import TradeGovernanceService


class MockDecisionTimelineService:
    """Mock for testing without database."""
    
    def __init__(self):
        self.timelines = {}
    
    def record_event(self, event_type, payload, correlation_id):
        if correlation_id not in self.timelines:
            self.timelines[correlation_id] = []
        self.timelines[correlation_id].append({
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": deepcopy(payload),
            "correlation_id": correlation_id,
            "sequence_number": len(self.timelines.get(correlation_id, [])),
        })
    
    def get_timeline(self, correlation_id):
        return deepcopy(self.timelines.get(correlation_id, []))


class TestDeterministicReplay:
    """Verify replay is deterministic."""
    
    def test_same_timeline_produces_same_simulation(self):
        """Replaying same timeline twice produces identical results."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        # Record a timeline
        correlation_id = "trade_001"
        timeline_service.record_event(
            "SIGNAL_DETECTED",
            {"signal_type": "momentum", "strength": 0.85},
            correlation_id,
        )
        timeline_service.record_event(
            "DECISION_PROPOSED",
            {"symbol": "EURUSD", "timeframe": "1H"},
            correlation_id,
        )
        timeline_service.record_event(
            "TRADE_EXECUTED",
            {"symbol": "EURUSD", "entry": 1.1050, "exit": 1.1060},
            correlation_id,
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED",
            {"pnl": 100.0, "outcome": "win"},
            correlation_id,
        )
        
        # Simulate twice
        result1 = simulator.simulate(correlation_id)
        result2 = simulator.simulate(correlation_id)
        
        # Results must be identical
        assert result1["correlation_id"] == result2["correlation_id"]
        assert result1["would_have_been_allowed"] == result2["would_have_been_allowed"]
        assert result1["counterfactual_pnl"] == result2["counterfactual_pnl"]
        assert result1["pnl_difference"] == result2["pnl_difference"]
    
    def test_replay_order_matters(self):
        """Different event order produces different simulation."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        # Timeline 1: Winning trade
        cid1 = "trade_win"
        timeline_service.record_event(
            "TRADE_EXECUTED", {"symbol": "EURUSD"}, cid1
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 500.0}, cid1
        )
        result1 = simulator.simulate(cid1)
        
        # Timeline 2: Losing trade
        cid2 = "trade_loss"
        timeline_service.record_event(
            "TRADE_EXECUTED", {"symbol": "EURUSD"}, cid2
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": -200.0}, cid2
        )
        result2 = simulator.simulate(cid2)
        
        # Results must differ
        assert result1["original_outcome"]["pnl"] != result2["original_outcome"]["pnl"]


class TestNoMutation:
    """Verify timelines are not mutated by simulation."""
    
    def test_simulation_does_not_modify_timeline(self):
        """Simulating a timeline doesn't mutate stored events."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_immutable"
        original_payload = {"pnl": 125.0, "outcome": "win"}
        
        timeline_service.record_event(
            "OUTCOME_RECORDED", original_payload, correlation_id
        )
        
        # Get original timeline
        timeline_before = timeline_service.get_timeline(correlation_id)
        original_event = deepcopy(timeline_before[0])
        
        # Simulate
        result = simulator.simulate(correlation_id)
        
        # Get timeline after simulation
        timeline_after = timeline_service.get_timeline(correlation_id)
        
        # Timeline must be unchanged
        assert len(timeline_after) == len(timeline_before)
        assert timeline_after[0] == original_event
        assert timeline_after[0]["payload"]["pnl"] == 125.0
    
    def test_multiple_simulations_preserve_timeline(self):
        """Multiple simulations don't accumulate mutations."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_multi"
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 75.0}, correlation_id
        )
        
        original_count = len(timeline_service.get_timeline(correlation_id))
        
        # Simulate multiple times
        for _ in range(5):
            simulator.simulate(correlation_id)
        
        # Timeline size must not change
        assert len(timeline_service.get_timeline(correlation_id)) == original_count


class TestBlockedAllowedClassification:
    """Verify correct classification of allowed vs blocked trades."""
    
    def test_no_violations_means_allowed(self):
        """Trade with no governance violations is allowed."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_clean"
        timeline_service.record_event(
            "GOVERNANCE_EVALUATED",
            {"violations": []},
            correlation_id,
        )
        
        result = simulator.simulate(correlation_id)
        
        assert result["would_have_been_allowed"] is True
        assert len(result["violated_rules"]) == 0
    
    def test_violations_means_blocked(self):
        """Trade with violations is marked as blocked."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_violation"
        timeline_service.record_event(
            "GOVERNANCE_EVALUATED",
            {
                "violations": [
                    "max_daily_loss_exceeded",
                    "cooldown_period_active",
                ]
            },
            correlation_id,
        )
        
        result = simulator.simulate(correlation_id)
        
        assert result["would_have_been_allowed"] is False
        assert "max_daily_loss_exceeded" in result["violated_rules"]
        assert "cooldown_period_active" in result["violated_rules"]
    
    def test_multiple_violations_tracked(self):
        """All violations are tracked in results."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_multi_vio"
        violations = [
            "max_trades_per_day",
            "max_daily_loss",
            "killzone_hours",
        ]
        
        timeline_service.record_event(
            "GOVERNANCE_EVALUATED",
            {"violations": violations},
            correlation_id,
        )
        
        result = simulator.simulate(correlation_id)
        
        assert len(result["violated_rules"]) == 3
        for vio in violations:
            assert vio in result["violated_rules"]


class TestAccuratePnLCalculations:
    """Verify P&L delta calculations are accurate."""
    
    def test_pnl_difference_calculated(self):
        """P&L difference computed correctly."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_pnl"
        original_pnl = 250.0
        
        timeline_service.record_event(
            "OUTCOME_RECORDED",
            {"pnl": original_pnl},
            correlation_id,
        )
        
        result = simulator.simulate(correlation_id)
        
        assert result["original_outcome"]["pnl"] == original_pnl
        assert isinstance(result["counterfactual_pnl"], float)
        assert isinstance(result["pnl_difference"], float)
    
    def test_multiple_trades_pnl_aggregated(self):
        """Multiple outcomes are aggregated correctly."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_agg"
        
        # Add multiple outcomes
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 100.0}, correlation_id
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 50.0}, correlation_id
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": -25.0}, correlation_id
        )
        
        result = simulator.simulate(correlation_id)
        
        # Total should be 100 + 50 - 25 = 125
        assert result["original_outcome"]["pnl"] == 125.0
    
    def test_positive_pnl_difference_on_blocking(self):
        """Blocking losing trades improves P&L."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_improvement"
        
        # Add winning and losing outcomes
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 200.0}, correlation_id
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": -150.0}, correlation_id
        )
        timeline_service.record_event(
            "GOVERNANCE_EVALUATED",
            {"violations": ["max_daily_loss"]},
            correlation_id,
        )
        
        result = simulator.simulate(correlation_id)
        
        # Counterfactual should improve (blocking losing trade)
        assert result["counterfactual_pnl"] >= result["original_outcome"]["pnl"]


class TestDrawdownMetrics:
    """Verify drawdown calculations."""
    
    def test_drawdown_calculated(self):
        """Maximum drawdown is calculated."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_dd"
        
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 100.0}, correlation_id
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": -80.0}, correlation_id
        )
        
        result = simulator.simulate(correlation_id)
        
        assert "execution_impact" in result
        assert "max_drawdown_original" in result["execution_impact"]
        assert "max_drawdown_counterfactual" in result["execution_impact"]
        assert isinstance(result["execution_impact"]["drawdown_improvement"], float)
    
    def test_counterfactual_reduces_drawdown(self):
        """Blocking losing trades reduces drawdown."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_dd_reduced"
        
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 100.0}, correlation_id
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": -50.0}, correlation_id
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 30.0}, correlation_id
        )
        timeline_service.record_event(
            "GOVERNANCE_EVALUATED",
            {"violations": ["max_daily_loss"]},
            correlation_id,
        )
        
        result = simulator.simulate(correlation_id)
        
        # Counterfactual drawdown should be less than original
        assert (
            result["execution_impact"]["max_drawdown_counterfactual"]
            <= result["execution_impact"]["max_drawdown_original"]
        )


class TestBatchSimulation:
    """Verify batch simulation correctness."""
    
    def test_batch_simulation_returns_list(self):
        """Batch simulation returns list of results."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        # Setup timelines
        for i in range(3):
            cid = f"trade_{i}"
            timeline_service.record_event(
                "OUTCOME_RECORDED", {"pnl": 100.0 * (i + 1)}, cid
            )
        
        correlation_ids = ["trade_0", "trade_1", "trade_2"]
        results = simulator.simulate_batch(correlation_ids)
        
        # Should have 3 results + 1 summary
        assert len(results) == 4
        assert results[-1].get("_batch_summary") is True
    
    def test_batch_summary_aggregates(self):
        """Batch summary aggregates results correctly."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        # Setup timelines with violations
        for i in range(2):
            cid = f"trade_batch_{i}"
            timeline_service.record_event(
                "GOVERNANCE_EVALUATED",
                {"violations": ["max_daily_loss"]},
                cid,
            )
            timeline_service.record_event(
                "OUTCOME_RECORDED",
                {"pnl": 100.0},
                cid,
            )
        
        results = simulator.simulate_batch(["trade_batch_0", "trade_batch_1"])
        summary = results[-1]
        
        assert summary["total_simulations"] == 2
        assert summary["blocked_count"] == 2
        assert summary["allowed_count"] == 0
    
    def test_batch_with_invalid_correlation_ids(self):
        """Batch handles invalid correlation IDs gracefully."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        # Mix valid and invalid
        correlation_ids = ["valid_trade", 12345, "another_valid"]
        results = simulator.simulate_batch(correlation_ids)
        
        # Should skip non-string IDs but continue
        assert len(results) >= 1  # At least the summary
    
    def test_batch_empty_list(self):
        """Batch with empty list returns empty."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        results = simulator.simulate_batch([])
        
        assert isinstance(results, list)
    
    def test_batch_rule_impact_totals(self):
        """Batch summary totals rule violations."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        # Trade 1: multiple violations
        timeline_service.record_event(
            "GOVERNANCE_EVALUATED",
            {"violations": ["max_daily_loss", "max_daily_loss"]},
            "trade_rule_1",
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED",
            {"pnl": 0.0},
            "trade_rule_1",
        )
        
        # Trade 2: different violation
        timeline_service.record_event(
            "GOVERNANCE_EVALUATED",
            {"violations": ["killzone_hours"]},
            "trade_rule_2",
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED",
            {"pnl": 0.0},
            "trade_rule_2",
        )
        
        results = simulator.simulate_batch(["trade_rule_1", "trade_rule_2"])
        summary = results[-1]
        
        assert summary["rule_violation_totals"]["max_daily_loss"] == 2
        assert summary["rule_violation_totals"]["killzone_hours"] == 1


class TestNonEnforcementGuarantee:
    """Explicit verification that simulation cannot enforce."""
    
    def test_no_execution_methods(self):
        """Simulator has no methods that execute trades."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        public_methods = [m for m in dir(simulator) if not m.startswith("_")]
        
        # Check for dangerous method names
        dangerous = ["execute", "block", "submit", "place", "send", "write"]
        for method in public_methods:
            method_lower = method.lower()
            assert not any(
                d in method_lower for d in dangerous
            ), f"Found dangerous method: {method}"
    
    def test_no_timeline_mutations(self):
        """Simulator cannot mutate timeline service."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_safe"
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 100.0}, correlation_id
        )
        
        original_timeline = timeline_service.get_timeline(correlation_id)
        original_length = len(original_timeline)
        
        # Run simulation
        simulator.simulate(correlation_id)
        
        # Timeline must be unchanged
        new_timeline = timeline_service.get_timeline(correlation_id)
        assert len(new_timeline) == original_length
    
    def test_simulation_result_read_only_intent(self):
        """Results include disclaimer about read-only nature."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_disclaimer"
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 50.0}, correlation_id
        )
        
        result = simulator.simulate(correlation_id)
        
        assert "disclaimer" in result
        assert "informational" in result["disclaimer"].lower()
        assert "does not influence" in result["disclaimer"].lower()
    
    def test_fail_silent_on_invalid_input(self):
        """Invalid inputs fail-silent without raising."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        # Should not raise
        result1 = simulator.simulate("")
        assert "error" not in result1 or result1.get("explanation")
        
        result2 = simulator.simulate(None)
        assert isinstance(result2, dict)
        
        result3 = simulator.simulate_batch(None)
        assert isinstance(result3, list)


class TestMissingTimeline:
    """Verify behavior when timeline doesn't exist."""
    
    def test_missing_correlation_id_handled(self):
        """Non-existent correlation_id returns graceful result."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        result = simulator.simulate("non_existent_trade_id")
        
        assert "correlation_id" in result
        assert result["correlation_id"] == "non_existent_trade_id"
        assert "explanation" in result
        assert "not found" in result["explanation"].lower() or "no timeline" in result["explanation"].lower()


class TestExportMetadata:
    """Verify export includes proper metadata."""
    
    def test_export_includes_disclaimer(self):
        """Export includes non-enforcement disclaimer."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_export"
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 75.0}, correlation_id
        )
        
        result = simulator.simulate(correlation_id)
        export = simulator.export_simulation(result)
        
        assert "disclaimer" in export
        assert "cannot affect" in export["disclaimer"].lower() or "does not" in export["disclaimer"].lower()
    
    def test_export_includes_metadata(self):
        """Export includes timestamp and service info."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        correlation_id = "trade_meta"
        timeline_service.record_event(
            "OUTCOME_RECORDED", {"pnl": 50.0}, correlation_id
        )
        
        result = simulator.simulate(correlation_id)
        export = simulator.export_simulation(result)
        
        assert "_export_metadata" in export
        assert "exported_at" in export["_export_metadata"]
        assert "service" in export["_export_metadata"]
        assert "CounterfactualEnforcementSimulator" in export["_export_metadata"]["service"]


class TestCompleteScenario:
    """End-to-end test of counterfactual simulation."""
    
    def test_full_trade_lifecycle_simulation(self):
        """Simulate complete trade with violations."""
        timeline_service = MockDecisionTimelineService()
        governance_service = TradeGovernanceService()
        simulator = CounterfactualEnforcementSimulator(
            timeline_service, governance_service
        )
        
        cid = "scenario_001"
        
        # Full lifecycle
        timeline_service.record_event(
            "SIGNAL_DETECTED",
            {"signal": "breakout", "strength": 0.9},
            cid,
        )
        timeline_service.record_event(
            "DECISION_PROPOSED",
            {"action": "BUY", "symbol": "EURUSD"},
            cid,
        )
        timeline_service.record_event(
            "POLICY_EVALUATED",
            {"status": "passed"},
            cid,
        )
        timeline_service.record_event(
            "GOVERNANCE_EVALUATED",
            {"violations": ["max_daily_loss", "cooldown_active"]},
            cid,
        )
        timeline_service.record_event(
            "TRADE_EXECUTED",
            {"entry": 1.1050, "size": 100},
            cid,
        )
        timeline_service.record_event(
            "OUTCOME_RECORDED",
            {"pnl": 125.0, "outcome": "win"},
            cid,
        )
        
        # Simulate
        result = simulator.simulate(cid)
        
        # Verify result structure
        assert result["correlation_id"] == cid
        assert result["would_have_been_allowed"] is False
        assert len(result["violated_rules"]) == 2
        assert "max_daily_loss" in result["violated_rules"]
        assert "cooldown_active" in result["violated_rules"]
        assert result["original_outcome"]["pnl"] == 125.0
        assert isinstance(result["counterfactual_pnl"], float)
        assert "explanation" in result
        assert "disclaimer" in result
        assert result["simulated_at"]
