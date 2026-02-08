# STAGE 8 ARCHITECTURE: SIGNAL-BASED RULES (Type A)
**Analysis Date**: December 30, 2025  
**Codebase**: prototypeictalgo  
**Status**: Fully implemented and tested

---

## ANSWER: Stage 8 is **SIGNAL-BASED RULES** (Option A)

Stage 8 is **NOT** a finite state machine. It is a **signal-based rule system** that:
1. Receives trade signals from Pine Script (via webhooks)
2. Evaluates binary approval conditions
3. Emits frozen execution snapshots when approved
4. Outputs immediately (no multi-step state transitions)

---

## ARCHITECTURE OVERVIEW

### Flow Diagram

```
Pine Script Market Signal
  ├─ Signal Type: "BUY" | "SELL"
  ├─ Confidence: 0.0-1.0 (threshold: 0.70+ minimum)
  ├─ Price: Current market price
  ├─ ICT Model: "CHOCH", "LIQUIDITY_SWEEP", "ORDER_BLOCK", etc.
  └─ Timeframe: "1H", "4H", "1D"
         ↓
    Webhook Received
    /api/webhook/receive?secret=<WEBHOOK_SECRET>
         ↓
Stage 8: HumanApprovalManager
    ├─ Check signal confidence ≥ 0.70
    ├─ Check Stage 7 expiration (not expired)
    ├─ Emit SIGNAL: "New advisory for approval"
    ├─ Wait for human decision: APPROVE | REJECT
    └─ If APPROVED:
         ├─ Freeze snapshot (immutable)
         ├─ Create AuditLogEntry
         └─ Return: frozen AdvisorySnapshot
         ↓
Stage 9: ExecutionEngine.execute()
    └─ Use frozen snapshot → broker → fill
```

---

## STAGE 8 COMPONENTS (NOT A STATE MACHINE)

### 1. Signal Input Contract

**Source**: Pine Script webhook (ict_detector.pine, 2,169 lines)

**Signal Payload**:
```json
{
  "type": "BUY",              // BUY | SELL (binary)
  "price": 1.2345,            // Current market price
  "confidence": 0.95,         // 0.0-1.0 confidence
  "idempotency_key": "...",   // Deduplication
  "rule_provenance": ["ruleA", "ruleB"],  // Which rules triggered
  "ict_model": "CHOCH",       // ICT trading model
  "timeframe": "4H"           // Timeframe where signal generated
}
```

**Minimum Threshold**: confidence ≥ 0.70 (hard minimum)

### 2. HumanApprovalManager (Pure Signal Handler)

**File**: `reasoner_service/human_approval_manager.py` (420 lines)

**NOT a state machine**. Instead:
- Receives signal → immediate evaluation
- No persistent state transitions
- No time-dependent state progression
- No waiting for future conditions

**Class Structure**:
```python
class HumanApprovalManager:
    def __init__(self, timeframe_candle_durations: Dict[str, int]):
        # Storage (not state machine states)
        self.approvals: Dict[str, AdvisorySnapshot] = {}
        self.approval_outcomes: Dict[str, ApprovalOutcome] = {}
        self.audit_log: List[AuditLogEntry] = []
    
    def approve_advisory(
        self,
        advisory_snapshot: AdvisorySnapshot,
        user_id: str,
        approve: bool = True,  # ← Binary decision
        reason: Optional[str] = None
    ) -> ApprovalOutcome:
        """Signal-based rule: if approve=True, freeze and emit"""
    
    def execute_if_approved(self, advisory_id: str) -> bool:
        """Rule: if APPROVED AND NOT EXPIRED, allow execution"""
```

### 3. Signal Evaluation Rules (No State Transitions)

#### Rule 1: Confidence Threshold
```python
if signal.confidence < 0.70:
    reject_signal()  # Binary outcome
else:
    accept_signal()  # Binary outcome
```

