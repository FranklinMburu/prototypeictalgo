# Bounded Reasoning Subsystem Implementation

## Overview

This document describes the implementation of a **bounded reasoning subsystem** for the `DecisionOrchestrator`, consisting of:

1. **`ReasoningManager`** – Stateless reasoning engine producing advisory signals
2. **`AdvisorySignal`** – Data structure for reasoning output
3. **Integration into `handle_event()`** – Event-driven orchestration with bounded reasoning

All components maintain strict isolation: reasoning never mutates orchestrator state, plans, or execution context.

---

## Component Design

### 1. AdvisorySignal Dataclass

**Purpose:** Represents a single advisory recommendation from bounded reasoning.

**Fields:**
```python
@dataclass
class AdvisorySignal:
    # REQUIRED
    decision_id: str           # UUID v4 of decision
    signal_type: str           # e.g., 'action_suggestion', 'risk_flag', 'optimization_hint'
    payload: Dict[str, Any]    # Signal-specific data (never modifies state)
    
    # OPTIONAL
    plan_id: Optional[str]     # UUID v4 of related plan, if any
    confidence: Optional[float]  # [0.0, 1.0] confidence score
    reasoning_mode: str        # Reasoning mode used (default: "default")
    timestamp: int             # Unix ms (auto-generated)
    error: Optional[str]       # Error message if reasoning failed
    metadata: Dict[str, Any]   # Auxiliary data
```

**Key Properties:**
- Immutable after creation
- Confidence is auto-clipped to [0.0, 1.0] or set to None if invalid
- Timestamp automatically set to current Unix milliseconds
- Error field indicates failed reasoning (non-fatal)

---

### 2. ReasoningManager Class

**Purpose:** Orchestrates bounded reasoning with multiple modes and time constraints.

**Initialization:**
```python
manager = ReasoningManager(
    modes={
        "default": async_reasoning_fn,
        "action_suggestion": async_reasoning_fn,
        "risk_flag": async_reasoning_fn,
        # ... more modes
    },
    memory_accessor=optional_memory_store,  # Read-only historical access
    timeout_ms=5000,                         # Max per-call duration
    logger=optional_telemetry_logger
)
```

**Constraints:**
- **Stateless**: No state maintained between calls
- **Time-bounded**: Reasoning timeout enforced via `asyncio.wait_for()`
- **Non-throwing**: All errors return advisory signals with `error` field set
- **Read-only**: No state mutations; accesses context as immutable

**Core Method:**
```python
async def reason(
    decision_id: str,
    event_payload: Dict[str, Any],
    execution_context: Optional[Dict[str, Any]] = None,
    reasoning_mode: str = "default",
    plan_id: Optional[str] = None
) -> List[AdvisorySignal]
```

**Returns:**
- List of `AdvisorySignal` objects (may be empty)
- Never throws exceptions; errors encoded in signals

**Error Handling:**
- Invalid payload type → `AdvisorySignal(signal_type="error", error="invalid_event_payload_type")`
- Unknown mode → `AdvisorySignal(signal_type="error", error="unknown_reasoning_mode: ...")`
- Timeout exceeded → `AdvisorySignal(signal_type="timeout", error="reasoning_timeout_exceeded")`
- Malformed signals → Recorded individually; other signals still returned
- Exception during reasoning → Caught and returned as error signal

---

### 3. Reasoning Function Protocol

User-provided reasoning functions must follow this interface:

```python
async def reasoning_function(
    payload: Dict[str, Any],           # Event payload to reason about
    context: Dict[str, Any],           # Read-only execution context
    timeout_remaining_ms: int          # Time budget in milliseconds
) -> List[Dict[str, Any]]:
    """
    Returns list of signal dicts with keys:
    - signal_type: str (required)
    - payload: Dict[str, Any] (required)
    - confidence: Optional[float] (optional, auto-clipped to [0.0, 1.0])
    - metadata: Optional[Dict] (optional)
    - plan_id: Optional[str] (optional)
    """
    # Example:
    return [
        {
            "signal_type": "action_suggestion",
            "payload": {"action": "verify", "reason": "high_confidence"},
            "confidence": 0.87,
            "metadata": {"source": "ai_model"}
        }
    ]
```

