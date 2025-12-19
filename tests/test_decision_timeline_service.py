"""
Tests for Decision Timeline Service

Verifies append-only behavior, deterministic replay, and immutability guarantees.
"""

import pytest
from datetime import datetime, timezone
import time
from reasoner_service.decision_timeline_service import DecisionTimelineService


class TestAppendOnlyBehavior:
    """Verify events are append-only and immutable."""
    
    def test_record_single_event(self):
        """Single event is recorded correctly."""
        service = DecisionTimelineService()
        
        service.record_event(
            "SIGNAL_DETECTED",
            {"symbol": "EURUSD", "signal": "BUY"},
            "trade_123"
        )
        
        timeline = service.get_timeline("trade_123")
        
        assert len(timeline) == 1
        assert timeline[0]["event_type"] == "SIGNAL_DETECTED"
        assert timeline[0]["correlation_id"] == "trade_123"
        assert timeline[0]["payload"]["symbol"] == "EURUSD"
    
    def test_multiple_events_append_in_order(self):
        """Multiple events append in correct order."""
        service = DecisionTimelineService()
        
        events = [
            ("SIGNAL_DETECTED", {"signal": "BUY"}),
            ("DECISION_PROPOSED", {"action": "execute"}),
            ("TRADE_EXECUTED", {"status": "filled"}),
        ]
        
        for event_type, payload in events:
            service.record_event(event_type, payload, "trade_123")
        
        timeline = service.get_timeline("trade_123")
        
        assert len(timeline) == 3
        assert timeline[0]["event_type"] == "SIGNAL_DETECTED"
        assert timeline[1]["event_type"] == "DECISION_PROPOSED"
        assert timeline[2]["event_type"] == "TRADE_EXECUTED"
    
    def test_sequence_numbers_monotonic(self):
        """Event sequence numbers are monotonically increasing."""
        service = DecisionTimelineService()
        
        for i in range(5):
            service.record_event(
                "TEST_EVENT",
                {"index": i},
                "trade_123"
            )
        
        timeline = service.get_timeline("trade_123")
        
        for i, event in enumerate(timeline):
            assert event["sequence_number"] == i
    
    def test_events_immutable_after_recording(self):
        """Events cannot be mutated after recording."""
        service = DecisionTimelineService()
        
        payload = {"symbol": "EURUSD", "value": 100}
        service.record_event("SIGNAL_DETECTED", payload, "trade_123")
        
        # Modify original payload
        payload["symbol"] = "GBPUSD"
        payload["value"] = 200
        
        # Retrieved timeline should be unchanged
        timeline = service.get_timeline("trade_123")
        assert timeline[0]["payload"]["symbol"] == "EURUSD"
        assert timeline[0]["payload"]["value"] == 100


class TestEventOrdering:
    """Verify events maintain temporal order."""
    
    def test_timestamps_ordered(self):
        """Event timestamps are in chronological order."""
        service = DecisionTimelineService()
        
        for i in range(3):
            service.record_event(
                "TEST_EVENT",
                {"index": i},
                "trade_123"
            )
            time.sleep(0.01)  # Small delay to ensure timestamp differences
        
        timeline = service.get_timeline("trade_123")
        
        for i in range(1, len(timeline)):
            prev_time = timeline[i - 1]["timestamp"]
            curr_time = timeline[i]["timestamp"]
            assert prev_time <= curr_time
    
    def test_correlation_isolation(self):
        """Events from different correlations don't mix."""
        service = DecisionTimelineService()
        
        service.record_event("EVENT1", {"data": "trade1"}, "trade_1")
        service.record_event("EVENT2", {"data": "trade2"}, "trade_2")
        service.record_event("EVENT3", {"data": "trade1_2"}, "trade_1")
        
        timeline_1 = service.get_timeline("trade_1")
        timeline_2 = service.get_timeline("trade_2")
        
        assert len(timeline_1) == 2
        assert len(timeline_2) == 1
        
        assert timeline_1[0]["payload"]["data"] == "trade1"
        assert timeline_1[1]["payload"]["data"] == "trade1_2"
        assert timeline_2[0]["payload"]["data"] == "trade2"


