#!/usr/bin/env python3
"""
Simple test script to verify handle_event method functionality.
"""
import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.orchestrator_events import Event, EventResult

async def test_handle_event():
    """Test the handle_event method with various event types."""
    print("Testing handle_event method...")

    # Create orchestrator instance
    orchestrator = DecisionOrchestrator()

    # Test 1: Invalid event type
    print("\n1. Testing invalid event type...")
    result = await orchestrator.handle_event("not_an_event")
    print(f"Result: {result}")
    assert result.status == "error"
    assert result.reason == "invalid_event_type"
    print("✓ Invalid event type handled correctly")

    # Test 2: Malformed event
    print("\n2. Testing malformed event...")
    malformed_event = Event(event_type="", payload="not_a_dict", timestamp=0, correlation_id="test")
    result = await orchestrator.handle_event(malformed_event)
    print(f"Result: {result}")
    assert result.status == "error"
    assert result.reason == "malformed_event"
    print("✓ Malformed event handled correctly")

    # Test 3: Unsupported event type
    print("\n3. Testing unsupported event type...")
    unsupported_event = Event(event_type="unknown", payload={}, timestamp=0, correlation_id="test")
    result = await orchestrator.handle_event(unsupported_event)
    print(f"Result: {result}")
    assert result.status == "rejected"
    assert result.reason == "unsupported_event_type"
    print("✓ Unsupported event type handled correctly")

    # Test 4: Plan execution event with missing data
    print("\n4. Testing plan execution event with missing data...")
    plan_event = Event(event_type="plan_execution", payload={}, timestamp=0, correlation_id="test")
    result = await orchestrator.handle_event(plan_event)
    print(f"Result: {result}")
    assert result.status == "error"
    assert result.reason == "missing_plan_or_context"
    print("✓ Missing plan/context handled correctly")

    # Test 5: Decision event with invalid payload
    print("\n5. Testing decision event with invalid payload...")
    decision_event = Event(event_type="decision", payload="not_a_dict", timestamp=0, correlation_id="test")
    result = await orchestrator.handle_event(decision_event)
    print(f"Result: {result}")
    assert result.status == "error"
    assert result.reason == "malformed_event"  # This gets caught by the general malformed event check
    print("✓ Invalid decision payload handled correctly")

    print("\n✅ All handle_event tests passed!")
    await orchestrator.close()

if __name__ == "__main__":
    asyncio.run(test_handle_event())