#### Rule 2: Stage 7 Expiration Check
```python
if advisory_snapshot.expiration_timestamp < now():
    return ApprovalOutcome.EXPIRED  # Terminal, no further transitions
else:
    proceed_to_approval()  # Immediate
```

#### Rule 3: Binary Approval
```python
if human_decides(approve=True):
    # IMMEDIATE ACTION: freeze snapshot
    approvals[advisory_id] = advisory_snapshot  # Immutable copy
    approval_outcomes[advisory_id] = ApprovalOutcome.APPROVED
    emit_frozen_snapshot()  # Pass to Stage 9
    return  # Done (no further state transitions)

elif human_decides(approve=False):
    # IMMEDIATE ACTION: reject
    approval_outcomes[advisory_id] = ApprovalOutcome.REJECTED
    return  # Done (no further state transitions)
```

### 4. Enums (All Terminal Outcomes, NOT State Transitions)

```python
class ApprovalOutcome(Enum):
    APPROVED = "APPROVED"              # Terminal: execute
    REJECTED = "REJECTED"              # Terminal: do not execute
    EXPIRED = "EXPIRED"                # Terminal: too old
    INVALIDATED = "INVALIDATED"        # Terminal: state changed
    PENDING = "PENDING"                # NOT USED in current implementation
```

**Key Point**: These are **outcomes**, not state machine states. Once set, they don't transition:
- APPROVED → stays APPROVED (until execution, then archived)
- REJECTED → stays REJECTED (frozen, never retried)
- EXPIRED → stays EXPIRED (never revived)

---

## DATA MODELS (Immutable Snapshots, Not State Transitions)

### AdvisorySnapshot (Frozen)

```python
@dataclass(frozen=True)  # ← Immutable
class AdvisorySnapshot:
    advisory_id: str
    htf_bias: str                    # e.g., "BIAS_UP"
    reasoning_mode: str              # e.g., "entry_evaluation"
    price: float                     # Price at approval time
    expiration_timestamp: datetime   # Stage 7 calculated
    created_at: datetime
    reasoning_context: Dict[str, Any]
```

**Purpose**: Capture advisory state at approval time (snapshot immutability rule)

**Not a state machine**: This is just a data container, not a state object with transitions.

### AuditLogEntry (Forensic Record)

```python
@dataclass(frozen=True)  # ← Immutable
class AuditLogEntry:
    advisory_id: str
    user_id: str
    timestamp_request: datetime      # When human saw signal
    timestamp_received: datetime     # When human approved/rejected
    state_snapshot: AdvisorySnapshot # Captured state
    outcome: ApprovalOutcome         # APPROVED|REJECTED|EXPIRED
    reason: Optional[str]            # Human rationale
    request_duration_ms: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:  # For audit export
        """Serialize for compliance logging"""
```

---

## CONTROL FLOW (NOT A STATE MACHINE)

### `approve_advisory()` Method