---

## Integration with DecisionOrchestrator

### Changes to `orchestrator.py`

**1. Import Addition:**
```python
from .reasoning_manager import ReasoningManager, AdvisorySignal
```

**2. Instance Variable:**
```python
class DecisionOrchestrator:
    def __init__(self, dsn: Optional[str] = None):
        # ... existing code ...
        self.reasoning_manager: Optional[ReasoningManager] = None
```

**3. Integration into `handle_event()`:**

The method now includes a reasoning step after pre-reasoning policy checks:

```
EVENT → PRE-VALIDATION → POLICY CHECKS → REASONING (NEW) → PLAN EXECUTION → DECISION PROCESSING
```

**Code Flow in `handle_event()` for "decision" events:**

```python
# 2. Policy Check
policy_result = await self.pre_reasoning_policy_check(decision)
if policy_result.get("result") == "veto":
    return EventResult(status="rejected", ...)

# 2.5. BOUNDED REASONING (NEW)
advisory_signals: List[AdvisorySignal] = []
advisory_errors: List[str] = []
if self.reasoning_manager is not None:
    try:
        reasoning_context = {
            "decision_id": decision_id,
            "timestamp": int(time.time() * 1000),
            "event_type": event.event_type,
            "correlation_id": event.correlation_id
        }
        advisory_signals = await self.reasoning_manager.reason(
            decision_id=decision_id,
            event_payload=decision,
            execution_context=reasoning_context,
            reasoning_mode=decision.get("reasoning_mode", "default"),
            plan_id=plan_id
        )
    except Exception as e:
        advisory_errors.append(f"reasoning_exception: {str(e)}")

# 3. Plan Execution (existing)
# 4. Decision Processing (existing)

# Return EventResult with advisory signals in metadata
return EventResult(
    status="accepted",
    decision_id=decision_id,
    metadata={
        "plan_result": plan_result,
        "advisory_signals": [
            {
                "decision_id": s.decision_id,
                "signal_type": s.signal_type,
                "payload": s.payload,
                "confidence": s.confidence,
                "reasoning_mode": s.reasoning_mode,
                "error": s.error
            }
            for s in advisory_signals
        ],
        "advisory_errors": advisory_errors
    }
)
```

**Key Properties:**
- Reasoning is **optional**: If `reasoning_manager` is None, skipped entirely
- **Non-fatal**: Reasoning errors captured in metadata, never crash orchestration
- **Advisory-only**: Signals don't directly modify state; orchestrator policy applies
- **Metadata-rich**: EventResult includes signals and errors for audit/debugging

---

## Usage Example

### Setup ReasoningManager

```python
# Define reasoning modes
async def verify_limit_mode(payload, context, timeout_ms):
    """Suggests limit verification."""
    symbol = payload.get("symbol", "UNKNOWN")
    confidence = payload.get("confidence", 0.0)
    
    if confidence > 0.8:
        return [
            {
                "signal_type": "action_suggestion",
                "payload": {
                    "action": "verify_limit",
                    "symbol": symbol,
                    "reason": "high_confidence_decision"
                },
                "confidence": min(0.95, confidence + 0.1)
            }
        ]
    return []

async def risk_assessment_mode(payload, context, timeout_ms):
    """Generates risk flags."""
    if payload.get("confidence", 0) > 0.9:
        return [
            {
                "signal_type": "risk_flag",
                "payload": {
                    "risk_level": "high",
                    "reason": "extreme_confidence"
                },
                "confidence": 0.99
            }
        ]
    return []

# Create manager
manager = ReasoningManager(
    modes={
        "default": verify_limit_mode,
        "verify_limit": verify_limit_mode,
        "risk_assessment": risk_assessment_mode
    },
    timeout_ms=2000,
    logger=telemetry_logger
)

# Attach to orchestrator
orchestrator.reasoning_manager = manager
```

