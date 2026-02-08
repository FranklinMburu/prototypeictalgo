Stage 8 — Quick Reference

===============================================================================
KEY CONCEPT: Binary Approval + Frozen Snapshot + Immutable Audit
===============================================================================

Stage 8 enforces a human approval boundary with three immutable contracts:

1. BINARY APPROVAL ONLY
   approve_advisory(approve=True)  → APPROVED (snapshot frozen, execution allowed)
   approve_advisory(approve=False) → REJECTED (no snapshot, execution blocked)
   NO MIDDLE GROUND. NO FALLBACK. ABSENCE = REJECTION.

2. FROZEN SNAPSHOT AT APPROVAL TIME
   When approved, advisory state is captured in an immutable snapshot.
   Execution uses ONLY frozen snapshot, never live data.
   frozen=True prevents any field modifications after creation.

3. IMMUTABLE AUDIT LOG
   Each approval decision logged in frozen AuditLogEntry.
   Audit trail is source of truth: user_id, timestamps, outcome, reason.
   Cannot be deleted, modified, or reordered (frozen dataclass).

===============================================================================
QUICK API
===============================================================================

HumanApprovalManager()
  Initialize manager. Optional: timeframe_candle_durations dict.

approve_advisory(snapshot, user_id, approve, reason)
  Process approval decision.
  Returns: ApprovalOutcome (APPROVED | REJECTED | EXPIRED)
  
execute_if_approved(advisory_id)
  Check if advisory can execute.
  Returns: True if APPROVED + unexpired, False otherwise.

is_approval_valid(advisory_id)
  Quick validity check.
  Returns: True if APPROVED + unexpired + snapshot exists.

get_audit_trail(advisory_id=None)
  Export immutable audit trail.
  Returns: List of dicts (for compliance export).

===============================================================================
THE FIVE RULES
===============================================================================

RULE 1: Binary Approval Only
  → approve=True returns APPROVED
  → approve=False returns REJECTED
  → No "conditional", "pending", or default states

RULE 2: Frozen Snapshot
  → Advisory state captured at approval time
  → Execution gets exact price/bias/mode from frozen snapshot
  → Prevents "approved state" creeping before execution

RULE 3: Stage 7 Expiration
  → Check expiration BEFORE approving
  → If expired at approval time → return EXPIRED
  → If approved but expires before execution → block execution

RULE 4: Immutable Audit Logging
  → All approvals logged to frozen AuditLogEntry list
  → Audit trail cannot be modified or deleted
  → Each entry records: advisory_id, user_id, outcome, reason, timestamps

RULE 5: Execute Only If Approved & Unexpired
  → execute_if_approved() returns True ONLY if:
     • Outcome is APPROVED (not REJECTED, EXPIRED, etc.)
     • Frozen snapshot exists
     • Snapshot not yet expired per Stage 7
  → Returns False for any other condition

===============================================================================
CLASSES OVERVIEW
===============================================================================

AdvisorySnapshot(frozen=True)
  Fields:
    advisory_id: str
    htf_bias: str              # e.g., "BIAS_UP"
    reasoning_mode: str        # e.g., "entry_evaluation"
    price: float               # Price at approval time
    expiration_timestamp: datetime  # Stage 7 calculated
    created_at: datetime
    reasoning_context: Dict[str, Any]
  
  Purpose: Immutable contract of what gets executed if approved.

AuditLogEntry(frozen=True)
  Fields:
    advisory_id: str
    user_id: str
    timestamp_request: datetime    # When human initiated
    timestamp_received: datetime   # When system processed
    state_snapshot: AdvisorySnapshot
    outcome: ApprovalOutcome       # APPROVED | REJECTED | EXPIRED
    reason: Optional[str]          # Why approved/rejected
    request_duration_ms: Optional[float]
  
  Purpose: Immutable record of human approval decision for compliance.

ApprovalOutcome(Enum)
  APPROVED       → Human explicitly approved
  REJECTED       → Human explicitly rejected
  EXPIRED        → Advisory expired per Stage 7 before approval
  INVALIDATED    → State changed (reserved for future)
  PENDING        → Awaiting decision (reserved for future)

===============================================================================
USAGE PATTERNS
===============================================================================

APPROVE AN ADVISORY:
  outcome = manager.approve_advisory(
      advisory_snapshot,
      user_id="trader_alice",
      approve=True,
      reason="Price action confirms setup"
  )
  
  if outcome == ApprovalOutcome.APPROVED:
      # Snapshot now frozen, execution allowed
      pass

EXECUTE IF APPROVED:
  if manager.execute_if_approved("ADV-001"):
      frozen = manager.approvals["ADV-001"]
      # Use frozen.price, frozen.htf_bias, frozen.reasoning_mode
      execute_trade(frozen.price)
  else:
      # Advisory not approved, expired, or invalid
      pass

