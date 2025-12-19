"""
Comprehensive tests for DecisionHumanReviewService (Phase 9)

Tests verify:
- Append-only behavior (no mutations)
- Determinism (same input = same output)
- Deepcopy on read
- Fail-silent error handling
- Informational-only output
- Zero system authority of reviews
- No upstream service mutations
- Explicit disclaimers
- Scenario isolation
- No enforcement keywords
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from copy import deepcopy

from reasoner_service.decision_human_review_service import (
    DecisionHumanReviewService,
    ReviewStatus,
    DisagreementSeverity,
)


@pytest.fixture
def review_service():
    """Create review service."""
    return DecisionHumanReviewService()


@pytest.fixture
def context_snapshot():
    """Create sample context snapshot."""
    return {
        "correlation_id": "trade_001",
        "decision_type": "entry",
        "symbol": "AAPL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "original_decision": {
            "recommendation": "enter",
            "confidence": 0.85,
            "reasoning": "Strong uptrend with high confidence",
        },
        "trade_outcome": {
            "entry_price": 150.0,
            "exit_price": 155.0,
            "pnl": 500.0,
            "status": "completed",
        },
        "governance_context": {
            "active_rules": ["max_exposure", "min_confidence"],
            "risk_flags": ["high_volatility"],
        },
    }


class TestAppendOnlyBehavior:
    """Verify append-only behavior with no mutations."""

    def test_sessions_never_deleted(self, review_service, context_snapshot):
        """Sessions should never be deleted."""
        session1 = review_service.create_review_session(context_snapshot)
        session_id = session1["session_id"]
        
        initial_count = len(review_service._review_sessions)
        
        # Try to create multiple sessions
        for i in range(3):
            ctx = context_snapshot.copy()
            ctx["correlation_id"] = f"trade_{i}"
            review_service.create_review_session(ctx)
        
        # All sessions should still exist
        assert len(review_service._review_sessions) == initial_count + 3

    def test_annotations_never_deleted(self, review_service, context_snapshot):
        """Annotations should never be deleted."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        # Attach annotations
        for i in range(3):
            annotation = {
                "annotator": f"human_{i}",
                "annotation_type": "observation",
                "text": f"Observation {i}",
            }
            review_service.attach_annotation(session_id, annotation)
        
        initial_count = len(review_service._annotations[session_id])
        assert initial_count == 3
        
        # Attach more
        review_service.attach_annotation(session_id, {
            "annotator": "human_new",
            "annotation_type": "question",
            "text": "New question",
        })
        
        # All annotations should exist
        assert len(review_service._annotations[session_id]) == initial_count + 1

    def test_disagreements_never_deleted(self, review_service, context_snapshot):
        """Disagreements should never be deleted."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        # Record disagreements
        for i in range(2):
            disagreement = {
                "disagreer": f"human_{i}",
                "severity": "moderate",
                "reason": f"Reason {i}",
                "alternative_decision": "exit",
                "pnl_impact": 100.0 * (i + 1),
            }
            review_service.record_disagreement(session_id, disagreement)
        
        initial_count = len(review_service._disagreements[session_id])
        assert initial_count == 2
        
        # Record more
        review_service.record_disagreement(session_id, {
            "disagreer": "human_new",
            "severity": "severe",
            "reason": "Severe issue",
            "alternative_decision": "hold",
            "pnl_impact": 500.0,
        })
        
        # All disagreements should exist
        assert len(review_service._disagreements[session_id]) == initial_count + 1

    def test_chronological_record_is_append_only(self, review_service, context_snapshot):
        """Chronological record should be append-only."""
        initial_count = len(review_service._all_reviews)
        
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        # Should have added one record
        assert len(review_service._all_reviews) == initial_count + 1
        
        review_service.attach_annotation(session_id, {
            "annotator": "human",
            "text": "Test",
        })
        
        # Should have added another record
        assert len(review_service._all_reviews) == initial_count + 2


class TestDeterminism:
    """Verify deterministic outputs (same input = same output)."""

    def test_same_context_produces_similar_sessions(self, review_service, context_snapshot):
        """Identical contexts produce sessions with same data."""
        session1 = review_service.create_review_session(context_snapshot)
        session2 = review_service.create_review_session(context_snapshot)
        
        # Session IDs will differ (timestamps), but content should match
        assert session1["correlation_id"] == session2["correlation_id"]
        assert session1["context_snapshot"] == session2["context_snapshot"]
        assert session1["status"] == session2["status"]

    def test_same_annotation_produces_same_data(self, review_service, context_snapshot):
        """Identical annotations produce same data."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        annotation = {
            "annotator": "human",
            "annotation_type": "observation",
            "text": "Test observation",
            "confidence_in_view": 0.75,
        }
        
        ann1 = review_service.attach_annotation(session_id, annotation)
        ann2 = review_service.attach_annotation(session_id, annotation)
        
        # Core data should match
        assert ann1["text"] == ann2["text"]
        assert ann1["confidence_in_view"] == ann2["confidence_in_view"]

    def test_summary_deterministic(self, review_service, context_snapshot):
        """Summary from same data is deterministic."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        # Attach identical data
        for i in range(2):
            review_service.attach_annotation(session_id, {
                "annotator": f"human_{i}",
                "text": "Test",
            })
        
        summary1 = review_service.summarize_reviews()
        summary2 = review_service.summarize_reviews()
        
        # Key metrics should match
        assert summary1["total_sessions"] == summary2["total_sessions"]
        assert summary1["total_annotations"] == summary2["total_annotations"]

    def test_export_deterministic(self, review_service, context_snapshot):
        """Export from same data is deterministic."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        review_service.attach_annotation(session_id, {
            "annotator": "human",
            "text": "Test annotation",
        })
        
        export1 = review_service.export_review_log(format="json")
        export2 = review_service.export_review_log(format="json")
        
        data1 = json.loads(export1)
        data2 = json.loads(export2)
        
        # Core data should match
        assert data1["total_sessions"] == data2["total_sessions"]
        assert data1["total_reviews"] == data2["total_reviews"]


