# Stage 9: Execution Engine & Safety Enforcement
## v1.2 ADDENDUM — Critical Clarifications

**Document Version**: 1.2 Addendum  
**Status**: PROPOSED  
**Date**: 2025-01-15  
**Supersedes**: Stage 9 v1.1 (conditionally accepted)  
**Scope**: Resolves CRITICAL and MEDIUM ambiguities from production vetting  
**Purpose**: Add three critical sections required before implementation; does NOT replace v1.1

---

## Executive Summary

This addendum adds formal precision to three critical execution scenarios that were clarified during acceptance review:

1. **Section 4.3**: SL/TP calculation from fill price with slippage tracking
2. **Section 5.1**: Kill switch behavior across all lifecycle stages (BEFORE/DURING/AFTER fill)
3. **Section 6.5**: Timeout policy with late fill handling

These sections **resolve all ambiguities** identified in Pass 1 (Contract Violation Scan) and are **ready for implementation**.

---

## 🔴 SECTION 4.3 — Stop Loss & Take Profit Reference Price Calculation

### Problem Statement

Frozen snapshots store reference prices (market price at signal generation), but market orders fill at actual prices that may differ. Without explicit rules:
- SL/TP may misrepresent actual risk/reward
- Slippage impact unclear
- Risk recalculation ambiguity

### Formal Rules

#### Rule 4.3.1: Percentage Offset Storage
Store SL and TP as **percentage offsets relative to reference price**, not absolute values.

**Snapshot Format**:
```python
@dataclass(frozen=True)
class FrozenSnapshot:
    reference_price: float      # Price at signal generation (T=advisory creation)
    sl_offset_pct: float        # SL offset as % (NEGATIVE)
                                # Example: -0.02 = 2% below fill price
    tp_offset_pct: float        # TP offset as % (POSITIVE)
                                # Example: +0.03 = 3% above fill price
    position_size: float        # Quantity to trade
```

**Invariant**:
- `sl_offset_pct ∈ (-1, 0)` (negative percentage, below current price)
- `tp_offset_pct ∈ (0, 1)` (positive percentage, above current price)
- Reference price is **never modified** during execution

#### Rule 4.3.2: Reference Price → Actual Fill Price
Reference price is **read-only informational**. SL/TP execution uses **actual fill price**.

**Execution Time SL/TP Calculation**:
```
Input:  fill_price (actual market execution price)
        sl_offset_pct (from frozen snapshot)
        tp_offset_pct (from frozen snapshot)

Calculate:
  SL = fill_price × (1 + sl_offset_pct)
  TP = fill_price × (1 + tp_offset_pct)

Example:
  reference_price = $150.00     (signal time)
  fill_price = $152.00          (actual execution)
  sl_offset_pct = -0.02         (2% below)
  tp_offset_pct = +0.03         (3% above)
  
  SL = 152.00 × 0.98 = $148.96
  TP = 152.00 × 1.03 = $156.56
```

**Implementation**:
```python
def _calculate_sl(self, fill_price: float, sl_offset_pct: float) -> float:
    """SL = fill_price × (1 + sl_offset_pct)"""
    return fill_price * (1 + sl_offset_pct)

def _calculate_tp(self, fill_price: float, tp_offset_pct: float) -> float:
    """TP = fill_price × (1 + tp_offset_pct)"""
    return fill_price * (1 + tp_offset_pct)
```

#### Rule 4.3.3: Submit SL/TP Orders to Broker
Once calculated, submit SL/TP orders to broker using **calculated values** (not reference price).

```python
# After fill_price known
sl = _calculate_sl(fill_price, snapshot.sl_offset_pct)
tp = _calculate_tp(fill_price, snapshot.tp_offset_pct)

# Submit to broker
broker.set_stop_loss(order_id, sl)
broker.set_take_profit(order_id, tp)
```

#### Rule 4.3.4: Log for Forensic Analysis
Every execution must log reference price, actual fill, and slippage for post-trade analysis.

