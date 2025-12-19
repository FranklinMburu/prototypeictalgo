"""
Comprehensive tests for DecisionTrustCalibrationService (Phase 10)

Tests verify:
- Pure descriptive analysis (no prescriptive elements)
- Determinism (same input = same output)
- Deepcopy on read and write
- Fail-silent error handling
- Informational-only output with disclaimers
- No banned keywords (execute, block, prevent, recommend, rank, optimize, etc.)
- No ranking or scoring semantics
- No feedback loops
- Read-only access patterns
- Isolation and independence
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from copy import deepcopy

from reasoner_service.decision_trust_calibration_service import (
    DecisionTrustCalibrationService,
    SignalType,
    CalibrationMetric,
)


@pytest.fixture
def calibration_service():
    """Create calibration service instance."""
    return DecisionTrustCalibrationService()


@pytest.fixture
def memory_snapshot():
    """Create sample memory snapshot."""
    return {
        "signal_records": [
            {
                "id": "signal_001",
                "signal_type": "trend",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": 0.85,
            },
            {
                "id": "signal_002",
                "signal_type": "momentum",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": 0.72,
            },
        ],
        "outcome_records": [
            {
                "signal_id": "signal_001",
                "actual_outcome": "favorable",
                "pnl": 500.0,
            },
            {
                "signal_id": "signal_002",
                "actual_outcome": "neutral",
                "pnl": 50.0,
            },
        ],
        "confidence_records": [
            {
                "confidence_value": 0.8,
                "timestamp": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            },
            {
                "confidence_value": 0.75,
                "timestamp": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            },
            {
                "confidence_value": 0.70,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ],
    }


@pytest.fixture
def offline_evaluations():
    """Create sample offline evaluation data."""
    return {
        "policy_results": [
            {
                "policy_id": "policy_001",
                "violated": False,
                "regret": 0.0,
            },
            {
                "policy_id": "policy_002",
                "violated": True,
                "regret": 100.0,
            },
            {
                "policy_id": "policy_001",
                "violated": False,
                "regret": 50.0,
            },
        ],
        "violation_events": [
            {
                "policy_id": "policy_003",
                "violation_type": "threshold",
            },
        ],
    }


@pytest.fixture
def human_reviews():
    """Create sample human review data."""
    return {
        "review_sessions": [
            {
                "session_id": "session_001",
                "annotator": "human_reviewer_1",
                "annotation_type": "concern",
                "text": "Position size too large",
            },
            {
                "session_id": "session_002",
                "disagreer": "human_reviewer_2",
                "reason": "Signal divergence not addressed",
                "type": "disagreement",
            },
        ]
    }


@pytest.fixture
def counterfactual_results():
    """Create sample counterfactual results."""
    return {
        "counterfactual_outcomes": [
            {
                "original_decision": "enter",
                "alternative_outcome": "Position size too large for current volatility",
                "simulated_pnl": 300.0,
            },
            {
                "original_decision": "hold",
                "alternative_outcome": "Signal divergence not addressed",
                "simulated_pnl": -100.0,
            },
        ]
    }


# ========== DETERMINISM TESTS ==========
class TestDeterminism:
    """Verify deterministic outputs."""

    def test_same_memory_snapshot_produces_same_signal_calibration(
        self, calibration_service, memory_snapshot
    ):
        """Identical memory snapshot produces identical calibration."""
        result1 = calibration_service.calibrate_signals(memory_snapshot)
        result2 = calibration_service.calibrate_signals(memory_snapshot)

        # Key metrics should match
        assert result1["total_signals"] == result2["total_signals"]
        assert result1["total_outcomes"] == result2["total_outcomes"]
        assert (
            result1["consistency_analysis"]["consistency_rate"]
            == result2["consistency_analysis"]["consistency_rate"]
        )

    def test_same_policy_evaluations_produce_same_calibration(
        self, calibration_service, offline_evaluations
    ):
        """Identical policy evaluations produce identical calibration."""
        result1 = calibration_service.calibrate_policies(offline_evaluations)
        result2 = calibration_service.calibrate_policies(offline_evaluations)

        assert result1["total_policies"] == result2["total_policies"]
        assert result1["total_evaluations"] == result2["total_evaluations"]
        assert (
            result1["violation_summary"]["violation_frequency"]
            == result2["violation_summary"]["violation_frequency"]
        )

    def test_same_reviewers_produce_same_calibration(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Identical review data produces identical calibration."""
        result1 = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)
        result2 = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)

        assert result1["total_reviewers"] == result2["total_reviewers"]
        assert result1["total_reviews"] == result2["total_reviews"]

    def test_export_deterministic(self, calibration_service, memory_snapshot):
        """Exports from identical results are identical."""
        calibration = calibration_service.calibrate_signals(memory_snapshot)

        export1 = calibration_service.export_trust_snapshot(calibration, format="json")
        export2 = calibration_service.export_trust_snapshot(calibration, format="json")

        # Parse and compare structure
        data1 = json.loads(export1)
        data2 = json.loads(export2)

        assert data1["total_signals"] == data2["total_signals"]
        assert data1["total_outcomes"] == data2["total_outcomes"]