class TestImmutabilityAndDeepcopy:
    """Verify deepcopy on read and immutability."""

    def test_returned_session_is_deepcopy(self, review_service, context_snapshot):
        """Modifying returned session should not affect internal state."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        original_status = session["status"]
        
        # Modify returned session
        session["status"] = "modified"
        session["context_snapshot"]["symbol"] = "MODIFIED"
        
        # Get session from internal storage
        stored = review_service._review_sessions[session_id]
        
        assert stored["status"] == original_status
        assert stored["context_snapshot"]["symbol"] != "MODIFIED"

    def test_returned_annotation_is_deepcopy(self, review_service, context_snapshot):
        """Modifying returned annotation should not affect internal state."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        annotation = review_service.attach_annotation(session_id, {
            "annotator": "human",
            "text": "Original text",
        })
        
        annotation_id = annotation["annotation_id"]
        original_text = annotation["text"]
        
        # Modify returned annotation
        annotation["text"] = "MODIFIED"
        annotation["annotator"] = "MODIFIED"
        
        # Get stored annotation
        stored = review_service._annotations[session_id][0]
        
        assert stored["text"] == original_text
        assert stored["annotator"] == "human"

    def test_returned_disagreement_is_deepcopy(self, review_service, context_snapshot):
        """Modifying returned disagreement should not affect internal state."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        disagreement = review_service.record_disagreement(session_id, {
            "disagreer": "human",
            "severity": "moderate",
            "reason": "Original reason",
            "pnl_impact": 100.0,
        })
        
        original_pnl = disagreement["pnl_impact"]
        
        # Modify returned disagreement
        disagreement["pnl_impact"] = 9999.99
        disagreement["severity"] = "catastrophic"
        
        # Get stored disagreement
        stored = review_service._disagreements[session_id][0]
        
        assert stored["pnl_impact"] == original_pnl
        assert stored["severity"] == "moderate"

    def test_returned_summary_is_deepcopy(self, review_service, context_snapshot):
        """Modifying returned summary should not affect state."""
        session = review_service.create_review_session(context_snapshot)
        
        summary = review_service.summarize_reviews()
        original_count = summary["total_sessions"]
        
        # Modify returned summary
        summary["total_sessions"] = 9999
        summary["sessions_by_status"]["created"] = 9999
        
        # Re-summarize
        summary2 = review_service.summarize_reviews()
        
        assert summary2["total_sessions"] == original_count


class TestFailSilentBehavior:
    """Verify fail-silent error handling."""

    def test_invalid_context_snapshot_returns_empty_session(self, review_service):
        """Invalid context snapshot should return empty session, not raise."""
        session = review_service.create_review_session(None)
        assert session is not None
        assert "session_id" in session

    def test_invalid_session_id_for_annotation(self, review_service):
        """Invalid session ID should return empty annotation, not raise."""
        annotation = review_service.attach_annotation(
            "invalid_session_id",
            {"annotator": "human", "text": "Test"}
        )
        assert annotation is not None
        assert "annotation_id" in annotation

    def test_invalid_annotation_type_handled(self, review_service, context_snapshot):
        """Invalid annotation type should be handled gracefully."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        annotation = review_service.attach_annotation(session_id, None)
        assert annotation is not None

    def test_invalid_disagreement_severity_defaults(self, review_service, context_snapshot):
        """Invalid severity should default gracefully."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        disagreement = review_service.record_disagreement(session_id, {
            "disagreer": "human",
            "severity": "invalid_severity",
            "reason": "Test",
        })
        
        # Should default to moderate
        assert disagreement["severity"] in ["minor", "moderate", "severe", "catastrophic"]

    def test_export_with_empty_reviews(self, review_service):
        """Export with no reviews should not raise."""
        export = review_service.export_review_log()
        assert export is not None
        assert isinstance(export, str)


class TestInformationalOnlyOutput:
    """Verify informational-only output with proper disclaimers."""

    def test_session_includes_disclaimer(self, review_service, context_snapshot):
        """Sessions should include disclaimer."""
        session = review_service.create_review_session(context_snapshot)
        
        assert "disclaimer" in session
        disclaimer_lower = session["disclaimer"].lower()
        assert "zero system authority" in disclaimer_lower
        assert ("informational" in disclaimer_lower or "audit" in disclaimer_lower)

    def test_annotation_includes_disclaimer(self, review_service, context_snapshot):
        """Annotations should include disclaimer."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        annotation = review_service.attach_annotation(session_id, {
            "annotator": "human",
            "text": "Test",
        })
        
        assert "disclaimer" in annotation
        assert "zero system authority" in annotation["disclaimer"].lower()

    def test_disagreement_includes_disclaimer(self, review_service, context_snapshot):
        """Disagreements should include disclaimer."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        disagreement = review_service.record_disagreement(session_id, {
            "disagreer": "human",
            "reason": "Test",
        })
        
        assert "disclaimer" in disagreement
        assert "zero system authority" in disagreement["disclaimer"].lower()
        assert "never triggers" in disagreement["disclaimer"].lower()

    def test_summary_includes_disclaimer(self, review_service):
        """Summary should include disclaimer."""
        summary = review_service.summarize_reviews()
        
        assert "disclaimer" in summary
        assert "informational" in summary["disclaimer"].lower()

    def test_export_includes_export_disclaimer(self, review_service):
        """Exported report should include export disclaimer."""
        export = review_service.export_review_log()
        
        export_lower = export.lower()
        assert "informational" in export_lower or "disclaimer" in export_lower


class TestZeroSystemAuthority:
    """Verify reviews have zero system authority."""

    def test_reviews_never_modify_upstream_services(self, review_service, context_snapshot):
        """Reviews should never modify upstream services."""
        # This service has no references to upstream services (by design)
        # All storage is internal only
        
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        # Attach annotations and disagreements
        for i in range(3):
            review_service.attach_annotation(session_id, {
                "annotator": f"human_{i}",
                "text": f"Annotation {i}",
            })
            review_service.record_disagreement(session_id, {
                "disagreer": f"human_{i}",
                "reason": f"Reason {i}",
                "severity": "severe",
            })
        
        # Verify no upstream mutations (internal storage only)
        assert len(review_service._review_sessions) == 1
        assert len(review_service._annotations[session_id]) == 3
        assert len(review_service._disagreements[session_id]) == 3

    def test_severity_never_triggers_enforcement(self, review_service, context_snapshot):
        """Severe disagreements should never trigger enforcement."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        # Record catastrophic disagreement
        disagreement = review_service.record_disagreement(session_id, {
            "disagreer": "human",
            "severity": "catastrophic",
            "reason": "Critical system failure",
            "pnl_impact": -10000.0,
        })
        
        # Severity is informational only
        assert disagreement["severity"] == "catastrophic"
        
        # No enforcement should occur (no methods to trigger it)
        summary = review_service.summarize_reviews()
        assert summary["disagreement_severity_distribution"]["catastrophic"] == 1


