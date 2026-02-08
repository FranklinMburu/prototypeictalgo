================================================================================
STAGE 4 IMPLEMENTATION — DETAILED TECHNICAL SPECIFICATION
================================================================================

Status: COMPLETE ✅
Date: December 23, 2025
Scope: Reasoning Mode Selection (v1.1 Trading Decision Loop)

================================================================================
PART 1: OVERVIEW
================================================================================

## What is Stage 4?

Stage 4 is the "Mode Selection" stage of the Trading Decision Loop. It sits
between the hard validation gate (Stage 3) and the bounded reasoning subsystem.

Its single responsibility: SELECT EXACTLY ONE reasoning mode per decision cycle.

Three modes are possible:
  1. bias_evaluation:   Evaluate/establish HTF bias direction
  2. entry_evaluation:  Find entry opportunities given valid HTF bias
  3. trade_management:  Manage/exit open positions

## Why Stage 4?

Without explicit mode selection:
  ❌ Could invoke wrong reasoning (entry when bias undefined)
  ❌ Could miss position management (focus only on entries)
  ❌ No clear separation of concerns
  ❌ Ambiguous state handling

With Stage 4:
  ✅ Each cycle has exactly one clear mode
  ✅ Reasoning logic can be optimized per mode
  ✅ Clear state machine progression
  ✅ All ambiguities resolved at orchestration level, not in reasoning

## Stage 4 is NOT

❌ No reasoning logic (that's ReasoningManager's job)
❌ No trading decisions (pure selection, no judgment)
❌ No state mutations (read-only input processing)
❌ No memory access (context is always fresh)
❌ No market data access (HTF bias comes pre-computed from payload)
❌ No timeouts (selection is instant, deterministic)

================================================================================
PART 2: THE HTFBiasState ENUM
================================================================================

## Definition

```python
class HTFBiasState(str, Enum):
    """HTF bias state machine."""
    UNDEFINED = "undefined"           # Step 0: No bias defined yet
    BIAS_UP = "bias_up"               # Step 1+: HTF is bullish
    BIAS_DOWN = "bias_down"           # Step 1+: HTF is bearish
    BIAS_NEUTRAL = "bias_neutral"     # Step 1+: HTF is consolidating
    INVALIDATED = "invalidated"       # Regression: previous bias broken
```

## State Meanings

### UNDEFINED
  - No bias evaluation has been performed
  - No prior bias decision exists
  - Often the starting state for a new symbol
  - Action: Must run bias_evaluation before any entry decisions
  - Example: Starting fresh on EUR/USD; no prior HTF context

### BIAS_UP
  - HTF shows bullish structure
  - Price above key moving averages, higher lows, higher highs, etc.
  - Valid for entry/trade decisions
  - Can transition to BIAS_DOWN or INVALIDATED
  - Example: EUR/USD daily is above 200MA, confirmed by 4H structure

### BIAS_DOWN
  - HTF shows bearish structure
  - Price below key moving averages, lower highs, lower lows, etc.
  - Valid for entry/trade decisions
  - Can transition to BIAS_UP or INVALIDATED
  - Example: GBP/USD daily is below 200MA, 4H showing lower highs

### BIAS_NEUTRAL
  - HTF shows neither clear bullish nor bearish bias
  - Consolidation, range-bound, or transition phase
  - Valid for entry/trade decisions (typically lower probability)
  - Can transition to BIAS_UP, BIAS_DOWN, or INVALIDATED
  - Example: USD/JPY 4H trading in 144.00-145.00 range

### INVALIDATED
  - Previous bias state is no longer valid
  - Price action contradicts prior structure (e.g., close below support)
  - Explicit signal that bias needs re-evaluation
  - Action: Must run bias_evaluation again
  - Example: Was BIAS_UP, but price broke below 4H support → INVALIDATED

## State Transitions

```
UNDEFINED
  ├─→ BIAS_UP (after successful bias_evaluation)
  ├─→ BIAS_DOWN (after successful bias_evaluation)
  └─→ BIAS_NEUTRAL (after successful bias_evaluation)

BIAS_UP / BIAS_DOWN / BIAS_NEUTRAL
  ├─→ BIAS_UP (change of bias direction)
  ├─→ BIAS_DOWN (change of bias direction)
  ├─→ BIAS_NEUTRAL (consolidation detected)
  └─→ INVALIDATED (price action breaks structure)

INVALIDATED
  ├─→ BIAS_UP (after re-evaluation confirms new bullish bias)
  ├─→ BIAS_DOWN (after re-evaluation confirms new bearish bias)
  └─→ BIAS_NEUTRAL (after re-evaluation shows consolidation)
```

