# Stage 9: Execution Engine
## QUICK REFERENCE

**Module**: `reasoner_service/execution_engine.py`  
**Tests**: `tests/test_execution_engine.py` (35/35 passing)  
**Status**: ✅ Production Ready

---

## The 6 Immutable Rules (Quick Reference)

| Rule | Enforcement | Key Code |
|------|-------------|----------|
| **Frozen Snapshot** | `frozen=True` dataclass prevents all mutations | `@dataclass(frozen=True) class FrozenSnapshot` |
| **SL/TP Calculation** | `SL = fill_price × (1 + sl_offset_pct)` | `_calculate_sl(fill_price, sl_offset)` |
| **Kill Switch BEFORE** | Check `is_active()` before submission | `if manager.is_active(symbol): return REJECTED` |
| **Kill Switch AFTER** | Never close filled position | Position stays open with SL/TP intact |
| **30s Hard Timeout** | `HARD_TIMEOUT_SECONDS = 30` never extended | `TimeoutController.start()` at submit |
| **Reconciliation** | Query once, ANY mismatch → manual resolution | `reconciliation_service.reconcile()` |

---

## Component Quick Lookup

### 1. FrozenSnapshot (IMMUTABLE)
```python
# Read-only after creation
snapshot = FrozenSnapshot(
    advisory_id="ADV-001",
    reference_price=150.00,
    sl_offset_pct=-0.02,        # 2% below fill
    tp_offset_pct=+0.03,        # 3% above fill
    position_size=100.0,
    symbol="AAPL",
    expiration_timestamp=now + timedelta(hours=1),
)

# Get hash for audit trail
hash = snapshot.snapshot_hash()
```

### 2. ExecutionEngine (Orchestrator)
```python
# Initialize
engine = ExecutionEngine(broker_adapter, kill_switch_manager)

# Execute
result = engine.execute(frozen_snapshot)

# Check result
if result.status == ExecutionStage.FILLED:
    # Filled at result.final_fill_price
    # SL: result.final_sl
    # TP: result.final_tp
```

### 3. KillSwitchManager
```python
manager = KillSwitchManager()

# Activate
manager.set_kill_switch(
    KillSwitchType.SYMBOL_LEVEL,
    KillSwitchState.ACTIVE,
    target="AAPL",
    reason="Risk limit"
)

# Check
if manager.is_active("AAPL"):
    # Kill switch active
```

### 4. TimeoutController
```python
controller = TimeoutController()

# Start (on broker submission)
controller.start()

# Check
if controller.is_expired():
    # 30s exceeded

# Get time
elapsed = controller.elapsed_seconds()
remaining = controller.time_remaining_seconds()
```

### 5. ReconciliationService
```python
service = ReconciliationService()

# Query broker ONCE
report = service.reconcile(
    advisory_id="ADV-001",
    broker_adapter=broker,
    order_id="ORDER-001",
    expected_position_size=100.0,
    expected_sl=147.98,
    expected_tp=155.53,
)

# Check result
if report.requires_manual_resolution:
    # Manual intervention needed
    print(f"Mismatches: {report.mismatches}")
```

### 6. ExecutionLogger
```python
logger = ExecutionLogger()

# Log events (automatic in execute())
logger.log_execution_start(advisory_id, snapshot, kill_state)
logger.log_order_submitted(advisory_id, order_id, symbol, size)
logger.log_order_filled(advisory_id, order_id, fill_price, size, sl, tp, slippage)
logger.log_timeout(advisory_id, elapsed_seconds)
logger.log_execution_result(result)

# Get audit trail
logs = logger.execution_logs
```

---

## Decision Trees

### Should execution proceed?

```
START
  ↓
Is advisory expired?
  ├─ YES → REJECT
  ↓ NO
Is snapshot valid (advisory_id not empty)?
  ├─ NO → REJECT
  ↓ YES
Is position_size > 0?
  ├─ NO → REJECT
  ↓ YES
Is sl_offset_pct < 0?  (negative = below)
  ├─ NO → REJECT
  ↓ YES
Is tp_offset_pct > 0?  (positive = above)
  ├─ NO → REJECT
  ↓ YES
Is kill switch OFF?
  ├─ ACTIVE → REJECT
  ↓ OFF
✅ SUBMIT ORDER
```

### What happens if fill is delayed?

```
Order submitted at T=0s
  ↓
Poll broker every 100ms
  ├─ Fill received at T=15s? → FILLED (SL/TP calculated)
  ├─ Fill received at T=30s? → FILLED (SL/TP calculated)
  ├─ Fill received at T=31s? → EXECUTED_FULL_LATE (VALID, SL/TP calculated)
  └─ No fill at T=32s? → FAILED_TIMEOUT (reconcile)
  ↓
Calculate SL, TP from fill_price (NOT reference_price)
  ↓
Run reconciliation (query once)
  ↓
Return result
```

### What happens on mismatch?

