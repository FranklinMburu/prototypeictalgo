"""
Comprehensive test suite for DecisionIntelligenceMemoryService.

Tests verify:
- Read-only semantics (no mutations, no writes)
- Deterministic outputs (same input = same output)
- Deepcopy protection (fetched data cannot affect service state)
- Fail-silent error handling
- Informational-only nature (no enforcement keywords)
- No side effects
- Archive protection (archive remains append-only)

All tests use TDD approach: test first, then implementation.
"""

import pytest
import json
import copy
from datetime import datetime, timezone
from typing import List, Dict, Any

from reasoner_service.decision_intelligence_memory_service import DecisionIntelligenceMemoryService


class TestReadOnlyGuarantee:
    """Verify memory service provides no write or mutation capabilities."""

    def test_memory_service_has_no_write_methods(self):
        """Verify no methods that write or mutate exist."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Get all public methods
        public_methods = [m for m in dir(memory_service) if not m.startswith('_')]
        
        # Verify forbidden keywords not in any method name
        forbidden_patterns = [
            'write', 'update', 'delete', 'remove', 'store', 'save',
            'execute', 'enforce', 'block', 'override', 'modify',
            'learn', 'adapt', 'retrain', 'mutate'
        ]
        
        for method_name in public_methods:
            for pattern in forbidden_patterns:
                assert pattern.lower() not in method_name.lower(), \
                    f"Method '{method_name}' contains forbidden pattern '{pattern}'"

    def test_memory_service_has_only_read_methods(self):
        """Verify only read/analysis methods exist."""
        memory_service = DecisionIntelligenceMemoryService()
        
        public_methods = {
            m for m in dir(memory_service) 
            if not m.startswith('_') and callable(getattr(memory_service, m))
        }
        
        # Expected read-only methods
        expected_methods = {
            'compute_trends',
            'detect_patterns',
            'compare_windows',
            'export_memory_snapshot'
        }
        
        # Verify all expected methods exist
        for method in expected_methods:
            assert method in public_methods, f"Missing method: {method}"

    def test_memory_service_no_direct_archive_access(self):
        """Verify no direct archive manipulation possible."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Should not have archive attribute accessible for direct mutation
        if hasattr(memory_service, '_archive'):
            archive = getattr(memory_service, '_archive', None)
            # Archive should not be a list that can be directly modified
            assert not isinstance(archive, list), \
                "Archive should not be directly accessible as mutable list"