Note: Stage 4 does NOT manage these transitions. The decision payload
provides the current state; Stage 4 only reads it.

================================================================================
PART 3: THE REASONING MODE SELECTOR
================================================================================

## Class Definition

```python
class ReasoningModeSelector:
    """Deterministic reasoning mode selector for Stage 4."""
    
    def __init__(self):
        # Initialize valid/invalid state sets
        ...
    
    def select_mode(
        self,
        htf_bias_state: HTFBiasState,
        position_open: bool
    ) -> ModeSelectionResult:
        """Deterministically select reasoning mode."""
        ...
    
    def select_mode_from_dict(
        self,
        state: Dict[str, Any]
    ) -> ModeSelectionResult:
        """Select mode from dict (convenience method)."""
        ...
```

## Input Contract

### Required Inputs
1. **htf_bias_state** (HTFBiasState enum)
   - Type: Must be HTFBiasState enum value, not string
   - Constraint: Must be valid (no None, no random values)
   - None allowed: No, hard error if missing
   - Default: No defaults, error if missing

2. **position_open** (bool)
   - Type: Must be exactly bool (True or False)
   - Constraint: Must be determinable from market state
   - None allowed: No, hard error if missing
   - Default: No defaults, error if missing

### Invalid Inputs (Hard Errors)
```python
# String instead of enum
selector.select_mode(htf_bias_state="bias_up", position_open=False)
→ ModeSelectionError("Invalid HTF bias state type: str")

# Missing input
decision_payload = {"position_open": False}  # missing htf_bias_state
→ ModeSelectionError("Missing required key: 'htf_bias_state'")

# Wrong type
selector.select_mode(htf_bias_state=HTFBiasState.BIAS_UP, position_open=1)
→ ModeSelectionError("Invalid position_open type: int. Must be bool")
```

## Selection Rules (Canonical)

```
Rule 1: If HTF bias is UNDEFINED or INVALIDATED
        → Select "bias_evaluation"
        
Rule 2: Else if HTF bias is valid (UP/DOWN/NEUTRAL) AND position is NOT open
        → Select "entry_evaluation"
        
Rule 3: Else if position IS open
        → Select "trade_management"
        
Rule 4: Else (unresolvable state)
        → Raise ModeSelectionError (hard failure)
```

## Truth Table

| HTF Bias State | Position Open | Selected Mode    | Rationale                     |
|----------------|---------------|------------------|-------------------------------|
| UNDEFINED      | False         | bias_evaluation  | Rule 1                        |
| UNDEFINED      | True          | bias_evaluation  | Rule 1 (bias first, then mgmt)|
| INVALIDATED    | False         | bias_evaluation  | Rule 1                        |
| INVALIDATED    | True          | bias_evaluation  | Rule 1 (re-evaluate bias)     |
| BIAS_UP        | False         | entry_evaluation | Rule 2                        |
| BIAS_UP        | True          | trade_management | Rule 3                        |
| BIAS_DOWN      | False         | entry_evaluation | Rule 2                        |
| BIAS_DOWN      | True          | trade_management | Rule 3                        |
| BIAS_NEUTRAL   | False         | entry_evaluation | Rule 2                        |
| BIAS_NEUTRAL   | True          | trade_management | Rule 3                        |

## Return Value

```python
@dataclass
class ModeSelectionResult:
    mode: Optional[ReasoningMode]  # "bias_evaluation" | "entry_evaluation" | "trade_management" | None
    reason: str                     # Human-readable explanation
    error: Optional[str]            # Error message if mode selection failed
```

### Success Case
```python
result = selector.select_mode(HTFBiasState.BIAS_UP, False)

result.mode     → "entry_evaluation"
result.reason   → "HTF bias is bias_up; no position open; ready for entry evaluation."
result.error    → None
```

### Error Case
```python
result = selector.select_mode("bias_up", False)  # Wrong type

result.mode     → None
result.reason   → ""
result.error    → "Invalid HTF bias state type: str. Must be HTFBiasState enum value."
```

================================================================================
PART 4: ORCHESTRATOR INTEGRATION
================================================================================

## Initialization

In `DecisionOrchestrator.__init__()`:

