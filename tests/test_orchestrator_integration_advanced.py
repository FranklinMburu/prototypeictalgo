"""
Integration tests for DecisionOrchestrator with advanced orchestration.

Demonstrates:
- Event correlation tracking
- Cooldown and session window enforcement
- Signal filtering with policies
- Metrics collection
- Backward compatibility
"""

import asyncio
import pytest
import time
import uuid
from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.orchestrator_events import Event, EventResult
from reasoner_service.reasoning_manager import ReasoningManager


@pytest.fixture
async def orchestrator_with_reasoning():
    """Create orchestrator with reasoning manager."""
    orch = DecisionOrchestrator()
    
    # Create simple reasoning modes
    async def default_mode(payload, context, timeout_ms):
        return [
            {
                "signal_type": "info",
                "payload": {"source": "default_mode"},
                "confidence": 0.8
            }
        ]
    
    manager = ReasoningManager(
        modes={"default": default_mode},
        timeout_ms=2000
    )
    orch.reasoning_manager = manager
    
    yield orch
    try:
        await orch.close()
    except Exception:
        pass


@pytest.mark.asyncio
async def test_orchestrator_with_cooldown_config(orchestrator_with_reasoning):
    """Test orchestrator cooldown configuration."""
    orch = orchestrator_with_reasoning
    
    # Configure cooldown for decision events
    await orch.configure_cooldown("decision", cooldown_ms=1000)
    
    # Verify cooldown manager has configuration
    is_cooling, next_available = await orch.orchestration_state.cooldown_manager.check_cooldown(
        "decision"
    )
    assert not is_cooling  # Not yet cooling


@pytest.mark.asyncio
async def test_orchestrator_event_correlation_tracking(orchestrator_with_reasoning):
    """Test event correlation tracking."""
    orch = orchestrator_with_reasoning
    
    # Create event tracker
    correlation_id = "evt-" + str(uuid.uuid4())
    tracker = await orch.orchestration_state.event_correlation.create_event_tracker(
        correlation_id, "decision"
    )
    
    assert tracker.correlation_id == correlation_id
    assert tracker.event_type == "decision"
    
    # Retrieve tracker
    retrieved = await orch.orchestration_state.event_correlation.get_event_tracker(
        correlation_id
    )
    assert retrieved is not None


@pytest.mark.asyncio
async def test_orchestrator_session_window_config(orchestrator_with_reasoning):
    """Test orchestrator session window configuration."""
    orch = orchestrator_with_reasoning
    
    # Configure session window (always active)
    await orch.configure_session_window(
        "decision",
        start_hour=0,
        end_hour=23,
        max_events=100
    )
    
    # Check window
    is_active = await orch.orchestration_state.cooldown_manager.check_session_window(
        "decision"
    )
    assert is_active


@pytest.mark.asyncio
async def test_orchestrator_metrics_recording(orchestrator_with_reasoning):
    """Test metrics recording."""
    orch = orchestrator_with_reasoning
    
    # Record some events
    await orch._record_event_metrics("accepted", processing_time_ms=100, reasoning_time_ms=50)
    await orch._record_event_metrics("accepted", processing_time_ms=120, reasoning_time_ms=60)
    await orch._record_event_metrics("rejected", processing_time_ms=80, reasoning_time_ms=0)
    
    # Get metrics
    metrics = await orch.get_orchestration_metrics()
    
    assert metrics["orchestration"]["total_events"] == 3
    assert metrics["orchestration"]["accepted_events"] == 2
    assert metrics["reasoning"]["total_calls"] == 2


@pytest.mark.asyncio
async def test_orchestrator_check_event_constraints(orchestrator_with_reasoning):
    """Test event constraint checking."""
    orch = orchestrator_with_reasoning
    
    # No constraints configured yet
    allowed, reason, next_available = await orch._check_event_constraints("decision")
    assert allowed
    assert reason is None
    
    # Configure and test cooldown
    await orch.configure_cooldown("decision", cooldown_ms=5000)
    await orch.orchestration_state.cooldown_manager.record_event("decision")
    
    # Now should be in cooldown
    allowed, reason, next_available = await orch._check_event_constraints("decision")
    assert not allowed
    assert reason == "cooldown_active"
    assert next_available is not None


@pytest.mark.asyncio
async def test_orchestrator_signal_filtering(orchestrator_with_reasoning):
    """Test signal filtering with policy store."""
    orch = orchestrator_with_reasoning
    
    # Create mock policy store
    class MockPolicyStore:
        async def get_policy(self, name, context):
            if name == "signal_filter_decision":
                return {
                    "min_confidence": 0.7,
                    "blocked_types": ["error"]
                }
            return {}
    
    mock_store = MockPolicyStore()
    orch.signal_filter = orch.signal_filter.__class__(policy_store=mock_store)
    
    signals = [
        {"signal_type": "action", "confidence": 0.8},
        {"signal_type": "error", "confidence": 0.9},
        {"signal_type": "warning", "confidence": 0.5}
    ]
    
    filtered, decisions = await orch._apply_signal_filters(
        signals, "decision", {}
    )
    
    # Should filter: error (blocked) and warning (low confidence)
    assert len(filtered) == 1
    assert filtered[0]["signal_type"] == "action"


