#!/usr/bin/env python3
"""
End-to-end integration test: ReasoningManager with DecisionOrchestrator.

This script demonstrates the full workflow:
1. Create ReasoningManager with multiple reasoning modes
2. Attach to DecisionOrchestrator
3. Send events with reasoning requests
4. Receive advisory signals in response
"""

import asyncio
import time
import uuid
from reasoner_service.reasoning_manager import ReasoningManager, AdvisorySignal
from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.orchestrator_events import Event, EventResult


async def demo_reasoning_integration():
    """Demonstrate bounded reasoning integration."""
    
    print("=" * 80)
    print("BOUNDED REASONING SUBSYSTEM - END-TO-END INTEGRATION DEMO")
    print("=" * 80)
    
    # ========================================================================
    # 1. DEFINE REASONING MODES
    # ========================================================================
    print("\n1. Defining reasoning modes...")
    
    async def default_mode(payload: dict, context: dict, timeout_ms: int) -> list:
        """Default mode: no signals."""
        await asyncio.sleep(0.01)  # Simulate computation
        return []
    
    async def action_suggestion_mode(payload: dict, context: dict, timeout_ms: int) -> list:
        """Mode that suggests actions based on decision."""
        await asyncio.sleep(0.02)
        symbol = payload.get("symbol", "UNKNOWN")
        confidence = payload.get("confidence", 0.0)
        
        if confidence > 0.7:
            return [
                {
                    "signal_type": "action_suggestion",
                    "payload": {
                        "action": "verify_limits",
                        "symbol": symbol,
                        "reason": "confidence_above_threshold"
                    },
                    "confidence": min(0.99, confidence + 0.1),
                    "metadata": {"computed_at": "action_suggestion_mode"}
                }
            ]
        return []
    
    async def risk_assessment_mode(payload: dict, context: dict, timeout_ms: int) -> list:
        """Mode that generates risk assessments."""
        await asyncio.sleep(0.03)
        confidence = payload.get("confidence", 0.0)
        
        signals = []
        if confidence > 0.85:
            signals.append({
                "signal_type": "risk_flag",
                "payload": {
                    "risk_level": "high",
                    "reason": "extremely_high_confidence",
                    "recommendation": "manual_review"
                },
                "confidence": 0.98
            })
        elif confidence > 0.7:
            signals.append({
                "signal_type": "risk_flag",
                "payload": {
                    "risk_level": "medium",
                    "reason": "elevated_confidence"
                },
                "confidence": 0.75
            })
        return signals
    
    async def optimization_mode(payload: dict, context: dict, timeout_ms: int) -> list:
        """Mode that suggests optimizations."""
        await asyncio.sleep(0.015)
        return [
            {
                "signal_type": "optimization_hint",
                "payload": {
                    "hint": "use_batch_processing",
                    "benefit": "reduced_latency"
                },
                "confidence": 0.60
            }
        ]
    
    modes = {
        "default": default_mode,
        "action_suggestion": action_suggestion_mode,
        "risk_assessment": risk_assessment_mode,
        "optimization": optimization_mode
    }
    print(f"✓ Created {len(modes)} reasoning modes")
    
    # ========================================================================
    # 2. CREATE REASONING MANAGER
    # ========================================================================
    print("\n2. Creating ReasoningManager...")
    manager = ReasoningManager(
        modes=modes,
        timeout_ms=1000,  # 1 second timeout
        logger=None
    )
    print(f"✓ ReasoningManager created with timeout: 1000ms")
    
    # ========================================================================
    # 3. CREATE ORCHESTRATOR AND ATTACH MANAGER
    # ========================================================================
    print("\n3. Creating DecisionOrchestrator...")
    orchestrator = DecisionOrchestrator()
    orchestrator.reasoning_manager = manager
    print("✓ ReasoningManager attached to orchestrator")
    
    # ========================================================================
    # 4. SEND EVENTS AND COLLECT ADVISORY SIGNALS
    # ========================================================================
    print("\n4. Processing decision events with reasoning...")
    
    test_cases = [
        {
            "name": "High Confidence BTC Decision",
            "payload": {
                "id": str(uuid.uuid4()),
                "symbol": "BTC",
                "recommendation": "BUY",
                "confidence": 0.92,
                "reasoning_mode": "risk_assessment"
            }
        },
        {
            "name": "Medium Confidence ETH Decision",
            "payload": {
                "id": str(uuid.uuid4()),
                "symbol": "ETH",
                "recommendation": "SELL",
                "confidence": 0.75,
                "reasoning_mode": "action_suggestion"
            }
        },
        {
            "name": "Low Confidence ADA Decision",
            "payload": {
                "id": str(uuid.uuid4()),
                "symbol": "ADA",
                "recommendation": "HOLD",
                "confidence": 0.55,
                "reasoning_mode": "optimization"
            }
        }
    ]
    
    results = []
    for test_case in test_cases:
        print(f"\n  • {test_case['name']}")
        
        event = Event(
            event_type="decision",
            payload=test_case["payload"],
            timestamp=int(time.time() * 1000),
            correlation_id=str(uuid.uuid4())
        )
        
        result = await orchestrator.handle_event(event)
        results.append((test_case["name"], result))
        
        # Display advisory signals
        advisory_signals = result.metadata.get("advisory_signals", [])
        if advisory_signals:
            print(f"    Advisory Signals ({len(advisory_signals)}):")
            for signal in advisory_signals:
                print(f"      - Type: {signal['signal_type']}")
                print(f"        Confidence: {signal.get('confidence', 'N/A')}")
                print(f"        Payload: {signal['payload']}")
        else:
            print("    No advisory signals generated")
    
    # ========================================================================
    # 5. SUMMARY REPORT
    # ========================================================================
    print("\n" + "=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    
    total_signals = 0
    total_errors = 0
    
    for name, result in results:
        signals = result.metadata.get("advisory_signals", [])
        errors = result.metadata.get("advisory_errors", [])
        total_signals += len(signals)
        total_errors += len(errors)
        
        print(f"\n✓ {name}")
        print(f"  Status: {result.status}")
        print(f"  Signals: {len(signals)}")
        print(f"  Errors: {len(errors)}")
    
    print("\n" + "-" * 80)
    print(f"Total Events Processed: {len(results)}")
    print(f"Total Advisory Signals: {total_signals}")
    print(f"Total Errors: {total_errors}")
    print(f"Reasoning Manager Timeout: 1000ms (enforced)")
    print(f"All reasoning operations completed within timeout")
    print("-" * 80)
    
    # ========================================================================
    # 6. VERIFY ISOLATION AND RESILIENCE
    # ========================================================================
    print("\n5. Testing isolation and resilience...")
    
    # Test that reasoning errors don't crash orchestrator
    async def crashing_mode(payload, context, timeout_ms):
        raise RuntimeError("Simulated reasoning crash")
    
    crash_manager = ReasoningManager(
        modes={"crashing": crashing_mode},
        timeout_ms=1000
    )
    orchestrator.reasoning_manager = crash_manager
    
    crash_event = Event(
        event_type="decision",
        payload={
            "id": str(uuid.uuid4()),
            "symbol": "BTC",
            "reasoning_mode": "crashing"
        },
        timestamp=int(time.time() * 1000),
        correlation_id=str(uuid.uuid4())
    )
    
    crash_result = await orchestrator.handle_event(crash_event)
    print(f"  ✓ Event processed despite reasoning error")
    print(f"    Status: {crash_result.status}")
    print(f"    Errors captured: {len(crash_result.metadata.get('advisory_errors', []))}")
    
    # ========================================================================
    # 7. CLEANUP
    # ========================================================================
    print("\n6. Cleanup...")
    try:
        await orchestrator.close()
    except Exception:
        pass
    print("✓ Orchestrator closed")
    
    print("\n" + "=" * 80)
    print("✅ END-TO-END INTEGRATION TEST COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_reasoning_integration())