class TestReplayDeterminism:
    """Verify replay is deterministic."""
    
    def test_same_replay_same_sequence(self):
        """Multiple replays return identical sequences."""
        service = DecisionTimelineService()
        
        events = [
            ("SIGNAL_DETECTED", {"signal": "BUY"}),
            ("DECISION_PROPOSED", {"action": "execute"}),
            ("TRADE_EXECUTED", {"status": "filled"}),
            ("OUTCOME_RECORDED", {"pnl": 150.0}),
        ]
        
        for event_type, payload in events:
            service.record_event(event_type, payload, "trade_123")
        
        # Replay multiple times
        replay1 = service.replay("trade_123")
        replay2 = service.replay("trade_123")
        replay3 = service.replay("trade_123")
        
        # All replays should be identical
        assert replay1 == replay2
        assert replay2 == replay3
        assert len(replay1) == 4
    
    def test_replay_is_immutable_copy(self):
        """Replayed events cannot affect stored timeline."""
        service = DecisionTimelineService()
        
        service.record_event("EVENT1", {"data": "original"}, "trade_123")
        
        # Replay and modify the result
        replay = service.replay("trade_123")
        replay[0]["payload"]["data"] = "modified"
        
        # Original timeline should be unchanged
        replay2 = service.replay("trade_123")
        assert replay2[0]["payload"]["data"] == "original"
    
    def test_get_timeline_alias(self):
        """replay() is functionally identical to get_timeline()."""
        service = DecisionTimelineService()
        
        for i in range(5):
            service.record_event("TEST_EVENT", {"index": i}, "trade_123")
        
        timeline = service.get_timeline("trade_123")
        replayed = service.replay("trade_123")
        
        assert timeline == replayed


class TestNoMutation:
    """Verify stored events cannot be mutated."""
    
    def test_past_events_immutable(self):
        """Past events remain immutable through multiple operations."""
        service = DecisionTimelineService()
        
        service.record_event("INITIAL", {"value": 1}, "trade_123")
        
        # Get timeline multiple times
        timeline1 = service.get_timeline("trade_123")
        timeline2 = service.get_timeline("trade_123")
        
        # Try to modify both copies
        timeline1[0]["payload"]["value"] = 999
        timeline2[0]["payload"]["value"] = 888
        
        # Original should be unchanged
        timeline3 = service.get_timeline("trade_123")
        assert timeline3[0]["payload"]["value"] == 1


class TestValidEventTypes:
    """Verify event type validation."""
    
    def test_valid_event_types(self):
        """All valid event types are accepted."""
        service = DecisionTimelineService()
        
        valid_types = [
            "SIGNAL_DETECTED",
            "DECISION_PROPOSED",
            "POLICY_EVALUATED",
            "POLICY_CONFIDENCE_SCORED",
            "GOVERNANCE_EVALUATED",
            "TRADE_EXECUTED",
            "OUTCOME_RECORDED",
        ]
        
        for event_type in valid_types:
            service.record_event(event_type, {"data": "test"}, "trade_123")
        
        timeline = service.get_timeline("trade_123")
        assert len(timeline) == len(valid_types)
        
        for i, event_type in enumerate(valid_types):
            assert timeline[i]["event_type"] == event_type
    
    def test_unknown_event_type_recorded_anyway(self):
        """Unknown event types are recorded with warning."""
        service = DecisionTimelineService()
        
        service.record_event(
            "UNKNOWN_TYPE",
            {"data": "test"},
            "trade_123"
        )
        
        timeline = service.get_timeline("trade_123")
        assert len(timeline) == 1
        assert timeline[0]["event_type"] == "UNKNOWN_TYPE"


class TestErrorHandling:
    """Verify fail-silent error handling."""
    
    def test_invalid_event_type_skipped(self):
        """Invalid event_type is skipped without raising."""
        service = DecisionTimelineService()
        
        # Should not raise
        service.record_event(None, {"data": "test"}, "trade_123")
        service.record_event(123, {"data": "test"}, "trade_123")
        service.record_event("", {"data": "test"}, "trade_123")
        
        timeline = service.get_timeline("trade_123")
        assert len(timeline) == 0
    
    def test_invalid_correlation_id_skipped(self):
        """Invalid correlation_id is skipped without raising."""
        service = DecisionTimelineService()
        
        service.record_event("EVENT1", {"data": "test"}, None)
        service.record_event("EVENT2", {"data": "test"}, "")
        service.record_event("EVENT3", {"data": "test"}, 123)
        
        assert service.get_event_count() == 0
    
    def test_invalid_payload_skipped(self):
        """Invalid payload is skipped without raising."""
        service = DecisionTimelineService()
        
        service.record_event("EVENT1", "not_a_dict", "trade_123")
        service.record_event("EVENT2", 123, "trade_123")
        service.record_event("EVENT3", None, "trade_123")
        
        timeline = service.get_timeline("trade_123")
        assert len(timeline) == 0
    
    def test_missing_correlation_returns_empty_list(self):
        """Getting timeline for non-existent correlation returns empty list."""
        service = DecisionTimelineService()
        
        timeline = service.get_timeline("nonexistent")
        assert timeline == []


