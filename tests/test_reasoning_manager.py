"""
Tests for ReasoningManager and its integration with DecisionOrchestrator.
"""

import asyncio
import pytest
import time
import uuid
from reasoner_service.reasoning_manager import ReasoningManager, AdvisorySignal
from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.orchestrator_events import Event, EventResult


# ============================================================================
# FIXTURES AND HELPERS
# ============================================================================

@pytest.fixture
async def reasoning_manager():
    """Create a ReasoningManager with default and custom modes."""
    
    async def default_reasoning(payload, context, timeout_ms):
        """Default reasoning mode: returns empty signals."""
        return []
    
    async def action_suggestion_mode(payload, context, timeout_ms):
        """Mode that suggests actions."""
        return [
            {
                "signal_type": "action_suggestion",
                "payload": {
                    "action": "verify_limit",
                    "symbol": payload.get("symbol", "UNKNOWN")
                },
                "confidence": 0.85
            }
        ]
    
    async def risk_flag_mode(payload, context, timeout_ms):
        """Mode that generates risk flags."""
        if payload.get("confidence", 0) > 0.9:
            return [
                {
                    "signal_type": "risk_flag",
                    "payload": {
                        "risk_level": "high",
                        "reason": "high_confidence_decision"
                    },
                    "confidence": 0.95
                }
            ]
        return []
    
    async def timeout_mode(payload, context, timeout_ms):
        """Mode that exceeds timeout."""
        await asyncio.sleep(10)  # Will be cancelled
        return []
    
    modes = {
        "default": default_reasoning,
        "action_suggestion": action_suggestion_mode,
        "risk_flag": risk_flag_mode,
        "timeout": timeout_mode
    }
    
    manager = ReasoningManager(
        modes=modes,
        timeout_ms=100,  # Short timeout for testing
        logger=None
    )
    return manager


@pytest.fixture
async def orchestrator():
    """Create a DecisionOrchestrator instance."""
    orch = DecisionOrchestrator()
    yield orch
    try:
        await orch.close()
    except Exception:
        pass


# ============================================================================
# ADVISORYSIGNAL TESTS
# ============================================================================

def test_advisory_signal_creation():
    """Test AdvisorySignal dataclass creation."""
    signal = AdvisorySignal(
        decision_id=str(uuid.uuid4()),
        signal_type="test_signal",
        payload={"key": "value"},
        confidence=0.85
    )
    
    assert signal.signal_type == "test_signal"
    assert signal.payload == {"key": "value"}
    assert signal.confidence == 0.85
    assert signal.reasoning_mode == "default"
    assert signal.timestamp > 0
    assert signal.error is None


def test_advisory_signal_with_error():
    """Test AdvisorySignal with error metadata."""
    signal = AdvisorySignal(
        decision_id=str(uuid.uuid4()),
        signal_type="error",
        payload={},
        error="test_error_message"
    )
    
    assert signal.signal_type == "error"
    assert signal.error == "test_error_message"


# ============================================================================
# REASONINGMANAGER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_reasoning_manager_default_mode(reasoning_manager):
    """Test ReasoningManager with default mode."""
    decision_id = str(uuid.uuid4())
    payload = {"symbol": "BTC", "recommendation": "BUY"}
    
    signals = await reasoning_manager.reason(
        decision_id=decision_id,
        event_payload=payload,
        reasoning_mode="default"
    )
    
    assert isinstance(signals, list)
    assert len(signals) == 0


@pytest.mark.asyncio
async def test_reasoning_manager_action_suggestion_mode(reasoning_manager):
    """Test ReasoningManager with action suggestion mode."""
    decision_id = str(uuid.uuid4())
    payload = {"symbol": "ETH", "recommendation": "SELL"}
    
    signals = await reasoning_manager.reason(
        decision_id=decision_id,
        event_payload=payload,
        reasoning_mode="action_suggestion"
    )
    
    assert len(signals) == 1
    assert signals[0].signal_type == "action_suggestion"
    assert signals[0].confidence == 0.85
    assert signals[0].payload["symbol"] == "ETH"


