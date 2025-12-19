"""
Tests for DecisionIntelligenceArchiveService

Verifies:
- Append-only guarantee (no updates/deletes)
- Immutability of stored records
- Deterministic reads (same input → same output)
- Fail-silent write behavior
- No mutation of original reports
- Trend calculations correctness
- No enforcement keywords anywhere
- Archive service isolation (cannot influence trading)
- Proper disclaimers on all stored data
"""

import pytest
from datetime import datetime, timezone, timedelta
from copy import deepcopy
import time

from reasoner_service.decision_intelligence_archive_service import (
    DecisionIntelligenceArchiveService,
)


class TestAppendOnlyGuarantee:
    """Verify append-only semantics are enforced."""
    
    def test_archive_report_appends_new_entry(self):
        """Archive service adds new reports without replacing."""
        archive = DecisionIntelligenceArchiveService()
        
        report1 = {
            "correlation_id": "trade_001",
            "confidence_score": 75.0,
            "governance_pressure": "low",
            "counterfactual_regret": 10.5,
            "risk_flags": [],
            "explanation": "Trade analysis 1",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        report2 = {
            "correlation_id": "trade_001",
            "confidence_score": 80.0,
            "governance_pressure": "none",
            "counterfactual_regret": 5.0,
            "risk_flags": [],
            "explanation": "Trade analysis 2 (later evaluation)",
            "evaluated_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "disclaimer": "Informational only",
        }
        
        # Archive both reports
        archive.archive_report(report1)
        archive.archive_report(report2)
        
        # Fetch all should return both
        all_reports = archive.fetch_all()
        assert len(all_reports) == 2
        assert all_reports[0]["confidence_score"] == 75.0
        assert all_reports[1]["confidence_score"] == 80.0
    
    def test_archive_preserves_insertion_order(self):
        """Archive maintains chronological insertion order (append-only)."""
        archive = DecisionIntelligenceArchiveService()
        
        reports = []
        for i in range(5):
            reports.append({
                "correlation_id": f"trade_{i:03d}",
                "confidence_score": 50.0 + i * 10,
                "governance_pressure": "none",
                "counterfactual_regret": 0.0,
                "risk_flags": [],
                "explanation": f"Analysis {i}",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "Informational only",
            })
        
        for report in reports:
            archive.archive_report(report)
        
        archived = archive.fetch_all()
        for i, stored in enumerate(archived):
            assert stored["correlation_id"] == f"trade_{i:03d}"
            assert stored["confidence_score"] == 50.0 + i * 10
    
    def test_no_update_operation_exists(self):
        """Archive service has no update method."""
        archive = DecisionIntelligenceArchiveService()
        
        # Verify no update method exists
        assert not hasattr(archive, "update_report")
        assert not hasattr(archive, "modify_report")
        assert not hasattr(archive, "edit_archived_record")
    
    def test_no_delete_operation_exists(self):
        """Archive service has no delete method."""
        archive = DecisionIntelligenceArchiveService()
        
        # Verify no delete method exists
        assert not hasattr(archive, "delete_report")
        assert not hasattr(archive, "remove_report")
        assert not hasattr(archive, "purge_record")


class TestImmutabilityVerification:
    """Verify stored records cannot be mutated after archival."""
    
    def test_fetched_reports_cannot_affect_archive(self):
        """Modifying a fetched report doesn't affect stored record."""
        archive = DecisionIntelligenceArchiveService()
        
        original_report = {
            "correlation_id": "trade_001",
            "confidence_score": 75.0,
            "governance_pressure": "low",
            "counterfactual_regret": 10.5,
            "risk_flags": ["high_regret"],
            "explanation": "Original explanation",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        archive.archive_report(deepcopy(original_report))
        
        # Fetch and mutate
        fetched = archive.fetch_by_correlation_id("trade_001")
        assert len(fetched) > 0
        fetched[0]["confidence_score"] = 99.0
        fetched[0]["explanation"] = "MODIFIED!"
        fetched[0]["risk_flags"].append("INJECTED")
        
        # Re-fetch should show original values
        re_fetched = archive.fetch_by_correlation_id("trade_001")
        assert re_fetched[0]["confidence_score"] == 75.0
        assert re_fetched[0]["explanation"] == "Original explanation"
        assert "INJECTED" not in re_fetched[0]["risk_flags"]
    
    def test_stored_lists_are_immutable_from_fetching(self):
        """Modifying list fields in fetched report doesn't affect archive."""
        archive = DecisionIntelligenceArchiveService()
        
        report = {
            "correlation_id": "trade_001",
            "confidence_score": 60.0,
            "governance_pressure": "medium",
            "counterfactual_regret": 20.0,
            "risk_flags": ["moderate_violation", "governance_pressure"],
            "explanation": "Medium confidence trade",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        archive.archive_report(report)
        
        # Fetch and clear risk flags
        fetched = archive.fetch_all()
        fetched[0]["risk_flags"].clear()
        fetched[0]["risk_flags"].append("MALICIOUS_FLAG")
        
        # Re-fetch should have original flags
        re_fetched = archive.fetch_all()
        assert "MALICIOUS_FLAG" not in re_fetched[0]["risk_flags"]
        assert "moderate_violation" in re_fetched[0]["risk_flags"]
        assert "governance_pressure" in re_fetched[0]["risk_flags"]
    
    def test_archive_input_not_mutated_after_storage(self):
        """Archiving a report doesn't modify the original input."""
        archive = DecisionIntelligenceArchiveService()
        
        report = {
            "correlation_id": "trade_001",
            "confidence_score": 75.0,
            "governance_pressure": "low",
            "counterfactual_regret": 10.5,
            "risk_flags": ["flag1"],
            "explanation": "Original",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        original_copy = deepcopy(report)
        archive.archive_report(report)
        
        # Original should be unchanged
        assert report == original_copy
        assert report["confidence_score"] == 75.0
        assert len(report["risk_flags"]) == 1


class TestDeterministicReads:
    """Verify read operations are deterministic and reproducible."""
    
    def test_fetch_same_id_returns_identical_results(self):
        """Multiple fetches of same correlation_id return identical data."""
        archive = DecisionIntelligenceArchiveService()
        
        report = {
            "correlation_id": "trade_001",
            "confidence_score": 72.5,
            "governance_pressure": "low",
            "counterfactual_regret": 12.3,
            "risk_flags": ["minor_regret"],
            "explanation": "Consistent analysis",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        archive.archive_report(report)
        
        # Fetch multiple times
        fetch1 = archive.fetch_by_correlation_id("trade_001")
        time.sleep(0.01)  # Small delay
        fetch2 = archive.fetch_by_correlation_id("trade_001")
        time.sleep(0.01)  # Small delay
        fetch3 = archive.fetch_by_correlation_id("trade_001")
        
        # All should be identical
        assert fetch1 == fetch2
        assert fetch2 == fetch3
    
    def test_fetch_all_is_deterministic(self):
        """Multiple fetch_all() calls return identical order and data."""
        archive = DecisionIntelligenceArchiveService()
        
        reports = [
            {
                "correlation_id": f"trade_{i:03d}",
                "confidence_score": 50.0 + i,
                "governance_pressure": "none",
                "counterfactual_regret": 0.0,
                "risk_flags": [],
                "explanation": f"Trade {i}",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "Informational only",
            }
            for i in range(10)
        ]
        
        for report in reports:
            archive.archive_report(report)
        
        # Fetch multiple times
        fetch1 = archive.fetch_all()
        fetch2 = archive.fetch_all()
        fetch3 = archive.fetch_all()
        
        # All fetches identical
        assert fetch1 == fetch2
        assert fetch2 == fetch3
        
        # Order preserved
        for i, record in enumerate(fetch1):
            assert record["correlation_id"] == f"trade_{i:03d}"
    
    def test_empty_fetch_returns_empty_list_deterministically(self):
        """Fetching non-existent correlation_id consistently returns empty list."""
        archive = DecisionIntelligenceArchiveService()
        
        fetch1 = archive.fetch_by_correlation_id("nonexistent_001")
        fetch2 = archive.fetch_by_correlation_id("nonexistent_001")
        fetch3 = archive.fetch_by_correlation_id("nonexistent_001")
        
        assert fetch1 == []
        assert fetch2 == []
        assert fetch3 == []


class TestFailSilentWriteBehavior:
    """Verify archive gracefully handles errors without crashing."""
    
    def test_archive_invalid_report_silently_ignored(self):
        """Archive silently handles invalid/malformed reports."""
        archive = DecisionIntelligenceArchiveService()
        
        # Try archiving None
        archive.archive_report(None)
        
        # Try archiving invalid types
        archive.archive_report("not a dict")
        archive.archive_report(123)
        archive.archive_report([])
        
        # Try archiving incomplete report
        archive.archive_report({
            "correlation_id": "trade_001",
            # Missing other fields
        })
        
        # Archive should still be usable
        valid_report = {
            "correlation_id": "trade_valid",
            "confidence_score": 75.0,
            "governance_pressure": "none",
            "counterfactual_regret": 0.0,
            "risk_flags": [],
            "explanation": "Valid",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        archive.archive_report(valid_report)
        assert len(archive.fetch_all()) >= 1
    
    def test_archive_batch_continues_on_invalid_items(self):
        """Archive batch operation skips invalid items and continues."""
        archive = DecisionIntelligenceArchiveService()
        
        reports = [
            {
                "correlation_id": "trade_001",
                "confidence_score": 75.0,
                "governance_pressure": "none",
                "counterfactual_regret": 0.0,
                "risk_flags": [],
                "explanation": "Valid 1",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "Informational only",
            },
            None,  # Invalid
            "invalid",  # Invalid
            {
                "correlation_id": "trade_002",
                "confidence_score": 80.0,
                "governance_pressure": "none",
                "counterfactual_regret": 0.0,
                "risk_flags": [],
                "explanation": "Valid 2",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "Informational only",
            },
        ]
        
        archive.archive_batch(reports)
        
        # Should have archived the valid ones
        all_archived = archive.fetch_all()
        valid_count = len([r for r in all_archived if r.get("correlation_id")])
        assert valid_count >= 2
    
    def test_archive_returns_no_exceptions(self):
        """Archive methods never raise exceptions."""
        archive = DecisionIntelligenceArchiveService()
        
        # These should all succeed without raising
        try:
            archive.archive_report(None)
            archive.archive_report({})
            archive.archive_report("invalid")
            archive.archive_batch(None)
            archive.archive_batch([None, None])
            archive.fetch_by_correlation_id(None)
            archive.fetch_by_correlation_id("nonexistent")
            archive.fetch_all()
            archive.compute_trends()
        except Exception as e:
            pytest.fail(f"Archive method raised exception: {e}")


class TestNoMutationOfOriginalReports:
    """Verify archive doesn't modify source reports."""
    
    def test_archived_report_detached_from_original(self):
        """Archived report is independent copy, not reference."""
        archive = DecisionIntelligenceArchiveService()
        
        original = {
            "correlation_id": "trade_001",
            "confidence_score": 75.0,
            "governance_pressure": "low",
            "counterfactual_regret": 10.5,
            "risk_flags": ["flag1", "flag2"],
            "explanation": "Original explanation",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        archive.archive_report(original)
        
        # Modify original
        original["confidence_score"] = 99.0
        original["risk_flags"] = ["INJECTED_FLAG"]
        original["explanation"] = "HACKED!"
        
        # Archived should be unaffected
        archived = archive.fetch_by_correlation_id("trade_001")[0]
        assert archived["confidence_score"] == 75.0
        assert "INJECTED_FLAG" not in archived["risk_flags"]
        assert archived["explanation"] == "Original explanation"


class TestTrendCalculations:
    """Verify trend calculations are correct and non-prescriptive."""
    
    def test_compute_trends_returns_valid_structure(self):
        """Trends summary has all required fields."""
        archive = DecisionIntelligenceArchiveService()
        
        # Add some reports
        for i in range(5):
            report = {
                "correlation_id": f"trade_{i:03d}",
                "confidence_score": 50.0 + i * 10,
                "governance_pressure": "none",
                "counterfactual_regret": 0.0,
                "risk_flags": [],
                "explanation": f"Trade {i}",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "Informational only",
            }
            archive.archive_report(report)
        
        trends = archive.compute_trends()
        
        # Verify structure
        assert isinstance(trends, dict)
        assert "total_archived" in trends
        assert "average_confidence" in trends
        assert "confidence_min" in trends
        assert "confidence_max" in trends
        assert "governance_pressure_distribution" in trends
        assert "disclaimer" in trends
    
    def test_confidence_drift_calculation(self):
        """Average confidence calculation is accurate."""
        archive = DecisionIntelligenceArchiveService()
        
        scores = [50.0, 60.0, 70.0, 80.0, 90.0]
        
        for i, score in enumerate(scores):
            report = {
                "correlation_id": f"trade_{i:03d}",
                "confidence_score": score,
                "governance_pressure": "none",
                "counterfactual_regret": 0.0,
                "risk_flags": [],
                "explanation": f"Score {score}",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "Informational only",
            }
            archive.archive_report(report)
        
        trends = archive.compute_trends()
        
        assert trends["average_confidence"] == 70.0
        assert trends["confidence_min"] == 50.0
        assert trends["confidence_max"] == 90.0
    
    def test_governance_pressure_distribution_frequency(self):
        """Governance pressure frequency is accurately counted."""
        archive = DecisionIntelligenceArchiveService()
        
        pressures = ["none", "none", "none", "low", "low", "medium"]
        
        for i, pressure in enumerate(pressures):
            report = {
                "correlation_id": f"trade_{i:03d}",
                "confidence_score": 75.0,
                "governance_pressure": pressure,
                "counterfactual_regret": 0.0,
                "risk_flags": [],
                "explanation": "Test",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "disclaimer": "Informational only",
            }
            archive.archive_report(report)
        
        trends = archive.compute_trends()
        dist = trends["governance_pressure_distribution"]
        
        assert dist.get("none") == 3
        assert dist.get("low") == 2
        assert dist.get("medium") == 1
    
    def test_trends_on_empty_archive(self):
        """Trends calculation handles empty archive gracefully."""
        archive = DecisionIntelligenceArchiveService()
        
        trends = archive.compute_trends()
        
        # Should return valid structure even when empty
        assert trends["total_archived"] == 0
        assert "average_confidence" in trends
        assert "disclaimer" in trends


class TestEnforcementKeywordProtection:
    """Verify no enforcement keywords/logic exist."""
    
    def test_archive_has_no_block_methods(self):
        """Archive has no methods that could block trades."""
        archive = DecisionIntelligenceArchiveService()
        
        assert not hasattr(archive, "block_trade")
        assert not hasattr(archive, "enforce_policy")
        assert not hasattr(archive, "reject_trade")
        assert not hasattr(archive, "allow_trade")
        assert not hasattr(archive, "execute_trade")
    
    def test_archive_has_no_execution_hooks(self):
        """Archive has no methods that could trigger execution."""
        archive = DecisionIntelligenceArchiveService()
        
        assert not hasattr(archive, "trigger_execution")
        assert not hasattr(archive, "submit_order")
        assert not hasattr(archive, "place_trade")
        assert not hasattr(archive, "invoke_orchestrator")
    
    def test_stored_data_contains_no_enforcement_keywords(self):
        """Stored reports don't have enforcement action fields."""
        archive = DecisionIntelligenceArchiveService()
        
        report = {
            "correlation_id": "trade_001",
            "confidence_score": 75.0,
            "governance_pressure": "low",
            "counterfactual_regret": 10.5,
            "risk_flags": ["minor_regret"],
            "explanation": "Trade analysis",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        archive.archive_report(report)
        stored = archive.fetch_all()[0]
        
        # Keys should NOT include enforcement fields
        forbidden_keys = [
            "block_trade", "allow_trade", "enforce", "execute",
            "reject", "approve", "action", "decision"
        ]
        
        for key in stored.keys():
            for forbidden in forbidden_keys:
                assert forbidden.lower() not in key.lower()


class TestArchiveServiceIsolation:
    """Verify archive cannot influence trading or other services."""
    
    def test_archive_has_no_service_references(self):
        """Archive doesn't hold references to execution services."""
        archive = DecisionIntelligenceArchiveService()
        
        # Should not have these service references
        assert not hasattr(archive, "orchestrator")
        assert not hasattr(archive, "trade_executor")
        assert not hasattr(archive, "governance_enforcer")
        assert not hasattr(archive, "execution_service")
    
    def test_archive_methods_only_read_and_append(self):
        """Archive only has read and append operations."""
        archive = DecisionIntelligenceArchiveService()
        
        # Public methods should be limited
        public_methods = [m for m in dir(archive) if not m.startswith('_')]
        
        # Allowed operations
        allowed = {'archive_report', 'archive_batch', 'fetch_by_correlation_id', 
                   'fetch_all', 'compute_trends'}
        
        actual_methods = set(public_methods)
        
        # All public methods should be in allowed list
        for method in actual_methods:
            if not method.startswith('__'):
                assert method in allowed or method in {'__class__', '__delattr__', '__dir__',
                                                        '__doc__', '__eq__', '__format__',
                                                        '__ge__', '__getattribute__', '__gt__',
                                                        '__hash__', '__init__', '__init_subclass__',
                                                        '__le__', '__lt__', '__module__', '__ne__',
                                                        '__new__', '__reduce__', '__reduce_ex__',
                                                        '__repr__', '__setattr__', '__sizeof__',
                                                        '__str__', '__subclass_hook__', '__weakref__'}


class TestDisclaimerPresence:
    """Verify all stored data includes proper disclaimers."""
    
    def test_single_report_has_disclaimer(self):
        """Each archived report includes non-enforcement disclaimer."""
        archive = DecisionIntelligenceArchiveService()
        
        report = {
            "correlation_id": "trade_001",
            "confidence_score": 75.0,
            "governance_pressure": "low",
            "counterfactual_regret": 10.5,
            "risk_flags": [],
            "explanation": "Trade analysis",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        archive.archive_report(report)
        stored = archive.fetch_by_correlation_id("trade_001")[0]
        
        assert "disclaimer" in stored
        assert stored["disclaimer"] != ""
        assert "informational" in stored["disclaimer"].lower()
    
    def test_trends_include_disclaimer(self):
        """Trend calculations include non-enforcement disclaimer."""
        archive = DecisionIntelligenceArchiveService()
        
        report = {
            "correlation_id": "trade_001",
            "confidence_score": 75.0,
            "governance_pressure": "low",
            "counterfactual_regret": 10.5,
            "risk_flags": [],
            "explanation": "Trade analysis",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "disclaimer": "Informational only",
        }
        
        archive.archive_report(report)
        trends = archive.compute_trends()
        
        assert "disclaimer" in trends
        assert trends["disclaimer"] != ""


class TestCompleteWorkflow:
    """Integration test of full archive workflow."""
    
    def test_complete_archive_lifecycle(self):
        """Full lifecycle: archive, fetch, trend analysis."""
        archive = DecisionIntelligenceArchiveService()
        
        # Generate reports over time
        reports = []
        for i in range(10):
            report = {
                "correlation_id": f"trade_{i:03d}",
                "confidence_score": 40.0 + i * 5,
                "governance_pressure": "none" if i < 5 else ("low" if i < 8 else "medium"),
                "counterfactual_regret": 0.0 if i < 3 else (5.0 if i < 7 else 10.0),
                "risk_flags": [] if i < 5 else ["elevated_regret"],
                "explanation": f"Trade {i} analysis",
                "evaluated_at": (datetime.now(timezone.utc) + timedelta(hours=i)).isoformat(),
                "disclaimer": "Informational only",
            }
            reports.append(report)
        
        # Archive batch
        archive.archive_batch(reports)
        
        # Verify all archived
        all_archived = archive.fetch_all()
        assert len(all_archived) == 10
        
        # Fetch specific correlations
        trade_5_reports = archive.fetch_by_correlation_id("trade_005")
        assert len(trade_5_reports) == 1
        assert trade_5_reports[0]["confidence_score"] == 65.0
        
        # Compute trends
        trends = archive.compute_trends()
        assert trends["total_archived"] == 10
        assert trends["average_confidence"] == 62.5  # (40+45+50+...+85)/10 = 625/10
        assert "disclaimer" in trends
        
        # Verify order preservation
        for i, stored in enumerate(all_archived):
            assert stored["correlation_id"] == f"trade_{i:03d}"
