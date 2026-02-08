"""
Execution Boundary: Data Models

CRITICAL PRINCIPLE:
"This layer does NOT infer intent from shadow-mode outputs."

This module defines STRICT DATA CONTRACTS for execution intents and approvals.
These models are:
- PURELY STRUCTURAL (no validation logic beyond type checking)
- HUMAN-AUTHORED (ExecutionIntent and HumanExecutionApproval must come from humans)
- AUDIT-FIRST (all fields are logged as-is)
- COMPLETELY ISOLATED from shadow-mode services

NO IMPORTS from shadow-mode modules (decision_*_service, orchestrator, etc.)
NO INFERENCE from shadow-mode metrics
NO AUTO-APPROVAL mechanisms
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from uuid import uuid4


class ExecutionIntentType(Enum):
    """
    Types of execution intents that humans can authorize.

    These are OPERATIONAL intents, not derived from signals or recommendations.
    Each represents a discrete trading action that requires explicit approval.
    """
    OPEN_POSITION = "open_position"
    CLOSE_POSITION = "close_position"
    MODIFY_POSITION = "modify_position"
    HALT_ALL_TRADING = "halt_all_trading"
    RESUME_TRADING = "resume_trading"
    MANUAL_OVERRIDE = "manual_override"


class IntentStatus(Enum):
    """Status of an execution intent throughout its lifecycle."""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ApprovalAuthority(Enum):
    """
    Authority levels for approvals.

    HUMAN_TRADER: Direct human approval (override authority)
    RISK_OFFICER: Risk/compliance approval
    SYSTEM_ADMIN: System administrator override (emergency only)
    """
    HUMAN_TRADER = "human_trader"
    RISK_OFFICER = "risk_officer"
    SYSTEM_ADMIN = "system_admin"


class KillSwitchType(Enum):
    """
    Kill switch types for emergency halting.

    MANUAL: Human-activated via explicit command
    CIRCUIT_BREAKER: Automated based on catastrophic system state
    TIMEOUT: Automated based on execution timeout
    """
    MANUAL = "manual"
    CIRCUIT_BREAKER = "circuit_breaker"
    TIMEOUT = "timeout"


@dataclass
class ExecutionIntent:
    """
    HUMAN-AUTHORED execution intent.

    CRITICAL: This must be created by HUMAN OPERATORS ONLY.
    It represents a discrete trading action to be executed.

    FIELDS ARE NOT INFERRED from shadow-mode outputs. They are explicit
    human directives: symbol, quantity, price, order type, etc.

    NO LOGIC IN THIS CLASS: It is pure data structure.
    NO IMPORTS from shadow-mode modules.
    """

    # Unique identifier for this intent
    intent_id: str = field(default_factory=lambda: str(uuid4()))

    # Type of execution (OPEN_POSITION, CLOSE_POSITION, etc.)
    intent_type: ExecutionIntentType = ExecutionIntentType.OPEN_POSITION

    # Status of this intent
    status: IntentStatus = IntentStatus.PENDING_APPROVAL

    # When this intent was created
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Human-authored metadata (EXPLICIT DIRECTIVES, NOT INFERRED)
    symbol: Optional[str] = None  # e.g., "AAPL"
    quantity: Optional[float] = None  # e.g., 100
    price: Optional[float] = None  # Limit price if applicable
    order_type: Optional[str] = None  # e.g., "MARKET", "LIMIT", "STOP"
    time_in_force: Optional[str] = None  # e.g., "GTC", "IOC"

    # Human rationale (REQUIRED for audit trail)
    human_rationale: str = ""
    """
    Explicit human explanation for this intent.
    Example: "Close position due to end-of-day risk management"
    
    This MUST NOT reference shadow-mode outputs or metrics.
    It must be human-readable, human-authored intent.
    """

    # Risk limits (explicit human-set bounds)
    max_loss: Optional[float] = None
    max_position_size: Optional[float] = None
    required_profit_margin: Optional[float] = None

    # Expiration time
    expires_at: Optional[datetime] = None

    # Additional structured metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """
        Minimal validation: only check that critical fields are present.
        No business logic. No inference. No shadow-mode processing.
        """
        if not self.human_rationale:
            raise ValueError("human_rationale is required for audit trail")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for logging.
        
        Serializes datetime objects as ISO format strings.
        """
        data = asdict(self)
        # Convert Enum values to strings
        data["intent_type"] = self.intent_type.value
        data["status"] = self.status.value
        # Convert datetime to ISO format
        if isinstance(data["created_at"], datetime):
            data["created_at"] = data["created_at"].isoformat()
        if isinstance(data["expires_at"], datetime) and data["expires_at"]:
            data["expires_at"] = data["expires_at"].isoformat()
        return data