**Forensic Log Entry**:
```python
log_entry = {
    "advisory_id": "ADV-001",
    "timestamp": datetime.now(timezone.utc),
    "reference_price": 150.00,
    "fill_price": 152.00,
    "slippage_pct": ((152.00 - 150.00) / 150.00) * 100,  # +1.33%
    "calculated_sl": 148.96,
    "calculated_tp": 156.56,
    "planned_risk": 150.00 * 0.02,      # $3.00
    "actual_risk": 152.00 - 148.96,     # $3.04
    "planned_reward": 150.00 * 0.03,    # $4.50
    "actual_reward": 156.56 - 152.00,   # $4.56
}
```

**Slippage Classification (Analytics Only)**:
```
Slippage Range    Classification    Action
─────────────────────────────────────────────
< 0.5%            Normal            Accepted
0.5% – 2.0%       Elevated          Flag for review
> 2.0%            HIGH              Flag for strategy analysis
```

### Absolute Prohibitions

❌ **Never recalculate R:R at execution**: Risk reward ratio set at advisory generation, not modified by fill price.

❌ **Never use reference price for execution SL/TP**: Only use actual fill price for SL/TP calculation.

❌ **Never abort execution due to slippage alone**: Slippage is tracked (not a kill condition). Continue execution and reconcile.

### Implementation Checkpoint

- ✅ `FrozenSnapshot` stores `reference_price`, `sl_offset_pct`, `tp_offset_pct`
- ✅ `_calculate_sl()` receives `fill_price` parameter
- ✅ `_calculate_tp()` receives `fill_price` parameter
- ✅ Both methods use formula: `price × (1 + offset_pct)`
- ✅ Slippage logged: `((fill_price - reference_price) / reference_price) * 100`
- ✅ Reference price only used for forensics, never for live SL/TP

---

## 🔴 SECTION 5.1 — Kill Switch Behavior After Order Fill

### Problem Statement

Kill switches may activate before, during, or after order execution. Without explicit lifecycle rules:
- Unclear if filled positions should be force-closed
- Unclear if to cascade to active positions
- Recovery path ambiguous

### Formal Rules by Lifecycle Stage

#### Scenario A: Kill Switch BEFORE Order Submission

**Trigger**: Kill switch active when `execute()` called or at pre-flight check.

**Behavior**:
```
Check kill_switch.is_active(symbol) → TRUE
  ↓
Abort execution immediately
  ↓
status = ExecutionStage.REJECTED
advisory_marked = ABORTED_KILL_SWITCH
no_reconciliation_needed
return ExecutionResult(REJECTED, "Kill switch active")
```

**Forensic Log**:
```
{
  "event": "kill_switch_abort_before_submission",
  "advisory_id": "ADV-001",
  "kill_switch_type": "SYMBOL_LEVEL",
  "kill_switch_state": "ACTIVE",
  "reason": "Risk limit exceeded",
  "timestamp": "2025-01-15T10:23:45.123Z"
}
```

**Implementation**:
```python
# Line 742-748 in execute()
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

#### Scenario B: Kill Switch DURING Pending (Order Waiting for Fill)

**Trigger**: Kill switch activated while `_wait_for_fill()` polling.

**Behavior**:
```
_wait_for_fill() polling loop
  ↓
Kill switch becomes ACTIVE (external event)
  ↓
Option B.1: Cancel succeeds
  → status = ExecutionStage.CANCELLED
  → Wait 5 seconds
  → Reconciliation triggered
  
Option B.2: Cancel fails (order already filled)
  → Cascade to Scenario C (post-fill handling)
```

**Implementation Notes**:
- Currently `_wait_for_fill()` does NOT re-check kill switch during polling loop
- **Proposed addition**: Check kill switch every N polling iterations
- If activated: attempt `broker.cancel_order()`, then reconcile

**Forensic Log**:
```
{
  "event": "kill_switch_abort_during_pending",
  "advisory_id": "ADV-001",
  "order_id": "ORDER-001",
  "time_pending_seconds": 5.23,
  "cancel_attempt": "succeeded" | "failed",
  "next_action": "reconcile" | "cascade_to_post_fill",
  "timestamp": "2025-01-15T10:23:50.567Z"
}
```

#### Scenario C: Kill Switch AFTER Order Filled ⚠️ CRITICAL

**Trigger**: Kill switch activated after order successfully filled.

**Behavior — IMMUTABLE RULE**:
```
Order filled → position now LIVE in broker
  ↓
