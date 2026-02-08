================================================================================
STAGE 4 ARCHITECTURAL VISION: MINIMAL SPINE
================================================================================

Stage 4 has been refactored to embody a single principle:

**A thin spine that future stages attach to, not a control center.**

================================================================================
THE SPINE METAPHOR
================================================================================

Before refactoring:
  Stage 4 was a **dense body** — 180 lines of orchestration, validation,
  error handling, logging. Control flowed through it. It felt like the
  orchestrator's "brain" for reasoning setup.

After refactoring:
  Stage 4 is now a **vertebra** — minimal structure that carries load
  (mode selection) and provides attachment points for future stages.
  Just 73 lines inline + 69 line helper. Clean, focused, reusable.

Visual:

  Before:
    ┌─────────────────────────────┐
    │   Stage 4 (180 lines)       │  ← Dense, monolithic
    │  - Validation              │     feels like control
    │  - Error handling          │     center
    │  - Logging                 │
    │  - Context setup           │
    │  - Guard + reasoning       │
    └─────────────────────────────┘

  After:
    ┌──────────────────┐
    │ Select Mode (73) │  ← Clean spine
    ├──────────────────┤
    │ Helper (69)      │  ← Reusable foundation
    └──────────────────┘
         ↑        ↓
    Accepts   Returns
    state      mode
              or error

================================================================================
SINGLE RESPONSIBILITY
================================================================================

Stage 4 does exactly one thing:

  "Given HTF bias state and position state, select a reasoning mode."

Not multiple things:
  ✗ Doesn't manage state
  ✗ Doesn't coordinate stages
  ✗ Doesn't cache results
  ✗ Doesn't modify data
  ✗ Doesn't access external systems

Just one thing:
  ✓ Select mode from state

This is radical simplicity.

================================================================================
CLEAN BOUNDARIES
================================================================================

Inputs:
  - htf_bias_state (from decision payload)
  - position_open (from decision payload)

Processing:
  - Validate inputs
  - Call selector
  - Handle errors

Outputs:
  - Selected mode (string)
  - OR rejection (EventResult)

No side effects. No state mutation. No context pollution.

================================================================================
REUSABILITY
================================================================================

The helper method _select_reasoning_mode() can be called from:

  - Main event handler (current)
  - Direct mode selection (future testing)
  - Other orchestrators (other systems)
  - Debugging utilities
  - Monitoring/telemetry

No assumptions about context. Just: state in → mode out.

================================================================================
FUTURE ATTACHMENT POINTS
================================================================================

Future stages will attach without modifying Stage 4:

Stage 5 (Quality Filters):
  ```
  if mode_result is None:
      apply_quality_gate()  # New stage
      return if below threshold
  ```
  Stage 4 still unchanged.

Stage 6 (Structured Advisory):
  ```
  create_advisory_schema(mode)  # New stage
  advisory_signals = await reasoning_manager.reason()
  ```
  Stage 4 still unchanged.

Stage 7 (Expiration):
  ```
  advisory_signals = await reasoning_manager.reason()
  add_expiration_time(advisory_signals)  # New stage
  ```
  Stage 4 still unchanged.

Each stage:
  - Uses mode from Stage 4
  - Doesn't modify Stage 4
  - Implements its own responsibility
  - Attaches to Stage 4 cleanly

================================================================================
WHAT'S NOT IN STAGE 4
================================================================================

Stage 4 explicitly does NOT include:

Memory Management (Stage 4b):
  - No decision history lookup
  - No outcome correlation
  - No memory constraints

Quality Assessment (Stage 5):
  - No confidence scoring
  - No regime suitability checks
  - No alignment validation

Advisory Formatting (Stage 6):
  - No schema enforcement
  - No field validation
  - No disclaimer injection

Expiration Logic (Stage 7):
  - No time calculations
  - No freshness validation
  - No reuse prevention

Each is a separate responsibility. Stage 4 is *none of these*.

Stage 4 is only: **Select Mode**

================================================================================
CODE STRUCTURE
================================================================================

In orchestrator.py:

```python
async def handle_event(event: Event):
    # ... Stage 1-3 ...
    
    if self.reasoning_manager is not None:
        mode_result = self._select_reasoning_mode(decision, event)
        if isinstance(mode_result, EventResult):
            return mode_result  # Early exit
        
        selected_reasoning_mode = mode_result
        logger.info("Stage 4 Mode Selected: %s", selected_reasoning_mode)
        
        # Guard: reasoning only with valid mode
        advisory_signals = await self.reasoning_manager.reason(
            reasoning_mode=selected_reasoning_mode
        )
    
    # ... Continue ...

def _select_reasoning_mode(decision, event):
    # Validate inputs
    # Select mode
    # Return mode or rejection
```

Observation:
  - Main handler: 10 lines for Stage 4
  - Helper: 69 lines for validation & selection
  - Total: 79 lines
  - Clean separation

================================================================================
GUIDING PRINCIPLE
================================================================================

"Do one thing. Do it well. Make it reusable."

Stage 4 embodies this principle. It:

  1. Does one thing: Select mode
  2. Does it well: Deterministic, type-safe, fail-closed
  3. Is reusable: Isolated helper, no dependencies, no side effects

Future stages will benefit from this clarity.

================================================================================
ARCHITECTURAL CONSEQUENCES
================================================================================

With this spine structure:

✓ **Easy to test**: Test mode selection in isolation
✓ **Easy to modify**: Change mode logic without touching orchestrator
✓ **Easy to reuse**: Helper method can be called from anywhere
✓ **Easy to extend**: Future stages attach cleanly
✓ **Easy to understand**: One responsibility per part
✓ **Easy to debug**: Clear input/output boundaries

✓ **Hard to misuse**: Limited surface, clear contracts
✗ **No monolithic coupling**: Stages aren't entangled

================================================================================
COMPARISON: CONTROL CENTER vs SPINE
================================================================================

Control Center Anti-Pattern:
  - Single stage responsible for many concerns
  - Other stages depend on its state/decisions
  - Changes require touching the core
  - Hard to test, modify, or extend
  - Becomes bottleneck and point of failure

Spine Pattern:
  - Single stage has single responsibility
  - Other stages attach independently
  - Changes isolated to one module
  - Easy to test, modify, and extend
  - Distributes concerns cleanly

Stage 4 is now a spine, not a control center.

================================================================================
END OF ARCHITECTURAL VISION
================================================================================

Stage 4: The thin vertebra upon which future stages build.

Minimal. Focused. Reusable. Ready.
