# EXECUTION BOUNDARY - QUICK REFERENCE

## Module Imports

```python
from execution_boundary import (
    ExecutionIntent,
    HumanExecutionApproval,
    KillSwitchState,
    ExecutionAuditRecord,
    KillSwitchController,
    ExecutionAuditLogger,
    SafetyGuards
)
from execution_boundary.execution_models import (
    ExecutionIntentType,
    IntentStatus,
    ApprovalAuthority,
    KillSwitchType
)
```

---

## Quick Start - Basic Workflow

### Step 1: Create Intent (Human)
```python
intent = ExecutionIntent(
    intent_type=ExecutionIntentType.OPEN_POSITION,
    symbol="AAPL",
    quantity=100,
    order_type="MARKET",
    human_rationale="Morning portfolio rebalancing",
    max_loss=500.0
)
```

### Step 2: Create Approval (Human)
```python
approval = HumanExecutionApproval(
    intent_id=intent.intent_id,
    approved=True,
    authority_level=ApprovalAuthority.HUMAN_TRADER,
    approved_by="alice@company.com",
    approval_rationale="Approved per daily risk limit"
)
```

### Step 3: Initialize Logger & Controller
```python
logger = ExecutionAuditLogger(log_file="/var/log/execution_boundary.log")
controller = KillSwitchController()
```

### Step 4: Log Intent & Approval
```python
logger.log_intent_created(intent, actor="alice@company.com", note="Intent created")
logger.log_approval_granted(intent.intent_id, approval, actor="alice@company.com", note="Approved")
```

### Step 5: Check Halt State
```python
if controller.is_halted():
    print(f"System halted: {controller.get_halt_reason()}")
    return
```

### Step 6: Run Safety Checks
```python
all_passed, summary, details = SafetyGuards.execute_all_checks(
    intent=intent,
    approval=approval,
    kill_switch=controller.state,
    audit_log=logger.get_logs()
)

if not all_passed:
    logger.log_execution_failed(intent.intent_id, actor="safety", error=summary)
    return

# All checks passed - execution can proceed
```

---

## Key Data Models

### ExecutionIntent
- `intent_id`: Auto-generated UUID
- `intent_type`: OPEN_POSITION, CLOSE_POSITION, MODIFY_POSITION, HALT_ALL_TRADING, RESUME_TRADING, MANUAL_OVERRIDE
- `symbol`: Trading symbol
- `quantity`: Position size
- `human_rationale`: **REQUIRED** - human explanation
- `status`: Current status (PENDING_APPROVAL, APPROVED, EXECUTED, etc.)

### HumanExecutionApproval
- `approval_id`: Auto-generated UUID
- `intent_id`: Intent being approved
- `approved`: True = approve, False = reject (default: False)
- `authority_level`: HUMAN_TRADER, RISK_OFFICER, SYSTEM_ADMIN
- `approved_by`: **REQUIRED** - human identifier
- `approval_rationale`: **REQUIRED** - reason for decision
- `is_valid()`: Checks if not expired

### KillSwitchState
- `manual_kill_active`: Manual halt (human-activated)
- `circuit_breaker_active`: System-detected catastrophic state
- `timeout_active`: Timeout-based halt
- `is_halted`: True if any switch active

---

## Kill Switch Operations

### Manual Kill (Emergency Halt)
```python
controller.activate_manual_kill(
    activated_by="alice@company.com",
    reason="Critical market condition detected"
)

# Check state
if controller.is_halted():
    print(f"Halted: {controller.get_halt_reason()}")

# Resume (requires explicit human action)
controller.deactivate_manual_kill(
    deactivated_by="bob@company.com",
    reason="Market condition resolved, resuming"
)
```

### Circuit Breaker (System Catastrophic State)
```python
try:
    # System operation
    pass
except Exception as e:
    controller.activate_circuit_breaker(reason=f"System error: {str(e)}")
    logger.log_kill_switch_activated("circuit_breaker", "system", str(e))
```

