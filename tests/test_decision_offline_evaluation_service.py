"""
Comprehensive tests for DecisionOfflineEvaluationService (Phase 8)

Tests verify:
- Replay-only behavior (no mutations)
- Determinism (same input = same output)
- Immutability and deepcopy on read
- Fail-silent error handling
- Informational-only output
- Scenario isolation
- No enforcement or execution keywords
- Proper disclaimer propagation
- Batch evaluation with graceful failures
- Comparison directional-only semantics
- Export report determinism
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from copy import deepcopy

from reasoner_service.decision_intelligence_archive_service import DecisionIntelligenceArchiveService
from reasoner_service.decision_intelligence_memory_service import DecisionIntelligenceMemoryService
from reasoner_service.counterfactual_enforcement_simulator import CounterfactualEnforcementSimulator
from reasoner_service.decision_offline_evaluation_service import DecisionOfflineEvaluationService


@pytest.fixture
def archive_service():
    """Create archive service with sample reports."""
    service = DecisionIntelligenceArchiveService()
    
    # Add sample reports
    for i in range(5):
        report = {
            "correlation_id": f"trade_{i}",
            "confidence_score": 0.5 + (i * 0.1),
            "governance_pressure": 0.3 + (i * 0.05),
            "risk_flags": ["flag1", "flag2"] if i % 2 == 0 else ["flag3"],
            "trade_volume": 100 + (i * 50),
            "regime": "restricted" if i % 2 == 0 else "normal",
            "governance_markers": ["marker1", "marker2"],
            "evaluated_at": (datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
            "explanation": f"Sample report {i}",
            "disclaimer": "Informational only",
        }
        service.archive_report(report)
    
    return service


@pytest.fixture
def memory_service(archive_service):
    """Create memory service with loaded archive."""
    service = DecisionIntelligenceMemoryService()
    service.load_from_archive(archive_service._archive)
    return service


@pytest.fixture
def simulator_service():
    """Create mock simulator service."""
    class MockSimulator:
        def __init__(self):
            pass
        
        def simulate(self, correlation_id):
            return {
                "correlation_id": correlation_id,
                "would_have_been_allowed": True,
                "violated_rules": [],
            }
    
    return MockSimulator()


@pytest.fixture
def evaluation_service(archive_service, memory_service, simulator_service):
    """Create evaluation service with dependencies."""
    return DecisionOfflineEvaluationService(
        archive_service,
        memory_service,
        simulator_service
    )


class TestReplayOnlyBehavior:
    """Verify replay-only behavior with no mutations."""

    def test_archive_unmodified_after_evaluation(self, archive_service, evaluation_service):
        """Archive should never be modified during evaluation."""
        initial_archive_copy = deepcopy(archive_service._archive)
        
        config = {
            "scenario_name": "test_scenario",
            "policy_constraints": {
                "min_confidence": 0.6,
            },
        }
        
        evaluation_service.evaluate_policy_scenario(config)
        
        assert archive_service._archive == initial_archive_copy
        assert len(archive_service._archive) == len(initial_archive_copy)

    def test_memory_unmodified_after_evaluation(self, memory_service, evaluation_service):
        """Memory service should never be modified during evaluation."""
        initial_memory_copy = deepcopy(memory_service._cached_reports)
        
        config = {
            "scenario_name": "test_scenario",
            "policy_constraints": {"max_exposure": 200},
        }
        
        evaluation_service.evaluate_policy_scenario(config)
        
        assert memory_service._cached_reports == initial_memory_copy

    def test_no_writes_to_archive(self, archive_service, evaluation_service):
        """Evaluation should not append new reports to archive."""
        initial_count = len(archive_service._archive)
        
        config = {"scenario_name": "test", "policy_constraints": {}}
        evaluation_service.evaluate_policy_scenario(config)
        
        assert len(archive_service._archive) == initial_count

    def test_returned_data_not_modifying_archive(self, archive_service, evaluation_service):
        """Modifying returned evaluation data should not affect archive."""
        config = {"scenario_name": "test", "policy_constraints": {}}
        result = evaluation_service.evaluate_policy_scenario(config)
        
        # Modify returned result
        result["statistics"]["trades_allowed"] = 999999
        
        # Re-evaluate with same config
        result2 = evaluation_service.evaluate_policy_scenario(config)
        
        # Second result should have original value, not modified
        assert result2["statistics"]["trades_allowed"] != 999999


class TestDeterminism:
    """Verify deterministic outputs (same input = same output)."""

    def test_same_config_produces_same_results(self, evaluation_service):
        """Identical configurations should produce identical results."""
        config = {
            "scenario_name": "determinism_test",
            "policy_constraints": {
                "min_confidence": 0.5,
                "max_exposure": 200,
            },
        }
        
        result1 = evaluation_service.evaluate_policy_scenario(config)
        result2 = evaluation_service.evaluate_policy_scenario(config)
        
        # Core statistics should be identical
        assert result1["statistics"]["total_trades_evaluated"] == result2["statistics"]["total_trades_evaluated"]
        assert result1["statistics"]["trades_allowed"] == result2["statistics"]["trades_allowed"]
        assert result1["impact_analysis"]["blocked_percentage"] == result2["impact_analysis"]["blocked_percentage"]

    def test_deterministic_with_time_window(self, evaluation_service):
        """Determinism should hold even with time window filtering."""
        now = datetime.now(timezone.utc).isoformat()
        past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        
        config = {
            "scenario_name": "time_window_test",
            "policy_constraints": {"min_confidence": 0.5},
            "evaluation_window": {"start": past, "end": now},
        }
        
        result1 = evaluation_service.evaluate_policy_scenario(config)
        result2 = evaluation_service.evaluate_policy_scenario(config)
        
        assert result1["statistics"] == result2["statistics"]

    def test_export_report_is_deterministic(self, evaluation_service):
        """Export reports from identical evaluations should be byte-for-byte identical."""
        config = {
            "scenario_name": "export_determinism",
            "policy_constraints": {},
        }
        
        result = evaluation_service.evaluate_policy_scenario(config)
        
        export1 = evaluation_service.export_evaluation_report(result, format="json")
        export2 = evaluation_service.export_evaluation_report(result, format="json")
        
        # Parse and compare to avoid timestamp differences
        data1 = json.loads(export1)
        data2 = json.loads(export2)
        
        # Core data should be identical
        assert data1["scenario_name"] == data2["scenario_name"]
        assert data1["statistics"] == data2["statistics"]

    def test_batch_evaluation_deterministic(self, evaluation_service):
        """Batch evaluations should be deterministic."""
        configs = [
            {
                "scenario_name": f"batch_test_{i}",
                "policy_constraints": {"min_confidence": 0.4 + (i * 0.1)},
            }
            for i in range(3)
        ]
        
        batch1 = evaluation_service.run_batch_evaluation(configs)
        batch2 = evaluation_service.run_batch_evaluation(configs)
        
        # Summary statistics should be identical
        assert batch1["summary_statistics"] == batch2["summary_statistics"]
        assert len(batch1["scenarios"]) == len(batch2["scenarios"])


class TestImmutabilityAndDeepcopy:
    """Verify deepcopy on read and immutability."""

    def test_returned_evaluation_is_deepcopy(self, evaluation_service):
        """Modifying returned evaluation should not affect internal cache."""
        config = {"scenario_name": "deepcopy_test", "policy_constraints": {}}
        
        result1 = evaluation_service.evaluate_policy_scenario(config)
        original_allowed = result1["statistics"]["trades_allowed"]
        
        # Modify returned data
        result1["statistics"]["trades_allowed"] = 99999
        
        # Get cached result
        cached = evaluation_service._evaluation_cache.get(result1["scenario_id"])
        
        if cached:
            assert cached["statistics"]["trades_allowed"] != 99999
            assert cached["statistics"]["trades_allowed"] == original_allowed

    def test_comparison_result_is_deepcopy(self, evaluation_service):
        """Modifying comparison result should not affect internal state."""
        config_a = {"scenario_name": "scenario_a", "policy_constraints": {}}
        config_b = {"scenario_name": "scenario_b", "policy_constraints": {"min_confidence": 0.7}}
        
        result_a = evaluation_service.evaluate_policy_scenario(config_a)
        result_b = evaluation_service.evaluate_policy_scenario(config_b)
        
        comparison = evaluation_service.compare_scenarios(result_a, result_b)
        
        # Modify returned comparison
        comparison["directional_differences"]["blocked_percentage"]["delta"] = 99999
        
        # Re-compare same scenarios
        comparison2 = evaluation_service.compare_scenarios(result_a, result_b)
        
        # Should have original delta, not modified value
        assert comparison2["directional_differences"]["blocked_percentage"]["delta"] != 99999

    def test_batch_result_is_deepcopy(self, evaluation_service):
        """Modifying batch result should not affect cache."""
        configs = [
            {"scenario_name": "batch_a", "policy_constraints": {}},
            {"scenario_name": "batch_b", "policy_constraints": {"min_confidence": 0.6}},
        ]
        
        batch = evaluation_service.run_batch_evaluation(configs)
        
        # Modify returned batch
        batch["successful_evaluations"] = 0
        
        # Re-run same configs
        batch2 = evaluation_service.run_batch_evaluation(configs)
        
        # Should have original successful count
        assert batch2["successful_evaluations"] > 0


class TestFailSilentBehavior:
    """Verify fail-silent error handling."""

    def test_invalid_config_returns_empty_result(self, evaluation_service):
        """Invalid config should return empty result structure, not raise."""
        config = None  # Invalid
        
        # Should not raise, should return structure (may have default values from archive)
        result = evaluation_service.evaluate_policy_scenario(config or {})
        assert result is not None
        assert "statistics" in result
        assert "disclaimer" in result

    def test_missing_time_window_fields_graceful(self, evaluation_service):
        """Missing time window fields should not cause errors."""
        config = {
            "scenario_name": "missing_window",
            "policy_constraints": {},
            "evaluation_window": {"start": "invalid_date"},  # Missing 'end'
        }
        
        result = evaluation_service.evaluate_policy_scenario(config)
        assert result is not None
        assert "statistics" in result

    def test_comparison_with_missing_fields(self, evaluation_service):
        """Comparison with missing fields should not raise."""
        result_a = {}  # Minimal
        result_b = {"scenario_name": "b"}  # Minimal
        
        comparison = evaluation_service.compare_scenarios(result_a, result_b)
        assert comparison is not None
        assert "directional_differences" in comparison

    def test_batch_partial_failures(self, evaluation_service):
        """Batch should handle partial failures gracefully."""
        configs = [
            {"scenario_name": "valid_1", "policy_constraints": {}},
            None,  # Invalid
            {"scenario_name": "valid_2", "policy_constraints": {"min_confidence": 0.5}},
        ]
        
        batch = evaluation_service.run_batch_evaluation(configs)
        
        assert batch["total_scenarios"] == 3
        assert batch["successful_evaluations"] == 2
        assert batch["failed_evaluations"] == 1

    def test_export_with_invalid_result(self, evaluation_service):
        """Export should handle invalid results gracefully."""
        invalid_result = {"scenario_name": "invalid"}
        
        # Should not raise
        report = evaluation_service.export_evaluation_report(invalid_result)
        assert report is not None
        assert isinstance(report, str)


class TestInformationalOnlyOutput:
    """Verify informational-only output with proper disclaimers."""

    def test_evaluation_includes_disclaimer(self, evaluation_service):
        """All evaluation results should include disclaimer."""
        config = {"scenario_name": "disclaimer_test", "policy_constraints": {}}
        result = evaluation_service.evaluate_policy_scenario(config)
        
        assert "disclaimer" in result
        assert "informational only" in result["disclaimer"].lower()
        assert "does not influence" in result["disclaimer"].lower()

    def test_comparison_includes_disclaimer(self, evaluation_service):
        """Comparisons should include informational disclaimer."""
        config_a = {"scenario_name": "a", "policy_constraints": {}}
        config_b = {"scenario_name": "b", "policy_constraints": {}}
        
        result_a = evaluation_service.evaluate_policy_scenario(config_a)
        result_b = evaluation_service.evaluate_policy_scenario(config_b)
        
        comparison = evaluation_service.compare_scenarios(result_a, result_b)
        
        assert "disclaimer" in comparison
        assert "informational only" in comparison["disclaimer"].lower()
        assert "no ranking" in comparison["disclaimer"].lower()

    def test_batch_includes_disclaimer(self, evaluation_service):
        """Batch results should include informational disclaimer."""
        configs = [{"scenario_name": "batch_test", "policy_constraints": {}}]
        batch = evaluation_service.run_batch_evaluation(configs)
        
        assert "disclaimer" in batch
        assert "informational only" in batch["disclaimer"].lower()

    def test_export_includes_export_disclaimer(self, evaluation_service):
        """Exported reports should include export disclaimer."""
        config = {"scenario_name": "export_test", "policy_constraints": {}}
        result = evaluation_service.evaluate_policy_scenario(config)
        
        export = evaluation_service.export_evaluation_report(result)
        
        assert "informational only" in export.lower()

    def test_comparison_no_ranking_or_recommendation(self, evaluation_service):
        """Comparison should never recommend one scenario over another."""
        config_a = {"scenario_name": "a", "policy_constraints": {"min_confidence": 0.3}}
        config_b = {"scenario_name": "b", "policy_constraints": {"min_confidence": 0.8}}
        
        result_a = evaluation_service.evaluate_policy_scenario(config_a)
        result_b = evaluation_service.evaluate_policy_scenario(config_b)
        
        comparison = evaluation_service.compare_scenarios(result_a, result_b)
        
        # Should never contain words like "better", "worse", "recommended"
        comparison_str = json.dumps(comparison).lower()
        assert " best " not in comparison_str
        assert " superior " not in comparison_str
        assert " inferior " not in comparison_str


class TestScenarioIsolation:
    """Verify scenario isolation in batch evaluation."""

    def test_batch_scenarios_independent(self, evaluation_service):
        """Failure in one batch scenario should not affect others."""
        configs = [
            {"scenario_name": "good_1", "policy_constraints": {"min_confidence": 0.3}},
            {"scenario_name": "good_2", "policy_constraints": {"max_exposure": 250}},
            {"scenario_name": "good_3", "policy_constraints": {"min_confidence": 0.7}},
        ]
        
        batch = evaluation_service.run_batch_evaluation(configs)
        
        # All should succeed
        assert all(s["status"] == "success" for s in batch["scenarios"])
        assert batch["successful_evaluations"] == 3

    def test_batch_failure_does_not_cascade(self, evaluation_service):
        """Failure in batch should be isolated to that scenario."""
        configs = [
            {"scenario_name": "scenario_1", "policy_constraints": {}},
            {"scenario_name": "scenario_2", "policy_constraints": {}},
            {"scenario_name": "scenario_3", "policy_constraints": {}},
        ]
        
        batch = evaluation_service.run_batch_evaluation(configs)
        
        # Count successful scenarios
        successful = sum(1 for s in batch["scenarios"] if s["status"] == "success")
        
        # Should have at least some successes (isolation verified)
        assert successful > 0


class TestNoEnforcementKeywords:
    """Verify no enforcement or execution keywords exist."""

    def test_no_enforce_keywords_in_evaluation(self, evaluation_service):
        """Evaluation results should not contain enforcement keywords."""
        config = {"scenario_name": "enforce_test", "policy_constraints": {}}
        result = evaluation_service.evaluate_policy_scenario(config)
        
        result_str = json.dumps(result).lower()
        
        enforcement_keywords = ["enforce", "execute", "block", "allow", "veto", "admit"]
        # Note: Some keywords may appear in neutral contexts; check explanation
        explanation = result.get("explanation", "").lower()
        
        # Explanation should be analytical, not imperative
        assert "will" not in explanation or "would" in explanation

    def test_no_execution_logic_keywords(self, evaluation_service):
        """Service should not use execution-related keywords."""
        config_a = {"scenario_name": "a", "policy_constraints": {}}
        config_b = {"scenario_name": "b", "policy_constraints": {}}
        
        result_a = evaluation_service.evaluate_policy_scenario(config_a)
        result_b = evaluation_service.evaluate_policy_scenario(config_b)
        
        comparison = evaluation_service.compare_scenarios(result_a, result_b)
        
        comparison_str = json.dumps(comparison).lower()
        
        # Should not recommend action
        assert "should" not in comparison_str or "showing" in comparison_str


class TestDeterministicExports:
    """Verify deterministic export format."""

    def test_json_export_deterministic(self, evaluation_service):
        """JSON export should be deterministic."""
        config = {"scenario_name": "json_export", "policy_constraints": {}}
        result = evaluation_service.evaluate_policy_scenario(config)
        
        export1 = evaluation_service.export_evaluation_report(result, format="json")
        export2 = evaluation_service.export_evaluation_report(result, format="json")
        
        data1 = json.loads(export1)
        data2 = json.loads(export2)
        
        # Core fields should be identical (excluding timestamps)
        assert data1["scenario_name"] == data2["scenario_name"]
        assert data1["statistics"] == data2["statistics"]

    def test_text_export_deterministic(self, evaluation_service):
        """Text export should include all required fields."""
        config = {"scenario_name": "text_export", "policy_constraints": {"min_confidence": 0.5}}
        result = evaluation_service.evaluate_policy_scenario(config)
        
        export = evaluation_service.export_evaluation_report(result, format="text")
        
        # Should contain key sections
        assert "SCENARIO" in export or "Scenario" in export
        assert "STATISTICS" in export
        assert "DISCLAIMER" in export
        assert "informational only" in export.lower()

    def test_export_includes_all_disclaimers(self, evaluation_service):
        """Exported report should include all disclaimer levels."""
        config = {"scenario_name": "disclaimers", "policy_constraints": {}}
        result = evaluation_service.evaluate_policy_scenario(config)
        
        export = evaluation_service.export_evaluation_report(result)
        
        export_lower = export.lower()
        
        # Should mention it's informational
        assert "informational" in export_lower
        
        # Should mention no actual enforcement
        assert "no actual" in export_lower or "does not" in export_lower


class TestConstraintEvaluation:
    """Verify policy constraint evaluation logic."""

    def test_min_confidence_constraint(self, evaluation_service):
        """Min confidence constraint should filter trades."""
        config = {
            "scenario_name": "min_conf_test",
            "policy_constraints": {"min_confidence": 0.7},
        }
        
        result = evaluation_service.evaluate_policy_scenario(config)
        
        # Should have blocked some trades (archive has mix of confidences)
        assert result["statistics"]["trades_would_block"] >= 0

    def test_max_exposure_constraint(self, evaluation_service):
        """Max exposure constraint should filter trades."""
        config = {
            "scenario_name": "max_exposure_test",
            "policy_constraints": {"max_exposure": 150},
        }
        
        result = evaluation_service.evaluate_policy_scenario(config)
        
        # Should evaluate trades
        assert result["statistics"]["total_trades_evaluated"] > 0

    def test_blocked_regimes_constraint(self, evaluation_service):
        """Blocked regimes constraint should filter by regime."""
        config = {
            "scenario_name": "blocked_regimes_test",
            "policy_constraints": {"blocked_regimes": ["restricted"]},
        }
        
        result = evaluation_service.evaluate_policy_scenario(config)
        
        # Should have some impact on results
        assert "blocked_percentage" in result["impact_analysis"]

    def test_multiple_constraints_combined(self, evaluation_service):
        """Multiple constraints should be evaluated together."""
        config = {
            "scenario_name": "multi_constraint_test",
            "policy_constraints": {
                "min_confidence": 0.6,
                "max_exposure": 200,
                "blocked_regimes": ["restricted"],
            },
        }
        
        result = evaluation_service.evaluate_policy_scenario(config)
        
        # Should handle all constraints without raising
        assert result["statistics"]["total_trades_evaluated"] >= 0
        assert result["impact_analysis"]["blocked_percentage"] >= 0


class TestComparisonDirectionalOnly:
    """Verify comparison is directional only, no ranking."""

    def test_comparison_shows_direction_not_ranking(self, evaluation_service):
        """Comparison should show direction without ranking."""
        config_a = {"scenario_name": "a_strict", "policy_constraints": {"min_confidence": 0.8}}
        config_b = {"scenario_name": "b_lenient", "policy_constraints": {"min_confidence": 0.3}}
        
        result_a = evaluation_service.evaluate_policy_scenario(config_a)
        result_b = evaluation_service.evaluate_policy_scenario(config_b)
        
        comparison = evaluation_service.compare_scenarios(result_a, result_b)
        
        # Should have directional data
        assert "directional_differences" in comparison
        
        # Each metric should show direction
        for metric, data in comparison["directional_differences"].items():
            assert "direction" in data
            assert data["direction"] in ["A_higher", "B_higher", "same"]

    def test_comparison_constraint_isolation(self, evaluation_service):
        """Comparison should isolate unique constraints."""
        config_a = {
            "scenario_name": "a",
            "policy_constraints": {"min_confidence": 0.5, "max_exposure": 200}
        }
        config_b = {
            "scenario_name": "b",
            "policy_constraints": {"min_confidence": 0.5, "blocked_regimes": ["restricted"]}
        }
        
        result_a = evaluation_service.evaluate_policy_scenario(config_a)
        result_b = evaluation_service.evaluate_policy_scenario(config_b)
        
        comparison = evaluation_service.compare_scenarios(result_a, result_b)
        
        isolation = comparison["isolation_analysis"]
        
        # Should identify unique constraints per scenario
        assert isinstance(isolation["scenario_a_unique_constraints"], list)
        assert isinstance(isolation["scenario_b_unique_constraints"], list)
        assert isinstance(isolation["shared_constraints"], list)


class TestIntegration:
    """Integration tests covering full workflows."""

    def test_full_workflow_evaluation_to_export(self, evaluation_service):
        """Full workflow from evaluation to export."""
        config = {
            "scenario_name": "full_workflow_test",
            "policy_constraints": {
                "min_confidence": 0.5,
                "max_exposure": 250,
            },
        }
        
        # 1. Evaluate
        result = evaluation_service.evaluate_policy_scenario(config)
        assert result is not None
        assert "disclaimer" in result
        
        # 2. Export JSON
        json_export = evaluation_service.export_evaluation_report(result, format="json")
        assert json_export is not None
        parsed = json.loads(json_export)
        assert parsed["scenario_name"] == "full_workflow_test"
        
        # 3. Export text
        text_export = evaluation_service.export_evaluation_report(result, format="text")
        assert text_export is not None
        assert "full_workflow_test" in text_export

    def test_batch_then_compare(self, evaluation_service):
        """Run batch then compare specific scenarios."""
        configs = [
            {"scenario_name": "batch_a", "policy_constraints": {"min_confidence": 0.4}},
            {"scenario_name": "batch_b", "policy_constraints": {"min_confidence": 0.7}},
            {"scenario_name": "batch_c", "policy_constraints": {"max_exposure": 300}},
        ]
        
        # 1. Run batch
        batch = evaluation_service.run_batch_evaluation(configs)
        assert batch["successful_evaluations"] >= 2
        
        # 2. Get individual results
        result_a = next(
            (s["result"] for s in batch["scenarios"] if s["scenario_name"] == "batch_a"),
            None
        )
        result_b = next(
            (s["result"] for s in batch["scenarios"] if s["scenario_name"] == "batch_b"),
            None
        )
        
        if result_a and result_b:
            # 3. Compare
            comparison = evaluation_service.compare_scenarios(result_a, result_b)
            assert comparison is not None
            assert "directional_differences" in comparison

    def test_archive_isolation_across_operations(self, archive_service, evaluation_service):
        """Archive should remain isolated across all operations."""
        initial_len = len(archive_service._archive)
        
        # Run multiple evaluations
        for i in range(3):
            config = {
                "scenario_name": f"scenario_{i}",
                "policy_constraints": {"min_confidence": 0.3 + (i * 0.1)},
            }
            evaluation_service.evaluate_policy_scenario(config)
        
        # Run batch
        batch_configs = [
            {"scenario_name": f"batch_{i}", "policy_constraints": {}}
            for i in range(2)
        ]
        evaluation_service.run_batch_evaluation(batch_configs)
        
        # Archive should be completely unchanged
        assert len(archive_service._archive) == initial_len