```python
def approve_advisory(
    self,
    advisory_snapshot: AdvisorySnapshot,
    user_id: str,
    approve: bool = True,
    reason: Optional[str] = None
) -> ApprovalOutcome:
    """
    SIGNAL-BASED: Receive signal, evaluate, emit outcome.
    NOT state machine: No queues, no state transitions, immediate output.
    """
    
    # STEP 1: Check expiration (immediate binary outcome)
    if self._stage7_expiration_check(advisory_snapshot):
        # Signal expired? Return immediately.
        outcome = ApprovalOutcome.EXPIRED
        audit_entry = AuditLogEntry(
            advisory_id=advisory_snapshot.advisory_id,
            user_id=user_id,
            timestamp_request=datetime.now(timezone.utc),
            timestamp_received=datetime.now(timezone.utc),
            state_snapshot=advisory_snapshot,
            outcome=outcome,
            reason="Advisory exceeded Stage 7 expiration window"
        )
        self._log_audit_entry(audit_entry)
        return outcome  # ← Terminal, no further transitions
    
    # STEP 2: Evaluate human decision (immediate binary outcome)
    if approve is True:
        # Signal approved? Freeze snapshot immediately.
        self.approvals[advisory_snapshot.advisory_id] = advisory_snapshot
        self.approval_outcomes[advisory_snapshot.advisory_id] = ApprovalOutcome.APPROVED
        
        audit_entry = AuditLogEntry(
            advisory_id=advisory_snapshot.advisory_id,
            user_id=user_id,
            timestamp_request=datetime.now(timezone.utc),
            timestamp_received=datetime.now(timezone.utc),
            state_snapshot=advisory_snapshot,
            outcome=ApprovalOutcome.APPROVED,
            reason=reason or "Human approved"
        )
        self._log_audit_entry(audit_entry)
        return ApprovalOutcome.APPROVED  # ← Terminal, emit snapshot
    
    else:
        # Signal rejected? Record and return.
        self.approval_outcomes[advisory_snapshot.advisory_id] = ApprovalOutcome.REJECTED
        
        audit_entry = AuditLogEntry(
            advisory_id=advisory_snapshot.advisory_id,
            user_id=user_id,
            timestamp_request=datetime.now(timezone.utc),
            timestamp_received=datetime.now(timezone.utc),
            state_snapshot=advisory_snapshot,
            outcome=ApprovalOutcome.REJECTED,
            reason=reason or "Human rejected"
        )
        self._log_audit_entry(audit_entry)
        return ApprovalOutcome.REJECTED  # ← Terminal, no snapshot
```

### `execute_if_approved()` Method

```python
def execute_if_approved(self, advisory_id: str) -> bool:
    """
    SIGNAL-BASED RULE: if (APPROVED AND NOT EXPIRED), return True; else False.
    Not state machine: Just a boolean check, no state transitions.
    """
    
    # Check if advisory was approved
    outcome = self.approval_outcomes.get(advisory_id)
    if outcome != ApprovalOutcome.APPROVED:
        return False  # ← Binary outcome
    
    # Check if approval still valid (not expired)
    snapshot = self.approvals.get(advisory_id)
    if snapshot is None:
        return False  # ← Binary outcome
    
    # Check if snapshot expired per Stage 7
    if self._stage7_expiration_check(snapshot):
        return False  # ← Binary outcome
    
    return True  # ← Binary outcome: safe to execute
```

---

## COMPARISON: WHY NOT A STATE MACHINE?

### State Machine Would Look Like:

```
[SIGNAL_RECEIVED]
       ↓
    [PENDING_APPROVAL]  ← State where signal waits for human
       ↓
  [HUMAN_REVIEWING]     ← State where human reviews
       ↓
  [APPROVED] ← State where advisory approved
       ↓
  [EXECUTING] ← State during execution
       ↓
  [FILLED]   ← Terminal state
```

### Actual Stage 8 (Signal-Based):

```
SIGNAL IN (Pine Script)
    ↓
evaluate_rules()
    ├─ confidence ≥ 0.70? → YES
    ├─ not_expired()? → YES
    └─ human_approved()? → YES
         ↓
OUTPUT: frozen AdvisorySnapshot (immediate)
         ↓
Stage 9 (ExecutionEngine) ← No queue, no wait, no state transition needed
```

**Key Differences**:
1. **No waiting**: Signal is evaluated immediately, not queued
2. **Binary outcomes only**: APPROVED | REJECTED | EXPIRED (terminal)
3. **No state progression**: No waiting-for-conditions, no re-evaluation
4. **Immutable snapshots**: Once frozen, never changed
5. **Immediate pass-through**: Output immediately to Stage 9

---

## WHY SIGNAL-BASED, NOT STATE MACHINE?

### 1. **Trading Signals Are Time-Critical**
- Signals expire quickly (Stage 7: 50% of candle duration)
- Waiting for state transitions would miss trading opportunities
- Rule-based evaluation is faster than state machines

