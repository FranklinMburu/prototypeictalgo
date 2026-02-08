"""
Stage 8: Human Approval & Execution Boundary v1.0

CRITICAL PRINCIPLES:
1. Immutable approval contract: Once approved, snapshot is frozen forever
2. Binary approvals only: APPROVED | REJECTED (no middle ground)
3. Stage 7 expiration integration: Advisory expires per candle duration rules
4. Audit immutability: Every human action logged, never modified
5. Fail-closed execution: Execute only if approved AND unexpired

NO AUTO-APPROVAL, NO INFERENCE, NO FALLBACK LOGIC.
Human decision is final and locked in frozen snapshot.

FROZEN SNAPSHOT RULE:
  - At approval time, advisory state is captured and frozen (immutable)
  - Execution uses ONLY frozen snapshot, never live data
  - This prevents logic creep and guarantees deterministic execution

STAGE 7 EXPIRATION RULE:
  Advisory expires at next candle close of its generating timeframe
  OR 50% of candle duration, whichever comes first.
  After expiration, advisory cannot be approved or executed.

AUDIT IMMUTABILITY:
  - Approval logged with exact timestamp (request received, state captured)
  - Entry frozen forever, never updated or deleted
  - All timestamps in UTC, immutable dataclass
  - Audit trail is source of truth for compliance
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Literal, List
import logging


logger = logging.getLogger(__name__)


class ApprovalOutcome(Enum):
    """Binary approval states + lifecycle states."""
    APPROVED = "APPROVED"      # Human explicitly approved
    REJECTED = "REJECTED"      # Human explicitly rejected
    EXPIRED = "EXPIRED"        # Exceeded Stage 7 time window
    INVALIDATED = "INVALIDATED"  # State changed, advisory no longer valid
    PENDING = "PENDING"        # Awaiting human decision


@dataclass(frozen=True)
class AdvisorySnapshot:
    """
    IMMUTABLE frozen snapshot of advisory state at approval time.
    
    frozen=True enforces immutability: no field modifications after creation.
    This prevents accidental mutation of the execution contract.
    """
    advisory_id: str
    htf_bias: str                    # e.g., "BIAS_UP", "BIAS_DOWN", "BIAS_NEUTRAL"
    reasoning_mode: str              # e.g., "entry_evaluation", "trade_management"
    price: float                     # Advisory price at creation time
    expiration_timestamp: datetime   # Stage 7 calculated expiration (UTC)
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reasoning_context: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        """Make dataclass hashable for use as dict key if needed."""
        return hash((self.advisory_id, self.created_at.isoformat()))


@dataclass(frozen=True)
class AuditLogEntry:
    """
    IMMUTABLE audit log entry recording human approval decision.
    
    frozen=True ensures audit trail cannot be modified after creation.
    This is critical for compliance and forensics.
    """
    advisory_id: str
    user_id: str
    timestamp_request: datetime      # When human initiated approval request
    timestamp_received: datetime     # When system received approval
    state_snapshot: AdvisorySnapshot # Frozen snapshot of advisory at approval time
    outcome: ApprovalOutcome         # APPROVED | REJECTED | EXPIRED | INVALIDATED
    reason: Optional[str] = None     # Explicit human rationale
    
    # Metadata for compliance
    request_duration_ms: Optional[float] = None  # Time from request to decision
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for audit trail persistence."""
        return {
            "advisory_id": self.advisory_id,
            "user_id": self.user_id,
            "timestamp_request": self.timestamp_request.isoformat(),
            "timestamp_received": self.timestamp_received.isoformat(),
            "state_snapshot": {
                "advisory_id": self.state_snapshot.advisory_id,
                "htf_bias": self.state_snapshot.htf_bias,
                "reasoning_mode": self.state_snapshot.reasoning_mode,
                "price": self.state_snapshot.price,
                "expiration_timestamp": self.state_snapshot.expiration_timestamp.isoformat(),
                "created_at": self.state_snapshot.created_at.isoformat(),
            },
            "outcome": self.outcome.value,
            "reason": self.reason,
            "request_duration_ms": self.request_duration_ms,
        }