@dataclass
class HumanExecutionApproval:
    """
    EXPLICIT HUMAN APPROVAL for execution.

    CRITICAL: This represents HUMAN AUTHORIZATION and must be generated by
    an authorized human operator ONLY.

    THIS IS NOT INFERRED from shadow-mode outputs.
    THIS CANNOT BE AUTO-GENERATED.
    THIS REQUIRES EXPLICIT HUMAN ACTION.

    Default behavior is DENY (absence of approval = no execution).
    """

    # Unique identifier for this approval
    approval_id: str = field(default_factory=lambda: str(uuid4()))

    # The intent being approved
    intent_id: str = ""
    """ID of the ExecutionIntent this approval authorizes."""

    # Approval decision (required)
    approved: bool = False
    """
    True = APPROVE this execution intent
    False = REJECT this execution intent
    
    Default is False (fail-closed: denial is default).
    """

    # Authority of approver
    authority_level: ApprovalAuthority = ApprovalAuthority.HUMAN_TRADER

    # Who made this approval (required)
    approved_by: str = ""
    """Human identifier (username, employee ID) of approver."""

    # When approved
    approved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Explicit approval rationale (REQUIRED for audit)
    approval_rationale: str = ""
    """
    Human explanation for this approval/rejection decision.
    Must explain WHY the intent is approved or rejected.
    
    Examples:
    - "APPROVED: Manual position close per daily risk review"
    - "REJECTED: Position size exceeds risk limit"
    """

    # Optional additional conditions
    conditional_approval: bool = False
    approval_conditions: List[str] = field(default_factory=list)
    """
    If conditional_approval=True, execution may proceed only if
    ALL conditions in approval_conditions are met.
    
    Conditions are human-specified strings describing constraints.
    Example: ["price >= 150.50", "volume > 1M shares"]
    """

    # Expiration of this approval
    expires_at: Optional[datetime] = None
    """Approval is invalid after this timestamp."""

    def __post_init__(self):
        """
        Minimal validation: only check that critical fields are present.
        No business logic. No inference. No shadow-mode processing.
        """
        if not self.intent_id:
            raise ValueError("intent_id is required")
        if not self.approved_by:
            raise ValueError("approved_by is required")
        if not self.approval_rationale:
            raise ValueError("approval_rationale is required for audit trail")

    def is_valid(self) -> bool:
        """
        Check if this approval is still valid (not expired).
        No other validation is performed here.
        """
        if self.expires_at is None:
            return True
        return datetime.now(timezone.utc) < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        data = asdict(self)
        data["authority_level"] = self.authority_level.value
        if isinstance(data["approved_at"], datetime):
            data["approved_at"] = data["approved_at"].isoformat()
        if isinstance(data["expires_at"], datetime) and data["expires_at"]:
            data["expires_at"] = data["expires_at"].isoformat()
        return data


