Stage 8 — Integration Guide v1.0

================================================================================
OVERVIEW
================================================================================

This guide explains how to integrate Stage 8 (Human Approval & Execution Boundary)
into the Trading Decision Loop and downstream systems.

Stage 8 enforces a binary approval contract with:
  ✓ Binary approval only (APPROVED | REJECTED)
  ✓ Frozen snapshot enforcement (immutable execution contract)
  ✓ Stage 7 expiration integration (freshness guarantee)
  ✓ Immutable audit logging (compliance record)
  ✓ Execution boundary enforcement (only approved advisories execute)

================================================================================
SECTION 1: BASIC INTEGRATION
================================================================================

1.1 IMPORT AND INITIALIZATION

```python
from reasoner_service.human_approval_manager import (
    HumanApprovalManager,
    AdvisorySnapshot,
    ApprovalOutcome,
)

# Initialize manager (with optional custom timeframe durations)
manager = HumanApprovalManager()

# OR with custom timeframes:
manager = HumanApprovalManager(
    timeframe_candle_durations={
        "2H": 7200,
        "8H": 28800,
    }
)
```

1.2 APPROVE ADVISORY

```python
from datetime import datetime, timezone, timedelta

# Get advisory from Stage 7 (with expiration_timestamp already calculated)
advisory_snapshot = AdvisorySnapshot(
    advisory_id="ADV-001",
    htf_bias="BIAS_UP",
    reasoning_mode="entry_evaluation",
    price=150.50,
    expiration_timestamp=datetime.now(timezone.utc) + timedelta(hours=1),
    created_at=datetime.now(timezone.utc),
    reasoning_context={"timeframe": "4H"},
)

# Human approves
outcome = manager.approve_advisory(
    advisory_snapshot,
    user_id="trader_alice",
    approve=True,
    reason="Price action confirms entry setup"
)

if outcome == ApprovalOutcome.APPROVED:
    print("Advisory approved and frozen")
else:
    print(f"Advisory {outcome.value}")
```

1.3 EXECUTE IF APPROVED

```python
# Check if advisory can be executed
can_execute = manager.execute_if_approved("ADV-001")

if can_execute:
    # Get frozen snapshot (immutable)
    frozen_snapshot = manager.approvals["ADV-001"]
    
    # Execute with exact frozen data (what human approved)
    execute_trade(
        symbol="AAPL",
        price=frozen_snapshot.price,
        reason=f"Approved via {frozen_snapshot.reasoning_mode}"
    )
else:
    print("Cannot execute (not approved, expired, or invalid)")
```

================================================================================
SECTION 2: ORCHESTRATOR INTEGRATION
================================================================================

Example of integrating Stage 8 into an orchestrator/decision loop:

```python
class DecisionOrchestrator:
    def __init__(self):
        self.approval_manager = HumanApprovalManager()
        self.pending_approvals = {}  # advisory_id → advisory_snapshot
    
    async def handle_advisory(self, advisory_snapshot: AdvisorySnapshot):
        """Process advisory through Stage 8 approval boundary."""
        
        # Store pending approval (waiting for human)
        self.pending_approvals[advisory_snapshot.advisory_id] = advisory_snapshot
        
        # In real system, notify human to approve/reject
        # via UI, webhook, email, etc.
        
        return {
            "status": "pending_approval",
            "advisory_id": advisory_snapshot.advisory_id,
        }
    
    async def human_approval_received(
        self,
        advisory_id: str,
        user_id: str,
        approved: bool,
        reason: str,
    ):
        """Human has made an approval decision."""
        
        # Get pending advisory
        advisory = self.pending_approvals.get(advisory_id)
        if not advisory:
            return {"status": "error", "reason": "advisory not found"}
        
        # Process through Stage 8
        outcome = self.approval_manager.approve_advisory(
            advisory,
            user_id=user_id,
            approve=approved,
            reason=reason,
        )
        
        # Clean up pending
        del self.pending_approvals[advisory_id]
        
        return {"status": outcome.value}
    
    async def execute_approved_advisories(self):
        """Execute all approved advisories."""
        
        executed = []
        for advisory_id in list(self.approval_manager.approvals.keys()):
            if self.approval_manager.execute_if_approved(advisory_id):
                frozen = self.approval_manager.approvals[advisory_id]
                # Execute trade with frozen snapshot
                result = await self.execute_trade(frozen)
                executed.append({
                    "advisory_id": advisory_id,
                    "result": result,
                })
        
        return executed
```

