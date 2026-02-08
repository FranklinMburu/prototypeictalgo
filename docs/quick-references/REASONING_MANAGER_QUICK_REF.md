# ReasoningManager Quick Reference

## Files Created/Modified

### Created
- `reasoner_service/reasoning_manager.py` – ReasoningManager class + AdvisorySignal dataclass
- `tests/test_reasoning_manager.py` – 15 comprehensive tests
- `REASONING_MANAGER_DESIGN.md` – Full design documentation

### Modified
- `reasoner_service/orchestrator.py`:
  - Added import: `from .reasoning_manager import ReasoningManager, AdvisorySignal`
  - Added field: `self.reasoning_manager: Optional[ReasoningManager] = None`
  - Integrated bounded reasoning into `handle_event()` method

---

## Class Definitions (Python Code)

### AdvisorySignal

```python
@dataclass
class AdvisorySignal:
    decision_id: str
    signal_type: str
    payload: Dict[str, Any]
    plan_id: Optional[str] = None
    confidence: Optional[float] = None  # Auto-clipped to [0.0, 1.0]
    reasoning_mode: str = "default"
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### ReasoningManager

```python
class ReasoningManager:
    def __init__(
        self,
        modes: Dict[str, Callable],        # Reasoning functions by mode
        memory_accessor: Optional[MemoryStore] = None,
        timeout_ms: int = 5000,
        logger: Optional[Any] = None
    )
    
    async def reason(
        decision_id: str,
        event_payload: Dict[str, Any],
        execution_context: Optional[Dict[str, Any]] = None,
        reasoning_mode: str = "default",
        plan_id: Optional[str] = None
    ) -> List[AdvisorySignal]
```

---

## Integration into handle_event()

Location: `reasoner_service/orchestrator.py`, lines ~875-950

**Step 1: After policy checks:**
```python
# 2.5. Bounded Reasoning: Generate advisory signals
advisory_signals: List[AdvisorySignal] = []
if self.reasoning_manager is not None:
    advisory_signals = await self.reasoning_manager.reason(
        decision_id=decision_id,
        event_payload=decision,
        execution_context=reasoning_context,
        reasoning_mode=decision.get("reasoning_mode", "default"),
        plan_id=plan_id
    )
```

**Step 2: Return EventResult with signals:**
```python
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
                "confidence": s.confidence
            }
            for s in advisory_signals
        ]
    }
)
```

---

## Usage Pattern

### 1. Define Reasoning Modes

```python
async def my_reasoning_mode(payload, context, timeout_ms):
    # payload: dict with decision data
    # context: read-only execution context
    # timeout_ms: remaining time budget
    return [
        {
            "signal_type": "action_suggestion",
            "payload": {"action": "verify"},
            "confidence": 0.85
        }
    ]
```

### 2. Create Manager

```python
manager = ReasoningManager(
    modes={
        "default": async_fn_1,
        "mode_2": async_fn_2
    },
    timeout_ms=2000
)
```

### 3. Attach to Orchestrator

```python
orchestrator.reasoning_manager = manager
```

### 4. Handle Events

```python
event = Event(
    event_type="decision",
    payload={
        "id": "dec-123",
        "reasoning_mode": "default",
        # ... other fields
    },
    timestamp=int(time.time() * 1000),
    correlation_id="evt-456"
)

result = await orchestrator.handle_event(event)

# Advisory signals in result.metadata["advisory_signals"]
for signal in result.metadata["advisory_signals"]:
    print(f"{signal['signal_type']}: {signal['payload']}")
```

---

## Key Constraints

✅ **Stateless**: No state between reasoning calls
✅ **Time-bounded**: `timeout_ms` enforced via `asyncio.wait_for()`
✅ **Non-throwing**: All errors return advisory signals
✅ **Read-only**: Never mutates orchestrator, plan, or context
✅ **Optional**: ReasoningManager can be None; orchestration unaffected
✅ **Non-blocking**: Reasoning errors never crash event handling

---

## Error Handling

All errors converted to AdvisorySignal with `error` field:

| Error Type | Signal Type | Error Message |
|-----------|------------|---------------|
| Invalid payload | `error` | `invalid_event_payload_type` |
| Unknown mode | `error` | `unknown_reasoning_mode: {mode}` |
| Timeout | `timeout` | `reasoning_timeout_exceeded` |
| Exception | `error` | `reasoning_exception: {message}` |
| Malformed output | `error` | `signal_construction_failed` |

---

## Test Results

**41 tests passing:**
- ✅ 15 ReasoningManager tests
- ✅ 23 Contract alignment tests
- ✅ 3 Plan executor tests

Run tests:
```bash
pytest tests/test_reasoning_manager.py -v
```

---

## Design Principles

1. **Isolation** – Reasoning never modifies external state
2. **Resilience** – All errors converted to signals; no crashes
3. **Observability** – Every signal includes timestamp, mode, error
4. **Extensibility** – New modes added without modifying orchestrator
5. **Optionality** – Works identically with/without reasoning manager

---

## Backward Compatibility

✅ **No breaking changes**
- Existing handle_event() works unchanged
- ReasoningManager disabled by default (None)
- All existing tests pass
- Advisory signals optional in metadata

---

## Next Implementation Steps

1. Connect MemoryStore to historical outcome storage
2. Implement telemetry/metrics for reasoning performance
3. Build curated reasoning mode library
4. Apply orchestrator policies to signals before execution
5. Add feedback loop for signal effectiveness learning
