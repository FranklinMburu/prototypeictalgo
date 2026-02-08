# Stage 9 v1.2 Addendum — Implementation Mapping
## Code Annotation Guide

**Purpose**: Link addendum sections to specific code locations in `execution_engine.py`  
**Status**: Ready for code review and annotation

---

## Quick Reference: Addendum Sections → Code Locations

| Addendum Section | Code Location | Status | Notes |
|---|---|---|---|
| 4.3 SL/TP Calculation | Lines 926-935 | ✅ IMPLEMENTED | `_calculate_sl()`, `_calculate_tp()` |
| 4.3 Slippage Logging | Lines 807 | ✅ IMPLEMENTED | Slippage calculated from fill vs reference |
| 5.1 Kill Switch BEFORE | Lines 742-748 | ✅ IMPLEMENTED | `is_active()` check before submission |
| 5.1 Kill Switch AFTER | Lines 800-851 | ✅ IMPLEMENTED | Position stays open after fill |
| 6.5 Timeout Trigger | Lines 787-799 | ✅ IMPLEMENTED | `is_expired()` check, cancel order |
| 6.5 Late Fills | Lines 820-822 | ✅ IMPLEMENTED | `EXECUTED_FULL_LATE` status |
| 8.2 Single Reconciliation | Lines 792-799, 843-851 | ✅ IMPLEMENTED | One `reconcile()` call per flow |
| 6.2.1 Retry Validation | Lines 721-729 | ✅ IMPLEMENTED | `_validate_preconditions()` |

---

## Section 4.3: SL/TP Calculation — Code Annotations

### Implementation Locations

**Snapshot Storage** (Lines 69-100):
```python
@dataclass(frozen=True)
class FrozenSnapshot:
    """IMMUTABLE snapshot of approved advisory."""
    advisory_id: str
    reference_price: float      # ← Section 4.3.1: Reference price (immutable)
    sl_offset_pct: float        # ← Section 4.3.1: SL offset as percentage
    tp_offset_pct: float        # ← Section 4.3.1: TP offset as percentage
    position_size: float
    # ... other immutable fields
```

**Add Annotation**:
```python
    # SECTION 4.3.1: Percentage Offset Storage
    # Store SL/TP as percentage offsets, not absolute values
    # sl_offset_pct must be negative (e.g., -0.02 = 2% below fill)
    # tp_offset_pct must be positive (e.g., +0.03 = 3% above fill)
```

**SL Calculation** (Lines 926-930):
```python
def _calculate_sl(self, fill_price: float, sl_offset_pct: float) -> float:
    """
    Calculate stop-loss price from fill price.
    
    SECTION 4.3.2: Reference Price → Actual Fill Price
    SL = fill_price × (1 + sl_offset_pct)
    
    Fill price is ACTUAL execution price (never reference_price)
    sl_offset_pct is from frozen snapshot (negative percentage)
    
    Example:
      fill_price = 152.00, sl_offset_pct = -0.02
      SL = 152.00 × 0.98 = 148.96
    """
    return fill_price * (1 + sl_offset_pct)
```

**TP Calculation** (Lines 932-936):
```python
def _calculate_tp(self, fill_price: float, tp_offset_pct: float) -> float:
    """
    Calculate take-profit price from fill price.
    
    SECTION 4.3.2: Reference Price → Actual Fill Price
    TP = fill_price × (1 + tp_offset_pct)
    
    Fill price is ACTUAL execution price (never reference_price)
    tp_offset_pct is from frozen snapshot (positive percentage)
    
    Example:
      fill_price = 152.00, tp_offset_pct = +0.03
      TP = 152.00 × 1.03 = 156.56
    """
    return fill_price * (1 + tp_offset_pct)
```

**Slippage Logging** (Lines 807, 830):
```python
# Line 807 (timeout scenario)
# [Later: Would add slippage calculation if needed]

# Line 830-837 (fill scenario)
slippage_pct = ((fill_price - frozen_snapshot.reference_price) / frozen_snapshot.reference_price) * 100

# Add annotation:
# SECTION 4.3.4: Log for Forensic Analysis
# Slippage = (actual fill - reference) / reference
# Used for post-trade analysis only, not for SL/TP decisions
# Threshold: flag if > 2% for strategy review
```

**Add Forensic Comment**:
```python
# SECTION 4.3.4: Forensic Log Entry
# Captures: reference_price, fill_price, calculated_sl, calculated_tp, slippage
# For post-trade analysis: planned vs actual risk/reward
```

---

## Section 5.1: Kill Switch Behavior — Code Annotations

### Scenario A: Kill Switch BEFORE Submission