@pytest.mark.asyncio
async def test_orchestrator_backward_compatibility(orchestrator_with_reasoning):
    """Test backward compatibility of EventResult."""
    orch = orchestrator_with_reasoning
    
    result = EventResult(
        status="accepted",
        reason=None,
        decision_id="dec-123",
        metadata={"test": "value"}
    )
    
    # Old fields should work
    assert result.status == "accepted"
    assert result.decision_id == "dec-123"
    assert result.metadata == {"test": "value"}
    
    # New fields should be optional
    assert result.event_state is None
    assert result.correlation_id is None
    assert result.policy_decisions == []


@pytest.mark.asyncio
async def test_orchestrator_event_result_with_advanced_fields():
    """Test EventResult with advanced orchestration fields."""
    result = EventResult(
        status="accepted",
        decision_id="dec-123",
        event_state="processed",
        correlation_id="evt-456",
        processing_time_ms=150,
        policy_decisions=[
            {
                "policy": "test_policy",
                "decision": "pass",
                "timestamp_ms": int(time.time() * 1000)
            }
        ],
        state_transitions=[
            ("pending", int(time.time() * 1000)),
            ("processed", int(time.time() * 1000))
        ]
    )
    
    assert result.event_state == "processed"
    assert result.correlation_id == "evt-456"
    assert result.processing_time_ms == 150
    assert len(result.policy_decisions) == 1
    assert len(result.state_transitions) == 2


@pytest.mark.asyncio
async def test_orchestrator_event_types_with_state():
    """Test new event status 'escalated'."""
    result = EventResult(
        status="escalated",
        reason="manual_intervention_required",
        decision_id="dec-123"
    )
    
    assert result.status == "escalated"


@pytest.mark.asyncio
async def test_end_to_end_orchestration_workflow(orchestrator_with_reasoning):
    """End-to-end workflow with advanced orchestration."""
    orch = orchestrator_with_reasoning
    
    # Configure constraints
    await orch.configure_cooldown("decision", cooldown_ms=2000)
    await orch.configure_session_window("decision", start_hour=0, end_hour=23, max_events=100)
    
    # Create event
    event = Event(
        event_type="decision",
        payload={
            "id": str(uuid.uuid4()),
            "symbol": "BTC",
            "recommendation": "BUY",
            "confidence": 0.85
        },
        timestamp=int(time.time() * 1000),
        correlation_id=str(uuid.uuid4())
    )
    
    # Check constraints before processing
    allowed, reason, next_avail = await orch._check_event_constraints("decision")
    assert allowed
    
    # Record event in correlation tracker
    tracker = await orch.orchestration_state.event_correlation.create_event_tracker(
        event.correlation_id, event.event_type
    )
    
    assert tracker is not None
    assert tracker.state.value == "pending"
    
    # Record processing
    await orch._record_event_metrics("accepted", processing_time_ms=150, reasoning_time_ms=75)
    
    # Check metrics
    metrics = await orch.get_orchestration_metrics()
    assert metrics["orchestration"]["total_events"] == 1
    assert metrics["reasoning"]["total_calls"] == 1


@pytest.mark.asyncio
async def test_concurrent_event_tracking(orchestrator_with_reasoning):
    """Test concurrent event tracking."""
    orch = orchestrator_with_reasoning
    
    # Create multiple events concurrently
    tasks = [
        orch.orchestration_state.event_correlation.create_event_tracker(
            f"evt-{i}", "decision"
        )
        for i in range(10)
    ]
    
    trackers = await asyncio.gather(*tasks)
    
    assert len(trackers) == 10
    assert all(t is not None for t in trackers)
    
    # Query by type
    decision_events = await orch.orchestration_state.event_correlation.get_events_by_type(
        "decision"
    )
    assert len(decision_events) == 10


@pytest.mark.asyncio
async def test_metrics_under_load(orchestrator_with_reasoning):
    """Test metrics recording under concurrent load."""
    orch = orchestrator_with_reasoning
    
    # Record many events concurrently
    tasks = [
        orch._record_event_metrics(
            "accepted" if i % 2 == 0 else "rejected",
            processing_time_ms=100 + i,
            reasoning_time_ms=50 + i if i % 2 == 0 else 0
        )
        for i in range(50)
    ]
    
    await asyncio.gather(*tasks)
    
    # Verify metrics
    metrics = await orch.get_orchestration_metrics()
    assert metrics["orchestration"]["total_events"] == 50
    assert metrics["orchestration"]["accepted_events"] == 25
    assert metrics["orchestration"]["rejected_events"] == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