================================================================================
SECTION 3: WORKFLOW INTEGRATION
================================================================================

3.1 TYPICAL APPROVAL WORKFLOW

1. ADVISORY GENERATION (Stage 7)
   └─ Generate advisory with expiration_timestamp
   └─ Create AdvisorySnapshot with all required fields
   └─ Send to Stage 8

2. HUMAN APPROVAL INITIATION (UI/API)
   └─ Human receives pending advisory notification
   └─ Reviews advisory details, reasoning, price
   └─ Decides: APPROVE or REJECT
   └─ Provides optional rationale

3. STAGE 8 PROCESSING (This)
   └─ Receives approval decision from human
   └─ Validates snapshot completeness
   └─ Checks Stage 7 expiration (if expired → EXPIRED)
   └─ If approved → freeze snapshot, return APPROVED
   └─ If rejected → return REJECTED
   └─ Log decision immutably to audit trail

4. EXECUTION PHASE (Stage 9+)
   └─ Check: manager.execute_if_approved(advisory_id)
   └─ Get: frozen_snapshot = manager.approvals[advisory_id]
   └─ Execute with frozen snapshot (exact price, mode, etc.)
   └─ Log execution with reference to approval decision

5. COMPLIANCE & AUDIT
   └─ Export: manager.get_audit_trail()
   └─ Verify: all approvals logged immutably
   └─ Trace: who approved, when, why, what exact state
   └─ Detect: anomalies in approval patterns

3.2 EXAMPLE: WEB API INTEGRATION

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()
orchestrator = DecisionOrchestrator()

class ApprovalRequest(BaseModel):
    advisory_id: str
    approved: bool
    reason: str
    user_id: str

@app.post("/approvals")
async def process_approval(req: ApprovalRequest):
    """Human submits approval decision via API."""
    
    result = await orchestrator.human_approval_received(
        advisory_id=req.advisory_id,
        user_id=req.user_id,
        approved=req.approved,
        reason=req.reason,
    )
    
    return result

@app.get("/execute")
async def execute_pending():
    """Execute all approved advisories."""
    
    executed = await orchestrator.execute_approved_advisories()
    
    return {
        "executed_count": len(executed),
        "executions": executed,
    }

@app.get("/audit/{advisory_id}")
async def get_audit_trail(advisory_id: str):
    """Retrieve audit trail for specific advisory."""
    
    trail = orchestrator.approval_manager.get_audit_trail(advisory_id)
    
    return {
        "advisory_id": advisory_id,
        "trail": trail,
    }
```

================================================================================
SECTION 4: ERROR HANDLING & VALIDATION
================================================================================

4.1 VALIDATION BEFORE CALLING STAGE 8

```python
def validate_advisory_snapshot(snapshot: AdvisorySnapshot) -> tuple[bool, str]:
    """Validate advisory before passing to approval manager."""
    
    if not snapshot.advisory_id:
        return False, "advisory_id required"
    if not snapshot.htf_bias:
        return False, "htf_bias required"
    if not snapshot.reasoning_mode:
        return False, "reasoning_mode required"
    if not snapshot.price or snapshot.price <= 0:
        return False, "price must be positive"
    if not snapshot.expiration_timestamp:
        return False, "expiration_timestamp required"
    
    return True, "valid"

# Usage
valid, msg = validate_advisory_snapshot(advisory)
if not valid:
    return {"status": "error", "reason": msg}

outcome = manager.approve_advisory(advisory, user_id, approve)
```

4.2 HANDLING APPROVAL OUTCOMES

```python
from reasoner_service.human_approval_manager import ApprovalOutcome