### Handle Event with Reasoning

```python
event = Event(
    event_type="decision",
    payload={
        "id": "dec-123",
        "symbol": "BTC",
        "recommendation": "BUY",
        "confidence": 0.92,
        "reasoning_mode": "risk_assessment"
    },
    timestamp=int(time.time() * 1000),
    correlation_id="evt-456"
)

result = await orchestrator.handle_event(event)

# Result contains advisory signals
print(result.metadata["advisory_signals"])
# Output:
# [
#     {
#         "decision_id": "dec-123",
#         "signal_type": "risk_flag",
#         "payload": {"risk_level": "high", "reason": "extreme_confidence"},
#         "confidence": 0.99,
#         "reasoning_mode": "risk_assessment",
#         "error": None
#     }
# ]
```

---

## Design Principles

### 1. **Isolation**
- ReasoningManager never reads/writes orchestrator state
- Never modifies Plan or ExecutionContext
- All context access is read-only and immutable

### 2. **Resilience**
- All exceptions caught and converted to advisory signals
- Reasoning timeouts don't crash orchestration
- Malformed signals don't prevent other signals from being processed

### 3. **Observability**
- Every advisory signal includes timestamp and reasoning mode
- Error signals include error message for debugging
- Reasoning errors captured in EventResult metadata

### 4. **Extensibility**
- User can define arbitrary reasoning modes
- Modes are plugged in as async functions
- New modes can be added without modifying orchestrator code

### 5. **Optionality**
- ReasoningManager is optional (`None` by default)
- Orchestration works identically with or without it
- No breaking changes to existing event handling

---

## Testing

### Test Coverage

**15 tests** covering:
- AdvisorySignal creation and validation
- ReasoningManager with multiple modes
- Timeout enforcement
- Error handling (invalid payloads, unknown modes, crashes)
- Confidence validation (auto-clipping)
- Integration with DecisionOrchestrator.handle_event()
- Non-fatal error propagation
- State isolation (reasoning doesn't mutate orchestrator)

### Run Tests

```bash
pytest tests/test_reasoning_manager.py -v
```

**Expected Output:**
```
tests/test_reasoning_manager.py::test_advisory_signal_creation PASSED
tests/test_reasoning_manager.py::test_reasoning_manager_default_mode PASSED
...
15 passed in 0.48s
```

---

## Files Modified/Created

1. **Created:** `reasoner_service/reasoning_manager.py` (350+ lines)
   - `AdvisorySignal` dataclass
   - `MemoryStore` protocol
   - `ReasoningFunction` protocol
   - `ReasoningManager` class

2. **Modified:** `reasoner_service/orchestrator.py`
   - Added import: `from .reasoning_manager import ReasoningManager, AdvisorySignal`
   - Added field: `self.reasoning_manager: Optional[ReasoningManager] = None`
   - Integrated bounded reasoning into `handle_event()` method
   - Advisory signals included in EventResult metadata

3. **Created:** `tests/test_reasoning_manager.py` (380+ lines)
   - 15 comprehensive tests
   - Fixtures for ReasoningManager and DecisionOrchestrator
   - Integration and isolation tests

---

## Backward Compatibility

✅ **No breaking changes**

- Existing `handle_event()` behavior unchanged when `reasoning_manager` is None
- All existing tests pass without modification
- ReasoningManager is optional and disabled by default
- Advisory signals added to EventResult metadata without affecting status/reason

---

## Next Steps

1. **MemoryStore Implementation**: Connect to historical outcome storage
2. **Telemetry**: Add reasoning metrics (latency, signal counts, errors)
3. **Mode Library**: Build curated reasoning modes (risk assessment, optimization, etc.)
4. **Policy Integration**: Apply orchestrator policies to signals before state mutation
5. **Feedback Loop**: Learn from signal effectiveness over time