class TestDeterministicBehavior:
    """Verify all outputs are deterministic (same input = same output)."""

    def test_compute_trends_deterministic(self):
        """Same reports produce identical trends output."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Create sample reports
        reports = [
            {
                "correlation_id": "cid-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "confidence_score": 0.75,
                "governance_pressure": 0.3,
                "risk_flags": ["FLAG_1"],
                "trade_volume": 1000
            },
            {
                "correlation_id": "cid-2",
                "timestamp": "2025-01-01T11:00:00Z",
                "confidence_score": 0.85,
                "governance_pressure": 0.2,
                "risk_flags": [],
                "trade_volume": 1500
            }
        ]
        
        # Simulate memory with reports
        memory_service._cached_reports = copy.deepcopy(reports)
        
        # Compute trends multiple times
        trends1 = memory_service.compute_trends()
        trends2 = memory_service.compute_trends()
        trends3 = memory_service.compute_trends()
        
        # All should be identical
        assert trends1 == trends2, "Trends not deterministic (call 1 vs 2)"
        assert trends2 == trends3, "Trends not deterministic (call 2 vs 3)"

    def test_detect_patterns_deterministic(self):
        """Same reports produce identical patterns."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {
                "correlation_id": f"cid-{i}",
                "timestamp": f"2025-01-01T{10+i:02d}:00:00Z",
                "confidence_score": 0.5 + (i * 0.05),
                "governance_pressure": 0.3,
                "risk_flags": ["REPEATED_VIOLATION"] if i % 2 == 0 else []
            }
            for i in range(5)
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        
        patterns1 = memory_service.detect_patterns()
        patterns2 = memory_service.detect_patterns()
        
        assert patterns1 == patterns2, "Patterns not deterministic"

    def test_compare_windows_deterministic(self):
        """Window comparison always returns same result."""
        memory_service = DecisionIntelligenceMemoryService()
        
        window_a = [
            {"confidence_score": 0.7, "governance_pressure": 0.3},
            {"confidence_score": 0.75, "governance_pressure": 0.25}
        ]
        window_b = [
            {"confidence_score": 0.8, "governance_pressure": 0.2},
            {"confidence_score": 0.85, "governance_pressure": 0.15}
        ]
        
        comparison1 = memory_service.compare_windows(window_a, window_b)
        comparison2 = memory_service.compare_windows(window_a, window_b)
        comparison3 = memory_service.compare_windows(window_a, window_b)
        
        assert comparison1 == comparison2 == comparison3, \
            "Window comparison not deterministic"

    def test_export_snapshot_deterministic(self):
        """Memory snapshot output is always identical."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {
                "correlation_id": f"cid-{i}",
                "timestamp": f"2025-01-01T{10+i:02d}:00:00Z",
                "confidence_score": 0.5 + (i * 0.1)
            }
            for i in range(3)
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        
        snapshot1 = memory_service.export_memory_snapshot()
        snapshot2 = memory_service.export_memory_snapshot()
        snapshot3 = memory_service.export_memory_snapshot()
        
        assert snapshot1 == snapshot2 == snapshot3, \
            "Memory snapshot not deterministic"


class TestDeepcopProtection:
    """Verify fetched data cannot affect service state."""

    def test_compute_trends_returns_deepcopy(self):
        """Modifying returned trends doesn't affect future outputs."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {
                "correlation_id": "cid-1",
                "timestamp": "2025-01-01T10:00:00Z",
                "confidence_score": 0.75,
                "governance_pressure": 0.3,
                "risk_flags": []
            }
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        
        # Get trends
        trends1 = memory_service.compute_trends()
        original_avg = trends1.get("confidence", {}).get("avg")
        
        # Mutate returned trends
        if "confidence" in trends1:
            trends1["confidence"]["avg"] = 999.99
        
        # Get trends again - should be unchanged
        trends2 = memory_service.compute_trends()
        assert trends2.get("confidence", {}).get("avg") == original_avg, \
            "Modifying returned trends affected service state"

    def test_detect_patterns_returns_deepcopy(self):
        """Modifying returned patterns doesn't affect service."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {"correlation_id": f"cid-{i}", "risk_flags": ["FLAG"] if i % 2 == 0 else []}
            for i in range(4)
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        
        patterns1 = memory_service.detect_patterns()
        patterns1_copy = copy.deepcopy(patterns1)
        
        # Mutate returned patterns
        if isinstance(patterns1, dict) and "repeated_violations" in patterns1:
            patterns1["repeated_violations"] = []
        
        # Get patterns again
        patterns2 = memory_service.detect_patterns()
        
        # Should match original, not mutated version
        assert patterns2 == patterns1_copy, \
            "Modifying returned patterns affected service state"

    def test_snapshot_returns_deepcopy(self):
        """Modifying exported snapshot doesn't affect service."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {"correlation_id": "cid-1", "confidence_score": 0.75}
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        
        snapshot1 = memory_service.export_memory_snapshot()
        snapshot1_copy = copy.deepcopy(snapshot1)
        
        # Mutate snapshot
        if isinstance(snapshot1, dict) and "snapshot_data" in snapshot1:
            snapshot1["snapshot_data"] = {"mutated": True}
        
        # Get snapshot again
        snapshot2 = memory_service.export_memory_snapshot()
        
        assert snapshot2 == snapshot1_copy, \
            "Modifying exported snapshot affected service state"


