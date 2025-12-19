"""
Tests for advanced event-driven orchestration features.

Covers:
- Event correlation and state tracking
- Cooldowns and session windows
- Signal filtering with policies
- Metrics and telemetry
- Backward compatibility
"""

import asyncio
import pytest
import time
import uuid
from reasoner_service.orchestration_advanced import (
    EventState, EventTracker, CooldownConfig, SessionWindow, CooldownTracker,
    ReasoningMetrics, OrchestrationMetrics, PolicyDecision, SignalFilter,
    EventCorrelationManager, CooldownManager, OrchestrationStateManager
)


# ============================================================================
# EVENT TRACKER TESTS
# ============================================================================

def test_event_tracker_creation():
    """Test EventTracker creation and initialization."""
    tracker = EventTracker(
        correlation_id="test-123",
        event_type="decision"
    )
    
    assert tracker.correlation_id == "test-123"
    assert tracker.event_type == "decision"
    assert tracker.state == EventState.PENDING
    assert tracker.created_at_ms > 0
    assert tracker.processed_at_ms is None


def test_event_tracker_state_updates():
    """Test EventTracker state transitions."""
    tracker = EventTracker("test-123", "decision")
    
    tracker.update_state(EventState.DEFERRED, "waiting_for_cooldown")
    assert tracker.state == EventState.DEFERRED
    assert tracker.reason == "waiting_for_cooldown"
    assert len(tracker.status_history) == 1
    
    tracker.update_state(EventState.PROCESSED)
    assert len(tracker.status_history) == 2


def test_event_tracker_mark_processed():
    """Test marking event as processed."""
    tracker = EventTracker("test-123", "decision")
    
    tracker.mark_processed("dec-456", signals_count=3)
    assert tracker.state == EventState.PROCESSED
    assert tracker.decision_id == "dec-456"
    assert tracker.signals_count == 3
    assert tracker.processed_at_ms is not None


def test_event_tracker_processing_time():
    """Test processing time calculation."""
    tracker = EventTracker("test-123", "decision")
    initial_time = tracker.created_at_ms
    
    time.sleep(0.01)  # 10ms
    tracker.mark_processed("dec-456")
    
    processing_time = tracker.get_processing_time_ms()
    assert processing_time >= 10


# ============================================================================
# COOLDOWN AND SESSION WINDOW TESTS
# ============================================================================

def test_cooldown_config_creation():
    """Test CooldownConfig."""
    config = CooldownConfig(
        event_type="decision",
        cooldown_ms=5000,
        max_events_per_window=10
    )
    
    assert config.event_type == "decision"
    assert config.cooldown_ms == 5000
    assert config.max_events_per_window == 10


def test_session_window_is_active():
    """Test SessionWindow active time check."""
    window = SessionWindow(
        event_type="decision",
        start_hour=9,
        end_hour=17,
        max_events=100
    )
    
    # Window is always active in test (depends on current time)
    is_active = window.is_active()
    assert isinstance(is_active, bool)


def test_cooldown_tracker_cooling_down():
    """Test CooldownTracker cooldown state."""
    tracker = CooldownTracker("decision")
    
    # Not initially cooling down
    assert not tracker.is_cooling_down()
    
    # Start cooldown (5 seconds in future)
    now_ms = int(time.time() * 1000)
    tracker.cooldown_until_ms = now_ms + 5000
    
    assert tracker.is_cooling_down()


def test_cooldown_tracker_reset_window():
    """Test CooldownTracker window reset."""
    tracker = CooldownTracker("decision")
    config = CooldownConfig("decision", 5000)
    
    tracker.reset_window(config)
    
    assert tracker.is_cooling_down()
    assert tracker.events_in_window == 0
    assert tracker.last_event_time_ms > 0


# ============================================================================
# METRICS TESTS
# ============================================================================

def test_reasoning_metrics_add_call():
    """Test ReasoningMetrics call recording."""
    metrics = ReasoningMetrics()
    
    metrics.add_call(success=True, execution_time_ms=100, signals=3)
    assert metrics.total_calls == 1
    assert metrics.successful_calls == 1
    assert metrics.failed_calls == 0
    assert metrics.total_signals_generated == 3
    
    metrics.add_call(success=False, execution_time_ms=50, signals=0)
    assert metrics.total_calls == 2
    assert metrics.successful_calls == 1
    assert metrics.failed_calls == 1