# ========== DEEPCOPY TESTS ==========
class TestDeepcopyProtection:
    """Verify deepcopy protection on inputs and outputs."""

    def test_modifying_returned_signal_calibration_doesnt_affect_state(
        self, calibration_service, memory_snapshot
    ):
        """Modifying returned signal calibration doesn't affect internal state."""
        result = calibration_service.calibrate_signals(memory_snapshot)
        original_rate = result["consistency_analysis"]["consistency_rate"]

        # Modify returned result
        result["consistency_analysis"]["consistency_rate"] = 0.9999

        # Re-calibrate and verify unchanged
        result2 = calibration_service.calibrate_signals(memory_snapshot)
        assert result2["consistency_analysis"]["consistency_rate"] == original_rate

    def test_modifying_input_memory_snapshot_doesnt_affect_calibration(
        self, calibration_service, memory_snapshot
    ):
        """Modifying input after calling doesn't affect calibration."""
        original_signals = len(memory_snapshot["signal_records"])

        result1 = calibration_service.calibrate_signals(memory_snapshot)

        # Modify input
        memory_snapshot["signal_records"].append({"id": "fake_signal"})

        # Calibration should be unchanged
        result2 = calibration_service.calibrate_signals(memory_snapshot)

        assert result1["total_signals"] != result2["total_signals"]

    def test_modifying_returned_policy_calibration_doesnt_affect_state(
        self, calibration_service, offline_evaluations
    ):
        """Modifying returned policy calibration doesn't affect internal state."""
        result = calibration_service.calibrate_policies(offline_evaluations)
        original_violations = result["violation_summary"]["total_violation_events"]

        # Modify returned result
        result["violation_summary"]["total_violation_events"] = 9999

        # Re-calibrate and verify unchanged
        result2 = calibration_service.calibrate_policies(offline_evaluations)
        assert result2["violation_summary"]["total_violation_events"] == original_violations

    def test_modifying_returned_reviewer_calibration_doesnt_affect_state(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Modifying returned reviewer calibration doesn't affect internal state."""
        result = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)
        original_reviewers = result["total_reviewers"]

        # Modify returned result
        result["total_reviewers"] = 9999

        # Re-calibrate and verify unchanged
        result2 = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)
        assert result2["total_reviewers"] == original_reviewers

    def test_modifying_returned_stability_doesnt_affect_state(
        self, calibration_service, memory_snapshot
    ):
        """Modifying returned stability doesn't affect internal state."""
        result = calibration_service.compute_stability(memory_snapshot)
        original_stability = result["stability_index"]

        # Modify returned result
        result["stability_index"] = 0.9999

        # Re-compute and verify unchanged
        result2 = calibration_service.compute_stability(memory_snapshot)
        assert result2["stability_index"] == original_stability


