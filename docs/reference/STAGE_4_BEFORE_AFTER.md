================================================================================
STAGE 4 BEFORE/AFTER: ARCHITECTURAL MINIMALISM
================================================================================

================================================================================
BEFORE: MONOLITHIC APPROACH (~180 lines inline)
================================================================================

```python
# Stage 4: Reasoning Mode Selection
# [Extensive inline validation, error handling, logging]
advisory_signals: List[AdvisorySignal] = []
advisory_errors: List[str] = []
selected_reasoning_mode: Optional[ReasoningMode] = None

if self.reasoning_manager is not None:
    try:
        htf_bias_state_str = decision.get("htf_bias_state")
        position_open = decision.get("position_open", False)
        
        if htf_bias_state_str is None:
            advisory_errors.append(...)
            logger.error(...)
            return EventResult(status="rejected", ...)
        
        try:
            htf_bias_state = HTFBiasState(htf_bias_state_str)
        except ValueError:
            advisory_errors.append(...)
            logger.error(...)
            return EventResult(status="rejected", ...)
        
        try:
            mode_selection_result = self.reasoning_mode_selector.select_mode(...)
            
            if mode_selection_result.mode is None or mode_selection_result.error:
                advisory_errors.append(...)
                logger.error(...)
                return EventResult(status="rejected", ...)
            
            selected_reasoning_mode = mode_selection_result.mode
            logger.info(...)
        
        except ModeSelectionError as e:
            advisory_errors.append(...)
            logger.error(...)
            return EventResult(status="rejected", ...)
        
        if selected_reasoning_mode is None:
            advisory_errors.append(...)
            logger.error(...)
            return EventResult(status="rejected", ...)
        
        # Invoke reasoning manager with selected mode
        decision_id = decision.get("id", event.correlation_id)
        plan_id = decision.get("plan", {}).get("id") ...
        
        reasoning_context: Dict[str, Any] = {
            "decision_id": decision_id,
            "timestamp": int(time.time() * 1000),
            "event_type": event.event_type,
            "correlation_id": event.correlation_id,
            "reasoning_mode_selected": selected_reasoning_mode,
            "htf_bias_state": htf_bias_state.value,
            "position_open": position_open
        }
        
        advisory_signals = await self.reasoning_manager.reason(...)
    
    except Exception as e:
        advisory_errors.append(...)
        logger.warning(...)
```

**Problems:**
- Hard to follow control flow
- Validation scattered throughout
- Multiple error paths
- Detailed logging clutters output
- Large cognitive load on reader
- Difficult to reuse
- Stage 4 reads as "control center"

================================================================================
AFTER: MINIMAL SPINE APPROACH (~50 lines inline + 68 line helper)
================================================================================

```python
# Stage 4: Reasoning Mode Selection
# Select mode based on HTF bias and position state.
# Returns early if mode selection fails.
advisory_signals: List[AdvisorySignal] = []
advisory_errors: List[str] = []
selected_reasoning_mode: Optional[ReasoningMode] = None

if self.reasoning_manager is not None:
    # Attempt mode selection
    mode_result = self._select_reasoning_mode(decision, event)
    if isinstance(mode_result, EventResult):
        # Mode selection failed; return rejection
        return mode_result
    
    selected_reasoning_mode = mode_result
    logger.info(
        "Stage 4 Mode Selected: %s (decision: %s)",
        selected_reasoning_mode,
        decision.get("id", event.correlation_id)
    )
    
    # Guard: reasoning only with valid mode
    try:
        decision_id = decision.get("id", event.correlation_id)
        plan_id = decision.get("plan", {}).get("id") ...
        
        # Invoke reasoning manager
        advisory_signals = await self.reasoning_manager.reason(
            decision_id=decision_id,
            event_payload=decision,
            execution_context={
                "decision_id": decision_id,
                "timestamp": int(time.time() * 1000),
                "event_type": event.event_type,
                "correlation_id": event.correlation_id,
                "reasoning_mode": selected_reasoning_mode
            },
            reasoning_mode=selected_reasoning_mode,
            plan_id=plan_id
        )
    except Exception as e:
        advisory_errors.append(f"reasoning_exception: {str(e)}")
        logger.warning("Reasoning exception (non-fatal): %s", e)
```