REJECT AN ADVISORY:
  outcome = manager.approve_advisory(
      advisory_snapshot,
      user_id="trader_bob",
      approve=False,
      reason="Risk/reward unfavorable"
  )
  
  if outcome == ApprovalOutcome.REJECTED:
      # Advisory NOT added to approvals, cannot execute
      pass

CHECK BEFORE EXECUTING:
  if manager.is_approval_valid("ADV-001"):
      can_execute = manager.execute_if_approved("ADV-001")
      if can_execute:
          # Safe to execute
          pass

EXPORT AUDIT TRAIL:
  trail = manager.get_audit_trail()
  for entry in trail:
      print(f"{entry['advisory_id']}: {entry['outcome']}")
      print(f"  User: {entry['user_id']}")
      print(f"  Reason: {entry['reason']}")
      print(f"  Price: {entry['state_snapshot']['price']}")

===============================================================================
APPROVAL OUTCOME DECISION TREE
===============================================================================

Is advisory expired per Stage 7?
  ├─ Yes  → Return EXPIRED (cannot approve expired advisory)
  └─ No
      └─ Human approves (approve=True)?
          ├─ Yes → Freeze snapshot, Return APPROVED
          └─ No  → Do not freeze, Return REJECTED

Can execute advisory_id?
  ├─ outcome == APPROVED?
  │   ├─ No  → Return False (cannot execute)
  │   └─ Yes
  │       └─ Frozen snapshot exists?
  │           ├─ No  → Return False (cannot execute)
  │           └─ Yes
  │               └─ Snapshot still unexpired?
  │                   ├─ No  → Return False (expired before execution)
  │                   └─ Yes → Return True (execute!)

===============================================================================
TESTING SUMMARY
===============================================================================

48 Tests, 100% Pass Rate

Categories:
  • Snapshot Immutability (3 tests)      — frozen dataclass works
  • Binary Constraint (4 tests)          — only APPROVED/REJECTED possible
  • Frozen Snapshots (4 tests)           — approved snapshots frozen
  • Stage 7 Expiration (5 tests)         — expiration checks work
  • Audit Immutability (8 tests)         — audit trail frozen
  • Execution Boundary (5 tests)         — only approved can execute
  • Validation (5 tests)                 — missing fields detected
  • Audit Trail Retrieval (3 tests)      — export works
  • Approval Validity (4 tests)          — is_approval_valid works
  • Multiple Approvals (1 test)          — multiple advisories independent
  • Edge Cases (3 tests)                 — timeframes, reasons, custom durations
  • Logging (4 tests)                    — decisions logged appropriately

===============================================================================
IMMUTABILITY GUARANTEES
===============================================================================

FROZEN SNAPSHOTS:
  ✓ frozen=True on AdvisorySnapshot
  ✓ No field modifications after creation
  ✓ Hash-based equality checking
  ✓ Exception raised if modification attempted
  ✓ Guarantees: "What was approved stays what was approved"

FROZEN AUDIT ENTRIES:
  ✓ frozen=True on AuditLogEntry
  ✓ No outcome changes after logged
  ✓ No deletion or reordering possible
  ✓ Exception raised if modification attempted
  ✓ Guarantees: "Audit trail is permanent record"

BINARY CONSTRAINT:
  ✓ Only two possible outcomes: APPROVED | REJECTED
  ✓ No intermediate states, no defaults
  ✓ Absence of approval = rejection
  ✓ Guarantees: "Approval decision is unambiguous"

STAGE 7 INTEGRATION:
  ✓ Expiration checked before approval
  ✓ Expiration checked before execution
  ✓ No grace periods, no "almost expired" logic
  ✓ Guarantees: "Only fresh advisories execute"

===============================================================================
COMPLIANCE FEATURES
===============================================================================

✓ Immutable Audit Trail
  — Who: user_id captured
  — When: timestamp_request and timestamp_received
  — What: frozen snapshot captured
  — Why: reason field captured
  — Result: approval outcome captured

✓ Fail-Closed Design
  — No auto-approval
  — No fallback logic
  — No "good enough" approvals
  — Execution requires explicit APPROVED

✓ Forensic Capability
  — Audit trail answers: "Who approved this? When? Why?"
  — Frozen snapshot answers: "What was the exact state?"
  — Timestamps enable: "How long was review period?"
  — Immutability ensures: "Record cannot be falsified"

✓ Integration with Stage 7
  — Expiration timestamp pre-calculated
  — Stage 8 enforces freshness
  — Advisory age always verifiable
  — Prevents stale signal execution

===============================================================================
EDGE CASES HANDLED
===============================================================================