def handle_approval_outcome(outcome: ApprovalOutcome, advisory_id: str):
    """Handle outcome from approve_advisory()."""
    
    if outcome == ApprovalOutcome.APPROVED:
        # Advisory frozen and approved
        logger.info(f"Advisory {advisory_id} approved and ready to execute")
        return True
    
    elif outcome == ApprovalOutcome.REJECTED:
        # Human explicitly rejected
        logger.info(f"Advisory {advisory_id} rejected by human")
        return False
    
    elif outcome == ApprovalOutcome.EXPIRED:
        # Advisory expired per Stage 7
        logger.warning(f"Advisory {advisory_id} expired, cannot approve")
        return False
    
    elif outcome == ApprovalOutcome.INVALIDATED:
        # State changed (reserved for future)
        logger.error(f"Advisory {advisory_id} invalidated")
        return False
    
    else:
        # Should not happen
        logger.error(f"Unknown outcome: {outcome}")
        return False
```

4.3 EXECUTION BOUNDARY VALIDATION

```python
def safe_execute(advisory_id: str, manager: HumanApprovalManager):
    """Execute advisory only if safe."""
    
    # Step 1: Quick validity check
    if not manager.is_approval_valid(advisory_id):
        logger.error(f"Advisory {advisory_id} is not valid for execution")
        return False
    
    # Step 2: Execute boundary check
    if not manager.execute_if_approved(advisory_id):
        logger.error(f"Advisory {advisory_id} cannot be executed")
        return False
    
    # Step 3: Get frozen snapshot
    frozen_snapshot = manager.approvals[advisory_id]
    
    # Step 4: Execute with frozen data
    try:
        result = execute_trade(
            price=frozen_snapshot.price,
            mode=frozen_snapshot.reasoning_mode,
        )
        logger.info(f"Executed advisory {advisory_id}: {result}")
        return True
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        return False
```

================================================================================
SECTION 5: COMPLIANCE & AUDIT INTEGRATION
================================================================================

5.1 EXPORTING AUDIT TRAIL

```python
import json
from datetime import datetime

def export_audit_trail(manager: HumanApprovalManager, filepath: str):
    """Export audit trail to JSON for compliance."""
    
    trail = manager.get_audit_trail()
    
    with open(filepath, 'w') as f:
        json.dump(trail, f, indent=2)
    
    logger.info(f"Exported {len(trail)} audit entries to {filepath}")

# Usage
export_audit_trail(manager, "audit_trail.json")
```

5.2 AUDIT TRAIL ANALYSIS

```python
def analyze_audit_trail(manager: HumanApprovalManager):
    """Analyze audit trail for compliance reporting."""
    
    trail = manager.get_audit_trail()
    
    stats = {
        "total_approvals": len(trail),
        "approved": sum(1 for e in trail if e["outcome"] == "APPROVED"),
        "rejected": sum(1 for e in trail if e["outcome"] == "REJECTED"),
        "expired": sum(1 for e in trail if e["outcome"] == "EXPIRED"),
        "users": set(e["user_id"] for e in trail),
    }
    
    return stats

# Usage
stats = analyze_audit_trail(manager)
print(f"Total approvals: {stats['total_approvals']}")
print(f"Approved: {stats['approved']}")
print(f"Rejected: {stats['rejected']}")
print(f"Expired: {stats['expired']}")
```

5.3 FORENSIC ANALYSIS

```python
def forensic_analysis(manager: HumanApprovalManager, advisory_id: str):
    """Full forensic trace of approval decision."""
    
    trail = manager.get_audit_trail(advisory_id)
    
    if not trail:
        return {"status": "not_found"}
    
    entry = trail[0]  # Get single entry (usually one per advisory)
    
    return {
        "advisory_id": advisory_id,
        "approver": entry["user_id"],
        "outcome": entry["outcome"],
        "decided_at": entry["timestamp_received"],
        "review_duration_ms": entry["request_duration_ms"],
        "rationale": entry["reason"],
        "frozen_state": {
            "price": entry["state_snapshot"]["price"],
            "bias": entry["state_snapshot"]["htf_bias"],
            "mode": entry["state_snapshot"]["reasoning_mode"],
            "expires": entry["state_snapshot"]["expiration_timestamp"],
        }
    }