```python
# Stage 4: Reasoning Mode Selector (deterministic mode selection)
self.reasoning_mode_selector = ReasoningModeSelector()
```

This is a lightweight, stateless object. One instance per orchestrator.

## Event Flow

### Complete Sequence

```
Event arrives
    ↓
[1] PRE-VALIDATION
    - Check event structure (event_type, payload)
    - Check system state (cooldowns, session windows)
    ↓
[2] POLICY CHECK (Stage 3: Hard Validation Gate)
    - pre_reasoning_policy_check()
    - Check cooldown, regime, exposure, kill switch, etc.
    - If veto/defer → return early (don't proceed to reasoning)
    ↓
[3] ★ REASONING MODE SELECTION (Stage 4) ★
    - Extract htf_bias_state from decision payload
    - Extract position_open from decision payload
    - Validate inputs (required, correct type, valid value)
    - Call selector.select_mode(htf_bias_state, position_open)
    - If error → return EventResult(status="rejected")
    - If success → continue with selected_reasoning_mode
    ↓
[4] BOUNDED REASONING (Stage 4b: Invoke reasoning with selected mode)
    - GUARD: Only if selected_reasoning_mode is not None
    - Call reasoning_manager.reason(..., reasoning_mode=selected_mode)
    - Generate advisory signals
    ↓
[5] PLAN EXECUTION
    - If plan in decision, execute it
    ↓
[6] DECISION PERSISTENCE
    - Store decision in archive
    ↓
Result returned to caller
```

## Stage 4 in handle_event()

Location: `reasoner_service/orchestrator.py`, method `handle_event()`, lines ~1043-1220

### Pseudocode

```python
async def handle_event(self, event: Event) -> EventResult:
    # ... [Steps 1-2: pre-validation and policy check] ...
    
    # ================================================================
    # STAGE 4: REASONING MODE SELECTION
    # ================================================================
    advisory_signals = []
    advisory_errors = []
    selected_reasoning_mode = None
    
    if self.reasoning_manager is not None:
        try:
            # Extract state from decision
            htf_bias_state_str = decision.get("htf_bias_state")
            position_open = decision.get("position_open", False)
            
            # Validate presence
            if htf_bias_state_str is None:
                # Error: missing required state
                logger.error("htf_bias_state is missing...")
                return EventResult(status="rejected", reason="mode_selection_failed")
            
            # Convert to enum
            try:
                htf_bias_state = HTFBiasState(htf_bias_state_str)
            except ValueError:
                # Error: invalid state value
                logger.error("invalid htf_bias_state='%s'...", htf_bias_state_str)
                return EventResult(status="rejected", reason="mode_selection_failed")
            
            # Select mode
            try:
                mode_result = self.reasoning_mode_selector.select_mode(
                    htf_bias_state=htf_bias_state,
                    position_open=position_open
                )
            except ModeSelectionError as e:
                # Error: unresolvable state
                logger.error("Mode selection hard error: %s...", e.message)
                return EventResult(status="rejected", reason="mode_selection_failed")
            
            # Check result
            if mode_result.mode is None or mode_result.error:
                # Error: mode selection returned error
                logger.error("Mode selection failed: %s...", mode_result.error)
                return EventResult(status="rejected", reason="mode_selection_failed")
            
            selected_reasoning_mode = mode_result.mode
            
            # Log success
            logger.info(
                "Stage 4 Mode Selected: %s. Reason: %s. "
                "HTF bias: %s, position_open: %s.",
                selected_reasoning_mode,
                mode_result.reason,
                htf_bias_state.value,
                position_open
            )
            
            # ================================================================
            # GUARD: Only invoke reasoning with valid mode
            # ================================================================
            if selected_reasoning_mode is None:
                # This should never happen if logic above is correct
                logger.error("Internal error: null reasoning_mode...")
                return EventResult(status="rejected", reason="mode_selection_failed")
            
            # Prepare context
            reasoning_context = {
                "decision_id": decision_id,
                "timestamp": int(time.time() * 1000),
                "event_type": event.event_type,
                "correlation_id": event.correlation_id,
                "reasoning_mode_selected": selected_reasoning_mode,
                "htf_bias_state": htf_bias_state.value,
                "position_open": position_open
            }
            
            # Invoke reasoning manager
            advisory_signals = await self.reasoning_manager.reason(
                decision_id=decision_id,
                event_payload=decision,
                execution_context=reasoning_context,
                reasoning_mode=selected_reasoning_mode,
                plan_id=plan_id
            )
        
        except Exception as e:
            # Catch unexpected errors (shouldn't reach here with proper input validation)
            advisory_errors.append(f"reasoning_exception: {str(e)}")
            logger.warning("Reasoning manager exception (non-fatal): %s", e)
    
    # ... [Steps 5-6: Plan execution, persistence] ...
```