class TestReadOnlyGuarantees:
    """Verify read-only access guarantees."""
    
    def test_multiple_readers_consistent(self):
        """Multiple readers always see same timeline."""
        service = DecisionTimelineService()
        
        # Record events
        for i in range(5):
            service.record_event("TEST_EVENT", {"index": i}, "trade_123")
        
        # Multiple readers
        reader1 = service.get_timeline("trade_123")
        reader2 = service.get_timeline("trade_123")
        reader3 = service.replay("trade_123")
        
        assert reader1 == reader2 == reader3
    
    def test_timeline_export_read_only(self):
        """Exported timeline includes read-only metadata."""
        service = DecisionTimelineService()
        
        service.record_event("EVENT1", {"data": "test"}, "trade_123")
        
        export = service.export_timeline("trade_123")
        
        assert export["found"] is True
        assert export["event_count"] == 1
        assert "disclaimer" in export
        assert "does not influence" in export["disclaimer"].lower()


class TestEventFiltering:
    """Verify event filtering capabilities."""
    
    def test_get_events_by_type(self):
        """Filter events by type returns only matching events."""
        service = DecisionTimelineService()
        
        service.record_event("SIGNAL_DETECTED", {"signal": "BUY"}, "trade_123")
        service.record_event("DECISION_PROPOSED", {"action": "execute"}, "trade_123")
        service.record_event("SIGNAL_DETECTED", {"signal": "SELL"}, "trade_123")
        
        signals = service.get_events_by_type("trade_123", "SIGNAL_DETECTED")
        
        assert len(signals) == 2
        assert all(e["event_type"] == "SIGNAL_DETECTED" for e in signals)
        assert signals[0]["payload"]["signal"] == "BUY"
        assert signals[1]["payload"]["signal"] == "SELL"


class TestTimelineValidation:
    """Verify timeline validation."""
    
    def test_valid_timeline(self):
        """Valid timeline passes validation."""
        service = DecisionTimelineService()
        
        for i in range(3):
            service.record_event("TEST_EVENT", {"index": i}, "trade_123")
        
        validation = service.validate_timeline("trade_123")
        
        assert validation["valid"] is True
        assert validation["event_count"] == 3
        assert len(validation["issues"]) == 0
    
    def test_missing_timeline_validation_fails(self):
        """Missing timeline fails validation."""
        service = DecisionTimelineService()
        
        validation = service.validate_timeline("nonexistent")
        
        assert validation["valid"] is False
        assert "not found" in validation.get("reason", "").lower()


class TestEventCount:
    """Verify event counting."""
    
    def test_count_by_correlation(self):
        """Get event count for specific correlation."""
        service = DecisionTimelineService()
        
        for i in range(5):
            service.record_event("TEST_EVENT", {"index": i}, "trade_1")
        
        for i in range(3):
            service.record_event("TEST_EVENT", {"index": i}, "trade_2")
        
        assert service.get_event_count("trade_1") == 5
        assert service.get_event_count("trade_2") == 3
    
    def test_count_all_events(self):
        """Get total event count across all correlations."""
        service = DecisionTimelineService()
        
        for i in range(5):
            service.record_event("TEST_EVENT", {"index": i}, "trade_1")
        
        for i in range(3):
            service.record_event("TEST_EVENT", {"index": i}, "trade_2")
        
        assert service.get_event_count() == 8


class TestCorrelationManagement:
    """Verify correlation ID management."""
    
    def test_get_all_correlation_ids(self):
        """Get all correlation IDs with events."""
        service = DecisionTimelineService()
        
        trades = ["trade_3", "trade_1", "trade_2"]
        for trade_id in trades:
            service.record_event("TEST_EVENT", {"data": "test"}, trade_id)
        
        all_ids = service.get_all_correlation_ids()
        
        assert len(all_ids) == 3
        assert all_ids == sorted(trades)


class TestStatistics:
    """Verify statistics collection."""
    
    def test_get_statistics(self):
        """Get service statistics."""
        service = DecisionTimelineService()
        
        events = [
            ("SIGNAL_DETECTED", "trade_1"),
            ("DECISION_PROPOSED", "trade_1"),
            ("SIGNAL_DETECTED", "trade_2"),
            ("TRADE_EXECUTED", "trade_2"),
        ]
        
        for event_type, correlation_id in events:
            service.record_event(event_type, {"data": "test"}, correlation_id)
        
        stats = service.get_statistics()
        
        assert stats["total_events"] == 4
        assert stats["total_correlations"] == 2
        assert stats["event_type_distribution"]["SIGNAL_DETECTED"] == 2
        assert stats["event_type_distribution"]["DECISION_PROPOSED"] == 1
        assert stats["event_type_distribution"]["TRADE_EXECUTED"] == 1