# Usage
analysis = forensic_analysis(manager, "ADV-001")
print(f"Approved by: {analysis['approver']}")
print(f"Frozen price: {analysis['frozen_state']['price']}")
print(f"Reason: {analysis['rationale']}")
```

================================================================================
SECTION 6: TESTING INTEGRATION
================================================================================

6.1 TEST FIXTURES

```python
import pytest
from datetime import datetime, timezone, timedelta

@pytest.fixture
def approval_manager():
    """Create fresh manager for each test."""
    from reasoner_service.human_approval_manager import HumanApprovalManager
    return HumanApprovalManager()

@pytest.fixture
def valid_advisory():
    """Create valid advisory snapshot."""
    from reasoner_service.human_approval_manager import AdvisorySnapshot
    now = datetime.now(timezone.utc)
    return AdvisorySnapshot(
        advisory_id="TEST-001",
        htf_bias="BIAS_UP",
        reasoning_mode="entry_evaluation",
        price=150.50,
        expiration_timestamp=now + timedelta(hours=1),
        created_at=now,
        reasoning_context={"timeframe": "4H"},
    )

@pytest.fixture
def expired_advisory():
    """Create expired advisory snapshot."""
    from reasoner_service.human_approval_manager import AdvisorySnapshot
    now = datetime.now(timezone.utc)
    return AdvisorySnapshot(
        advisory_id="TEST-EXPIRED",
        htf_bias="BIAS_DOWN",
        reasoning_mode="trade_management",
        price=100.00,
        expiration_timestamp=now - timedelta(minutes=5),
        created_at=now - timedelta(hours=2),
        reasoning_context={"timeframe": "1H"},
    )
```

6.2 INTEGRATION TEST EXAMPLE

```python
def test_approval_workflow(approval_manager, valid_advisory):
    """Test complete approval workflow."""
    
    # Step 1: Approve
    outcome = approval_manager.approve_advisory(
        valid_advisory,
        user_id="test_user",
        approve=True,
        reason="Test approval"
    )
    assert outcome.value == "APPROVED"
    
    # Step 2: Check validity
    assert approval_manager.is_approval_valid("TEST-001") is True
    
    # Step 3: Execute
    can_execute = approval_manager.execute_if_approved("TEST-001")
    assert can_execute is True
    
    # Step 4: Get frozen snapshot
    frozen = approval_manager.approvals["TEST-001"]
    assert frozen.price == 150.50
    
    # Step 5: Verify audit trail
    trail = approval_manager.get_audit_trail("TEST-001")
    assert len(trail) == 1
    assert trail[0]["outcome"] == "APPROVED"
```

================================================================================
SECTION 7: MONITORING & OBSERVABILITY
================================================================================

7.1 APPROVAL METRICS

```python
def track_approval_metrics(manager: HumanApprovalManager):
    """Track approval metrics for monitoring."""
    
    trail = manager.get_audit_trail()
    
    metrics = {
        "total_approvals": len(trail),
        "approval_rate": sum(1 for e in trail if e["outcome"] == "APPROVED") / len(trail) if trail else 0,
        "rejection_rate": sum(1 for e in trail if e["outcome"] == "REJECTED") / len(trail) if trail else 0,
        "expiration_rate": sum(1 for e in trail if e["outcome"] == "EXPIRED") / len(trail) if trail else 0,
        "avg_review_duration_ms": sum(e.get("request_duration_ms", 0) for e in trail) / len(trail) if trail else 0,
    }
    
    return metrics

# Usage
metrics = track_approval_metrics(manager)
logger.info(f"Approval metrics: {metrics}")
```

7.2 ALERTING

```python
def check_approval_health(manager: HumanApprovalManager):
    """Check for concerning approval patterns."""
    
    trail = manager.get_audit_trail()
    
    if not trail:
        return []
    
    alerts = []
    
    # Alert on high rejection rate
    rejection_rate = sum(1 for e in trail if e["outcome"] == "REJECTED") / len(trail)
    if rejection_rate > 0.5:
        alerts.append(f"High rejection rate: {rejection_rate:.1%}")
    
    # Alert on high expiration rate
    expiration_rate = sum(1 for e in trail if e["outcome"] == "EXPIRED") / len(trail)
    if expiration_rate > 0.3:
        alerts.append(f"High expiration rate: {expiration_rate:.1%}")
    
    # Alert on unusual review duration
    review_durations = [e.get("request_duration_ms", 0) for e in trail]
    avg_duration = sum(review_durations) / len(review_durations) if review_durations else 0
    max_duration = max(review_durations) if review_durations else 0
    
    if max_duration > 300000:  # 5 minutes
        alerts.append(f"Unusually long review: {max_duration/1000:.0f}s")
    
    return alerts