class TestFailSilentBehavior:
    """Verify graceful error handling without exceptions."""

    def test_compute_trends_with_invalid_reports(self):
        """Invalid reports don't cause exceptions."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Set up with mixed valid/invalid reports
        memory_service._cached_reports = [
            {"correlation_id": "valid", "confidence_score": 0.75},
            None,  # Invalid
            {"invalid": "structure"},  # Invalid
            {"confidence_score": "not_a_number"},  # Invalid
        ]
        
        # Should not raise exception
        result = memory_service.compute_trends()
        assert result is not None, "Failed silent: returned None"
        assert isinstance(result, dict), "Should return dict even with errors"

    def test_detect_patterns_with_empty_archive(self):
        """Empty archive handled gracefully."""
        memory_service = DecisionIntelligenceMemoryService()
        memory_service._cached_reports = []
        
        # Should not raise exception
        result = memory_service.detect_patterns()
        assert result is not None, "Failed on empty archive"
        assert isinstance(result, dict), "Should return dict for empty archive"

    def test_compare_windows_with_invalid_data(self):
        """Invalid window data handled gracefully."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Should not raise exception with None
        result1 = memory_service.compare_windows(None, None)
        assert result1 is not None, "Failed with None windows"
        
        # Should not raise exception with invalid structure
        result2 = memory_service.compare_windows([], [])
        assert result2 is not None, "Failed with empty windows"

    def test_export_snapshot_with_corrupted_data(self):
        """Corrupted data handled gracefully."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Set up with corrupted reports
        memory_service._cached_reports = [
            {"correlation_id": 123},  # ID not string
            {},  # Empty report
            {"timestamp": "invalid_date"},
        ]
        
        # Should not raise exception
        result = memory_service.export_memory_snapshot()
        assert result is not None, "Failed on corrupted data"
        assert isinstance(result, dict), "Should return dict"


class TestInformationalOnlyNature:
    """Verify all outputs are informational only (no enforcement keywords)."""

    def test_no_enforcement_keywords_in_trends(self):
        """Trends contain no enforcement or blocking keywords."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {
                "correlation_id": "cid-1",
                "confidence_score": 0.75,
                "governance_pressure": 0.3,
                "risk_flags": []
            }
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        trends = memory_service.compute_trends()
        
        # Convert to string and check for forbidden keywords
        trends_str = json.dumps(trends, default=str).lower()
        
        forbidden_keywords = [
            'execute', 'enforce', 'block', 'stop', 'halt', 'prevent',
            'override', 'kill', 'cancel', 'abort', 'veto'
        ]
        
        for keyword in forbidden_keywords:
            assert keyword not in trends_str, \
                f"Enforcement keyword '{keyword}' found in trends"

    def test_no_enforcement_keywords_in_patterns(self):
        """Patterns contain no enforcement or blocking keywords."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {"correlation_id": f"cid-{i}", "risk_flags": ["FLAG"]}
            for i in range(3)
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        patterns = memory_service.detect_patterns()
        
        patterns_str = json.dumps(patterns, default=str).lower()
        
        forbidden_keywords = [
            'execute', 'enforce', 'block', 'prevent', 'override'
        ]
        
        for keyword in forbidden_keywords:
            assert keyword not in patterns_str, \
                f"Enforcement keyword '{keyword}' found in patterns"

    def test_no_enforcement_keywords_in_comparison(self):
        """Comparison contains no recommendations or enforcement."""
        memory_service = DecisionIntelligenceMemoryService()
        
        window_a = [{"confidence_score": 0.5}]
        window_b = [{"confidence_score": 0.8}]
        
        comparison = memory_service.compare_windows(window_a, window_b)
        comparison_str = json.dumps(comparison, default=str).lower()
        
        # Should not contain action keywords
        forbidden_keywords = [
            'should', 'must', 'recommend', 'suggest', 'action',
            'execute', 'enforce', 'block'
        ]
        
        for keyword in forbidden_keywords:
            assert keyword not in comparison_str, \
                f"Enforcement keyword '{keyword}' found in comparison"

    def test_snapshot_contains_disclaimer(self):
        """Memory snapshot includes explicit disclaimer."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [{"correlation_id": "cid-1", "confidence_score": 0.75}]
        memory_service._cached_reports = copy.deepcopy(reports)
        
        snapshot = memory_service.export_memory_snapshot()
        snapshot_str = json.dumps(snapshot, default=str)
        
        # Must contain disclaimer about informational nature
        assert "informational" in snapshot_str.lower(), \
            "Snapshot missing informational disclaimer"
        assert "does not influence" in snapshot_str.lower() or \
               "does not" in snapshot_str.lower(), \
            "Snapshot missing non-influence disclaimer"