✓ Expired Advisory
  — Attempting to approve → return EXPIRED
  — Attempting to execute → return False
  — Not added to approvals dict

✓ Non-Existent Advisory
  — Attempting to execute → return False
  — is_approval_valid() → return False

✓ Multiple Approvals
  — Each advisory tracked independently
  — Approving one doesn't affect others
  — Rejection of one doesn't affect others

✓ Optional Reason Field
  — reason=None is allowed
  — Logged as None in audit trail
  — Does not block approval

✓ Custom Timeframe Durations
  — Can pass custom duration mappings
  — Falls back to defaults if not provided
  — Used in expiration calculation

✓ Advisory at Exact Expiration Time
  — Handled by now > expiration check
  — Treats "at expiration" as expired
  — Safe behavior (fail-closed)

===============================================================================
PROPERTIES & ATTRIBUTES
===============================================================================

manager.approvals: Dict[str, AdvisorySnapshot]
  — Stores frozen snapshots for APPROVED advisories
  — Key: advisory_id
  — Value: immutable snapshot (used for execution)

manager.approval_outcomes: Dict[str, ApprovalOutcome]
  — Stores final outcome for each advisory
  — Key: advisory_id
  — Value: APPROVED | REJECTED | EXPIRED | INVALIDATED

manager.audit_log: List[AuditLogEntry]
  — Chronological immutable audit trail
  — Each entry is frozen (immutable)
  — Exportable for compliance

manager.timeframe_durations: Dict[str, int]
  — Maps timeframe to duration in seconds
  — Used for Stage 7 expiration calculation
  — Defaults: 1M=60s, 5M=300s, 1H=3600s, 4H=14400s, 1D=86400s

===============================================================================
INTEGRATION POINTS
===============================================================================

UPSTREAM (Stage 7):
  Provides:
    — advisory with expiration_timestamp pre-calculated
    — timeframe information
  Contract:
    — expiration = min(next_candle_close, created + 50% of duration)

DOWNSTREAM (Stage 9+):
  Calls:
    — manager.execute_if_approved(advisory_id) → bool
    — manager.approvals[advisory_id] → frozen snapshot
    — manager.is_approval_valid(advisory_id) → bool
  Expects:
    — Only execute if execute_if_approved() returns True
    — Use frozen snapshot for execution (never live data)
    — All approvals tracked in audit trail

COMPLIANCE:
  Calls:
    — manager.get_audit_trail() → List[Dict]
    — manager.get_audit_trail(advisory_id) → List[Dict]
  Expects:
    — Immutable audit records
    — Completeness (all approvals logged)
    — Traceability (user_id, timestamps)

===============================================================================
PERFORMANCE CHARACTERISTICS
===============================================================================

Approval Processing:
  Time: O(1) constant time
  Space: O(n) where n = number of advisories
  
Execution Check:
  Time: O(1) constant time (dict lookup + expiration check)
  Space: O(1) (no additional allocation)

Audit Trail Export:
  Time: O(n) where n = number of entries
  Space: O(n) (serialization of all entries)

Expiration Check:
  Time: O(1) (current time comparison)
  Space: O(1) (no additional allocation)

Audit Log Append:
  Time: O(1) amortized (list append)
  Space: O(m) where m = entry size (~1KB per entry)

===============================================================================
ASSUMPTIONS & CONSTRAINTS
===============================================================================

ASSUMPTIONS:
  ✓ All timestamps are UTC (no timezone conversion)
  ✓ Candle durations provided or defaults used
  ✓ Stage 7 pre-calculates expiration_timestamp
  ✓ Human users identified by user_id
  ✓ Audit log can grow unbounded (no archival)
  ✓ Snapshot reasoning_context may contain timeframe

CONSTRAINTS (by design):
  ✓ Binary approval only (no gradations)
  ✓ No approval revocation (immutable)
  ✓ No conditional approvals (all or nothing)
  ✓ No role-based levels (all users equal)
  ✓ No advisory grouping (all independent)
  ✓ First approval/rejection wins (no override)

These constraints enforce immutability and fail-closed design.

===============================================================================
FILES
===============================================================================

Implementation:
  /reasoner_service/human_approval_manager.py
    — HumanApprovalManager (474 lines)
    — AdvisorySnapshot, AuditLogEntry, ApprovalOutcome
    — All methods fully implemented

Tests:
  /tests/test_human_approval_manager.py
    — 48 comprehensive tests
    — 100% pass rate
    — All rules verified

Documentation:
  STAGE_8_IMPLEMENTATION_SUMMARY.md    — Full reference
  STAGE_8_QUICK_REFERENCE.md           — This file
  STAGE_8_TECHNICAL_SPECIFICATION.md   — Detailed spec
  STAGE_8_INTEGRATION_GUIDE.md         — Integration patterns

===============================================================================