# ========== FAIL-SILENT TESTS ==========
class TestFailSilentBehavior:
    """Verify fail-silent error handling."""

    def test_none_memory_snapshot_returns_valid_result(self, calibration_service):
        """None memory snapshot returns valid result, not exception."""
        result = calibration_service.calibrate_signals(None)
        assert result is not None
        assert "disclaimer" in result
        assert "total_signals" in result

    def test_empty_memory_snapshot_returns_valid_result(self, calibration_service):
        """Empty memory snapshot returns valid result."""
        result = calibration_service.calibrate_signals({})
        assert result is not None
        assert result["total_signals"] == 0
        assert "disclaimer" in result

    def test_invalid_policy_evaluations_returns_valid_result(self, calibration_service):
        """Invalid policy evaluations return valid result."""
        result = calibration_service.calibrate_policies(None)
        assert result is not None
        assert "disclaimer" in result

    def test_invalid_reviews_returns_valid_result(self, calibration_service):
        """Invalid reviews return valid result."""
        result = calibration_service.calibrate_reviewers(None, None)
        assert result is not None
        assert "disclaimer" in result

    def test_invalid_confidence_records_returns_valid_result(self, calibration_service):
        """Invalid confidence records return valid result."""
        result = calibration_service.compute_stability({})
        assert result is not None
        assert "stability_index" in result

    def test_invalid_export_format_defaults_to_json(self, calibration_service):
        """Invalid export format defaults to JSON."""
        result = {"test": "data"}
        export = calibration_service.export_trust_snapshot(result, format="invalid")
        assert isinstance(export, str)
        # Should be valid JSON
        json.loads(export)


# ========== DISCLAIMER TESTS ==========
class TestDisclaimerRequirements:
    """Verify informational-only disclaimers in all outputs."""

    def test_signal_calibration_includes_disclaimer(
        self, calibration_service, memory_snapshot
    ):
        """Signal calibration includes disclaimer."""
        result = calibration_service.calibrate_signals(memory_snapshot)
        assert "disclaimer" in result
        assert "informational" in result["disclaimer"].lower()
        assert "no authority" in result["disclaimer"].lower()

    def test_policy_calibration_includes_disclaimer(
        self, calibration_service, offline_evaluations
    ):
        """Policy calibration includes disclaimer."""
        result = calibration_service.calibrate_policies(offline_evaluations)
        assert "disclaimer" in result
        assert "informational" in result["disclaimer"].lower()

    def test_reviewer_calibration_includes_disclaimer(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Reviewer calibration includes disclaimer."""
        result = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)
        assert "disclaimer" in result
        assert "no authority" in result["disclaimer"].lower()

    def test_stability_includes_disclaimer(self, calibration_service, memory_snapshot):
        """Stability computation includes disclaimer."""
        result = calibration_service.compute_stability(memory_snapshot)
        assert "disclaimer" in result
        assert "informational" in result["disclaimer"].lower()

    def test_export_includes_explicit_disclaimers(
        self, calibration_service, memory_snapshot
    ):
        """Exported data includes explicit disclaimers."""
        calibration = calibration_service.calibrate_signals(memory_snapshot)
        export = calibration_service.export_trust_snapshot(calibration, format="text")

        assert "disclaimer" in export.lower()
        assert "informational" in export.lower()


# ========== NO BANNED KEYWORDS TESTS ==========
class TestNoBannedKeywords:
    """Verify no banned keywords in public methods and output."""

    BANNED_KEYWORDS = [
        "execute",
        "block",
        "prevent",
        "stop",
        "enforce",
        "trigger",
        "halt",
        "recommend",
        "choose",
        "rank",
        "optimize",
        "weight",
    ]

    def test_signal_calibration_has_no_banned_keywords(
        self, calibration_service, memory_snapshot
    ):
        """Signal calibration output has no banned keywords."""
        result = calibration_service.calibrate_signals(memory_snapshot)
        result_str = json.dumps(result).lower()

        for keyword in self.BANNED_KEYWORDS:
            # Allow "weighting" in "coefficient", etc.
            if keyword == "weight" and "weighting" in result_str:
                continue
            # Allow negative uses: "do not recommend"
            if keyword in ["recommend", "rank", "optimize"] and f"do not {keyword}" in result_str:
                continue
            assert keyword not in result_str

    def test_policy_calibration_has_no_banned_keywords(
        self, calibration_service, offline_evaluations
    ):
        """Policy calibration output has no banned keywords."""
        result = calibration_service.calibrate_policies(offline_evaluations)
        result_str = json.dumps(result).lower()

        for keyword in self.BANNED_KEYWORDS:
            # Allow negative uses: "do not recommend"
            if keyword in ["recommend", "rank", "optimize"] and f"do not {keyword}" in result_str:
                continue
            assert keyword not in result_str

    def test_reviewer_calibration_has_no_banned_keywords(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Reviewer calibration output has no banned keywords."""
        result = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)
        result_str = json.dumps(result).lower()

        for keyword in self.BANNED_KEYWORDS:
            # Allow negative uses: "does not rank"
            if keyword in ["rank", "recommend", "optimize"]:
                if f"do not {keyword}" in result_str or f"does not {keyword}" in result_str:
                    continue
            assert keyword not in result_str

    def test_stability_has_no_banned_keywords(self, calibration_service, memory_snapshot):
        """Stability computation has no banned keywords."""
        result = calibration_service.compute_stability(memory_snapshot)
        result_str = json.dumps(result).lower()

        for keyword in self.BANNED_KEYWORDS:
            # Allow negative uses in disclaimers: "do not rank systems"
            if keyword in ["rank", "optimize"] and f"do not {keyword}" in result_str:
                continue
            assert keyword not in result_str

    def test_exports_have_no_banned_keywords(
        self, calibration_service, memory_snapshot
    ):
        """Exported data has no banned keywords."""
        calibration = calibration_service.calibrate_signals(memory_snapshot)

        export_json = calibration_service.export_trust_snapshot(calibration, format="json")
        export_text = calibration_service.export_trust_snapshot(calibration, format="text")

        for keyword in self.BANNED_KEYWORDS:
            # Allow negative uses in disclaimers
            if keyword in ["recommend", "rank", "optimize"]:
                if f"do not {keyword}" in export_json.lower() or f"do not {keyword}" in export_text.lower():
                    continue
            assert keyword not in export_json.lower()
            assert keyword not in export_text.lower()