## Error Handling Strategy

Three categories of errors in Stage 4:

### Category 1: Missing Input
Symptom: `decision.get("htf_bias_state")` returns None

Response:
```python
if htf_bias_state_str is None:
    advisory_errors.append("mode_selection_error: htf_bias_state not provided")
    logger.error("Stage 4 Mode Selection Failed: htf_bias_state is missing...")
    return EventResult(
        status="rejected",
        reason="mode_selection_failed",
        metadata={"error": "htf_bias_state_missing", "advisory_errors": [...]}
    )
```

### Category 2: Invalid Input
Symptom: `htf_bias_state_str` is a valid string but not a valid enum value

Response:
```python
try:
    htf_bias_state = HTFBiasState(htf_bias_state_str)
except ValueError:
    advisory_errors.append(f"mode_selection_error: invalid htf_bias_state='{htf_bias_state_str}'")
    logger.error("Stage 4 Mode Selection Failed: invalid HTF bias state '%s'...", htf_bias_state_str)
    return EventResult(
        status="rejected",
        reason="mode_selection_failed",
        metadata={"error": f"invalid_htf_bias_state:{htf_bias_state_str}", ...}
    )
```

### Category 3: Unresolvable State
Symptom: `selector.select_mode()` raises `ModeSelectionError`

Response:
```python
except ModeSelectionError as e:
    advisory_errors.append(f"mode_selection_error: {e.message}")
    logger.error("Stage 4 Mode Selection Hard Error: %s...", e.message)
    return EventResult(
        status="rejected",
        reason="mode_selection_failed",
        metadata={"error": e.message, "advisory_errors": [...]}
    )
```

## Guard: Null Mode Check

Before invoking reasoning manager:

```python
if selected_reasoning_mode is None:
    advisory_errors.append("internal_error: reasoning_mode_selector returned None mode")
    logger.error("Internal Error: ReasoningModeSelector returned None mode...")
    return EventResult(
        status="rejected",
        reason="mode_selection_failed",
        metadata={"error": "null_reasoning_mode", ...}
    )
```

This is a safety guard. If code above is correct, this should never execute.

================================================================================
PART 5: LOGGING
================================================================================

## Log Levels and Messages

### SUCCESS: Info Level

```
INFO Stage 4 Mode Selected: bias_evaluation. Reason: HTF bias state is 
     undefined; bias evaluation required before entry evaluation. 
     HTF bias: undefined, position_open: False. Decision: decision-uuid-123
```

```
INFO Stage 4 Mode Selected: entry_evaluation. Reason: HTF bias is bias_up; 
     no position open; ready for entry evaluation. 
     HTF bias: bias_up, position_open: False. Decision: decision-uuid-123
```

```
INFO Stage 4 Mode Selected: trade_management. Reason: Position is open; 
     trade management mode selected (HTF bias: bias_down). 
     HTF bias: bias_down, position_open: True. Decision: decision-uuid-123
```

### ERROR: Error Level (Missing Input)

```
ERROR Stage 4 Mode Selection Failed: htf_bias_state is missing. 
      Cannot select reasoning mode without HTF bias state. 
      Decision: decision-uuid-123
```

### ERROR: Error Level (Invalid Input)

```
ERROR Stage 4 Mode Selection Failed: invalid htf_bias_state='foobar'. 
      Valid values: undefined, bias_up, bias_down, bias_neutral, invalidated. 
      Decision: decision-uuid-123
```

### ERROR: Error Level (Unresolvable State)

```
ERROR Stage 4 Mode Selection Hard Error: Unresolvable state: 
      HTF bias=undefined, position_open=False. 
      This should not occur with valid inputs. 
      Decision: decision-uuid-123
```

This should never happen, but if it does, we log it clearly.

### ERROR: Error Level (Internal Error)

```
ERROR Internal Error: ReasoningModeSelector returned None mode. 
      This indicates a logic error in mode selection. 
      Decision: decision-uuid-123
```