Plus:

```python
# Helper method (isolated, reusable, testable)
def _select_reasoning_mode(
    self,
    decision: Dict[str, Any],
    event: Event
) -> Union[ReasoningMode, EventResult]:
    """Stage 4: Select reasoning mode based on HTF bias and position state.
    
    Returns:
        Selected mode string if successful
        EventResult(status='rejected') if mode selection fails
    """
    # Extract state
    htf_bias_state_str = decision.get("htf_bias_state")
    position_open = decision.get("position_open", False)
    decision_id = decision.get("id", event.correlation_id)
    
    # Validate inputs
    if htf_bias_state_str is None:
        logger.error("Stage 4: htf_bias_state missing (decision: %s)", decision_id)
        return EventResult(
            status="rejected",
            reason="mode_selection_failed",
            metadata={"error": "htf_bias_state_missing"}
        )
    
    try:
        htf_bias_state = HTFBiasState(htf_bias_state_str)
    except ValueError:
        logger.error(
            "Stage 4: invalid htf_bias_state='%s' (decision: %s)",
            htf_bias_state_str,
            decision_id
        )
        return EventResult(
            status="rejected",
            reason="mode_selection_failed",
            metadata={"error": f"invalid_htf_bias_state:{htf_bias_state_str}"}
        )
    
    # Select mode
    try:
        result = self.reasoning_mode_selector.select_mode(
            htf_bias_state=htf_bias_state,
            position_open=position_open
        )
        if result.error:
            logger.error(
                "Stage 4: mode selection error: %s (decision: %s)",
                result.error,
                decision_id
            )
            return EventResult(
                status="rejected",
                reason="mode_selection_failed",
                metadata={"error": result.error}
            )
        return result.mode
    except ModeSelectionError as e:
        logger.error("Stage 4: %s (decision: %s)", e.message, decision_id)
        return EventResult(
            status="rejected",
            reason="mode_selection_failed",
            metadata={"error": e.message}
        )
```

**Benefits:**
- Clear, linear control flow
- Validation isolated in helper
- Early returns prevent nesting
- Minimal logging in hot path
- Easy to understand at a glance
- Reusable for other stages
- Stage 4 reads as "thin spine"

================================================================================
SIDE-BY-SIDE COMPARISON
================================================================================

| Aspect | Before | After |
|--------|--------|-------|
| Lines in handle_event() | ~180 | ~50 |
| Nested try-catch blocks | 4+ | 1 |
| Validation paths | Scattered | Isolated |
| Error messages | Detailed | Minimal |
| Code reusability | None | High |
| Cognitive load | High | Low |
| Testability | Indirect | Direct |
| Stage boundary clarity | Blurred | Clear |

================================================================================
CONTROL FLOW COMPARISON
================================================================================

BEFORE: Nested conditionals in hot path

```
if reasoning_manager:
  try:
    extract state
    if not state:
      error
      return
    try:
      convert enum
    except:
      error
      return
    try:
      select mode
      if error:
        error
        return
    except:
      error
      return
    if not mode:
      error
      return
    invoke reasoning
  except:
    error
```

AFTER: Linear with early return

```
if reasoning_manager:
  result = select_reasoning_mode()  # All validation here
  if error:
    return
  invoke reasoning
```

================================================================================
WHAT STAGE 4 IS NOW
================================================================================

A thin spine that:

1. **Accepts** state from decision payload
2. **Validates** via helper method (returns early on error)
3. **Stores** selected mode in local variable
4. **Guards** before invoking reasoning manager
5. **Returns** rejection if anything fails

That's it. No side effects, no state management, no coordination.

Future stages will attach here:
- Stage 5 (Quality filters) → Attach to guard
- Stage 6 (Advisory schema) → Attach to output
- Stage 7 (Expiration) → Attach to advisory generation

Stage 4 is the vertebra. Other stages hang off it.

================================================================================
END OF BEFORE/AFTER COMPARISON
================================================================================