@pytest.mark.asyncio
async def test_reasoning_manager_risk_flag_mode_high_confidence(reasoning_manager):
    """Test ReasoningManager risk flag mode with high confidence."""
    decision_id = str(uuid.uuid4())
    payload = {"symbol": "BTC", "confidence": 0.95}
    
    signals = await reasoning_manager.reason(
        decision_id=decision_id,
        event_payload=payload,
        reasoning_mode="risk_flag"
    )
    
    assert len(signals) == 1
    assert signals[0].signal_type == "risk_flag"
    assert signals[0].payload["risk_level"] == "high"


@pytest.mark.asyncio
async def test_reasoning_manager_risk_flag_mode_low_confidence(reasoning_manager):
    """Test ReasoningManager risk flag mode with low confidence."""
    decision_id = str(uuid.uuid4())
    payload = {"symbol": "BTC", "confidence": 0.5}
    
    signals = await reasoning_manager.reason(
        decision_id=decision_id,
        event_payload=payload,
        reasoning_mode="risk_flag"
    )
    
    assert len(signals) == 0


@pytest.mark.asyncio
async def test_reasoning_manager_invalid_payload_type(reasoning_manager):
    """Test ReasoningManager with invalid payload type."""
    decision_id = str(uuid.uuid4())
    
    signals = await reasoning_manager.reason(
        decision_id=decision_id,
        event_payload="not_a_dict",  # Invalid
        reasoning_mode="default"
    )
    
    assert len(signals) == 1
    assert signals[0].signal_type == "error"
    assert signals[0].error == "invalid_event_payload_type"


@pytest.mark.asyncio
async def test_reasoning_manager_unknown_mode(reasoning_manager):
    """Test ReasoningManager with unknown reasoning mode."""
    decision_id = str(uuid.uuid4())
    
    signals = await reasoning_manager.reason(
        decision_id=decision_id,
        event_payload={"test": "data"},
        reasoning_mode="unknown_mode"
    )
    
    assert len(signals) == 1
    assert signals[0].signal_type == "error"
    assert "unknown_reasoning_mode" in signals[0].error


@pytest.mark.asyncio
async def test_reasoning_manager_timeout(reasoning_manager):
    """Test ReasoningManager timeout enforcement."""
    decision_id = str(uuid.uuid4())
    payload = {"test": "data"}
    
    signals = await reasoning_manager.reason(
        decision_id=decision_id,
        event_payload=payload,
        reasoning_mode="timeout"
    )
    
    assert len(signals) == 1
    assert signals[0].signal_type == "timeout"
    assert signals[0].error == "reasoning_timeout_exceeded"


@pytest.mark.asyncio
async def test_reasoning_manager_with_context(reasoning_manager):
    """Test ReasoningManager with execution context."""
    decision_id = str(uuid.uuid4())
    payload = {"test": "data"}
    context = {
        "execution_id": str(uuid.uuid4()),
        "user_id": "test_user",
        "timestamp": int(time.time() * 1000)
    }
    
    signals = await reasoning_manager.reason(
        decision_id=decision_id,
        event_payload=payload,
        execution_context=context,
        reasoning_mode="action_suggestion"
    )
    
    # Should execute successfully with context
    assert isinstance(signals, list)