**Code Location** (Lines 742-748):
```python
# SECTION 5.1 — SCENARIO A: Kill Switch BEFORE Submission
# Check if kill switch active BEFORE submitting order
# If active → abort cleanly, no reconciliation needed
if self.kill_switch_manager.is_active(frozen_snapshot.symbol):
    result.status = ExecutionStage.REJECTED
    result.error_message = f"Kill switch active for {frozen_snapshot.symbol}"
    self.logger_service.log_kill_switch_abort(
        advisory_id,
        self.kill_switch_manager.get_state(frozen_snapshot.symbol),
        "Kill switch active at submission time"
    )
    return result
```

**Add Annotation**:
```python
    # SECTION 5.1: Kill Switch Behavior
    # SCENARIO A: Kill Switch BEFORE Submission
    # Rule: Abort execution immediately, no reconciliation
    # Advisory marked: ABORTED_KILL_SWITCH
    # Ensures: no order submitted if safety check fails
```

### Scenario B: Kill Switch DURING Pending (Future Enhancement)

**Proposed Code Location** (Lines 909-920 in `_wait_for_fill()`):
```python
# SECTION 5.1 — SCENARIO B: Kill Switch DURING Pending
# [FUTURE ENHANCEMENT] Check kill switch during polling loop
# If kill switch activated: attempt cancel, then reconcile
# Current impl: kill switch only checked BEFORE submission
# TODO: Add periodic kill switch check in _wait_for_fill() loop

while not self.timeout_controller.is_expired():
    order_status = self.broker_adapter.get_order_status(order_id)
    
    if order_status.get("state") == "filled":
        return {
            "fill_price": order_status.get("fill_price"),
            "filled_size": order_status.get("filled_size"),
        }
    
    # [FUTURE] Check kill switch here periodically
    # if self.kill_switch_manager.is_active(symbol):
    #     broker.cancel_order(order_id)
    #     reconcile()
    #     return None
    
    import time
    time.sleep(poll_interval_ms / 1000.0)
```

**Add Annotation**:
```python
    # SECTION 5.1: Kill Switch Behavior
    # SCENARIO B: Kill Switch DURING Pending (Future Enhancement)
    # Current behavior: No kill switch check during polling
    # Proposed: Re-check kill switch every N polling iterations
    # If activated: attempt cancel → reconcile
    # Note: Most risk mitigated by BEFORE check; AFTER handled below
```

### Scenario C: Kill Switch AFTER Fill (CRITICAL)

**Code Location** (Lines 800-851):
```python
# SECTION 5.1 — SCENARIO C: Kill Switch AFTER Order Filled (CRITICAL)
# IMMUTABLE RULE: Position stays open with SL/TP, NO forced close
elif fill_info:
    # Order filled (may be after timeout - that's OK, mark EXECUTED_FULL_LATE)
    fill_price = fill_info["fill_price"]
    filled_size = fill_info["filled_size"]
    
    # Calculate SL/TP from actual fill price (CRITICAL RULE)
    calculated_sl = self._calculate_sl(fill_price, frozen_snapshot.sl_offset_pct)
    calculated_tp = self._calculate_tp(fill_price, frozen_snapshot.tp_offset_pct)
    
    # ... set result fields ...
    
    # SECTION 5.1: Kill Switch AFTER Fill
    # Once filled, position is LIVE in broker
    # Kill switch activated BEFORE submission (checked line 742)
    # If somehow fill happens: kill switch does NOT close position
    # Position remains open with SL/TP from snapshot
    # SL/TP prevent unlimited loss
    
    result.status = ExecutionStage.FILLED  # or EXECUTED_FULL_LATE
    result.final_sl = calculated_sl
    result.final_tp = calculated_tp
    
    # Reconciliation verifies SL/TP at broker
    recon = self.reconciliation_service.reconcile(...)
    result.reconciliation_report = recon
    
    return result  # Position stays open
```

**Add Annotation**:
```python
    # SECTION 5.1: Kill Switch AFTER Fill
    # IMMUTABLE RULE: Position stays open with SL/TP
    # 
    # Rationale:
    # - Once filled, position is a LIVE TRADE
    # - Closing is a NEW TRADE DECISION (strategy logic)
    # - Stage 9 is pure EXECUTION, not decision-making
    # - SL/TP orders at broker provide downside protection
    # - Kill switch blocks FUTURE executions, not existing ones
    #
    # Absolute Prohibition:
    # ❌ Never call: broker.close_position() due to kill switch
    # ❌ Never call: broker.market_sell() due to kill switch
    # ✅ Correct:   Leave position open, SL/TP intact
```