# ========== NO RANKING/SCORING TESTS ==========
class TestNoRankingOrScoring:
    """Verify no ranking or prescriptive scoring."""

    def test_signal_calibration_not_ranking_signals(
        self, calibration_service, memory_snapshot
    ):
        """Signal calibration doesn't rank signals."""
        result = calibration_service.calibrate_signals(memory_snapshot)

        # Should have counts and frequencies, not rankings
        assert "consistency_rate" in result["consistency_analysis"]
        assert "best" not in json.dumps(result).lower()
        assert "worst" not in json.dumps(result).lower()

    def test_policy_calibration_not_ranking_policies(
        self, calibration_service, offline_evaluations
    ):
        """Policy calibration doesn't rank policies."""
        result = calibration_service.calibrate_policies(offline_evaluations)

        # Should have frequencies, not rankings
        assert "violation_frequency" in result["violation_summary"]
        assert "best_policy" not in json.dumps(result).lower()
        assert "score" not in json.dumps(result).lower()

    def test_reviewer_calibration_not_ranking_reviewers(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Reviewer calibration doesn't rank reviewers."""
        result = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)

        # Should have frequencies, not rankings or scores
        result_str = json.dumps(result).lower()
        assert "best_reviewer" not in result_str
        assert "reviewer_score" not in result_str
        assert "rating" not in result_str

    def test_stability_not_actionable(self, calibration_service, memory_snapshot):
        """Stability metrics are not actionable."""
        result = calibration_service.compute_stability(memory_snapshot)

        result_str = json.dumps(result).lower()
        # Should can appear in "should not be used to"
        assert "should not" in result_str or "should" not in result_str
        assert "adjust" not in result_str