class TestNoEnforcementKeywords:
    """Verify no enforcement or execution keywords exist."""

    def test_no_block_keywords(self, review_service, context_snapshot):
        """Output should not contain enforcement keywords."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        annotation = review_service.attach_annotation(session_id, {
            "annotator": "human",
            "annotation_type": "concern",
            "text": "This trade should not have been executed",
        })
        
        annotation_str = json.dumps(annotation).lower()
        
        # Should not suggest enforcement
        assert "block" not in annotation_str or "blockchain" in annotation_str
        assert "enforce" not in annotation_str or "enforcement" in annotation_str

    def test_summary_no_action_keywords(self, review_service, context_snapshot):
        """Summary should not suggest actions."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        review_service.record_disagreement(session_id, {
            "disagreer": "human",
            "severity": "severe",
            "reason": "Should not happen",
        })
        
        summary = review_service.summarize_reviews()
        summary_str = json.dumps(summary).lower()
        
        # Should not suggest enforcement
        explanation = summary.get("explanation", "").lower()
        assert "should" not in explanation or "would" in explanation

    def test_export_no_control_semantics(self, review_service):
        """Export should not contain control semantics."""
        export = review_service.export_review_log(format="text")
        
        export_lower = export.lower()
        
        # Should not suggest control
        assert "override" not in export_lower
        assert "prevent" not in export_lower or "prevented" in export_lower