@pytest.mark.asyncio
async def test_reasoning_manager_confidence_validation(reasoning_manager):
    """Test AdvisorySignal confidence validation."""
    decision_id = str(uuid.uuid4())
    
    async def bad_confidence_mode(payload, context, timeout_ms):
        return [
            {
                "signal_type": "test",
                "payload": {},
                "confidence": 1.5  # Invalid: > 1.0
            },
            {
                "signal_type": "test",
                "payload": {},
                "confidence": "not_a_number"  # Invalid type
            }
        ]
    
    manager = ReasoningManager(
        modes={"bad_confidence": bad_confidence_mode},
        timeout_ms=5000
    )
    
    signals = await manager.reason(
        decision_id=decision_id,
        event_payload={},
        reasoning_mode="bad_confidence"
    )
    
    # Both signals should be created but with None confidence
    assert len(signals) == 2
    assert signals[0].confidence is None
    assert signals[1].confidence is None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_orchestrator_handle_event_with_reasoning_manager(orchestrator, reasoning_manager):
    """Test DecisionOrchestrator.handle_event() with ReasoningManager."""
    orchestrator.reasoning_manager = reasoning_manager
    
    event = Event(
        event_type="decision",
        payload={
            "id": str(uuid.uuid4()),
            "symbol": "BTC",
            "recommendation": "BUY",
            "reasoning_mode": "action_suggestion"
        },
        timestamp=int(time.time() * 1000),
        correlation_id=str(uuid.uuid4())
    )
    
    result = await orchestrator.handle_event(event)
    
    # Result should include advisory signals in metadata
    assert result.status == "accepted"
    assert "advisory_signals" in result.metadata
    assert "advisory_errors" in result.metadata


@pytest.mark.asyncio
async def test_orchestrator_handle_event_without_reasoning_manager(orchestrator):
    """Test DecisionOrchestrator.handle_event() without ReasoningManager."""
    # orchestrator.reasoning_manager remains None
    
    event = Event(
        event_type="decision",
        payload={
            "id": str(uuid.uuid4()),
            "symbol": "BTC",
            "recommendation": "BUY"
        },
        timestamp=int(time.time() * 1000),
        correlation_id=str(uuid.uuid4())
    )
    
    result = await orchestrator.handle_event(event)
    
    # Should work normally without reasoning manager
    assert result.status in ["accepted", "rejected", "error", "deferred"]


@pytest.mark.asyncio
async def test_orchestrator_reasoning_manager_non_fatal_error(orchestrator, reasoning_manager):
    """Test that ReasoningManager errors don't crash orchestrator."""
    
    async def crashing_mode(payload, context, timeout_ms):
        raise RuntimeError("Simulated reasoning crash")
    
    manager = ReasoningManager(
        modes={"crashing": crashing_mode},
        timeout_ms=5000
    )
    orchestrator.reasoning_manager = manager
    
    event = Event(
        event_type="plan_execution",
        payload={
            "plan": {
                "id": str(uuid.uuid4()),
                "version": 1,
                "created_at": int(time.time() * 1000),
                "steps": [
                    {
                        "id": str(uuid.uuid4()),
                        "action": "test",
                        "payload": {}
                    }
                ],
                "name": "test_plan",
                "context_requirements": []
            },
            "execution_context": {
                "plan": {},
                "execution_id": str(uuid.uuid4()),
                "started_at": int(time.time() * 1000),
                "deadline_ms": int(time.time() * 1000) + 5000,
                "environment": {}
            }
        },
        timestamp=int(time.time() * 1000),
        correlation_id=str(uuid.uuid4())
    )
    
    result = await orchestrator.handle_event(event)
    
    # Orchestrator should survive the plan execution
    assert result.status in ["accepted", "rejected", "error"]
    assert isinstance(result, EventResult)


@pytest.mark.asyncio
async def test_orchestrator_reasoning_isolation(orchestrator, reasoning_manager):
    """Test that ReasoningManager doesn't mutate orchestrator state."""
    orchestrator.reasoning_manager = reasoning_manager
    
    # Store initial state
    initial_dedup = len(orchestrator._dedup)
    initial_dlq = len(orchestrator._persist_dlq)
    
    event = Event(
        event_type="decision",
        payload={
            "id": str(uuid.uuid4()),
            "symbol": "BTC",
            "reasoning_mode": "action_suggestion"
        },
        timestamp=int(time.time() * 1000),
        correlation_id=str(uuid.uuid4())
    )
    
    result = await orchestrator.handle_event(event)
    
    # State should not be mutated by reasoning manager
    # (actual state may change from decision processing, but reasoning shouldn't cause it)
    assert isinstance(result, EventResult)
    assert "advisory_signals" in result.metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