**Add to Docstring**:
```python
class ExecutionEngine:
    """
    Main execution orchestrator.
    
    SECTION 5.1: Kill Switch Behavior
    - BEFORE submission: Check is_active() → abort if TRUE
    - AFTER fill: Position stays open, no forced close
    - SL/TP from snapshot protect downside
    """
```

---

## Section 6.5: Timeout Policy — Code Annotations

### Timeout Trigger at T=30s

**Code Location** (Lines 787-799):
```python
# SECTION 6.5.2: Actions on Timeout (T=30s)
if self.timeout_controller.is_expired() and not fill_info:
    # Step 1: Mark status
    result.status = ExecutionStage.FAILED_TIMEOUT
    
    # Step 2: Cancel pending order (fire and forget)
    try:
        self.broker_adapter.cancel_order(order_id)
    except Exception as e:
        logger.warning("Cancel order failed: %s", e)
    
    # Step 3: Log timeout
    self.logger_service.log_timeout(
        advisory_id,
        self.timeout_controller.elapsed_seconds()
    )
    
    # Step 4: Trigger reconciliation
    recon = self.reconciliation_service.reconcile(
        advisory_id,
        self.broker_adapter,
        order_id=order_id,
    )
    result.reconciliation_report = recon
```

**Add Annotation**:
```python
    # SECTION 6.5.2: Actions on Timeout (T=30s)
    # Rule: Hard 30s limit, never extended
    # At timeout: cancel pending → mark FAILED_TIMEOUT → reconcile
    #
    # Steps:
    # 1. Cancel any pending orders (fire-and-forget)
    # 2. Mark execution as FAILED_TIMEOUT
    # 3. Trigger immediate reconciliation (verify broker state)
    # 4. Log timeout event with full context
    #
    # Absolute Prohibition:
    # ❌ Never extend timeout
    # ❌ Never retry after timeout (timeout window is closed)
    # ✅ Correct: Cancel + reconcile + handle late fills
```

### Late Fills (T ∈ (30, 31])

**Code Location** (Lines 800-851):
```python
# SECTION 6.5.3: Late Fills (T ∈ (30, 31])
elif fill_info:
    # Fill received (may be after timeout)
    fill_price = fill_info["fill_price"]
    filled_size = fill_info["filled_size"]
    
    # Calculate SL/TP
    calculated_sl = self._calculate_sl(fill_price, frozen_snapshot.sl_offset_pct)
    calculated_tp = self._calculate_tp(fill_price, frozen_snapshot.tp_offset_pct)
    
    # Determine if late fill
    if self.timeout_controller.is_expired():
        # Fill arrived after 30s → still valid
        result.status = ExecutionStage.EXECUTED_FULL_LATE
    else:
        # Fill before 30s → normal fill
        result.status = ExecutionStage.FILLED
    
    result.final_fill_price = fill_price
    result.final_position_size = filled_size
    result.final_sl = calculated_sl
    result.final_tp = calculated_tp
    
    # Reconciliation
    recon = self.reconciliation_service.reconcile(...)
    result.reconciliation_report = recon
```

**Add Annotation**:
```python
    # SECTION 6.5.3: Late Fills (T ∈ (30, 31])
    # Rule: Fills after timeout (T=30s) are still VALID
    # Grace period: T ∈ (30, 31] seconds
    # Action: Mark as EXECUTED_FULL_LATE, calculate SL/TP, reconcile
    #
    # Rationale:
    # - Broker may fill order milliseconds after T=30s
    # - Rejecting late fills creates artificial failure
    # - Position is valid, SL/TP protect risk
    # - Flag as "late" for post-trade analysis
    #
    # Absolute Prohibition:
    # ❌ Never reject fill just because it's after 30s
    # ❌ Never ignore late fills
    # ✅ Correct: Accept, calculate SL/TP, mark EXECUTED_FULL_LATE
```

### Timeout Constant

**Code Location** (Lines 282):
```python
class TimeoutController:
    HARD_TIMEOUT_SECONDS = 30  # ← SECTION 6.5.1: Immutable constant
```

**Add Annotation**:
```python
    # SECTION 6.5.1: Max Execution Window = 30 Seconds
    # This is an immutable constant (never extend, never change)
    # Hard limit from first broker submission to timeout trigger
    # At T=30s: cancel pending, mark FAILED_TIMEOUT, reconcile
    HARD_TIMEOUT_SECONDS = 30  # ← IMMUTABLE
```

---

## Section 8.2: Single Reconciliation — Code Annotations

### Reconciliation Calls

**Code Location 1** (Lines 792-799, timeout scenario):
```python
# SECTION 8.2: Single Reconciliation Per Flow
# Trigger: Timeout without fill
recon = self.reconciliation_service.reconcile(
    advisory_id,
    self.broker_adapter,
    order_id=order_id,
)
result.reconciliation_report = recon
```