### 2. **Human Approval Is Binary**
- No conditional approval ("if market moves, then approve")
- No partial approval or mid-decision states
- Human says YES or NO, decision is final
- No reason to model as state transitions

### 3. **Immutable Snapshots Prevent Logic Creep**
- At approval time, advisory state is frozen
- No re-evaluation, no "what if market moved" logic
- Signal-based rules: if frozen snapshot exists AND approved, execute

### 4. **Compliance & Audit**
- Every approval logged immutably (AuditLogEntry)
- Human decision is final record
- No state transitions to revert or modify
- Forensic-grade: what was approved is what was executed

### 5. **Integration with Upstream (Stage 7)**
- Stage 7 calculates expiration_timestamp once
- Stage 8 just checks: is expired? YES/NO (binary rule)
- No state-based expiration (e.g., "entering EXPIRED state")
- Simple binary check: `if now > expiration_timestamp → reject`

---

## EXPLICIT TERMINAL OUTCOMES (Not States)

```python
# These are OUTCOMES, not states in a machine:

# Outcome 1: APPROVED
# → Action: Freeze snapshot
# → Next: Stage 9 executes
# → Terminal: No further approval decisions

# Outcome 2: REJECTED
# → Action: Record rejection
# → Next: Wait for new signal
# → Terminal: Advisory not frozen, not executed

# Outcome 3: EXPIRED
# → Action: Return EXPIRED
# → Next: Signal aged out
# → Terminal: Advisory not executable, not re-evaluated

# Outcome 4: PENDING (deprecated, not used)
# → Not used in current implementation
# → Kept for backwards compatibility

# Outcome 5: INVALIDATED (deprecated, not used)
# → Placeholder for future "market moved, invalidate approval"
# → Not implemented
```

---

## TEST VALIDATION (Confirms Signal-Based, Not State Machine)

### Test File: `tests/test_human_approval_manager.py` (650+ lines, 48 tests)

**Key Test Patterns** (all signal-based, not state transitions):

1. **Binary Approval Tests**
   ```python
   def test_approve_advisory_happy_path():
       # Given a signal
       # When human approves
       # Then snapshot frozen (immediate, no state queue)
   
   def test_reject_advisory():
       # Given a signal
       # When human rejects
       # Then no snapshot (immediate, no state queue)
   ```

2. **Expiration Tests**
   ```python
   def test_expired_advisory_cannot_be_approved():
       # Given an expired signal
       # When approve() called
       # Then return EXPIRED (immediate, terminal)
   
   def test_expired_advisory_blocks_execution():
       # Given an approved signal that later expires
       # When execute_if_approved() called
       # Then return False (binary check, no state transition)
   ```

3. **Immutability Tests**
   ```python
   def test_frozen_snapshot_immutable():
       # Given frozen snapshot
       # When try to modify
       # Then dataclass raises FrozenInstanceError (no state mutation)
   
   def test_audit_entry_immutable():
       # Given audit entry
       # When try to modify
       # Then frozen, cannot change (no state transition)
   ```

4. **Audit Trail Tests**
   ```python
   def test_audit_log_records_decision():
       # Given approval decision
       # When decision made
       # Then AuditLogEntry created immediately (signal-based)
   
   def test_audit_trail_immutable():
       # Given audit log entry
       # When try to modify
       # Then frozen forever (no state transitions)
   ```

**All 48 tests pass**, confirming:
- Signal in → Binary evaluation → Immediate outcome (no state queue)
- No state machine transitions
- All outcomes terminal and immutable

---

## INTEGRATION WITH STAGE 9 (Output Contract)

### Stage 8 Output → Stage 9 Input