### Timeout (Elapsed Time)
```python
controller.activate_timeout(
    reason="Execution timeout exceeded",
    duration_seconds=300
)

# Check if expired
if controller.check_timeout_expired():
    print("Timeout has elapsed")
```

---

## Audit Logging

### Log Intent Creation
```python
logger.log_intent_created(intent, actor="alice@company.com", note="Intent created via UI")
```

### Log Approval
```python
logger.log_approval_granted(
    intent.intent_id, approval, actor="bob@company.com", 
    note="Approval granted by trader"
)
```

### Log Execution Events
```python
logger.log_execution_started(
    intent.intent_id, actor="executor",
    note="Execution started"
)

logger.log_execution_completed(
    intent.intent_id, actor="broker",
    note="Order placed successfully",
    event_data={"order_id": "12345"}
)

logger.log_execution_failed(
    intent.intent_id, actor="broker",
    error="Order rejected: insufficient funds"
)
```

### Query Logs
```python
# Get all logs for this intent
intent_logs = logger.get_logs(intent_id=intent.intent_id)

# Get all approvals
approval_logs = logger.get_logs(event_type="approval_granted")

# Export for compliance
json_export = logger.export_logs_json()
```

---

## Safety Guards

### Run Individual Checks
```python
# Check explicit approval
is_valid, reason = SafetyGuards.check_explicit_approval(intent, approval)
if not is_valid:
    print(f"Approval check failed: {reason}")

# Check kill switch
is_valid, reason = SafetyGuards.check_kill_switch(controller.state)
if not is_valid:
    print(f"Kill switch check failed: {reason}")

# Check intent constraints
is_valid, reason = SafetyGuards.check_intent_constraints(intent)
if not is_valid:
    print(f"Intent check failed: {reason}")
```

### Run All Checks
```python
all_passed, summary, details = SafetyGuards.execute_all_checks(
    intent=intent,
    approval=approval,
    kill_switch=controller.state,
    audit_log=logger.get_logs()
)

print(summary)  # "✅ ALL CHECKS PASSED" or "❌ SAFETY CHECK FAILED"

for check in details:
    print(f"  {check}")
    # Output example:
    # ✅ PASS - Explicit Approval: Approval is valid
    # ✅ PASS - Kill Switch: All kill switches are inactive
    # ✅ PASS - Intent Constraints: Intent constraints are satisfied
    # etc.
```

---

## Approval Authority Levels

| Level | Can Approve | Cannot Approve |
|-------|-------------|----------------|
| **HUMAN_TRADER** | OPEN_POSITION, CLOSE_POSITION, MODIFY_POSITION | HALT_ALL_TRADING, RESUME_TRADING, MANUAL_OVERRIDE |
| **RISK_OFFICER** | All routine operations | MANUAL_OVERRIDE (emergency only) |
| **SYSTEM_ADMIN** | Everything | Nothing (can approve all) |

---

## Conditional Approval

```python
# Create conditional approval (conditions are human-specified)
approval = HumanExecutionApproval(
    intent_id=intent.intent_id,
    approved=True,
    conditional_approval=True,
    approval_conditions=[
        "price >= 150.50",
        "volume > 1M shares",
        "bid-ask spread < 0.10"
    ],
    approved_by="alice@company.com",
    approval_rationale="Approved with conditions"
)

# Check conditions exist
is_valid, reason = SafetyGuards.check_approval_conditions(approval)
if not is_valid:
    print(f"Conditions check failed: {reason}")
    
# Note: Condition evaluation is domain-specific (not in this module)
```

---

## Default Behaviors

| Scenario | Behavior |
|----------|----------|
| Approval missing | ❌ DENY (execution blocked) |
| Approval with approved=False | ❌ DENY (execution blocked) |
| Approval expired | ❌ DENY (execution blocked) |
| Any kill switch active | ❌ DENY (execution blocked) |
| Any safety check fails | ❌ DENY (execution blocked) |
| All checks pass | ✅ PERMIT (execution allowed) |

---

## Error Handling

