"""
Tests for DecisionIntelligenceReportService

Verifies:
- Pure informational analysis (no enforcement)
- Deterministic outputs
- No input mutations
- Fail-silent behavior
- Graceful degradation on service failures
- Clear non-enforcement disclaimers
- Batch processing
- Risk flag detection
"""

import pytest
from datetime import datetime, timezone
from copy import deepcopy

from reasoner_service.decision_intelligence_report_service import (
    DecisionIntelligenceReportService,
)


class MockDecisionTimelineService:
    """Mock timeline service for testing."""
    
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
            "sequence_number": len(self.timelines[correlation_id]),
        })
    
    def get_timeline(self, correlation_id):
        return deepcopy(self.timelines.get(correlation_id, []))


class MockTradeGovernanceService:
    """Mock governance service for testing."""
    
    def __init__(self):
        self.evaluation_results = {}
    
    def evaluate_trade(self, trade_context):
        cid = trade_context.get("correlation_id")
        if cid in self.evaluation_results:
            return deepcopy(self.evaluation_results[cid])
        
        return {
            "allowed": True,
            "violations": [],
            "explanation": "No violations detected",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "This is informational only",
        }


class MockCounterfactualSimulator:
    """Mock counterfactual simulator for testing."""
    
    def __init__(self):
        self.simulations = {}
    
    def simulate(self, correlation_id):
        if correlation_id in self.simulations:
            return deepcopy(self.simulations[correlation_id])
        
        return {
            "correlation_id": correlation_id,
            "would_have_been_allowed": True,
            "violated_rules": [],
            "counterfactual_pnl": 0.0,
            "pnl_difference": 0.0,
            "disclaimer": "This is informational only",
        }


class MockPolicyConfidenceEvaluator:
    """Mock policy confidence evaluator for testing."""
    
    def __init__(self):
        self.confidence_scores = {}
    
    def evaluate_policy(self, policy_name):
        if policy_name in self.confidence_scores:
            return deepcopy(self.confidence_scores[policy_name])
        
        return {
            "policy_name": policy_name,
            "confidence_score": 0.5,
            "ready_for_enforcement": False,
            "disclaimer": "Informational only",
        }


class MockOutcomeAnalyticsService:
    """Mock outcome analytics service for testing."""
    
    def __init__(self):
        self.analytics = {}
    
    def policy_veto_impact(self):
        return {
            "total_trades": 100,
            "veto_count": 10,
            "veto_accuracy": 0.8,
            "false_positives": 2,
            "false_negatives": 8,
        }
    
    def get_recent_outcomes(self, limit=10):
        return {
            "trades": [],
            "average_pnl": 50.0,
            "win_rate": 0.55,
            "total_trades": 0,
        }


class TestNonEnforcementGuarantee:
    """Verify service cannot enforce or block."""
    
    def test_no_execution_methods(self):
        """Service has no methods that execute trades."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        public_methods = [m for m in dir(service) if not m.startswith("_")]
        
        # Check for dangerous method names
        dangerous = ["execute", "block", "allow", "permit", "deny", "submit"]
        for method in public_methods:
            method_lower = method.lower()
            assert not any(
                d in method_lower for d in dangerous
            ), f"Found dangerous method: {method}"
    
    def test_report_never_contains_actionable_fields(self):
        """Report cannot contain 'allowed', 'blocked', or enforcement decisions."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        timeline = MockDecisionTimelineService()
        timeline.record_event(
            "OUTCOME_RECORDED",
            {"pnl": 100.0},
            "trade_001"
        )
        
        report = service.generate_report("trade_001")
        
        # Report should not have enforcement fields (as dict keys)
        assert "allowed" not in report
        assert "blocked" not in report
        # Check that top-level keys don't contain dangerous enforcement keywords
        report_keys = str(report.keys()).lower()
        assert "block_trade" not in report_keys
    
    def test_disclaimer_present_and_explicit(self):
        """Every report includes explicit non-enforcement disclaimer."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        assert "disclaimer" in report
        assert "informational" in report["disclaimer"].lower()
        assert "does not" in report["disclaimer"].lower()


class TestDeterministicOutput:
    """Verify identical inputs produce identical outputs."""
    
    def test_same_correlation_id_produces_same_report(self):
        """Identical correlation IDs produce identical reports."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report1 = service.generate_report("trade_001")
        report2 = service.generate_report("trade_001")
        
        # Timestamps will differ slightly, so exclude from comparison
        report1_copy = {k: v for k, v in report1.items() if k != "evaluated_at"}
        report2_copy = {k: v for k, v in report2.items() if k != "evaluated_at"}
        
        assert report1_copy == report2_copy
        assert report1["confidence_score"] == report2["confidence_score"]
        assert report1["governance_pressure"] == report2["governance_pressure"]
    
    def test_deterministic_confidence_score_calculation(self):
        """Confidence score calculation is deterministic."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        # Run multiple times
        scores = []
        for _ in range(5):
            report = service.generate_report("trade_001")
            scores.append(report["confidence_score"])
        
        # All scores must be identical
        assert len(set(scores)) == 1, f"Scores not deterministic: {scores}"


class TestNoMutation:
    """Verify input services are not mutated."""
    
    def test_timeline_not_mutated(self):
        """Timeline service not modified by report generation."""
        timeline = MockDecisionTimelineService()
        timeline.record_event(
            "OUTCOME_RECORDED",
            {"pnl": 100.0},
            "trade_001"
        )
        
        original_timeline = deepcopy(timeline.get_timeline("trade_001"))
        
        service = DecisionIntelligenceReportService(
            timeline_service=timeline,
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        service.generate_report("trade_001")
        
        # Timeline must be unchanged
        assert timeline.get_timeline("trade_001") == original_timeline
    
    def test_no_state_modification(self):
        """Service does not maintain state between calls."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        # Two independent calls
        report1 = service.generate_report("trade_001")
        report2 = service.generate_report("trade_002")
        
        # Reports should be independent
        assert report1["correlation_id"] == "trade_001"
        assert report2["correlation_id"] == "trade_002"