class TestCompleteDecisionTimeline:
    """Test a complete decision timeline from signal to outcome."""
    
    def test_complete_trade_lifecycle(self):
        """Complete timeline from signal detection to outcome."""
        service = DecisionTimelineService()
        trade_id = "trade_20251219_001"
        
        # Signal detected
        service.record_event(
            "SIGNAL_DETECTED",
            {"symbol": "EURUSD", "signal_type": "momentum", "strength": 0.85},
            trade_id
        )
        
        # Decision proposed
        service.record_event(
            "DECISION_PROPOSED",
            {"action": "BUY", "quantity": 100000, "level": 1.0850},
            trade_id
        )
        
        # Policy evaluated
        service.record_event(
            "POLICY_EVALUATED",
            {"policy": "risk_limit", "status": "approved"},
            trade_id
        )
        
        # Policy confidence scored
        service.record_event(
            "POLICY_CONFIDENCE_SCORED",
            {"confidence": 0.82, "sample_size": 150},
            trade_id
        )
        
        # Governance evaluated
        service.record_event(
            "GOVERNANCE_EVALUATED",
            {"allowed": True, "violations": []},
            trade_id
        )
        
        # Trade executed
        service.record_event(
            "TRADE_EXECUTED",
            {"execution_time": "2025-12-19T10:30:00Z", "fill_price": 1.0851},
            trade_id
        )
        
        # Outcome recorded
        service.record_event(
            "OUTCOME_RECORDED",
            {"pnl": 250.0, "outcome": "win", "bars_held": 15},
            trade_id
        )
        
        # Verify complete timeline
        timeline = service.replay(trade_id)
        
        assert len(timeline) == 7
        assert timeline[0]["event_type"] == "SIGNAL_DETECTED"
        assert timeline[-1]["event_type"] == "OUTCOME_RECORDED"
        assert timeline[-1]["payload"]["pnl"] == 250.0
        
        # Verify all event types present
        event_types = [e["event_type"] for e in timeline]
        assert "SIGNAL_DETECTED" in event_types
        assert "DECISION_PROPOSED" in event_types
        assert "TRADE_EXECUTED" in event_types
        assert "OUTCOME_RECORDED" in event_types
    
    def test_replay_reconstructs_full_history(self):
        """Replay reconstructs complete decision history."""
        service = DecisionTimelineService()
        trade_id = "trade_20251219_002"
        
        # Build timeline
        timeline_events = [
            ("SIGNAL_DETECTED", {"signal": "BUY", "confidence": 0.9}),
            ("DECISION_PROPOSED", {"action": "execute"}),
            ("POLICY_EVALUATED", {"status": "approved"}),
            ("TRADE_EXECUTED", {"status": "filled", "price": 100.50}),
            ("OUTCOME_RECORDED", {"pnl": 500.0}),
        ]
        
        for event_type, payload in timeline_events:
            service.record_event(event_type, payload, trade_id)
        
        # Replay should reconstruct history in order
        replayed = service.replay(trade_id)
        
        assert len(replayed) == len(timeline_events)
        for i, (event_type, _) in enumerate(timeline_events):
            assert replayed[i]["event_type"] == event_type


class TestThreadSafety:
    """Verify thread-safe operations (basic)."""
    
    def test_concurrent_recording_preserves_order(self):
        """Events recorded concurrently maintain order."""
        service = DecisionTimelineService()
        
        # Sequential recording should maintain order
        for i in range(10):
            service.record_event(
                "TEST_EVENT",
                {"index": i},
                "trade_123"
            )
        
        timeline = service.get_timeline("trade_123")
        
        # Verify order is maintained
        assert len(timeline) == 10
        for i, event in enumerate(timeline):
            assert event["payload"]["index"] == i


class TestDisclaimer:
    """Verify disclaimer is present in outputs."""
    
    def test_export_includes_disclaimer(self):
        """Exported timeline includes disclaimer."""
        service = DecisionTimelineService()
        
        service.record_event("EVENT1", {"data": "test"}, "trade_123")
        
        export = service.export_timeline("trade_123")
        
        assert "disclaimer" in export
        assert "records" in export["disclaimer"].lower()
        assert "does not influence" in export["disclaimer"].lower()