Again, this should never happen. It's a safety net.

## Metadata in EventResult

All Stage 4 errors include metadata:

```python
EventResult(
    status="rejected",
    reason="mode_selection_failed",
    metadata={
        "error": "specific_error_description",
        "advisory_errors": ["mode_selection_error: ...", "..."],
        "htf_bias_state": "undefined",  # if available
        "position_open": False,           # if available
        "decision_id": "..."              # for tracing
    }
)
```

This allows caller to understand why mode selection failed.

================================================================================
PART 6: TESTING STRATEGY
================================================================================

## Test Categories

### 1. Enum Tests (6 tests)
Verify HTFBiasState enum is correct.

```python
def test_undefined_value():
    assert HTFBiasState.UNDEFINED.value == "undefined"

def test_from_string():
    assert HTFBiasState("bias_up") == HTFBiasState.BIAS_UP
```

### 2. Mode Selection Rules (12 tests)

#### Rule 1: UNDEFINED/INVALIDATED → bias_evaluation
```python
def test_undefined_no_position():
    result = selector.select_mode(HTFBiasState.UNDEFINED, False)
    assert result.mode == "bias_evaluation"

def test_undefined_with_position():
    result = selector.select_mode(HTFBiasState.UNDEFINED, True)
    assert result.mode == "bias_evaluation"  # Rule 1 takes precedence

def test_invalidated_no_position():
    result = selector.select_mode(HTFBiasState.INVALIDATED, False)
    assert result.mode == "bias_evaluation"

def test_invalidated_with_position():
    result = selector.select_mode(HTFBiasState.INVALIDATED, True)
    assert result.mode == "bias_evaluation"
```

#### Rule 2: Valid bias & no position → entry_evaluation
```python
def test_bias_up_no_position():
    result = selector.select_mode(HTFBiasState.BIAS_UP, False)
    assert result.mode == "entry_evaluation"

def test_bias_down_no_position():
    result = selector.select_mode(HTFBiasState.BIAS_DOWN, False)
    assert result.mode == "entry_evaluation"

def test_bias_neutral_no_position():
    result = selector.select_mode(HTFBiasState.BIAS_NEUTRAL, False)
    assert result.mode == "entry_evaluation"
```

#### Rule 3: Position open → trade_management
```python
def test_bias_up_with_position():
    result = selector.select_mode(HTFBiasState.BIAS_UP, True)
    assert result.mode == "trade_management"

def test_bias_down_with_position():
    result = selector.select_mode(HTFBiasState.BIAS_DOWN, True)
    assert result.mode == "trade_management"

def test_bias_neutral_with_position():
    result = selector.select_mode(HTFBiasState.BIAS_NEUTRAL, True)
    assert result.mode == "trade_management"
```

### 3. Error Cases (7 tests)

```python
def test_invalid_bias_state_type_string():
    with pytest.raises(ModeSelectionError):
        selector.select_mode(htf_bias_state="bias_up", position_open=False)

def test_invalid_bias_state_type_none():
    with pytest.raises(ModeSelectionError):
        selector.select_mode(htf_bias_state=None, position_open=False)

def test_invalid_position_type_string():
    with pytest.raises(ModeSelectionError):
        selector.select_mode(HTFBiasState.BIAS_UP, position_open="true")

def test_invalid_position_type_int():
    with pytest.raises(ModeSelectionError):
        selector.select_mode(HTFBiasState.BIAS_UP, position_open=1)

def test_select_mode_from_dict_missing_bias_state():
    with pytest.raises(ModeSelectionError):
        selector.select_mode_from_dict({"position_open": False})

def test_select_mode_from_dict_missing_position():
    with pytest.raises(ModeSelectionError):
        selector.select_mode_from_dict({"htf_bias_state": "bias_up"})

def test_select_mode_from_dict_invalid_string_bias():
    with pytest.raises(ModeSelectionError):
        selector.select_mode_from_dict({
            "htf_bias_state": "invalid_bias",
            "position_open": False
        })
```

### 4. Integration Tests (4 tests)