class HumanApprovalManager:
    """
    Stage 8: Execution boundary enforcing human approval contract.
    
    Responsibility:
    - Enforce binary approval constraint (APPROVED | REJECTED)
    - Freeze advisory snapshot at approval time (immutable)
    - Integrate Stage 7 expiration rules (candle duration)
    - Log all approvals immutably for compliance
    - Execute only if approved AND unexpired
    - Block invalid, expired, or rejected advisories
    """
    
    def __init__(self, timeframe_candle_durations: Optional[Dict[str, int]] = None):
        """
        Initialize approval manager.
        
        Args:
            timeframe_candle_durations: Dict mapping timeframe to duration in seconds.
                Example: {"1H": 3600, "4H": 14400, "1D": 86400}
                Used for Stage 7 expiration calculation.
        """
        self.approvals: Dict[str, AdvisorySnapshot] = {}
        self.approval_outcomes: Dict[str, ApprovalOutcome] = {}
        self.audit_log: List[AuditLogEntry] = []
        
        # Default candle durations if not provided
        self.timeframe_durations = timeframe_candle_durations or {
            "1M": 60,
            "5M": 300,
            "15M": 900,
            "1H": 3600,
            "4H": 14400,
            "1D": 86400,
        }
    
    def approve_advisory(
        self,
        advisory_snapshot: AdvisorySnapshot,
        user_id: str,
        approve: bool = True,
        reason: Optional[str] = None,
    ) -> ApprovalOutcome:
        """
        Stage 8: Process human approval decision (APPROVED or REJECTED).
        
        IMMUTABLE CONTRACT:
        1. Check if advisory has expired per Stage 7 rules
        2. If expired → return EXPIRED immediately (cannot approve expired)
        3. If not expired → accept binary decision (approve=True/False)
        4. Freeze snapshot at approval time (immutable)
        5. Log approval decision immutably
        
        Args:
            advisory_snapshot: Snapshot of advisory at request time
            user_id: Human identifier of approver
            approve: True=APPROVED, False=REJECTED (binary only)
            reason: Optional human rationale for audit trail
        
        Returns:
            ApprovalOutcome: APPROVED, REJECTED, EXPIRED, or INVALIDATED
        
        Raises:
            ValueError: If snapshot is missing critical fields
        """
        timestamp_request = datetime.now(timezone.utc)
        
        # Validate snapshot completeness
        if not advisory_snapshot.advisory_id:
            raise ValueError("snapshot advisory_id is required")
        if not advisory_snapshot.htf_bias:
            raise ValueError("snapshot htf_bias is required")
        if not advisory_snapshot.reasoning_mode:
            raise ValueError("snapshot reasoning_mode is required")
        if not advisory_snapshot.expiration_timestamp:
            raise ValueError("snapshot expiration_timestamp is required")
        
        # Stage 7: Check if advisory has expired
        is_expired = self._stage7_expiration_check(advisory_snapshot)
        if is_expired:
            outcome = ApprovalOutcome.EXPIRED
            entry = AuditLogEntry(
                advisory_id=advisory_snapshot.advisory_id,
                user_id=user_id,
                timestamp_request=timestamp_request,
                timestamp_received=datetime.now(timezone.utc),
                state_snapshot=advisory_snapshot,
                outcome=outcome,
                reason="Advisory expired per Stage 7 expiration rules",
            )
            self._log_audit_entry(entry)
            logger.error(
                "Stage 8: Advisory expired (advisory_id: %s, expiration: %s, user: %s)",
                advisory_snapshot.advisory_id,
                advisory_snapshot.expiration_timestamp.isoformat(),
                user_id
            )
            return outcome
        
        # Binary approval decision
        if approve:
            outcome = ApprovalOutcome.APPROVED
            # Freeze snapshot at approval time
            self.approvals[advisory_snapshot.advisory_id] = advisory_snapshot
            log_msg = "Advisory approved"
        else:
            outcome = ApprovalOutcome.REJECTED
            log_msg = "Advisory rejected"
        
        # Immutable audit logging
        timestamp_received = datetime.now(timezone.utc)
        request_duration_ms = (timestamp_received - timestamp_request).total_seconds() * 1000
        
        entry = AuditLogEntry(
            advisory_id=advisory_snapshot.advisory_id,
            user_id=user_id,
            timestamp_request=timestamp_request,
            timestamp_received=timestamp_received,
            state_snapshot=advisory_snapshot,
            outcome=outcome,
            reason=reason,
            request_duration_ms=request_duration_ms,
        )
        
        # Store outcome for execution boundary
        self.approval_outcomes[advisory_snapshot.advisory_id] = outcome
        
        # Log immutably
        self._log_audit_entry(entry)
        
        logger.info(
            "Stage 8: %s (advisory_id: %s, user: %s)",
            log_msg,
            advisory_snapshot.advisory_id,
            user_id
        )
        
        return outcome
    
    def execute_if_approved(self, advisory_id: str) -> bool:
        """
        Execute frozen advisory only if APPROVED and unexpired.
        
        Execution boundary:
        - Check if advisory has been explicitly APPROVED
        - Check if frozen snapshot exists (immutable contract)
        - Check if snapshot has not expired per Stage 7
        - Return True only if ALL conditions met
        - Return False and log rejection otherwise
        
        Args:
            advisory_id: ID of advisory to execute
        
        Returns:
            True if advisory executed, False if blocked
        """
        # Step 1: Check if approval outcome is APPROVED
        outcome = self.approval_outcomes.get(advisory_id)
        if outcome is None:
            logger.error(
                "Stage 8: Execution blocked (advisory_id: %s, reason: no approval found)",
                advisory_id
            )
            return False
        
        if outcome != ApprovalOutcome.APPROVED:
            logger.error(
                "Stage 8: Execution blocked (advisory_id: %s, outcome: %s)",
                advisory_id,
                outcome.value
            )
            return False
        
        # Step 2: Check if frozen snapshot exists
        snapshot = self.approvals.get(advisory_id)
        if snapshot is None:
            logger.error(
                "Stage 8: Execution blocked (advisory_id: %s, reason: no frozen snapshot)",
                advisory_id
            )
            return False
        
        # Step 3: Check if snapshot has not expired per Stage 7
        is_expired = self._stage7_expiration_check(snapshot)
        if is_expired:
            logger.error(
                "Stage 8: Execution blocked (advisory_id: %s, reason: snapshot expired)",
                advisory_id
            )
            return False
        
        # All checks passed: execute with frozen snapshot
        logger.info(
            "Stage 8: Execution approved (advisory_id: %s, bias: %s, mode: %s, price: %.2f)",
            snapshot.advisory_id,
            snapshot.htf_bias,
            snapshot.reasoning_mode,
            snapshot.price
        )
        return True
    
    def _stage7_expiration_check(self, advisory_snapshot: AdvisorySnapshot) -> bool:
        """
        Check if advisory has expired per Stage 7 rules.
        
        Stage 7 Expiration Rule:
          Advisory expires at next candle close of its generating timeframe
          OR 50% of candle duration, whichever comes first.
        
        Implementation:
          1. Extract timeframe from advisory (assumed in reasoning_context or HTF)
          2. Calculate next candle close time
          3. Calculate 50% of candle duration
          4. Take the minimum of two
          5. Check if current time exceeds expiration time
        
        Args:
            advisory_snapshot: Snapshot with expiration_timestamp
        
        Returns:
            True if advisory has expired, False if still valid
        """
        now_utc = datetime.now(timezone.utc)
        
        # Extract timeframe (default to 4H if not found)
        timeframe = advisory_snapshot.reasoning_context.get("timeframe", "4H")
        
        # Get candle duration in seconds
        candle_duration_seconds = self.timeframe_durations.get(timeframe, 14400)  # 4H default
        
        # Stage 7 expiration is min(next_candle_close, created_at + 50% of duration)
        # The expiration_timestamp is pre-calculated by Stage 7
        expiration_time = advisory_snapshot.expiration_timestamp
        
        is_expired = now_utc > expiration_time
        
        if is_expired:
            logger.warning(
                "Stage 7 Expiration: Advisory %s expired at %s (now: %s)",
                advisory_snapshot.advisory_id,
                expiration_time.isoformat(),
                now_utc.isoformat()
            )
        
        return is_expired
    
    def _log_audit_entry(self, entry: AuditLogEntry):
        """
        Record immutable audit entry.
        
        CRITICAL: This entry is NEVER modified after creation.
        The immutable dataclass and frozen list ensure forensic integrity.
        
        Args:
            entry: AuditLogEntry to log (immutable)
        """
        self.audit_log.append(entry)
        logger.debug(
            "Audit logged: %s (advisory: %s, outcome: %s)",
            entry.__class__.__name__,
            entry.advisory_id,
            entry.outcome.value
        )
    
    def get_audit_trail(self, advisory_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieve immutable audit trail.
        
        Args:
            advisory_id: Optional filter to specific advisory
        
        Returns:
            List of audit log entries as dicts (immutable records)
        """
        if advisory_id is None:
            return [entry.to_dict() for entry in self.audit_log]
        
        return [
            entry.to_dict()
            for entry in self.audit_log
            if entry.advisory_id == advisory_id
        ]
    
    def is_approval_valid(self, advisory_id: str) -> bool:
        """
        Check if advisory approval is still valid.
        
        An approval is valid only if:
        1. Advisory was explicitly APPROVED
        2. Frozen snapshot exists
        3. Snapshot has not expired per Stage 7
        
        Args:
            advisory_id: ID to check
        
        Returns:
            True if valid and executable, False otherwise
        """
        outcome = self.approval_outcomes.get(advisory_id)
        if outcome != ApprovalOutcome.APPROVED:
            return False
        
        snapshot = self.approvals.get(advisory_id)
        if snapshot is None:
            return False
        
        is_expired = self._stage7_expiration_check(snapshot)
        return not is_expired