```python
# All methods fail-silent (no exceptions raised)

# Logging failures (e.g., file write fails)
logger = ExecutionAuditLogger(log_file="/invalid/path")
# Falls back to in-memory logging automatically

# Invalid kill switch activation (returns False)
success = controller.activate_manual_kill("", "")  # Empty strings invalid
# Returns: False (no exception)

# Invalid approval creation
try:
    approval = HumanExecutionApproval(
        # Missing required fields
    )
except ValueError as e:
    print(f"Invalid approval: {e}")
    # Only validation in __post_init__ raises exceptions
```

---

## Forbidden Patterns

❌ **DO NOT:**

```python
# Import shadow-mode services
from reasoner_service.decision_trust_calibration_service import *  # ❌

# Auto-approve based on metrics
if signal.confidence > 0.8:
    approval.approved = True  # ❌

# Infer intent from signals
intent.symbol = signal.get_symbol()  # ❌

# Bypass safety checks
SafetyGuards.execute_all_checks(...)  # SKIP THIS  # ❌

# Modify audit logs
logs = logger.get_logs()
logs.pop()  # ❌

# Programmatic override of manual kill
if controller.state.manual_kill_active:
    controller.deactivate_manual_kill()  # ❌

# Use shadow-mode field names
if intent.confidence > 0.5:  # ❌ "confidence" not in ExecutionIntent
    execute()
```

---

## Production Checklist

- [ ] Initialize logger with production log file path
- [ ] Configure audit log rotation policy
- [ ] Create runbook for kill switch activation
- [ ] Train approvers on authority levels
- [ ] Set up monitoring for failed approvals
- [ ] Set up alerts for kill switch activations
- [ ] Verify audit logs are append-only
- [ ] Document integration with broker APIs
- [ ] Test fail-closed behavior
- [ ] Review with compliance/legal team

---

## Documentation Reference

| Document | Purpose |
|----------|---------|
| `EXECUTION_BOUNDARY_DELIVERY_SUMMARY.md` | Overview and key deliverables |
| `EXECUTION_BOUNDARY_INTEGRATION_GUIDE.md` | Detailed integration and deployment |
| `EXECUTION_BOUNDARY_ARCHITECTURE.md` | System architecture and data flow |
| `execution_boundary/EXECUTION_BOUNDARY_README.md` | Technical module documentation |
| This file | Quick reference and common patterns |

---

## Common Workflows

### Scenario 1: Open Position
```python
# Human creates intent
intent = ExecutionIntent(
    intent_type=ExecutionIntentType.OPEN_POSITION,
    symbol="AAPL",
    quantity=100,
    human_rationale="Portfolio rebalancing"
)

# Human approves
approval = HumanExecutionApproval(
    intent_id=intent.intent_id,
    approved=True,
    approved_by="alice@company.com",
    approval_rationale="Within daily limits"
)

# System checks all guards
if SafetyGuards.execute_all_checks(...)[0]:
    # Call broker API (external layer)
    order = broker.place_order(intent.symbol, intent.quantity)
    logger.log_execution_completed(intent.intent_id, "broker", f"Order {order.id}")
```

### Scenario 2: Emergency Halt
```python
# System detects critical state
try:
    critical_operation()
except SystemError as e:
    controller.activate_circuit_breaker(f"System error: {e}")
    logger.log_kill_switch_activated("circuit_breaker", "system", str(e))
    
    # All execution now blocked
    if controller.is_halted():
        # Log failure and return
        logger.log_execution_failed(intent.intent_id, "system", "System halted")
        return
```

### Scenario 3: Conditional Approval
```python
# Approval with conditions
approval = HumanExecutionApproval(
    intent_id=intent.intent_id,
    approved=True,
    conditional_approval=True,
    approval_conditions=[
        "only execute if price > 150.00",
        "only execute if volume > 1M"
    ],
    approved_by="alice@company.com",
    approval_rationale="Approved with price/volume guards"
)

# Conditions are checked by domain-specific logic (external to this module)
# This module only verifies conditions exist
```

---

**For detailed information, see the comprehensive documentation files.**