# Usage
alerts = check_approval_health(manager)
for alert in alerts:
    logger.warning(f"Approval health alert: {alert}")
```

================================================================================
SECTION 8: PRODUCTION CHECKLIST
================================================================================

Before deploying Stage 8 to production:

✓ IMPLEMENTATION:
  □ Stage 8 code reviewed and approved
  □ All 48 tests passing (100% pass rate)
  □ Code syntax validated
  □ Imports verified
  □ No external dependencies missing

✓ INTEGRATION:
  □ Integrated with orchestrator
  □ Integrated with approval workflow
  □ Execution boundary enforced
  □ Audit trail exported to persistent storage
  □ Compliance team can access audit trail

✓ TESTING:
  □ Unit tests: 48/48 passing
  □ Integration tests written and passing
  □ End-to-end workflow tested
  □ Error cases tested
  □ Edge cases tested

✓ MONITORING:
  □ Approval metrics tracked
  □ Rejection rate monitored
  □ Expiration rate monitored
  □ Review duration tracked
  □ Alerts configured

✓ COMPLIANCE:
  □ Audit trail complete and immutable
  □ All approvals logged
  □ User IDs captured
  □ Timestamps accurate
  □ Frozen snapshots preserved
  □ Audit export working
  □ Forensic analysis possible

✓ DOCUMENTATION:
  □ API documentation complete
  □ Integration guide available
  □ Troubleshooting guide available
  □ Runbooks created
  □ Team trained

✓ OPERATIONAL:
  □ Logging configured
  □ Log retention policy set
  □ Audit trail backup configured
  □ Incident response plan ready
  □ Rollback plan ready

================================================================================
SECTION 9: TROUBLESHOOTING
================================================================================

Problem: execute_if_approved() returns False
Solution:
  1. Check: is approval_outcomes[advisory_id] == APPROVED?
  2. Check: does approvals[advisory_id] exist?
  3. Check: is snapshot expired per Stage 7?
  4. Check logs for error message

Problem: Approval returns EXPIRED
Solution:
  1. Verify Stage 7 calculated expiration_timestamp correctly
  2. Check: is now > expiration_timestamp?
  3. Verify UTC timezone is used consistently
  4. Check timeframe duration mapping

Problem: Audit trail missing approvals
Solution:
  1. Check: is _log_audit_entry() being called?
  2. Verify: all approvals go through approve_advisory()?
  3. Check logs for errors during approval
  4. Verify: audit_log list is not being cleared

Problem: Frozen snapshot modification failed
Solution:
  1. Remember: frozen=True prevents ALL modifications
  2. Don't try to modify snapshot after creation
  3. Create new snapshot if different data needed
  4. Use frozen snapshot as-is for execution

Problem: ValueError during approval
Solution:
  1. Check: advisory_id not empty?
  2. Check: htf_bias not empty?
  3. Check: reasoning_mode not empty?
  4. Check: expiration_timestamp is set?

================================================================================
SECTION 10: GLOSSARY
================================================================================

APPROVED: Advisory explicitly approved by human, snapshot frozen, can execute

REJECTED: Advisory explicitly rejected by human, snapshot not stored, cannot execute

EXPIRED: Advisory exceeded Stage 7 expiration time, cannot be approved

FROZEN SNAPSHOT: Immutable copy of advisory at approval time, used for execution

AUDIT TRAIL: Immutable log of all approval decisions with user, time, reason, outcome

EXECUTION BOUNDARY: Point where decision "should I execute?" is enforced

STAGE 7 EXPIRATION: Freshness rule from Stage 7 (advisory expires after time limit)

FAIL-CLOSED: Default behavior is to block/deny (opposite of fail-open)

IMMUTABLE: Cannot be modified or deleted after creation (frozen dataclass)

================================================================================