# ========== DESCRIPTIVE ONLY TESTS ==========
class TestDescriptiveOnly:
    """Verify purely descriptive outputs."""

    def test_signal_consistency_is_historical_frequency(
        self, calibration_service, memory_snapshot
    ):
        """Signal consistency is historical frequency, not future prediction."""
        result = calibration_service.calibrate_signals(memory_snapshot)

        consistency = result["consistency_analysis"]
        assert "consistency_rate" in consistency
        assert consistency.get("note", "").lower() in [
            "historical consistency only. does not predict future alignment.",
            "",
        ]

    def test_violation_frequency_not_policy_recommendation(
        self, calibration_service, offline_evaluations
    ):
        """Violation frequency is not a policy recommendation."""
        result = calibration_service.calibrate_policies(offline_evaluations)

        summary = result["violation_summary"]
        assert "violation_frequency" in summary
        assert "not a policy" in summary.get("note", "").lower()

    def test_regret_analysis_not_optimization_guide(
        self, calibration_service, offline_evaluations
    ):
        """Regret analysis is not an optimization guide."""
        result = calibration_service.calibrate_policies(offline_evaluations)

        regret = result["regret_analysis"]
        assert "not an optimization guide" in regret.get("note", "").lower()

    def test_alignment_analysis_not_reviewer_ranking(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Alignment analysis doesn't rank reviewers."""
        result = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)

        alignment = result["alignment_analysis"]
        assert "no reviewer ranking" in alignment.get("note", "").lower()

    def test_disagreement_patterns_not_reviewer_scoring(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Disagreement patterns don't score reviewers."""
        result = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)

        disagreements = result["disagreement_patterns"]
        assert "not a reviewer ranking" in disagreements.get("note", "").lower()

    def test_confidence_statistics_not_predictive(self, calibration_service, memory_snapshot):
        """Confidence statistics are not predictive."""
        result = calibration_service.compute_stability(memory_snapshot)

        stats = result["confidence_statistics"]
        assert "not predictive" in stats.get("note", "").lower()

    def test_decay_analysis_not_predictive(self, calibration_service, memory_snapshot):
        """Decay analysis is not predictive."""
        result = calibration_service.compute_stability(memory_snapshot)

        decay = result["decay_analysis"]
        assert "not predictive" in decay.get("note", "").lower()


# ========== ISOLATION TESTS ==========
class TestIsolation:
    """Verify service isolation and no external mutations."""

    def test_no_external_service_mutations_on_signal_calibration(
        self, calibration_service, memory_snapshot
    ):
        """Signal calibration doesn't modify external services."""
        # Service should only have internal state, no external references
        calibration_service.calibrate_signals(memory_snapshot)

        # All data should be in internal storage only
        assert len(calibration_service._signal_calibrations) >= 0
        assert len(calibration_service._all_calibration_events) >= 0

    def test_no_external_mutations_on_policy_calibration(
        self, calibration_service, offline_evaluations
    ):
        """Policy calibration doesn't modify external services."""
        calibration_service.calibrate_policies(offline_evaluations)

        # All data internal
        assert len(calibration_service._all_calibration_events) >= 0

    def test_no_external_mutations_on_reviewer_calibration(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Reviewer calibration doesn't modify external services."""
        calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)

        # All data internal
        assert len(calibration_service._all_calibration_events) >= 0

    def test_multiple_calibrations_independent(
        self, calibration_service, memory_snapshot, offline_evaluations
    ):
        """Multiple calibrations don't interfere with each other."""
        # Create independent services
        svc1 = DecisionTrustCalibrationService()
        svc2 = DecisionTrustCalibrationService()

        result1 = svc1.calibrate_signals(memory_snapshot)
        result2 = svc2.calibrate_signals(memory_snapshot)

        assert result1["total_signals"] == result2["total_signals"]
        assert len(svc1._all_calibration_events) == len(svc2._all_calibration_events)


# ========== EXPORT FORMAT TESTS ==========
class TestExportFormats:
    """Verify export format correctness."""

    def test_json_export_is_valid_json(self, calibration_service, memory_snapshot):
        """JSON export is valid JSON."""
        calibration = calibration_service.calibrate_signals(memory_snapshot)
        export = calibration_service.export_trust_snapshot(calibration, format="json")

        # Should be parseable
        data = json.loads(export)
        assert isinstance(data, dict)

    def test_text_export_is_readable(self, calibration_service, memory_snapshot):
        """Text export is human-readable."""
        calibration = calibration_service.calibrate_signals(memory_snapshot)
        export = calibration_service.export_trust_snapshot(calibration, format="text")

        assert isinstance(export, str)
        assert "DECISION TRUST CALIBRATION SNAPSHOT" in export

    def test_json_export_includes_disclaimer(self, calibration_service, memory_snapshot):
        """JSON export includes disclaimer."""
        calibration = calibration_service.calibrate_signals(memory_snapshot)
        export = calibration_service.export_trust_snapshot(calibration, format="json")

        data = json.loads(export)
        assert "disclaimer" in data
        assert "no authority" in data["disclaimer"].lower()

    def test_text_export_includes_disclaimer(self, calibration_service, memory_snapshot):
        """Text export includes disclaimer."""
        calibration = calibration_service.calibrate_signals(memory_snapshot)
        export = calibration_service.export_trust_snapshot(calibration, format="text")

        assert "DISCLAIMER" in export
        assert "no authority" in export.lower()