@dataclass
class KillSwitchState:
    """
    Kill switch state: manual and programmatic halts.

    CRITICAL PRINCIPLE:
    - Manual kill switches ALWAYS override programmatic state
    - Kill switch activation requires explicit human action (manual) or
      catastrophic system detection (circuit breaker)
    - Default is OFF (system may operate)
    - Absence of explicit activation means "proceed"
    """

    # Manual kill switch: human-activated
    manual_kill_active: bool = False
    """True = manual halt active (human override)"""

    manual_kill_activated_by: Optional[str] = None
    """Who activated the manual kill switch."""

    manual_kill_activated_at: Optional[datetime] = None
    """When the manual kill switch was activated."""

    manual_kill_reason: str = ""
    """Human explanation for manual kill activation."""

    # Circuit breaker: automated halt based on system state
    circuit_breaker_active: bool = False
    """True = circuit breaker engaged (system in critical state)"""

    circuit_breaker_trigger_at: Optional[datetime] = None
    """When the circuit breaker was triggered."""

    circuit_breaker_reason: str = ""
    """
    Explanation for circuit breaker engagement.
    Examples: "System error recovery threshold exceeded",
              "Critical market condition detected"
    """

    # Timeout: halt after extended failure
    timeout_active: bool = False
    """True = timeout halt active (execution timeout exceeded)"""

    timeout_triggered_at: Optional[datetime] = None
    """When timeout was triggered."""

    timeout_duration_seconds: int = 300
    """Duration of timeout (default 5 minutes)."""

    @property
    def is_halted(self) -> bool:
        """
        True if system should halt (any kill switch is active).
        
        Manual kill switch has HIGHEST priority.
        """
        return self.manual_kill_active or self.circuit_breaker_active or self.timeout_active

    def activate_manual_kill(self, activated_by: str, reason: str):
        """
        Activate manual kill switch.

        Args:
            activated_by: Human identifier (username, ID)
            reason: Human explanation for activation
        """
        self.manual_kill_active = True
        self.manual_kill_activated_by = activated_by
        self.manual_kill_activated_at = datetime.now(timezone.utc)
        self.manual_kill_reason = reason

    def deactivate_manual_kill(self):
        """Deactivate manual kill switch."""
        self.manual_kill_active = False

    def activate_circuit_breaker(self, reason: str):
        """
        Activate circuit breaker (automated halt).

        Args:
            reason: Explanation for circuit breaker engagement
        """
        self.circuit_breaker_active = True
        self.circuit_breaker_trigger_at = datetime.now(timezone.utc)
        self.circuit_breaker_reason = reason

    def deactivate_circuit_breaker(self):
        """Deactivate circuit breaker."""
        self.circuit_breaker_active = False

    def activate_timeout(self, reason: str, duration_seconds: int = 300):
        """
        Activate timeout halt.

        Args:
            reason: Explanation for timeout activation
            duration_seconds: Duration of timeout
        """
        self.timeout_active = True
        self.timeout_triggered_at = datetime.now(timezone.utc)
        self.timeout_duration_seconds = duration_seconds

    def deactivate_timeout(self):
        """Deactivate timeout halt."""
        self.timeout_active = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "manual_kill_active": self.manual_kill_active,
            "manual_kill_activated_by": self.manual_kill_activated_by,
            "manual_kill_activated_at": (
                self.manual_kill_activated_at.isoformat()
                if self.manual_kill_activated_at
                else None
            ),
            "manual_kill_reason": self.manual_kill_reason,
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_trigger_at": (
                self.circuit_breaker_trigger_at.isoformat()
                if self.circuit_breaker_trigger_at
                else None
            ),
            "circuit_breaker_reason": self.circuit_breaker_reason,
            "timeout_active": self.timeout_active,
            "timeout_triggered_at": (
                self.timeout_triggered_at.isoformat()
                if self.timeout_triggered_at
                else None
            ),
            "timeout_duration_seconds": self.timeout_duration_seconds,
            "is_halted": self.is_halted,
        }


@dataclass
class ExecutionAuditRecord:
    """
    APPEND-ONLY audit log record for execution events.

    CRITICAL PRINCIPLE:
    - Every execution event is logged immutably
    - Logs are append-only (never modified, never deleted)
    - Logs include all context: intent, approval, status, errors
    - Logs are human-readable for compliance review

    This is PURE DATA. No logic beyond initial validation.
    """

    # Unique identifier for this audit record
    record_id: str = field(default_factory=lambda: str(uuid4()))

    # When this event occurred
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Type of audit event
    event_type: str = ""
    """
    Examples: "intent_created", "approval_granted", "approval_rejected",
              "execution_started", "execution_completed", "execution_failed",
              "kill_switch_activated", "kill_switch_deactivated"
    """

    # The intent being audited
    intent_id: str = ""

    # The approval (if applicable)
    approval_id: Optional[str] = None

    # Current status
    status: str = ""

    # Structured event data
    event_data: Dict[str, Any] = field(default_factory=dict)

    # Human explanation (required for all events)
    human_note: str = ""
    """
    Human-readable explanation of this event.
    Examples:
    - "User alice approved OPEN_POSITION for AAPL"
    - "Execution failed: Market order rejected by broker"
    - "Manual kill switch activated due to system error"
    """

    # Actor (human or system component)
    actor: str = ""
    """
    Identifier of who/what triggered this event.
    Examples: "alice@company.com", "circuit_breaker", "timeout_monitor"
    """

    # Severity level
    severity: str = "INFO"
    """
    CRITICAL: System halt, kill switch, critical errors
    WARNING: Rejections, timeouts, boundary conditions
    INFO: Normal operations (approvals, executions, completions)
    """

    def __post_init__(self):
        """Minimal validation: ensure critical fields are present."""
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.intent_id:
            raise ValueError("intent_id is required")
        if not self.actor:
            raise ValueError("actor is required")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "intent_id": self.intent_id,
            "approval_id": self.approval_id,
            "status": self.status,
            "event_data": self.event_data,
            "human_note": self.human_note,
            "actor": self.actor,
            "severity": self.severity,
        }