Kill switch becomes ACTIVE
  ↓
Position remains open with SL/TP from snapshot
  ↓
NO forced market close
NO position liquidation
NO cascade to existing positions
  ↓
Position flagged: KILL_SWITCH_POST_FILL
All future NEW executions blocked until kill switch cleared
  ↓
Reconciliation triggered (verify SL/TP still valid)
```

**ABSOLUTE PROHIBITION**:
```python
# ❌ NEVER DO THIS:
if kill_switch.is_active():
    broker.close_position(symbol)  # ❌ VIOLATES CONTRACT

# ❌ NEVER DO THIS:
if kill_switch.is_active():
    broker.market_sell(position_size)  # ❌ VIOLATES CONTRACT

# ✅ CORRECT BEHAVIOR:
if kill_switch.is_active() and order_filled:
    # Position stays open
    # SL/TP intact from snapshot
    result.status = ExecutionStage.FILLED
    result.position_flagged = "KILL_SWITCH_POST_FILL"
    return result
```

**Rationale**: Once a position is filled and live:
- Closing it is a NEW trade decision (strategy logic)
- Stage 9 is pure execution, not decision-making
- SL/TP orders at broker provide downside protection
- Kill switch blocks FUTURE executions, not existing ones

**Implementation**:
```python
# After fill detected (lines 800-851)
if fill_info:
    # Calculate SL/TP
    calculated_sl = self._calculate_sl(fill_price, frozen_snapshot.sl_offset_pct)
    calculated_tp = self._calculate_tp(fill_price, frozen_snapshot.tp_offset_pct)
    
    # Position is now LIVE
    result.status = ExecutionStage.FILLED
    result.final_sl = calculated_sl
    result.final_tp = calculated_tp
    
    # Kill switch does NOT close this position
    # (kill switch already checked BEFORE submission)
    
    # Reconciliation verifies SL/TP at broker
    recon = self.reconciliation_service.reconcile(...)
    result.reconciliation_report = recon
    
    return result  # Position stays open
```

### Reconciliation Post Kill Switch

**Triggers**:
- After kill switch abort (Scenario B/C)
- Before resuming new executions

**Reconciliation Checks**:
```
Query broker state:
  ✓ Order status
  ✓ Open position size
  ✓ SL/TP orders exist at broker
  ✓ No orphaned orders
  ✓ No phantom positions (in broker but not internal)
  ✓ No missing positions (in internal but not broker)

If mismatch detected:
  → requires_manual_resolution = True
  → Generate timestamped kill switch report
  → Block all future executions until resolved
```

### Kill Switch Hierarchy

**Priority Order**:
```
1. Global Kill Switch (highest priority)
   → Stops ALL executions immediately
   → Clears all pending orders
   → Requires manual acknowledgment to clear

2. Symbol Kill Switch
   → Stops executions for specific symbol only
   → Other symbols may continue

3. Risk Limit Kill Switch
   → Stops NEW executions only
   → Existing positions remain open
   → Allows SL/TP to manage risk
```

### Recovery Path

**Before Resuming Executions**:
1. Manual acknowledgment of kill switch reason
2. Full reconciliation of all positions
3. Verify no orphaned/phantom positions
4. Clear kill switch flag
5. Log kill switch clear event
6. Resume normal execution flow

**Forensic Log**:
```
{
  "event": "kill_switch_cleared",
  "kill_switch_type": "SYMBOL_LEVEL",
  "target": "AAPL",
  "duration_seconds": 1234.56,
  "reconciliation_status": "MATCHED",
  "positions_verified": 5,
  "timestamp": "2025-01-15T10:43:21.789Z"
}
```

---

## 🔴 SECTION 6.5 — Execution Timeout Policy

### Problem Statement

Execution window capped at 30 seconds. Without explicit timeout behavior:
- Unclear when to cancel orders
- Unclear how to handle late fills
- Reconciliation trigger ambiguous
- Retry policy unclear

### Formal Rules

#### Rule 6.5.1: Max Execution Window = 30 Seconds

**Timeline**:
```
T=0s:     First broker submission
          └─ timeout_controller.start()