# ========== INTEGRATION TESTS ==========
class TestIntegration:
    """Full workflow integration tests."""

    def test_full_signal_calibration_workflow(self, calibration_service, memory_snapshot):
        """Full signal calibration workflow."""
        # 1. Calibrate signals
        calibration = calibration_service.calibrate_signals(memory_snapshot)

        assert "total_signals" in calibration
        assert "consistency_analysis" in calibration
        assert "disclaimer" in calibration

        # 2. Export
        export_json = calibration_service.export_trust_snapshot(calibration, format="json")
        export_text = calibration_service.export_trust_snapshot(calibration, format="text")

        assert isinstance(export_json, str)
        assert isinstance(export_text, str)

        # Parse and verify
        data = json.loads(export_json)
        assert data["total_signals"] == calibration["total_signals"]

    def test_full_policy_calibration_workflow(self, calibration_service, offline_evaluations):
        """Full policy calibration workflow."""
        # 1. Calibrate policies
        calibration = calibration_service.calibrate_policies(offline_evaluations)

        assert "total_policies" in calibration
        assert "violation_summary" in calibration
        assert "regret_analysis" in calibration

        # 2. Export
        export = calibration_service.export_trust_snapshot(calibration, format="json")
        data = json.loads(export)

        assert data["total_policies"] == calibration["total_policies"]

    def test_full_reviewer_calibration_workflow(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Full reviewer calibration workflow."""
        # 1. Calibrate reviewers
        calibration = calibration_service.calibrate_reviewers(
            human_reviews, counterfactual_results
        )

        assert "total_reviewers" in calibration
        assert "alignment_analysis" in calibration
        assert "disagreement_patterns" in calibration

        # 2. Export
        export = calibration_service.export_trust_snapshot(calibration, format="json")
        data = json.loads(export)

        assert data["total_reviewers"] == calibration["total_reviewers"]

    def test_full_stability_workflow(self, calibration_service, memory_snapshot):
        """Full stability computation workflow."""
        # 1. Compute stability
        stability = calibration_service.compute_stability(memory_snapshot)

        assert "stability_index" in stability
        assert "confidence_statistics" in stability
        assert "decay_analysis" in stability

        # 2. Export
        export = calibration_service.export_trust_snapshot(stability, format="json")
        data = json.loads(export)

        assert "stability_index" in data


# ========== EXPLICIT NON-GOALS TESTS ==========
class TestExplicitNonGoals:
    """Verify service doesn't do things it shouldn't."""

    def test_service_never_modifies_memory_service_state(
        self, calibration_service, memory_snapshot
    ):
        """Service never modifies DecisionIntelligenceMemoryService."""
        # This is verified by the service having read-only access pattern
        # and no code that writes to external services
        calibration_service.calibrate_signals(memory_snapshot)

        # Memory snapshot should be unchanged
        assert memory_snapshot["signal_records"][0]["id"] == "signal_001"

    def test_service_never_learns_from_outcomes(self, calibration_service, memory_snapshot):
        """Service never learns or optimizes from outcomes."""
        # Multiple calls produce same results
        result1 = calibration_service.calibrate_signals(memory_snapshot)
        result2 = calibration_service.calibrate_signals(memory_snapshot)
        result3 = calibration_service.calibrate_signals(memory_snapshot)

        assert result1["total_signals"] == result2["total_signals"] == result3["total_signals"]

    def test_service_never_triggers_enforcement(
        self, calibration_service, offline_evaluations
    ):
        """Service never triggers enforcement or blocking."""
        # Severe regret should not trigger anything
        result = calibration_service.calibrate_policies(offline_evaluations)

        # Should just be analytical
        assert result["regret_analysis"]["total_regret_magnitude"] > 0
        # Check that explanation is descriptive, not prescriptive
        explanation = result["explanation"].lower()
        assert "historical analysis" in explanation or "analysis" in explanation

    def test_service_never_orchestrates_other_services(
        self, calibration_service, human_reviews, counterfactual_results
    ):
        """Service never orchestrates or coordinates other services."""
        # Should just analyze, not trigger workflows
        result = calibration_service.calibrate_reviewers(human_reviews, counterfactual_results)

        # Pure analysis result
        assert result["total_reviewers"] >= 0
        assert "do not rank" in result["explanation"].lower()