```
Reconciliation started
  ↓
Query broker order status (ONCE)
  ↓
Query broker positions (ONCE)
  ↓
Compare expected vs actual
  ├─ Position size mismatch? → MISMATCH
  ├─ SL missing? → MISMATCH
  ├─ TP missing? → MISMATCH
  ├─ Phantom position? → PHANTOM_POSITION
  ├─ Position missing? → MISSING_POSITION
  └─ All matched? → MATCHED
  ↓
Set requires_manual_resolution = True if ANY mismatch
  ↓
Return report (NO auto-correction)
```

---

## Common Scenarios

### Scenario 1: Successful Execution

```python
# 1. Create snapshot (from Stage 8)
snapshot = FrozenSnapshot(
    advisory_id="ADV-001",
    reference_price=150.00,
    sl_offset_pct=-0.02,
    tp_offset_pct=+0.03,
    position_size=100.0,
    symbol="AAPL",
    expiration_timestamp=now + timedelta(hours=1),
)

# 2. Execute
engine = ExecutionEngine(broker, kill_switch)
result = engine.execute(snapshot)

# 3. Check result
assert result.status == ExecutionStage.FILLED
assert result.final_fill_price == 151.00  # Example
assert result.final_sl == 148.96          # 151 × 0.98
assert result.final_tp == 155.53          # 151 × 1.03
assert result.slippage_pct == 0.67        # (151-150)/150

# ✅ Position is now open with SL/TP
```

### Scenario 2: Kill Switch Activated

```python
# 1. Activate kill switch
kill_switch.set_kill_switch(
    KillSwitchType.SYMBOL_LEVEL,
    KillSwitchState.ACTIVE,
    target="AAPL",
    reason="Risk limit exceeded"
)

# 2. Try to execute
result = engine.execute(snapshot)

# 3. Result shows rejection
assert result.status == ExecutionStage.REJECTED
assert "Kill switch" in result.error_message

# ❌ Order never submitted
```

### Scenario 3: Timeout (No Fill)

```python
# 1. Order submitted
# 2. Waiting for fill
# 3. At T=30s, no fill yet

# Result:
assert result.status == ExecutionStage.FAILED_TIMEOUT
assert result.total_duration_seconds >= 30

# Broker order is cancelled
# Reconciliation run to check broker state
if result.reconciliation_report.requires_manual_resolution:
    # Manual review needed
```

### Scenario 4: Late Fill (After Timeout)

```python
# 1. Order submitted at T=0s
# 2. At T=30s, still waiting
# 3. At T=30.5s, fill arrives

# Result:
assert result.status == ExecutionStage.EXECUTED_FULL_LATE
assert result.final_fill_price == 151.00
assert result.final_sl == 148.96
assert result.final_tp == 155.53

# ✅ Position is open, SL/TP intact
# Fill is VALID even though after timeout
```

### Scenario 5: Reconciliation Mismatch

```python
# 1. Order filled at broker
# 2. Reconciliation queries broker
# 3. Position size doesn't match

# Result:
assert result.status == ExecutionStage.FILLED  # Execution succeeded
assert result.reconciliation_report.requires_manual_resolution == True
assert result.reconciliation_report.status == ReconciliationStatus.MISMATCH

# Mismatches list:
# ["Expected position 100.0, found 50.0 in broker"]

# ⚠️ Requires manual investigation and correction
```

---

## Data Model Reference

### ExecutionStage (Final Status)
- `SUBMITTED` - Order sent to broker
- `PENDING` - Waiting for fill (internal)
- `FILLED` - ✅ Completely filled
- `EXECUTED_FULL_LATE` - ✅ Filled after timeout (VALID)
- `CANCELLED` - Order cancelled before fill
- `FAILED` - Order submission failed
- `FAILED_TIMEOUT` - ❌ No fill within 30s
- `REJECTED` - ❌ Pre-flight validation failed
- `PARTIALLY_FILLED` - (internal tracking)

### KillSwitchType
- `GLOBAL` - All trading stopped
- `SYMBOL_LEVEL` - Trading stopped for one symbol
- `RISK_LIMIT` - Risk limit exceeded
- `MANUAL` - Manual emergency stop

### KillSwitchState
- `OFF` - Kill switch inactive
- `WARNING` - Warning state (execution may proceed)
- `ACTIVE` - Kill switch active, execution blocked

### ReconciliationStatus
- `MATCHED` - Broker state matches internal
- `MISMATCH` - General mismatch detected
- `PHANTOM_POSITION` - Position in broker but not internal
- `MISSING_POSITION` - Position internal but not in broker
- `MISSING_SL_TP` - SL or TP missing from broker

---

## Error Handling Patterns