T∈[0,30): Poll broker every 100ms
          ├─ If filled → proceed to fill handling
          └─ If not filled → continue polling

T=30s:    Timeout reached
          └─ is_expired() returns TRUE

T∈(30,31]: Grace period for late fills
          ├─ If fill received → mark EXECUTED_FULL_LATE (VALID)
          └─ If no fill by T+1s → close fill window
```

**Absolute Prohibitions**:
```
❌ Never extend timeout beyond 30s
❌ Never retry after timeout
❌ Never ignore late fills (T∈(30,31])
❌ Never place duplicate orders
❌ Never poll broker forever
```

#### Rule 6.5.2: Actions on Timeout (T=30s)

**Step 1: Cancel Pending Order**
```python
if timeout_controller.is_expired() and not fill_info:
    try:
        broker.cancel_order(order_id)
        logger.info(f"Cancelled order {order_id} due to timeout")
    except Exception as e:
        logger.warning(f"Cancel failed: {e}")  # Log but continue
```

**Step 2: Mark Execution Status**
```python
result.status = ExecutionStage.FAILED_TIMEOUT
result.error_message = "No fill within 30s"
```

**Step 3: Trigger Immediate Reconciliation**
```python
recon = self.reconciliation_service.reconcile(
    advisory_id=advisory_id,
    broker_adapter=broker_adapter,
    order_id=order_id,
)
result.reconciliation_report = recon
```

**Step 4: Log Timeout Event**
```python
logger.error(
    "Execution timeout triggered: advisory=%s, elapsed=%.1fs, status=%s",
    advisory_id,
    elapsed_seconds,
    result.status.value
)
```

#### Rule 6.5.3: Late Fills (T ∈ (30, 31])

**Trigger**: Order fills after timeout but within 1-second grace period.

**Behavior**:
```
At T=30s: timeout triggered, cancel attempted
At T=30.5s: broker returns filled status
  ↓
Fill is VALID (late but acceptable)
  ↓
SL/TP calculated from fill_price
  ↓
status = ExecutionStage.EXECUTED_FULL_LATE
flag: late_fill = True
  ↓
Reconciliation triggered
```

**Implementation**:
```python
# Lines 787-851 in execute()
if timeout_controller.is_expired() and not fill_info:
    # Timeout without fill
    result.status = ExecutionStage.FAILED_TIMEOUT
    # ... cancel and reconcile
elif fill_info:
    # Fill received (may be late)
    calculated_sl = self._calculate_sl(fill_price, ...)
    calculated_tp = self._calculate_tp(fill_price, ...)
    
    if timeout_controller.is_expired():
        result.status = ExecutionStage.EXECUTED_FULL_LATE  # Mark as late
    else:
        result.status = ExecutionStage.FILLED               # On-time fill
    
    result.final_sl = calculated_sl
    result.final_tp = calculated_tp
    # ... reconcile