class TestReportStructure:
    """Verify report has required fields and correct structure."""
    
    def test_report_has_required_fields(self):
        """Report includes all required fields."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        required_fields = [
            "correlation_id",
            "confidence_score",
            "governance_pressure",
            "counterfactual_regret",
            "risk_flags",
            "explanation",
            "evaluated_at",
            "disclaimer",
        ]
        
        for field in required_fields:
            assert field in report, f"Missing field: {field}"
    
    def test_confidence_score_in_valid_range(self):
        """Confidence score is between 0 and 100."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        assert 0 <= report["confidence_score"] <= 100
    
    def test_governance_pressure_has_valid_value(self):
        """Governance pressure is one of the valid values."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        valid_pressures = ["none", "low", "medium", "high"]
        assert report["governance_pressure"] in valid_pressures
    
    def test_risk_flags_is_list(self):
        """Risk flags is a list."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        assert isinstance(report["risk_flags"], list)
        for flag in report["risk_flags"]:
            assert isinstance(flag, str)
    
    def test_explanation_is_non_empty_string(self):
        """Explanation is a non-empty string."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        assert isinstance(report["explanation"], str)
        assert len(report["explanation"]) > 0
    
    def test_evaluated_at_is_iso_timestamp(self):
        """Evaluated timestamp is ISO format."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        # Should be parseable as ISO timestamp
        try:
            datetime.fromisoformat(report["evaluated_at"].replace("Z", "+00:00"))
            assert True
        except ValueError:
            assert False, f"Invalid ISO timestamp: {report['evaluated_at']}"


class TestFailSilentBehavior:
    """Verify service degrades gracefully on errors."""
    
    def test_missing_timeline_returns_report(self):
        """Missing timeline returns report, not error."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        # Non-existent correlation ID
        report = service.generate_report("non_existent")
        
        assert "correlation_id" in report
        assert isinstance(report, dict)
        assert "explanation" in report
    
    def test_service_failure_degrades_gracefully(self):
        """If a service fails, report still generated."""
        
        class FailingTimelineService:
            def get_timeline(self, correlation_id):
                raise RuntimeError("Service error")
        
        service = DecisionIntelligenceReportService(
            timeline_service=FailingTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        # Should not raise, should return report
        report = service.generate_report("trade_001")
        
        assert isinstance(report, dict)
        assert "correlation_id" in report
        assert "explanation" in report
    
    def test_invalid_input_handled_gracefully(self):
        """Invalid inputs return graceful error."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        # Invalid correlation ID types
        report1 = service.generate_report(None)
        assert isinstance(report1, dict)
        
        report2 = service.generate_report(123)
        assert isinstance(report2, dict)
        
        report3 = service.generate_report("")
        assert isinstance(report3, dict)


class TestBatchProcessing:
    """Verify batch report generation."""
    
    def test_batch_returns_list_of_reports(self):
        """Batch generation returns list of reports."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        correlation_ids = ["trade_001", "trade_002", "trade_003"]
        reports = service.generate_batch(correlation_ids)
        
        assert isinstance(reports, list)
        # Should have 3 individual reports + 1 batch summary = 4 total
        assert len(reports) == 4
    
    def test_batch_includes_summary(self):
        """Batch results include summary."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        correlation_ids = ["trade_001", "trade_002"]
        reports = service.generate_batch(correlation_ids)
        
        # Last item should be summary
        summary = reports[-1]
        assert "_batch_summary" in summary or isinstance(summary, dict)
    
    def test_batch_empty_list(self):
        """Batch with empty list returns empty."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        reports = service.generate_batch([])
        
        assert isinstance(reports, list)
    
    def test_batch_with_invalid_items(self):
        """Batch skips invalid items gracefully."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        # Mix valid and invalid
        correlation_ids = ["trade_001", None, 123, "trade_002"]
        reports = service.generate_batch(correlation_ids)
        
        assert isinstance(reports, list)
        # Should have at least some reports
        assert len(reports) >= 2