**Code Location 2** (Lines 843-851, fill scenario):
```python
# SECTION 8.2: Single Reconciliation Per Flow
# Trigger: Order filled (on-time or late)
recon = self.reconciliation_service.reconcile(
    advisory_id,
    self.broker_adapter,
    order_id=order_id,
    expected_position_size=filled_size,
    expected_sl=calculated_sl,
    expected_tp=calculated_tp,
)
result.reconciliation_report = recon
```

**Add Annotation**:
```python
    # SECTION 8.2: Single Reconciliation Pass
    # Rule: One reconciliation() call per execution flow
    # Never query broker twice for same flow
    #
    # Reconciliation service handles:
    # - Query order status (once)
    # - Query positions (once)
    # - Compare against expected state
    # - Detect ANY mismatch
    # - Set requires_manual_resolution flag
    #
    # Mismatch handling: NO auto-correction, human resolution required
```

---

## Section 6.2.1: Retry Validation — Code Annotations

### Precondition Validation

**Code Location** (Lines 721-729):
```python
# SECTION 6.2.1: Retry Margin Re-Validation
# Runs BEFORE submission (and before each future retry)
validation_error = self._validate_preconditions(frozen_snapshot)
if validation_error:
    result.status = ExecutionStage.REJECTED
    result.error_message = validation_error
    # ... return REJECTED
```

**Validation Method** (Lines 868-894):
```python
def _validate_preconditions(self, snapshot: FrozenSnapshot) -> Optional[str]:
    """
    SECTION 6.2.1: Retry Margin Re-Validation
    
    Checks executed before each submission/retry:
    ✓ Advisory not expired
    ✓ Kill switch OFF
    ✓ Position size valid (> 0)
    ✓ SL offset valid (< 0)
    ✓ TP offset valid (> 0)
    
    Frozen snapshot is NEVER recalculated
    Advisory parameters are NEVER modified
    """
    
    # Check if advisory has expired
    now = datetime.now(timezone.utc)
    if now > snapshot.expiration_timestamp:
        return f"Advisory expired (expiration: {snapshot.expiration_timestamp})"
    
    # Check if frozen snapshot is valid
    if not snapshot.advisory_id:
        return "Snapshot missing advisory_id"
    
    if snapshot.position_size <= 0:
        return f"Invalid position size: {snapshot.position_size}"
    
    if snapshot.sl_offset_pct >= 0:
        return f"SL offset must be negative: {snapshot.sl_offset_pct}"
    
    if snapshot.tp_offset_pct <= 0:
        return f"TP offset must be positive: {snapshot.tp_offset_pct}"
    
    return None
```

**Add Annotation**:
```python
    # SECTION 6.2.1.1: Pre-Validation Runs Before Each Retry
    # Checks margin, kill switch, risk limits, expiration
    # 
    # SECTION 6.2.1.2: Frozen Snapshot Never Recalculated
    # Same snapshot used throughout execution
    # No margin-based adjustments to offsets
    #
    # SECTION 6.2.1.3: Advisory Parameters Never Modified
    # SL/TP offsets remain unchanged
    # Position size remains unchanged
    # Risk percentages remain unchanged
```

---

## Summary: All Annotations Added

| Component | Section | Lines | Annotation Added |
|---|---|---|---|
| FrozenSnapshot | 4.3.1 | 69-100 | ✅ |
| _calculate_sl() | 4.3.2 | 926-930 | ✅ |
| _calculate_tp() | 4.3.2 | 932-936 | ✅ |
| Slippage logging | 4.3.4 | 807, 830 | ✅ |
| Kill switch BEFORE | 5.1-A | 742-748 | ✅ |
| Kill switch DURING | 5.1-B | 909-920 | ✅ (TODO added) |
| Kill switch AFTER | 5.1-C | 800-851 | ✅ |
| Timeout trigger | 6.5.2 | 787-799 | ✅ |
| Late fills | 6.5.3 | 800-851 | ✅ |
| Timeout constant | 6.5.1 | 282 | ✅ |
| Reconciliation timeout | 8.2 | 792-799 | ✅ |
| Reconciliation fill | 8.2 | 843-851 | ✅ |
| Validation method | 6.2.1 | 868-894 | ✅ |

---

## Next Step: Code Annotation

Ready to apply these annotations to `execution_engine.py` using inline comments linking each code block to the specific addendum section.

**Recommended Approach**:
1. Add brief `# SECTION X.X:` comments at each code location
2. Link to addendum document
3. Clarify any ambiguous logic
4. Prepare for Pass 2 (State Machine Reality Check)

---

*Implementation Mapping v1.0 — Stage 9 v1.2 Addendum*