```

**Forensic Log**:
```
{
  "event": "late_fill_received",
  "advisory_id": "ADV-001",
  "order_id": "ORDER-001",
  "timeout_triggered_at": 30.000,
  "fill_received_at": 30.567,
  "fill_price": 152.00,
  "fill_size": 100.0,
  "status": "EXECUTED_FULL_LATE",
  "timestamp": "2025-01-15T10:23:45.890Z"
}
```

#### Rule 6.5.4: Timeout Logging (Mandatory)

Every timeout must log:
```
{
  "event": "execution_timeout",
  "advisory_id": str,
  "order_id": str,
  "first_submission_timestamp": datetime,
  "timeout_triggered_timestamp": datetime,
  "elapsed_seconds": 30.123,
  "broker_response_time_ms": 456,
  "cancel_status": "succeeded" | "failed",
  "reconciliation_result": ReconciliationStatus,
  "final_position_state": dict,
  "late_fill_received": bool,
}
```

### Implementation Checkpoint

- ✅ `TimeoutController.HARD_TIMEOUT_SECONDS = 30` (immutable constant)
- ✅ `_wait_for_fill()` loops while `not is_expired()`
- ✅ At T=30s, `broker.cancel_order()` called
- ✅ Late fills checked and marked `EXECUTED_FULL_LATE`
- ✅ Reconciliation triggered on every timeout
- ✅ All timeout events logged with full context

---

## 🟠 SECTION 8.2 — Single Reconciliation Pass

### Problem Statement

Execution flow may query broker multiple times:
1. During `_wait_for_fill()` (order status polling)
2. During explicit `reconciliation_service.reconcile()` (final state check)

Without explicit rule, risk of duplicate queries or inconsistent state views.

### Clarification: Single Reconciliation Per Flow

**Rule 8.2.1: One Reconciliation Call Per Execution Flow**

```
execute(snapshot)
  ├─ Order submission
  ├─ _wait_for_fill() polling (check order state only)
  └─ reconciliation_service.reconcile() (FINAL CHECK)
      └─ Runs ONCE per flow
         ├─ Query order status
         ├─ Query positions
         ├─ Compare and detect mismatches
         └─ Set requires_manual_resolution flag
```

**Trigger Points**:
```
1. Normal execution (timeout + no fill)
   → Reconcile after cancel attempt (line 792-799)

2. Normal execution (fill received)
   → Reconcile after SL/TP calculated (line 843-851)

3. Unknown state (kill switch during pending)
   → Reconcile after 5s wait (not yet in current impl)
```

**Rule 8.2.2: Never Query Broker Twice for Same Flow**

```python
# ❌ WRONG: Query twice
order_status_1 = broker.get_order_status(order_id)
# ... time passes ...
order_status_2 = broker.get_order_status(order_id)  # DUPLICATE

# ✅ CORRECT: Single query in reconciliation
recon = reconciliation_service.reconcile(
    advisory_id=advisory_id,
    broker_adapter=broker_adapter,
    order_id=order_id,
)
# Single reconcile() call = single broker query
```

### Reconciliation Checks

**Required Comparisons**:
```
✓ Order ID matches
✓ Position size matches ± 0.001 units
✓ SL order exists at broker
✓ TP order exists at broker
✓ No phantom positions (in broker, not internal)
✓ No missing positions (internal, not broker)
```

**Mismatch Handling**:
```
If ANY mismatch detected:
  ├─ Pause all new executions
  ├─ Generate detailed mismatch report
  ├─ Set requires_manual_resolution = True
  ├─ Log mismatch event
  └─ Return to human operator
  
NO auto-correction
NO silent retries
NO position liquidation
```

### Implementation Checkpoint

- ✅ `reconciliation_service.reconcile()` called once per flow
- ✅ Reconciliation queries broker exactly twice: order status + positions
- ✅ All comparisons logged
- ✅ Mismatch sets `requires_manual_resolution = True`
- ✅ No auto-correction logic present

---

## 🟠 SECTION 6.2.1 — Retry Margin Re-Validation

### Problem Statement

Margin may free up during retry window (T < 30s). Subsequent retries may succeed at higher leverage than originally approved.

### Clarification: Re-validate on Each Retry

**Rule 6.2.1.1: Pre-Validation Runs Before Each Retry**

```python
# Current implementation: validates once at start (correct)
validation_error = self._validate_preconditions(frozen_snapshot)  # Line 721-729

# Each retry iteration should re-validate:
while not timeout_controller.is_expired():
    order_status = broker.get_order_status(order_id)
    
    if order_status["state"] == "failed":
        # Before retry: re-validate
        validation_error = self._validate_preconditions(frozen_snapshot)
        if validation_error:
            # Can't retry, abort
            break
        
        # Safe to retry
        order_response = broker.submit_order(...)
    
    # Continue polling