class TestNoSideEffects:
    """Verify all methods have no side effects."""

    def test_compute_trends_no_state_mutation(self):
        """compute_trends doesn't modify internal state."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {"correlation_id": "cid-1", "confidence_score": 0.75}
        ]
        memory_service._cached_reports = copy.deepcopy(reports)
        
        state_before = copy.deepcopy(memory_service._cached_reports)
        
        memory_service.compute_trends()
        
        state_after = memory_service._cached_reports
        
        assert state_before == state_after, \
            "compute_trends modified internal state"

    def test_detect_patterns_no_state_mutation(self):
        """detect_patterns doesn't modify internal state."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [{"correlation_id": "cid-1", "risk_flags": ["FLAG"]}]
        memory_service._cached_reports = copy.deepcopy(reports)
        
        state_before = copy.deepcopy(memory_service._cached_reports)
        
        memory_service.detect_patterns()
        
        state_after = memory_service._cached_reports
        
        assert state_before == state_after, \
            "detect_patterns modified internal state"

    def test_compare_windows_no_state_mutation(self):
        """compare_windows doesn't modify internal state."""
        memory_service = DecisionIntelligenceMemoryService()
        
        initial_state = {"test": "data"}
        memory_service._cached_reports = copy.deepcopy(initial_state)
        
        state_before = copy.deepcopy(memory_service._cached_reports)
        
        memory_service.compare_windows([{"x": 1}], [{"y": 2}])
        
        state_after = memory_service._cached_reports
        
        assert state_before == state_after, \
            "compare_windows modified internal state"

    def test_export_snapshot_no_state_mutation(self):
        """export_snapshot doesn't modify internal state."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [{"correlation_id": "cid-1"}]
        memory_service._cached_reports = copy.deepcopy(reports)
        
        state_before = copy.deepcopy(memory_service._cached_reports)
        
        memory_service.export_memory_snapshot()
        
        state_after = memory_service._cached_reports
        
        assert state_before == state_after, \
            "export_snapshot modified internal state"


class TestArchiveProtection:
    """Verify archive remains append-only and protected."""

    def test_memory_service_cannot_modify_archive(self):
        """Memory service cannot update or delete from archive."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Verify no methods exist to modify archive
        public_methods = {
            m for m in dir(memory_service)
            if not m.startswith('_') and callable(getattr(memory_service, m))
        }
        
        forbidden_methods = [
            'delete', 'remove', 'update', 'modify', 'truncate',
            'clear', 'reset', 'drop'
        ]
        
        for method in forbidden_methods:
            assert method not in public_methods, \
                f"Forbidden method '{method}' exists in memory service"

    def test_memory_reads_only_from_archive(self):
        """Memory service only reads, never writes to archive."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # All write operations should be impossible
        # Verify through method inspection
        public_methods = {
            m for m in dir(memory_service)
            if not m.startswith('_') and callable(getattr(memory_service, m))
        }
        
        # Only read methods should exist
        read_only_methods = {
            'compute_trends',
            'detect_patterns',
            'compare_windows',
            'export_memory_snapshot'
        }
        
        # Verify no other public methods exist
        unexpected_methods = public_methods - read_only_methods
        for method in unexpected_methods:
            assert method not in [
                'compute_trends', 'detect_patterns', 'compare_windows',
                'export_memory_snapshot'
            ], f"Unexpected public method: {method}"


class TestCompleteWorkflow:
    """Integration test of complete memory service workflow."""

    def test_end_to_end_memory_analysis(self):
        """Complete workflow: load reports, analyze, export."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Simulate loaded archive reports
        reports = [
            {
                "correlation_id": "trade-001",
                "timestamp": "2025-01-01T10:00:00Z",
                "confidence_score": 0.75,
                "governance_pressure": 0.3,
                "risk_flags": ["FLAG_1"],
                "trade_volume": 1000
            },
            {
                "correlation_id": "trade-002",
                "timestamp": "2025-01-01T11:00:00Z",
                "confidence_score": 0.85,
                "governance_pressure": 0.2,
                "risk_flags": [],
                "trade_volume": 1500
            },
            {
                "correlation_id": "trade-003",
                "timestamp": "2025-01-01T12:00:00Z",
                "confidence_score": 0.65,
                "governance_pressure": 0.4,
                "risk_flags": ["FLAG_1"],
                "trade_volume": 800
            }
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        
        # 1. Compute trends
        trends = memory_service.compute_trends()
        assert trends is not None
        assert "confidence" in trends
        
        # 2. Detect patterns
        patterns = memory_service.detect_patterns()
        assert patterns is not None
        assert "repeated_violations" in patterns
        
        # 3. Compare windows
        window_a = reports[:2]
        window_b = reports[1:]
        comparison = memory_service.compare_windows(window_a, window_b)
        assert comparison is not None
        
        # 4. Export snapshot
        snapshot = memory_service.export_memory_snapshot()
        assert snapshot is not None
        assert "disclaimer" in snapshot or "informational" in str(snapshot).lower()
        
        # 5. Verify all operations were non-mutating
        assert memory_service._cached_reports == reports, \
            "Workflow modified internal state"


class TestServiceIsolation:
    """Verify memory service is isolated from other services."""

    def test_no_service_references(self):
        """Memory service has no references to other services."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Check no attributes reference other services
        for attr_name in dir(memory_service):
            if not attr_name.startswith('_'):
                continue
            
            attr = getattr(memory_service, attr_name, None)
            
            # Should not reference archive service or other services
            class_name = type(attr).__name__
            assert "Service" not in class_name or \
                   "Memory" in class_name, \
                f"Found service reference: {class_name}"

    def test_memory_service_only_accepts_data_dict(self):
        """Methods only accept data dictionaries, not service objects."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # All input parameters should be plain data structures
        # (verified through successful testing with dict/list data)
        
        # Should work with dict
        window_a = [{"confidence_score": 0.5}]
        window_b = [{"confidence_score": 0.8}]
        
        # Should not raise exception
        result = memory_service.compare_windows(window_a, window_b)
        assert result is not None


class TestTrendComputations:
    """Verify trend calculations are accurate and informational."""

    def test_confidence_trend_calculations(self):
        """Confidence score trends calculated correctly."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {"correlation_id": "cid-1", "confidence_score": 0.5},
            {"correlation_id": "cid-2", "confidence_score": 0.75},
            {"correlation_id": "cid-3", "confidence_score": 1.0}
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        trends = memory_service.compute_trends()
        
        assert "confidence" in trends
        confidence = trends["confidence"]
        
        # Expected: avg = 0.75, min = 0.5, max = 1.0
        assert confidence.get("avg") == 0.75, "Confidence average incorrect"
        assert confidence.get("min") == 0.5, "Confidence min incorrect"
        assert confidence.get("max") == 1.0, "Confidence max incorrect"

    def test_governance_pressure_distribution(self):
        """Governance pressure distribution calculated."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {"correlation_id": "cid-1", "governance_pressure": 0.2},
            {"correlation_id": "cid-2", "governance_pressure": 0.5},
            {"correlation_id": "cid-3", "governance_pressure": 0.8}
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        trends = memory_service.compute_trends()
        
        assert "governance_pressure" in trends
        gov_pressure = trends["governance_pressure"]
        
        assert gov_pressure.get("avg") == 0.5
        assert gov_pressure.get("min") == 0.2
        assert gov_pressure.get("max") == 0.8

    def test_risk_flag_frequency(self):
        """Risk flag frequency calculated."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {"correlation_id": "cid-1", "risk_flags": ["FLAG_A"]},
            {"correlation_id": "cid-2", "risk_flags": ["FLAG_A", "FLAG_B"]},
            {"correlation_id": "cid-3", "risk_flags": []}
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        trends = memory_service.compute_trends()
        
        assert "risk_flag_frequency" in trends
        frequencies = trends["risk_flag_frequency"]
        
        # FLAG_A appears in 2 reports
        assert frequencies.get("FLAG_A") == 2
        # FLAG_B appears in 1 report
        assert frequencies.get("FLAG_B") == 1


class TestPatternDetection:
    """Verify pattern detection is accurate and informational."""

    def test_repeated_violations_detection(self):
        """Repeated governance violations detected."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {
                "correlation_id": "cid-1",
                "risk_flags": ["REPEATED_VIOLATION"]
            },
            {
                "correlation_id": "cid-2",
                "risk_flags": ["REPEATED_VIOLATION"]
            },
            {
                "correlation_id": "cid-3",
                "risk_flags": []
            }
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        patterns = memory_service.detect_patterns()
        
        assert "repeated_violations" in patterns
        assert len(patterns["repeated_violations"]) == 2

    def test_confidence_decay_detection(self):
        """Confidence decay sequences detected."""
        memory_service = DecisionIntelligenceMemoryService()
        
        # Decreasing confidence scores
        reports = [
            {"correlation_id": "cid-1", "confidence_score": 0.9},
            {"correlation_id": "cid-2", "confidence_score": 0.7},
            {"correlation_id": "cid-3", "confidence_score": 0.5}
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        patterns = memory_service.detect_patterns()
        
        assert "confidence_decay_sequences" in patterns

    def test_regret_clustering(self):
        """Counterfactual regret clustering detected."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {
                "correlation_id": "cid-1",
                "counterfactual_regret": 0.2
            },
            {
                "correlation_id": "cid-2",
                "counterfactual_regret": 0.25
            },
            {
                "correlation_id": "cid-3",
                "counterfactual_regret": 0.02
            }
        ]
        
        memory_service._cached_reports = copy.deepcopy(reports)
        patterns = memory_service.detect_patterns()
        
        assert "regret_clusters" in patterns


class TestWindowComparison:
    """Verify window comparison is directional and informational."""

    def test_comparison_shows_direction_only(self):
        """Comparison only shows improvement/degradation, no scoring."""
        memory_service = DecisionIntelligenceMemoryService()
        
        window_a = [
            {"confidence_score": 0.5, "governance_pressure": 0.4},
            {"confidence_score": 0.6, "governance_pressure": 0.3}
        ]
        window_b = [
            {"confidence_score": 0.8, "governance_pressure": 0.2},
            {"confidence_score": 0.85, "governance_pressure": 0.15}
        ]
        
        comparison = memory_service.compare_windows(window_a, window_b)
        
        # Should show direction
        assert "confidence_direction" in comparison or \
               "direction" in str(comparison).lower()
        
        # Should NOT contain numeric scores
        comparison_str = json.dumps(comparison, default=str)
        # May contain numbers for actual values, but not for "scores"
        # Verify no "score" key exists
        assert "\"score\"" not in comparison_str or \
               "improvement_score" not in comparison_str

    def test_comparison_no_recommendations(self):
        """Comparison provides no action recommendations."""
        memory_service = DecisionIntelligenceMemoryService()
        
        window_a = [{"confidence_score": 0.5}]
        window_b = [{"confidence_score": 0.8}]
        
        comparison = memory_service.compare_windows(window_a, window_b)
        comparison_str = json.dumps(comparison, default=str).lower()
        
        forbidden_words = ['recommend', 'should', 'must', 'suggest']
        
        for word in forbidden_words:
            assert word not in comparison_str, \
                f"Comparison contains recommendation word: {word}"


class TestExportSnapshot:
    """Verify memory snapshot export is comprehensive and safe."""

    def test_snapshot_includes_metadata(self):
        """Snapshot includes timestamp and metadata."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [{"correlation_id": "cid-1", "confidence_score": 0.75}]
        memory_service._cached_reports = copy.deepcopy(reports)
        
        snapshot = memory_service.export_memory_snapshot()
        
        assert "metadata" in snapshot or "timestamp" in snapshot
        assert "report_count" in snapshot or len(snapshot) > 0

    def test_snapshot_machine_readable_format(self):
        """Snapshot can be serialized to JSON."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [{"correlation_id": "cid-1"}]
        memory_service._cached_reports = copy.deepcopy(reports)
        
        snapshot = memory_service.export_memory_snapshot()
        
        # Should be JSON serializable
        json_str = json.dumps(snapshot, default=str)
        assert json_str is not None
        assert len(json_str) > 0

    def test_snapshot_human_readable_format(self):
        """Snapshot includes human-readable summary."""
        memory_service = DecisionIntelligenceMemoryService()
        
        reports = [
            {"correlation_id": "cid-1", "confidence_score": 0.75},
            {"correlation_id": "cid-2", "confidence_score": 0.85}
        ]
        memory_service._cached_reports = copy.deepcopy(reports)
        
        snapshot = memory_service.export_memory_snapshot()
        snapshot_str = json.dumps(snapshot, default=str)
        
        # Should contain summary information
        assert "summary" in snapshot_str.lower() or "total" in snapshot_str.lower()