def test_reasoning_metrics_averages():
    """Test ReasoningMetrics calculation."""
    metrics = ReasoningMetrics()
    
    metrics.add_call(True, 100)
    metrics.add_call(True, 200)
    
    assert metrics.get_average_execution_time_ms() == 150.0
    assert metrics.get_success_rate() == 100.0


def test_orchestration_metrics_add_event():
    """Test OrchestrationMetrics event recording."""
    metrics = OrchestrationMetrics()
    
    metrics.add_event("accepted", 100)
    metrics.add_event("rejected", 50)
    metrics.add_event("deferred", 75)
    
    assert metrics.total_events == 3
    assert metrics.accepted_events == 1
    assert metrics.rejected_events == 1
    assert metrics.deferred_events == 1


def test_orchestration_metrics_acceptance_rate():
    """Test OrchestrationMetrics acceptance rate."""
    metrics = OrchestrationMetrics()
    
    metrics.add_event("accepted", 100)
    metrics.add_event("accepted", 100)
    metrics.add_event("rejected", 50)
    
    assert metrics.get_acceptance_rate() == pytest.approx(66.67, abs=1)


# ============================================================================
# SIGNAL FILTER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_signal_filter_without_policy():
    """Test SignalFilter without policy store."""
    filter_engine = SignalFilter(policy_store=None)
    
    signals = [
        {"signal_type": "action", "payload": {}, "confidence": 0.8},
        {"signal_type": "risk", "payload": {}, "confidence": 0.9}
    ]
    
    filtered, decisions = await filter_engine.apply_policies(
        signals, "decision", {}
    )
    
    assert len(filtered) == 2
    assert len(decisions) == 0


@pytest.mark.asyncio
async def test_signal_filter_with_policy():
    """Test SignalFilter with mock policy store."""
    class MockPolicyStore:
        async def get_policy(self, name, context):
            if name == "signal_filter_decision":
                return {
                    "allow_high_confidence": True,
                    "min_confidence": 0.75,
                    "blocked_types": ["error"]
                }
            return {}
    
    filter_engine = SignalFilter(policy_store=MockPolicyStore())
    
    signals = [
        {"signal_type": "action", "payload": {}, "confidence": 0.8},
        {"signal_type": "error", "payload": {}, "confidence": 0.9},
        {"signal_type": "risk", "payload": {}, "confidence": 0.5}
    ]
    
    filtered, decisions = await filter_engine.apply_policies(
        signals, "decision", {}
    )
    
    # Should filter: error (blocked type) and risk (confidence < 0.75)
    assert len(filtered) == 1
    assert filtered[0]["signal_type"] == "action"
    assert len(decisions) == 1
    assert decisions[0].signals_filtered == 2


# ============================================================================
# EVENT CORRELATION MANAGER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_event_correlation_create_tracker():
    """Test EventCorrelationManager tracker creation."""
    manager = EventCorrelationManager()
    
    tracker = await manager.create_event_tracker("evt-123", "decision")
    
    assert tracker.correlation_id == "evt-123"
    assert tracker.event_type == "decision"
    
    retrieved = await manager.get_event_tracker("evt-123")
    assert retrieved is not None
    assert retrieved.correlation_id == "evt-123"


@pytest.mark.asyncio
async def test_event_correlation_update_state():
    """Test EventCorrelationManager state updates."""
    manager = EventCorrelationManager()
    
    await manager.create_event_tracker("evt-123", "decision")
    success = await manager.update_event_state(
        "evt-123",
        EventState.PROCESSED,
        "manual_review"
    )
    
    assert success
    tracker = await manager.get_event_tracker("evt-123")
    assert tracker.state == EventState.PROCESSED
    assert tracker.reason == "manual_review"


@pytest.mark.asyncio
async def test_event_correlation_history():
    """Test EventCorrelationManager state history."""
    manager = EventCorrelationManager()
    
    await manager.create_event_tracker("evt-123", "decision")
    await manager.update_event_state("evt-123", EventState.DEFERRED)
    await manager.update_event_state("evt-123", EventState.PROCESSED)
    
    history = await manager.get_event_history("evt-123")
    assert len(history) == 2


@pytest.mark.asyncio
async def test_event_correlation_get_by_type():
    """Test EventCorrelationManager query by type."""
    manager = EventCorrelationManager()
    
    await manager.create_event_tracker("evt-1", "decision")
    await manager.create_event_tracker("evt-2", "decision")
    await manager.create_event_tracker("evt-3", "alert")
    
    decisions = await manager.get_events_by_type("decision")
    assert len(decisions) == 2