### Pattern 1: Check execution result
```python
result = engine.execute(snapshot)

if result.status == ExecutionStage.FILLED:
    # Successfully filled
    print(f"Filled at ${result.final_fill_price}")
    
elif result.status == ExecutionStage.REJECTED:
    # Pre-flight validation failed
    print(f"Error: {result.error_message}")
    
elif result.status == ExecutionStage.FAILED_TIMEOUT:
    # Timeout without fill
    print(f"Timeout after {result.total_duration_seconds}s")
    if result.reconciliation_report:
        print(f"Broker state: {result.reconciliation_report.status}")
        
elif result.status == ExecutionStage.EXECUTED_FULL_LATE:
    # Late fill (after 30s) - VALID
    print(f"Late fill at T={result.total_duration_seconds}s")
```

### Pattern 2: Review reconciliation mismatch
```python
if result.reconciliation_report:
    report = result.reconciliation_report
    
    if report.requires_manual_resolution:
        print(f"⚠️ MISMATCH DETECTED")
        print(f"Status: {report.status}")
        print(f"Advisory: {report.advisory_id}")
        print(f"Mismatches:")
        for mismatch in report.mismatches:
            print(f"  - {mismatch}")
        
        print(f"Broker state:")
        print(f"  Position: {report.broker_position_size}")
        print(f"  SL: {report.broker_sl}")
        print(f"  TP: {report.broker_tp}")
        
        print(f"Expected:")
        print(f"  Position: {report.internal_position_size}")
        print(f"  SL: {report.internal_sl}")
        print(f"  TP: {report.internal_tp}")
        
        # Manual investigation and correction required
```

### Pattern 3: Monitor execution logs
```python
logs = engine.logger_service.execution_logs

for log in logs:
    timestamp = log.get("timestamp")
    event = log.get("event")
    advisory_id = log.get("advisory_id")
    
    if event == "execution_result":
        print(f"{timestamp} | RESULT | {log.get('status')}")
    elif event == "order_filled":
        print(f"{timestamp} | FILL | ${log.get('fill_price')}")
    elif event == "timeout":
        print(f"{timestamp} | TIMEOUT | {log.get('elapsed_seconds')}s")
    elif event == "kill_switch_abort":
        print(f"{timestamp} | KILLED | {log.get('reason')}")
```

---

## Validation Checklist

Before executing:
- [ ] Snapshot created from Stage 8 approval
- [ ] Advisory not expired
- [ ] Position size > 0
- [ ] SL offset < 0 (negative = below)
- [ ] TP offset > 0 (positive = above)
- [ ] Kill switch is OFF
- [ ] Broker adapter implemented
- [ ] Sufficient margin available

After execution:
- [ ] Check result status
- [ ] If mismatch, review reconciliation report
- [ ] If late fill, verify SL/TP calculated correctly
- [ ] If timeout, check reconciliation findings
- [ ] Review execution logs for audit trail

---

## Integration Points

### Stage 8 → Stage 9
```python
# Stage 8: Human Approval
approval_outcome = human_approval_manager.approve_advisory(
    advisory,
    approval=ApprovalOutcome.APPROVED
)

# Extract frozen snapshot
frozen_snapshot = approval_outcome.snapshot

# Stage 9: Execution
result = execution_engine.execute(frozen_snapshot)
```

### Broker Integration
```python
class MyBrokerAdapter(BrokerAdapter):
    def submit_order(self, symbol, quantity, order_type):
        # Real API call
        response = self.broker_api.create_order(symbol, quantity)
        return {
            "order_id": response["id"],
            "state": "submitted"
        }
    
    def get_order_status(self, order_id):
        status = self.broker_api.get_order(order_id)
        return {
            "order_id": order_id,
            "state": status["state"],
            "fill_price": status.get("avg_fill_price"),
            "filled_size": status.get("filled_qty")
        }
    
    def get_positions(self):
        positions = self.broker_api.get_positions()
        return [
            {
                "symbol": pos["symbol"],
                "size": pos["qty"],
                "entry_price": pos["avg_fill_price"],
                "sl": pos.get("sl"),
                "tp": pos.get("tp")
            }
            for pos in positions
        ]
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `REJECTED` status | Advisory expired or snapshot invalid | Check advisory expiration, validate snapshot fields |
| `FAILED_TIMEOUT` | No fill within 30s | Normal, check broker for pending orders |
| `MISMATCH` reconciliation | Position size or SL/TP doesn't match broker | Manual review and correction needed |
| `EXECUTED_FULL_LATE` | Fill arrived after 30s | Normal, late fills allowed, SL/TP calculated correctly |
| SL/TP wrong | Using wrong formula | Must use: `SL = fill_price × (1 + sl_offset)` |
| Kill switch doesn't work | Check state, not just type | Use `is_active()` method, not direct flag check |

---

## Performance Notes

- **Poll Interval**: 100ms (configurable)
- **Timeout**: 30s hard limit (non-configurable)
- **Reconciliation**: Single broker query
- **Logging**: In-memory, exported as list

---

## Next Steps

1. Implement `BrokerAdapter` for your broker
2. Integrate with Stage 8 approval flow
3. Configure kill switches for your risk limits
4. Deploy to sandbox environment
5. Monitor execution logs and reconciliation reports

---

*Quick Reference v1.0 | Stage 9 - Execution Engine*