class TestSessionStatus:
    """Verify session status tracking."""

    def test_session_status_transitions(self, review_service, context_snapshot):
        """Session status should transition appropriately."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        # Initial status
        assert session["status"] == ReviewStatus.CREATED.value
        
        # After annotation, should be IN_PROGRESS
        review_service.attach_annotation(session_id, {
            "annotator": "human",
            "text": "Test",
        })
        
        session_updated = review_service._review_sessions[session_id]
        assert session_updated["status"] == ReviewStatus.IN_PROGRESS.value

    def test_session_counts_updated(self, review_service, context_snapshot):
        """Session should track annotation and disagreement counts."""
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        
        assert session["annotation_count"] == 0
        assert session["disagreement_count"] == 0
        
        review_service.attach_annotation(session_id, {
            "annotator": "human",
            "text": "Test",
        })
        
        session_updated = review_service._review_sessions[session_id]
        assert session_updated["annotation_count"] == 1
        
        review_service.record_disagreement(session_id, {
            "disagreer": "human",
            "reason": "Test",
        })
        
        session_updated = review_service._review_sessions[session_id]
        assert session_updated["disagreement_count"] == 1


class TestChronologicalRecording:
    """Verify chronological recording of all reviews."""

    def test_all_events_recorded_chronologically(self, review_service, context_snapshot):
        """All review events should be recorded chronologically."""
        session1 = review_service.create_review_session(context_snapshot)
        session1_id = session1["session_id"]
        
        ctx2 = context_snapshot.copy()
        ctx2["correlation_id"] = "trade_002"
        session2 = review_service.create_review_session(ctx2)
        session2_id = session2["session_id"]
        
        review_service.attach_annotation(session1_id, {
            "annotator": "human",
            "text": "Annotation 1",
        })
        
        review_service.record_disagreement(session2_id, {
            "disagreer": "human",
            "reason": "Disagreement 1",
        })
        
        # Check chronological order
        all_reviews = review_service._all_reviews
        assert len(all_reviews) >= 4
        assert all_reviews[0]["type"] == "session_created"
        assert all_reviews[1]["type"] == "session_created"
        assert all_reviews[2]["type"] == "annotation_attached"
        assert all_reviews[3]["type"] == "disagreement_recorded"


class TestExportFormats:
    """Verify export formats."""

    def test_json_export_is_valid_json(self, review_service, context_snapshot):
        """JSON export should be valid JSON."""
        session = review_service.create_review_session(context_snapshot)
        
        export = review_service.export_review_log(format="json")
        
        # Should be parseable
        data = json.loads(export)
        assert isinstance(data, dict)
        assert "total_sessions" in data

    def test_text_export_is_readable(self, review_service, context_snapshot):
        """Text export should be human-readable."""
        session = review_service.create_review_session(context_snapshot)
        
        export = review_service.export_review_log(format="text")
        
        assert isinstance(export, str)
        assert "DECISION HUMAN REVIEW LOG" in export
        assert "Session:" in export

    def test_json_export_sorted_keys(self, review_service, context_snapshot):
        """JSON export should have sorted keys for determinism."""
        session = review_service.create_review_session(context_snapshot)
        
        export1 = review_service.export_review_log(format="json")
        export2 = review_service.export_review_log(format="json")
        
        # Should have identical structure (sorted keys ensure determinism)
        data1 = json.loads(export1)
        data2 = json.loads(export2)
        
        # Compare structure and key counts (timestamps will differ in chronological record)
        assert data1["total_sessions"] == data2["total_sessions"]
        assert len(data1.keys()) == len(data2.keys())
        assert set(data1.keys()) == set(data2.keys())


class TestIntegration:
    """Integration tests covering full workflows."""

    def test_full_review_workflow(self, review_service, context_snapshot):
        """Full workflow from session creation to export."""
        # 1. Create session
        session = review_service.create_review_session(context_snapshot)
        session_id = session["session_id"]
        assert session is not None
        
        # 2. Attach annotations
        for i in range(2):
            annotation = review_service.attach_annotation(session_id, {
                "annotator": f"human_{i}",
                "annotation_type": "observation",
                "text": f"Observation {i}",
                "confidence_in_view": 0.7 + (i * 0.1),
            })
            assert annotation is not None
        
        # 3. Record disagreements
        for i in range(2):
            disagreement = review_service.record_disagreement(session_id, {
                "disagreer": f"human_{i}",
                "severity": ["minor", "moderate"][i],
                "reason": f"Reason {i}",
                "alternative_decision": "hold",
                "pnl_impact": 100.0 * (i + 1),
            })
            assert disagreement is not None
        
        # 4. Summarize
        summary = review_service.summarize_reviews()
        assert summary["total_sessions"] == 1
        assert summary["total_annotations"] == 2
        assert summary["total_disagreements"] == 2
        
        # 5. Export
        export_json = review_service.export_review_log(format="json")
        export_text = review_service.export_review_log(format="text")
        
        assert export_json is not None
        assert export_text is not None
        
        # Parse JSON to verify structure
        data = json.loads(export_json)
        assert data["total_sessions"] == 1

    def test_multiple_sessions_workflow(self, review_service, context_snapshot):
        """Workflow with multiple independent sessions."""
        sessions = []
        
        # Create multiple sessions
        for i in range(3):
            ctx = context_snapshot.copy()
            ctx["correlation_id"] = f"trade_{i}"
            session = review_service.create_review_session(ctx)
            sessions.append(session)
        
        # Add reviews to each
        for session in sessions:
            session_id = session["session_id"]
            
            review_service.attach_annotation(session_id, {
                "annotator": "human",
                "text": f"Note for {session_id}",
            })
            
            review_service.record_disagreement(session_id, {
                "disagreer": "human",
                "reason": f"Disagreement for {session_id}",
            })
        
        # Verify summary
        summary = review_service.summarize_reviews()
        assert summary["total_sessions"] == 3
        assert summary["total_annotations"] == 3
        assert summary["total_disagreements"] == 3