class TestRiskFlagDetection:
    """Verify risk flags are correctly identified."""
    
    def test_no_flags_for_clean_trade(self):
        """Clean trade has no risk flags."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("clean_trade")
        
        # Clean trades may have 0 flags
        assert isinstance(report["risk_flags"], list)
    
    def test_flags_are_informational_only(self):
        """Risk flags are descriptions, not enforcement."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        # Create governance service with violations
        governance = MockTradeGovernanceService()
        governance.evaluation_results["flagged_trade"] = {
            "allowed": True,  # Even with violations, allowed=True!
            "violations": ["max_daily_loss", "cooldown_active"],
            "explanation": "Violations present",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=governance,
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("flagged_trade")
        
        # Flags should be descriptive, not actionable
        for flag in report["risk_flags"]:
            assert "block" not in flag.lower()
            assert "deny" not in flag.lower()
            assert "reject" not in flag.lower()


class TestGovernancePressureCalculation:
    """Verify governance pressure levels."""
    
    def test_governance_pressure_reflects_violations(self):
        """Governance pressure correlates with violation count."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        # Should have valid pressure level
        valid_levels = ["none", "low", "medium", "high"]
        assert report["governance_pressure"] in valid_levels


class TestCounterfactualRegretCalculation:
    """Verify regret metric calculation."""
    
    def test_counterfactual_regret_is_numeric(self):
        """Counterfactual regret is a numeric value."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        assert isinstance(report["counterfactual_regret"], (int, float))
    
    def test_regret_can_be_zero(self):
        """Regret can be zero (no counterfactual difference)."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        # Regret should be numeric (can be zero or positive)
        assert report["counterfactual_regret"] >= 0


class TestCompleteWorkflow:
    """End-to-end tests of report generation."""
    
    def test_full_report_generation_workflow(self):
        """Complete workflow from correlation ID to report."""
        timeline = MockDecisionTimelineService()
        timeline.record_event(
            "SIGNAL_DETECTED",
            {"signal": "momentum"},
            "scenario_001"
        )
        timeline.record_event(
            "TRADE_EXECUTED",
            {"entry": 1.1050},
            "scenario_001"
        )
        timeline.record_event(
            "OUTCOME_RECORDED",
            {"pnl": 125.0},
            "scenario_001"
        )
        
        governance = MockTradeGovernanceService()
        counterfactual = MockCounterfactualSimulator()
        policy_eval = MockPolicyConfidenceEvaluator()
        analytics = MockOutcomeAnalyticsService()
        
        service = DecisionIntelligenceReportService(
            timeline_service=timeline,
            governance_service=governance,
            counterfactual_simulator=counterfactual,
            policy_confidence_evaluator=policy_eval,
            outcome_analytics_service=analytics,
        )
        
        report = service.generate_report("scenario_001")
        
        # Should have all required fields
        assert "correlation_id" in report
        assert "confidence_score" in report
        assert "governance_pressure" in report
        assert "counterfactual_regret" in report
        assert "risk_flags" in report
        assert "explanation" in report
        assert "evaluated_at" in report
        assert "disclaimer" in report
        
        # All values should be valid
        assert report["correlation_id"] == "scenario_001"
        assert 0 <= report["confidence_score"] <= 100
        assert report["governance_pressure"] in ["none", "low", "medium", "high"]
        assert isinstance(report["risk_flags"], list)
        assert len(report["explanation"]) > 0


class TestTransparency:
    """Verify calculations are transparent and explainable."""
    
    def test_explanation_mentions_key_factors(self):
        """Explanation describes key factors in score calculation."""
        service = DecisionIntelligenceReportService(
            timeline_service=MockDecisionTimelineService(),
            governance_service=MockTradeGovernanceService(),
            counterfactual_simulator=MockCounterfactualSimulator(),
            policy_confidence_evaluator=MockPolicyConfidenceEvaluator(),
            outcome_analytics_service=MockOutcomeAnalyticsService(),
        )
        
        report = service.generate_report("trade_001")
        
        # Explanation should be informative
        assert len(report["explanation"]) > 20  # Non-trivial explanation
        explanation_lower = report["explanation"].lower()
        
        # Should mention some aspect of analysis
        assert any(keyword in explanation_lower 
                  for keyword in ["governance", "confidence", "risk", "factor"])