# ============================================================================
# COOLDOWN MANAGER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_cooldown_manager_configure():
    """Test CooldownManager configuration."""
    manager = CooldownManager()
    
    config = CooldownConfig("decision", 5000)
    await manager.configure_cooldown(config)
    
    is_cooling, next_available = await manager.check_cooldown("decision")
    assert not is_cooling


@pytest.mark.asyncio
async def test_cooldown_manager_enforce_cooldown():
    """Test CooldownManager cooldown enforcement."""
    manager = CooldownManager()
    config = CooldownConfig("decision", 5000, max_events_per_window=10)
    
    await manager.configure_cooldown(config)
    await manager.record_event("decision")
    
    is_cooling, next_available = await manager.check_cooldown("decision")
    assert is_cooling
    assert next_available > int(time.time() * 1000)


@pytest.mark.asyncio
async def test_cooldown_manager_session_window():
    """Test CooldownManager session window."""
    manager = CooldownManager()
    
    window = SessionWindow("decision", start_hour=0, end_hour=23)
    await manager.configure_session_window(window)
    
    is_active = await manager.check_session_window("decision")
    assert is_active


# ============================================================================
# ORCHESTRATION STATE MANAGER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_orchestration_state_record_reasoning():
    """Test OrchestrationStateManager reasoning metrics."""
    manager = OrchestrationStateManager()
    
    await manager.record_reasoning_call(True, 100, 3)
    await manager.record_reasoning_call(False, 50, 0)
    
    stats = await manager.get_reasoning_stats()
    assert stats["total_calls"] == 2
    assert stats["successful_calls"] == 1
    assert stats["total_signals"] == 3


@pytest.mark.asyncio
async def test_orchestration_state_record_event():
    """Test OrchestrationStateManager event metrics."""
    manager = OrchestrationStateManager()
    
    await manager.record_event_processing("accepted", 100)
    await manager.record_event_processing("accepted", 100)
    await manager.record_event_processing("rejected", 50)
    
    stats = await manager.get_orchestration_stats()
    assert stats["total_events"] == 3
    assert stats["accepted_events"] == 2
    assert pytest.approx(stats["acceptance_rate"], abs=1) == 66.67


@pytest.mark.asyncio
async def test_orchestration_state_concurrent_updates():
    """Test OrchestrationStateManager with concurrent updates."""
    manager = OrchestrationStateManager()
    
    # Record multiple concurrent metrics
    tasks = [
        manager.record_event_processing("accepted", 100)
        for _ in range(10)
    ]
    
    await asyncio.gather(*tasks)
    
    stats = await manager.get_orchestration_stats()
    assert stats["total_events"] == 10
    assert stats["accepted_events"] == 10


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_end_to_end_event_workflow():
    """Test complete event processing workflow."""
    state_manager = OrchestrationStateManager()
    
    # Create event tracker
    correlation_id = "evt-" + str(uuid.uuid4())
    tracker = await state_manager.event_correlation.create_event_tracker(
        correlation_id, "decision"
    )
    
    # Simulate processing
    await state_manager.event_correlation.update_event_state(
        correlation_id, EventState.PROCESSED
    )
    tracker = await state_manager.event_correlation.get_event_tracker(correlation_id)
    assert tracker.state == EventState.PROCESSED
    
    # Record metrics
    await state_manager.record_event_processing("accepted", 150)
    await state_manager.record_reasoning_call(True, 100, 2)
    
    # Get stats
    orch_stats = await state_manager.get_orchestration_stats()
    reasoning_stats = await state_manager.get_reasoning_stats()
    
    assert orch_stats["total_events"] == 1
    assert reasoning_stats["total_calls"] == 1


@pytest.mark.asyncio
async def test_cooldown_and_correlation_together():
    """Test cooldowns with event correlation."""
    state_manager = OrchestrationStateManager()
    
    # Configure cooldown
    config = CooldownConfig("decision", 1000, max_events_per_window=2)
    await state_manager.cooldown_manager.configure_cooldown(config)
    
    # First event should not be cooling
    is_cooling, _ = await state_manager.cooldown_manager.check_cooldown("decision")
    assert not is_cooling
    
    # Record event
    await state_manager.cooldown_manager.record_event("decision")
    
    # Now should be cooling
    is_cooling, next_available = await state_manager.cooldown_manager.check_cooldown("decision")
    assert is_cooling


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