```python
def test_state_machine_progression_new_bias():
    # Step 1: No bias
    result1 = selector.select_mode(HTFBiasState.UNDEFINED, False)
    assert result1.mode == "bias_evaluation"
    
    # Step 2: After bias established
    result2 = selector.select_mode(HTFBiasState.BIAS_UP, False)
    assert result2.mode == "entry_evaluation"

def test_state_machine_progression_entry_to_position():
    result1 = selector.select_mode(HTFBiasState.BIAS_UP, False)
    assert result1.mode == "entry_evaluation"
    
    result2 = selector.select_mode(HTFBiasState.BIAS_UP, True)
    assert result2.mode == "trade_management"

def test_state_machine_progression_invalidation():
    result1 = selector.select_mode(HTFBiasState.BIAS_DOWN, False)
    assert result1.mode == "entry_evaluation"
    
    result2 = selector.select_mode(HTFBiasState.INVALIDATED, False)
    assert result2.mode == "bias_evaluation"

def test_all_valid_combinations():
    for bias in [UNDEFINED, BIAS_UP, BIAS_DOWN, BIAS_NEUTRAL, INVALIDATED]:
        for position in [True, False]:
            result = selector.select_mode(bias, position)
            assert result.mode in ["bias_evaluation", "entry_evaluation", "trade_management"]
            assert result.error is None
```

## Test Results

```
31 tests total
31 passed
0 failed
100% pass rate
```

================================================================================
PART 7: DECISION PAYLOAD REQUIREMENTS
================================================================================

For Stage 4 to work, the decision payload MUST include:

```python
decision = {
    "id": "decision-uuid-123",                    # ← Required by orchestrator
    "symbol": "EURUSD",                           # ← Required by trading
    "htf_bias_state": "bias_up",                  # ← Required by Stage 4 ★
    "position_open": False,                       # ← Required by Stage 4 ★
    "entry_price": 1.08500,                       # ← Optional, for context
    "take_profit": 1.09000,                       # ← Optional
    "stop_loss": 1.08000,                         # ← Optional
    "reason": "...",                              # ← Optional, for audit
    # ... other fields ...
}
```

### htf_bias_state: Format

Can be:
  - String: "undefined", "bias_up", "bias_down", "bias_neutral", "invalidated"
  - HTFBiasState enum: HTFBiasState.BIAS_UP

Both are accepted (string is converted to enum internally).

### position_open: Format

Must be:
  - Boolean: True or False
  - No default (error if missing)
  - No conversion (int/string rejected)

### If Missing

If either field is missing from decision payload:

  Status: EventResult(status="rejected", reason="mode_selection_failed")
  Logged: "htf_bias_state is missing" or "position_open is missing"

### If Invalid

If values are invalid:

  Status: EventResult(status="rejected", reason="mode_selection_failed")
  Logged: "invalid htf_bias_state='foobar'" or "Invalid position_open type: int"

================================================================================
PART 8: EXECUTION CONTEXT ENRICHMENT
================================================================================

After successful mode selection, the execution context is enriched with:

```python
reasoning_context = {
    "decision_id": decision_id,
    "timestamp": int(time.time() * 1000),
    "event_type": "decision",
    "correlation_id": event.correlation_id,
    "reasoning_mode_selected": "entry_evaluation",      # ← Selected mode
    "htf_bias_state": "bias_up",                        # ← Input state
    "position_open": False                              # ← Input state
}
```

This context is passed to `reasoning_manager.reason()` and is available
to reasoning functions for logging/debugging purposes.

Note: Reasoning functions MUST NOT use this to re-decide the mode.
The mode is selected, the decision is made. Reasoning functions operate
within that mode only.

================================================================================
PART 9: NON-FUNCTIONAL REQUIREMENTS
================================================================================

## Performance
  - Mode selection: < 1ms (deterministic, no I/O, no LLM)
  - No external calls (stateless, local computation only)

## Determinism
  - Same inputs → same mode, always
  - No randomness, no conditional branching on uncontrolled state
  - Fully reproducible, auditable

## Fail-Closed
  - Invalid input → hard error, reject the cycle
  - No fallbacks, no defaults, no recovery attempts
  - Missing required fields → immediate rejection

## Type Safety
  - Enum for HTFBiasState (not string)
  - Bool for position_open (not int/string)
  - Mode is one of 3 literals (not arbitrary string)

## Error Transparency
  - All errors logged with specifics
  - All errors include decision_id for tracing
  - All errors include input state (if available)
  - Caller gets clear reason in EventResult.metadata

## No State Mutations
  - ReasoningModeSelector is stateless
  - No side effects, no global state changes
  - Safe for concurrent use (immutable)

================================================================================
END OF TECHNICAL SPECIFICATION
================================================================================