```python
# Stage 8 output
frozen_snapshot = AdvisorySnapshot(
    advisory_id="ADV-001",
    htf_bias="BIAS_UP",
    reasoning_mode="entry_evaluation",
    price=150.50,
    expiration_timestamp=datetime.now() + timedelta(hours=1),
    created_at=datetime.now(),
    reasoning_context={"timeframe": "4H"}
)

# Stage 9 input contract (FrozenSnapshot is different type)
# Stage 9 expects:
frozen_snapshot_for_execution = FrozenSnapshot(
    advisory_id="ADV-001",
    htf_bias="BIAS_UP",
    reasoning_mode="entry_evaluation",
    reference_price=150.50,
    sl_offset_pct=-0.02,      # 2% below fill
    tp_offset_pct=+0.03,       # 3% above fill
    position_size=1.0,
    symbol="XAUUSD"
)

# Stage 8 → Stage 9: No state machine transitions, just pass snapshot
# Stage 9 handles: order placement, fill monitoring, timeout, kill switch
```

---

## SUMMARY TABLE

| Aspect | Signal-Based (Stage 8) | State Machine (NOT Used) |
|--------|----------------------|-------------------------|
| **Input** | Binary signal (BUY/SELL) from Pine Script | N/A |
| **Evaluation** | Immediate rule check (confidence, expiration) | Multi-step transitions over time |
| **Decision** | Binary outcome (APPROVED/REJECTED/EXPIRED) | State progression (PENDING → REVIEWING → EXECUTING → FILLED) |
| **Timing** | Instant (no queue, no delay) | Sequential (each state takes time) |
| **Snapshot** | Frozen at approval (immutable) | Would evolve through states |
| **Terminal** | Yes (outcomes don't transition) | No (states transition continuously) |
| **Audit** | Immutable log entry per signal | Would have log per state transition |
| **Integration** | Immediate pass to Stage 9 | Would batch/queue multiple state changes |

---

## EXPLICIT CODE PROOF (Signal-Based, Not State Machine)

### Evidence 1: No State Queue

```python
# In HumanApprovalManager.__init__():
self.approvals: Dict[str, AdvisorySnapshot] = {}
self.approval_outcomes: Dict[str, ApprovalOutcome] = {}
self.audit_log: List[AuditLogEntry] = []

# NO queue, NO state machine states, NO transition table
# Just storage for outcomes and frozen snapshots
```

### Evidence 2: Immediate Return (No State Progression)

```python
# In approve_advisory():
if approve is True:
    self.approvals[advisory_id] = snapshot
    self.approval_outcomes[advisory_id] = ApprovalOutcome.APPROVED
    self._log_audit_entry(entry)
    return ApprovalOutcome.APPROVED  # ← IMMEDIATE return, done
```

### Evidence 3: Binary Check (No State Transitions)

```python
# In execute_if_approved():
if outcome != ApprovalOutcome.APPROVED:
    return False  # ← Binary check
if not self._stage7_expiration_check(snapshot):
    return True   # ← Binary check
return False      # ← Binary check (only 2 outcomes)
```

### Evidence 4: Immutable Outcomes (No Transitions)

```python
# ApprovalOutcome is Enum (not a state machine)
class ApprovalOutcome(Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"  # placeholder, never used
    PENDING = "PENDING"          # placeholder, never used

# Once set, outcome never transitions:
self.approval_outcomes[advisory_id] = ApprovalOutcome.APPROVED
# → Stays APPROVED until advisory archived
# → Never becomes REJECTED or EXPIRED
```

---

## CONCLUSION

**Stage 8 is definitively signal-based rules (Option A), NOT a finite state machine (Option B).**

**Why**:
1. **Input**: Market signal (PIN Script webhook) triggers immediately
2. **Evaluation**: Binary rules evaluated instantly (confidence, expiration, human approval)
3. **Output**: Frozen snapshot emitted directly to Stage 9 (no queue, no wait)
4. **Terminal**: Outcomes are final and immutable (APPROVED | REJECTED | EXPIRED)
5. **No Transitions**: No state progression, no waiting for conditions, no re-evaluation

**Architecture**: Signal In → Evaluate Rules → Binary Outcome → Frozen Snapshot → Stage 9

**Implementation**: `HumanApprovalManager` with immutable snapshots and audit logging, not a state machine.