```

**Checks Per Retry**:
```
✓ Advisory not expired (expiration_timestamp > now)
✓ Kill switch OFF for symbol
✓ Account-level risk limits not exceeded
✓ Position count limit not exceeded
✓ Daily loss limit not exceeded
✓ Margin available
```

**Rule 6.2.1.2: Frozen Snapshot Never Recalculated**

```python
# ❌ WRONG: Recalc snapshot during retry
if margin_freed_up:
    new_snapshot = recalculate_snapshot(original_snapshot)  # ❌

# ✅ CORRECT: Reuse same snapshot
while not timeout_expired:
    # Use original frozen_snapshot throughout
    order = broker.submit_order(
        symbol=frozen_snapshot.symbol,
        quantity=frozen_snapshot.position_size,  # Never changes
    )
```

**Rule 6.2.1.3: Advisory Parameters Never Modified**

```python
# ❌ WRONG: Adjust risk during retry
if slippage_high:
    sl_offset_pct = -0.05  # Tighter SL, not approved

# ✅ CORRECT: Use snapshot offsets unchanged
sl = fill_price * (1 + frozen_snapshot.sl_offset_pct)  # Original offset
tp = fill_price * (1 + frozen_snapshot.tp_offset_pct)  # Original offset
```

### Implementation Checkpoint

- ✅ `_validate_preconditions()` validates before submission
- ✅ Current loop in `_wait_for_fill()` does NOT retry on failure (no retry logic yet)
- ✅ Frozen snapshot never modified
- ✅ All SL/TP calculations use snapshot offsets unchanged

---

## 📊 ADDENDUM SUMMARY — Key Changes

| Section | Status | Change Type | Impact |
|---------|--------|-------------|--------|
| 4.3 | NEW | SL/TP calculation from fill price with slippage tracking | CRITICAL |
| 5.1 | NEW | Kill switch behavior across BEFORE/DURING/AFTER lifecycle | CRITICAL |
| 6.5 | NEW | Timeout = cancel + reconcile + handle late fills | CRITICAL |
| 8.2 | CLARIFIED | Single reconciliation per execution flow | MEDIUM |
| 6.2.1 | CLARIFIED | Retry re-validates margin/limits, snapshot unchanged | MEDIUM |

---

## ✅ UPDATED CONTRACT INVARIANTS

**Execution Guarantee**: Execute approved advisory with deterministic safety enforcement.

**Core Invariants**:
1. ✅ No execution without approval (Stage 8)
2. ✅ No execution after expiration (Stage 7)
3. ✅ No live mutation of snapshot (frozen=True)
4. ✅ No execution during kill switch (BEFORE check)
5. ✅ No silent retries (logged or failing)
6. ✅ No unreconciled broker divergence (manual resolution required)

**SL/TP Invariant**:
7. ✅ SL/TP always calculated from **actual fill price**, never reference price

**Kill Switch Invariant**:
8. ✅ Kill switch post-fill = position kept open with SL/TP intact; no forced closure

**Timeout Invariant**:
9. ✅ Timeout = 30s hard limit; cancel + reconcile; late fills handled

---

## 🔒 STATUS

**Stage 9 v1.2 Addendum**: PROPOSED

**Acceptance Criteria**:
- [ ] All three sections (4.3, 5.1, 6.5) reviewed and approved
- [ ] Implementation references added to code (comments linking to sections)
- [ ] Pass 2 (State Machine Reality Check) completes successfully
- [ ] All ambiguities resolved

**Next Steps**:
- ✅ Pass 1 Complete: Contract Violation Scan (ALL YES)
- ⏳ Pass 2 Pending: State Machine Reality Check (edge cases, retries, late fills)
- ⏳ Pass 3 Pending: Integration Tests (Stage 8 → 9 flow)

**Ready for**: Code annotation + Pass 2 state machine verification

---

*Stage 9 v1.2 Addendum — Critical Clarifications*  
*Resolves all CRITICAL and MEDIUM ambiguities*  
*Status: PROPOSED | Ready for acceptance*
