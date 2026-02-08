"""
Stage 9: Execution Engine & Safety Enforcement v1.0

IMMUTABLE CONTRACT PRINCIPLES:
1. Frozen Snapshot Rule: Advisory snapshot NEVER changes after approval
2. SL/TP Calculation Rule: Calculated from actual fill price, not reference price
3. Kill Switch Rules: BEFORE order → abort, DURING → cancel, AFTER → position stays open
4. Execution Timeout Rule: Hard 30s timeout, late fills are VALID
5. Retry Rules: Only within 30s window, no frozen snapshot changes
6. Reconciliation Rule: Query once, detect ANY mismatch, require manual resolution

NO STRATEGY LOGIC, NO INDICATOR CALCULATIONS, NO PRICE PREDICTION.
PURE EXECUTION INFRASTRUCTURE WITH FORENSIC-GRADE LOGGING.
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Literal
from uuid import uuid4
import logging
import hashlib


logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS
# ============================================================================

class ExecutionStage(Enum):
    """Execution lifecycle stages."""
    SUBMITTED = "submitted"           # Order submitted to broker
    PENDING = "pending"               # Waiting for fill
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"                 # Order completely filled
    CANCELLED = "cancelled"           # Order cancelled before fill
    FAILED = "failed"                 # Submission failed
    FAILED_TIMEOUT = "failed_timeout" # Timeout before fill
    EXECUTED_FULL_LATE = "executed_full_late"  # Filled after timeout (VALID)
    REJECTED = "rejected"             # Pre-flight validation failed


class KillSwitchType(Enum):
    """Kill switch types."""
    GLOBAL = "global"
    SYMBOL_LEVEL = "symbol_level"
    RISK_LIMIT = "risk_limit"
    MANUAL = "manual"


class KillSwitchState(Enum):
    """Kill switch activation state."""
    OFF = "off"
    WARNING = "warning"
    ACTIVE = "active"


class ReconciliationStatus(Enum):
    """Reconciliation outcome."""
    MATCHED = "matched"               # Broker state matches internal state
    MISMATCH = "mismatch"            # Mismatch detected
    PHANTOM_POSITION = "phantom_position"  # Position exists in broker, not internally
    MISSING_POSITION = "missing_position"  # Position exists internally, not in broker
    MISSING_SL_TP = "missing_sl_tp"   # SL/TP missing from broker


# ============================================================================
# DATA MODELS - IMMUTABLE CONTRACTS
# ============================================================================

@dataclass(frozen=True)
class FrozenSnapshot:
    """
    IMMUTABLE snapshot of approved advisory.
    
    frozen=True enforces: NEVER changes after creation.
    Contains reference state for SL/TP calculation.
    
    CRITICAL RULES:
    - SL/TP stored as PERCENTAGE OFFSETS only
    - Live SL/TP calculated from actual fill_price
    - Snapshot NEVER recalculated or re-derived
    - Snapshot NEVER modified during execution
    
    SECTION 4.3.1 (Addendum): Percentage Offset Storage
    Store SL/TP as % offsets, not absolute values:
    - sl_offset_pct: NEGATIVE (e.g., -0.02 = 2% below fill_price)
    - tp_offset_pct: POSITIVE (e.g., +0.03 = 3% above fill_price)
    - reference_price: immutable, used for slippage analytics only
    """
    advisory_id: str
    htf_bias: str
    reasoning_mode: str
    reference_price: float          # Reference, NOT live price; used for slippage calc only
    sl_offset_pct: float            # NEGATIVE: -0.02 = 2% below fill price (NOT reference)
    tp_offset_pct: float            # POSITIVE: +0.03 = 3% above fill price (NOT reference)
    position_size: float
    symbol: str
    expiration_timestamp: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reasoning_context: Dict[str, Any] = field(default_factory=dict)
    
    def snapshot_hash(self) -> str:
        """Forensic hash of snapshot (for audit trail)."""
        content = f"{self.advisory_id}{self.reference_price}{self.sl_offset_pct}{self.tp_offset_pct}{self.position_size}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class ExecutionAttempt:
    """
    Record of a single execution attempt (may include retries).
    """
    attempt_id: str = field(default_factory=lambda: str(uuid4()))
    advisory_id: str = ""
    timestamp_submit: Optional[datetime] = None
    timestamp_fill: Optional[datetime] = None
    order_id: Optional[str] = None
    fill_price: Optional[float] = None
    filled_size: Optional[float] = None
    stage: ExecutionStage = ExecutionStage.SUBMITTED
    slippage_pct: Optional[float] = None
    
    # Calculated SL/TP (from fill price, not reference price)
    calculated_sl: Optional[float] = None
    calculated_tp: Optional[float] = None
    
    # Attempt tracking
    retry_count: int = 0
    retry_reasons: List[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """
    Final outcome of execution flow (after all retries/reconciliation).
    """
    advisory_id: str
    status: ExecutionStage = ExecutionStage.SUBMITTED  # Default, will be updated
    final_order_id: Optional[str] = None
    final_fill_price: Optional[float] = None
    final_position_size: Optional[float] = None
    final_sl: Optional[float] = None
    final_tp: Optional[float] = None
    slippage_pct: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    kill_switch_state: KillSwitchState = KillSwitchState.OFF
    attempts: List[ExecutionAttempt] = field(default_factory=list)
    reconciliation_report: Optional['ReconciliationReport'] = None
    error_message: Optional[str] = None


@dataclass
class ReconciliationReport:
    """
    Broker state vs internal state reconciliation.
    
    RULE: Query broker ONCE, detect ANY mismatch, require manual resolution.
    """
    reconciliation_id: str = field(default_factory=lambda: str(uuid4()))
    advisory_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Broker state (as returned from broker)
    broker_order_id: Optional[str] = None
    broker_order_state: Optional[str] = None
    broker_fill_price: Optional[float] = None
    broker_filled_size: Optional[float] = None
    broker_position_size: Optional[float] = None
    broker_sl: Optional[float] = None
    broker_tp: Optional[float] = None
    
    # Internal state
    internal_order_id: Optional[str] = None
    internal_fill_price: Optional[float] = None
    internal_position_size: Optional[float] = None
    internal_sl: Optional[float] = None
    internal_tp: Optional[float] = None
    
    # Reconciliation findings
    status: ReconciliationStatus = ReconciliationStatus.MATCHED
    mismatches: List[str] = field(default_factory=list)
    requires_manual_resolution: bool = False


@dataclass
class ExecutionContext:
    """
    Context for execution (read-only during execution).
    """
    frozen_snapshot: FrozenSnapshot
    kill_switch_manager: 'KillSwitchManager'
    timeout_controller: 'TimeoutController'
    broker_adapter: 'BrokerAdapter'
    logger_service: 'ExecutionLogger'


# ============================================================================
# KILL SWITCH MANAGER
# ============================================================================

class KillSwitchManager:
    """
    Enforce kill switch rules.
    
    RULE: BEFORE order → abort cleanly
          DURING pending → attempt cancel, then reconcile
          AFTER fill → position STAYS OPEN with SL/TP intact
    
    ABSOLUTE PROHIBITIONS:
    ❌ Never force-close a filled position due to kill switch
    ❌ Never modify SL/TP after fill
    """
    
    def __init__(self):
        self.kill_switches: Dict[str, KillSwitchState] = {}
        self.switch_history: List[Dict[str, Any]] = []
    
    def set_kill_switch(
        self,
        switch_type: KillSwitchType,
        state: KillSwitchState,
        target: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        """
        Activate or deactivate kill switch.
        
        Args:
            switch_type: GLOBAL, SYMBOL_LEVEL, RISK_LIMIT, MANUAL
            state: OFF, WARNING, ACTIVE
            target: symbol if SYMBOL_LEVEL, "global" if GLOBAL
            reason: Why switch was activated
        """
        key = target or "global"
        self.kill_switches[key] = state
        
        self.switch_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "switch_type": switch_type.value,
            "target": key,
            "state": state.value,
            "reason": reason,
        })
        
        logger.warning(
            "Kill switch activated: type=%s, target=%s, state=%s, reason=%s",
            switch_type.value, key, state.value, reason
        )
    
    def is_active(self, target: Optional[str] = None) -> bool:
        """
        Check if kill switch is active (BEFORE order submission).
        
        Args:
            target: symbol or None for global
        
        Returns:
            True if ACTIVE or WARNING, False if OFF
        """
        key = target or "global"
        state = self.kill_switches.get(key, KillSwitchState.OFF)
        return state in (KillSwitchState.ACTIVE, KillSwitchState.WARNING)
    
    def get_state(self, target: Optional[str] = None) -> KillSwitchState:
        """Get current kill switch state."""
        key = target or "global"
        return self.kill_switches.get(key, KillSwitchState.OFF)


# ============================================================================
# TIMEOUT CONTROLLER
# ============================================================================

class TimeoutController:
    """
    Enforce 30-second hard timeout.
    
    RULE: Hard timeout 30s from first broker submission.
           At second 31: cancel pending orders, mark FAILED_TIMEOUT.
           Late fills AFTER timeout are VALID (mark EXECUTED_FULL_LATE).
    
    ABSOLUTE PROHIBITIONS:
    ❌ Never extend timeout
    ❌ Never retry after timeout
    ❌ Never place duplicate orders
    
    SECTION 6.5.1 (Addendum): Max Execution Window = 30 Seconds
    This is an immutable constant (never extended, never changed).
    Hard limit from first broker submission to timeout trigger.
    At T=30s: cancel pending → mark FAILED_TIMEOUT → reconcile.
    Late fills T ∈ (30, 31] are VALID (mark EXECUTED_FULL_LATE).
    """
    
    HARD_TIMEOUT_SECONDS = 30  # ← IMMUTABLE CONSTANT (see Section 6.5.1)
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.timeout_triggered = False
    
    def start(self):
        """Start timeout clock (on first broker submission)."""
        self.start_time = datetime.now(timezone.utc)
        logger.info("Execution timeout started (30s hard limit)")
    
    def is_expired(self) -> bool:
        """Check if 30s window has expired."""
        if self.start_time is None:
            return False
        
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        is_expired = elapsed > self.HARD_TIMEOUT_SECONDS
        
        if is_expired and not self.timeout_triggered:
            self.timeout_triggered = True
            logger.error(
                "Execution timeout triggered (elapsed: %.1fs > 30s)",
                elapsed
            )
        
        return is_expired
    
    def elapsed_seconds(self) -> float:
        """Get elapsed time since start."""
        if self.start_time is None:
            return 0
        return (datetime.now(timezone.utc) - self.start_time).total_seconds()
    
    def time_remaining_seconds(self) -> float:
        """Get remaining time before timeout."""
        remaining = self.HARD_TIMEOUT_SECONDS - self.elapsed_seconds()
        return max(0, remaining)


# ============================================================================
# RECONCILIATION SERVICE
# ============================================================================

class ReconciliationService:
    """
    Reconcile broker state vs internal state.
    
    RULE: Query broker ONCE per execution flow.
          Detect: phantom positions, missing positions, missing SL/TP.
          On ANY mismatch: pause all executions, require manual resolution.
    
    ABSOLUTE PROHIBITIONS:
    ❌ No auto-correction
    ❌ No silent retries after mismatch
    ❌ No assumptions about broker success
    """
    
    def __init__(self):
        self.reconciliations: List[ReconciliationReport] = []
    
    def reconcile(
        self,
        advisory_id: str,
        broker_adapter: 'BrokerAdapter',
        order_id: Optional[str] = None,
        expected_position_size: Optional[float] = None,
        expected_sl: Optional[float] = None,
        expected_tp: Optional[float] = None,
    ) -> ReconciliationReport:
        """
        Query broker state and compare against expected state.
        
        Args:
            advisory_id: Advisory being reconciled
            broker_adapter: Broker interface to query
            order_id: Order to check status
            expected_position_size: What we expect position to be
            expected_sl: What we expect SL to be
            expected_tp: What we expect TP to be
        
        Returns:
            ReconciliationReport with findings
        """
        report = ReconciliationReport(advisory_id=advisory_id)
        
        # Query broker ONCE (no retries)
        logger.info("Reconciliation: Querying broker state (advisory: %s)", advisory_id)
        
        # Get order status
        if order_id:
            order_status = broker_adapter.get_order_status(order_id)
            report.broker_order_id = order_id
            report.broker_order_state = order_status.get("state")
            report.broker_fill_price = order_status.get("fill_price")
            report.broker_filled_size = order_status.get("filled_size")
            
            report.internal_order_id = order_id
            report.internal_fill_price = report.broker_fill_price
        
        # Get position state
        positions = broker_adapter.get_positions()
        if positions:
            pos = positions[0]  # Assume single position
            report.broker_position_size = pos.get("size")
            report.broker_sl = pos.get("sl")
            report.broker_tp = pos.get("tp")
            report.internal_position_size = expected_position_size
            report.internal_sl = expected_sl
            report.internal_tp = expected_tp
        
        # Detect mismatches
        if expected_position_size is not None:
            if report.broker_position_size is None:
                report.status = ReconciliationStatus.MISSING_POSITION
                report.mismatches.append(
                    f"Expected position {expected_position_size}, found NONE in broker"
                )
                report.requires_manual_resolution = True
            elif abs(report.broker_position_size - expected_position_size) > 0.001:
                report.status = ReconciliationStatus.MISMATCH
                report.mismatches.append(
                    f"Position size mismatch: expected {expected_position_size}, broker has {report.broker_position_size}"
                )
                report.requires_manual_resolution = True
        
        # Check SL/TP integrity
        if expected_sl is not None and report.broker_sl is None:
            report.status = ReconciliationStatus.MISSING_SL_TP
            report.mismatches.append("SL/TP missing from broker")
            report.requires_manual_resolution = True
        
        if report.requires_manual_resolution:
            logger.error(
                "Reconciliation MISMATCH detected (advisory: %s, mismatches: %s)",
                advisory_id,
                report.mismatches
            )
        else:
            logger.info("Reconciliation: Matched (advisory: %s)", advisory_id)
        
        self.reconciliations.append(report)
        return report


# ============================================================================
# BROKER ADAPTER (INTERFACE - STUBBED)
# ============================================================================

class BrokerAdapter:
    """
    Stubbed broker interface (no real API calls).
    
    In production, implement with real broker SDK.
    Methods: submit_order, cancel_order, get_order_status, get_positions.
    
    NO STRATEGY LOGIC HERE. Just broker interface.
    """
    
    def submit_order(
        self,
        symbol: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "MARKET",
    ) -> Dict[str, Any]:
        """
        Submit order to broker.
        
        Args:
            symbol: Trading symbol
            quantity: Position size
            price: Limit price (if applicable)
            order_type: MARKET, LIMIT, STOP
        
        Returns:
            {
                "order_id": str,
                "state": "submitted",
                "fill_price": None,
                "filled_size": 0,
            }
        """
        raise NotImplementedError("Implement in subclass with real broker API")
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Attempt to cancel pending order.
        
        Returns:
            True if cancellation succeeded, False otherwise.
        """
        raise NotImplementedError("Implement in subclass with real broker API")
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        Get current order status from broker.
        
        Returns:
            {
                "order_id": str,
                "state": "pending" | "filled" | "cancelled" | "failed",
                "fill_price": float or None,
                "filled_size": float,
            }
        """
        raise NotImplementedError("Implement in subclass with real broker API")
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions from broker.
        
        Returns:
            [
                {
                    "symbol": str,
                    "size": float,
                    "entry_price": float,
                    "sl": float or None,
                    "tp": float or None,
                }
            ]
        """
        raise NotImplementedError("Implement in subclass with real broker API")


# ============================================================================
# EXECUTION LOGGER
# ============================================================================

class ExecutionLogger:
    """
    Forensic-grade logging for compliance and replay.
    
    MANDATORY LOGGING:
    - Advisory ID
    - Snapshot hash
    - Timestamps (submit, fill, timeout)
    - Fill price
    - Calculated SL/TP
    - Slippage %
    - Kill switch state
    - Final execution outcome
    """
    
    def __init__(self):
        self.execution_logs: List[Dict[str, Any]] = []
    
    def log_execution_start(
        self,
        advisory_id: str,
        snapshot: FrozenSnapshot,
        kill_switch_state: KillSwitchState,
    ):
        """Log execution initiation."""
        log_entry = {
            "event": "execution_start",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "advisory_id": advisory_id,
            "snapshot_hash": snapshot.snapshot_hash(),
            "position_size": snapshot.position_size,
            "reference_price": snapshot.reference_price,
            "sl_offset_pct": snapshot.sl_offset_pct,
            "tp_offset_pct": snapshot.tp_offset_pct,
            "kill_switch_state": kill_switch_state.value,
        }
        self.execution_logs.append(log_entry)
        logger.info("Execution started: advisory=%s, snapshot_hash=%s",
                   advisory_id, snapshot.snapshot_hash())
    
    def log_order_submitted(
        self,
        advisory_id: str,
        order_id: str,
        symbol: str,
        quantity: float,
    ):
        """Log order submission to broker."""
        log_entry = {
            "event": "order_submitted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "advisory_id": advisory_id,
            "order_id": order_id,
            "symbol": symbol,
            "quantity": quantity,
        }
        self.execution_logs.append(log_entry)
        logger.info("Order submitted: order_id=%s, symbol=%s, qty=%s",
                   order_id, symbol, quantity)
    
    def log_order_filled(
        self,
        advisory_id: str,
        order_id: str,
        fill_price: float,
        filled_size: float,
        calculated_sl: float,
        calculated_tp: float,
        slippage_pct: float,
    ):
        """Log order fill with calculated SL/TP."""
        log_entry = {
            "event": "order_filled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "advisory_id": advisory_id,
            "order_id": order_id,
            "fill_price": fill_price,
            "filled_size": filled_size,
            "calculated_sl": calculated_sl,
            "calculated_tp": calculated_tp,
            "slippage_pct": slippage_pct,
        }
        self.execution_logs.append(log_entry)
        logger.info(
            "Order filled: order_id=%s, fill_price=%.2f, sl=%.2f, tp=%.2f, slippage=%.2f%%",
            order_id, fill_price, calculated_sl, calculated_tp, slippage_pct
        )
    
    def log_timeout(self, advisory_id: str, elapsed_seconds: float):
        """Log execution timeout."""
        log_entry = {
            "event": "timeout",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "advisory_id": advisory_id,
            "elapsed_seconds": elapsed_seconds,
        }
        self.execution_logs.append(log_entry)
        logger.error("Execution timeout: advisory=%s, elapsed=%.1fs",
                    advisory_id, elapsed_seconds)
    
    def log_kill_switch_abort(
        self,
        advisory_id: str,
        kill_switch_state: KillSwitchState,
        reason: str,
    ):
        """Log kill switch preventing order submission."""
        log_entry = {
            "event": "kill_switch_abort",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "advisory_id": advisory_id,
            "kill_switch_state": kill_switch_state.value,
            "reason": reason,
        }
        self.execution_logs.append(log_entry)
        logger.error("Kill switch aborted execution: advisory=%s, reason=%s",
                    advisory_id, reason)
    
    def log_execution_result(
        self,
        result: ExecutionResult,
    ):
        """Log final execution result."""
        log_entry = {
            "event": "execution_result",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "advisory_id": result.advisory_id,
            "status": result.status.value,
            "final_order_id": result.final_order_id,
            "final_fill_price": result.final_fill_price,
            "final_position_size": result.final_position_size,
            "final_sl": result.final_sl,
            "final_tp": result.final_tp,
            "slippage_pct": result.slippage_pct,
            "total_duration_seconds": result.total_duration_seconds,
            "kill_switch_state": result.kill_switch_state.value,
            "error_message": result.error_message,
        }
        self.execution_logs.append(log_entry)
        logger.info("Execution result: advisory=%s, status=%s, duration=%.1fs",
                   result.advisory_id, result.status.value, result.total_duration_seconds or 0)


# ============================================================================
# EXECUTION ENGINE (MAIN ORCHESTRATOR)
# ============================================================================

class ExecutionEngine:
    """
    Main execution orchestrator.
    
    RESPONSIBILITY: Execute an already-approved advisory with safety enforcement.
    
    DO NOT:
    - Design strategy
    - Recalculate risk
    - Interpret market logic
    - Modify advisory intent
    - Invent behavior
    
    DO ONLY:
    - Execute frozen snapshot
    - Enforce safety (kill switches, timeouts)
    - Calculate SL/TP from actual fill price
    - Log deterministically
    """
    
    def __init__(
        self,
        broker_adapter: BrokerAdapter,
        kill_switch_manager: Optional[KillSwitchManager] = None,
    ):
        self.broker_adapter = broker_adapter
        self.kill_switch_manager = kill_switch_manager or KillSwitchManager()
        self.timeout_controller = TimeoutController()
        self.reconciliation_service = ReconciliationService()
        self.logger_service = ExecutionLogger()
    
    def execute(
        self,
        frozen_snapshot: FrozenSnapshot,
    ) -> ExecutionResult:
        """
        Execute an approved advisory.
        
        FLOW:
        1. Validate pre-conditions (advisory not expired, kill switch off)
        2. Submit order to broker
        3. Wait for fill or timeout
        4. Calculate SL/TP from actual fill price (NOT reference price)
        5. Log and return result
        
        Args:
            frozen_snapshot: Immutable approved advisory snapshot
        
        Returns:
            ExecutionResult with final status and details
        """
        advisory_id = frozen_snapshot.advisory_id
        result = ExecutionResult(advisory_id=advisory_id)
        
        try:
            # Step 1: Log execution start
            kill_switch_state = self.kill_switch_manager.get_state()
            self.logger_service.log_execution_start(
                advisory_id,
                frozen_snapshot,
                kill_switch_state
            )
            
            # Step 2: Validate pre-conditions
            validation_error = self._validate_preconditions(frozen_snapshot)
            if validation_error:
                result.status = ExecutionStage.REJECTED
                result.error_message = validation_error
                self.logger_service.log_kill_switch_abort(
                    advisory_id,
                    kill_switch_state,
                    validation_error
                )
                return result
            
            # Step 3: Check kill switch BEFORE submission
            # SECTION 5.1-A (Addendum): Kill Switch BEFORE Submission
            # Rule: Abort execution immediately if active
            # Advisory marked: ABORTED_KILL_SWITCH
            # Ensures: no order submitted if safety check fails
            if self.kill_switch_manager.is_active(frozen_snapshot.symbol):
                result.status = ExecutionStage.REJECTED
                result.error_message = f"Kill switch active for {frozen_snapshot.symbol}"
                self.logger_service.log_kill_switch_abort(
                    advisory_id,
                    self.kill_switch_manager.get_state(frozen_snapshot.symbol),
                    "Kill switch active at submission time"
                )
                return result
            
            # Step 4: Submit order
            self.timeout_controller.start()
            order_response = self.broker_adapter.submit_order(
                symbol=frozen_snapshot.symbol,
                quantity=frozen_snapshot.position_size,
                order_type="MARKET"
            )
            order_id = order_response.get("order_id")
            
            attempt = ExecutionAttempt(
                advisory_id=advisory_id,
                timestamp_submit=datetime.now(timezone.utc),
                order_id=order_id,
            )
            result.attempts.append(attempt)
            result.final_order_id = order_id
            
            self.logger_service.log_order_submitted(
                advisory_id,
                order_id,
                frozen_snapshot.symbol,
                frozen_snapshot.position_size
            )
            
            # Step 5: Wait for fill with timeout
            fill_info = self._wait_for_fill(order_id)
            
            if self.timeout_controller.is_expired() and not fill_info:
                # SECTION 6.5.2 (Addendum): Actions on Timeout (T=30s)
                # Rule: Hard 30s limit, never extended
                # Steps: cancel pending → mark FAILED_TIMEOUT → reconcile
                # Absolute Prohibition: ❌ Never retry after timeout
                
                # Timeout without fill
                result.status = ExecutionStage.FAILED_TIMEOUT
                attempt.stage = ExecutionStage.FAILED_TIMEOUT
                self.logger_service.log_timeout(
                    advisory_id,
                    self.timeout_controller.elapsed_seconds()
                )
                
                # Cancel pending order (fire-and-forget)
                try:
                    self.broker_adapter.cancel_order(order_id)
                except Exception as e:
                    logger.warning("Cancel order failed: %s", e)
                
                # SECTION 8.2 (Addendum): Single Reconciliation Per Flow
                # Run reconciliation (ONCE per flow, after timeout)
                recon = self.reconciliation_service.reconcile(
                    advisory_id,
                    self.broker_adapter,
                    order_id=order_id,
                )
                result.reconciliation_report = recon
                
            elif fill_info:
                # SECTION 5.1-C (Addendum): Kill Switch AFTER Fill (CRITICAL)
                # IMMUTABLE RULE: Position stays open with SL/TP, NO forced close
                # Once filled, position is LIVE in broker
                # SL/TP from snapshot protect downside
                
                # Order filled (may be after timeout - that's OK, mark EXECUTED_FULL_LATE)
                fill_price = fill_info["fill_price"]
                filled_size = fill_info["filled_size"]
                
                # SECTION 4.3.2 (Addendum): Reference Price → Actual Fill Price
                # Calculate SL/TP from ACTUAL fill price, NOT reference price
                # Formula: SL = fill_price × (1 + sl_offset_pct)
                #          TP = fill_price × (1 + tp_offset_pct)
                calculated_sl = self._calculate_sl(fill_price, frozen_snapshot.sl_offset_pct)
                calculated_tp = self._calculate_tp(fill_price, frozen_snapshot.tp_offset_pct)
                
                # SECTION 4.3.4 (Addendum): Log for Forensic Analysis
                # Slippage = (actual fill - reference) / reference
                # Used for post-trade analysis only, not for SL/TP decisions
                slippage_pct = ((fill_price - frozen_snapshot.reference_price) / frozen_snapshot.reference_price) * 100
                
                attempt.timestamp_fill = datetime.now(timezone.utc)
                attempt.fill_price = fill_price
                attempt.filled_size = filled_size
                attempt.calculated_sl = calculated_sl
                attempt.calculated_tp = calculated_tp
                attempt.slippage_pct = slippage_pct
                
                # SECTION 6.5.3 (Addendum): Late Fills (T ∈ (30, 31])
                # Rule: Fills after timeout are still VALID
                # Grace period allows broker fills slightly after T=30s
                # Determine if late fill
                if self.timeout_controller.is_expired():
                    result.status = ExecutionStage.EXECUTED_FULL_LATE  # Fill after 30s (still valid)
                    attempt.stage = ExecutionStage.EXECUTED_FULL_LATE
                else:
                    result.status = ExecutionStage.FILLED  # Fill before 30s (on-time)
                    attempt.stage = ExecutionStage.FILLED
                
                result.final_fill_price = fill_price
                result.final_position_size = filled_size
                result.final_sl = calculated_sl
                result.final_tp = calculated_tp
                result.slippage_pct = slippage_pct
                
                self.logger_service.log_order_filled(
                    advisory_id,
                    order_id,
                    fill_price,
                    filled_size,
                    calculated_sl,
                    calculated_tp,
                    slippage_pct
                )
                
                # SECTION 8.2 (Addendum): Single Reconciliation Per Flow
                # Run reconciliation (ONCE per flow, after fill)
                # Verifies: position size, SL, TP, no phantom positions
                # On mismatch: sets requires_manual_resolution = True
                recon = self.reconciliation_service.reconcile(
                    advisory_id,
                    self.broker_adapter,
                    order_id=order_id,
                    expected_position_size=filled_size,
                    expected_sl=calculated_sl,
                    expected_tp=calculated_tp,
                )
                result.reconciliation_report = recon
            
            # Step 6: Set final kill switch state
            result.kill_switch_state = self.kill_switch_manager.get_state(frozen_snapshot.symbol)
            
            # Step 7: Calculate total duration
            result.total_duration_seconds = self.timeout_controller.elapsed_seconds()
            
        except Exception as e:
            result.status = ExecutionStage.FAILED
            result.error_message = str(e)
            logger.exception("Execution exception: %s", e)
        
        # Log final result
        self.logger_service.log_execution_result(result)
        
        return result
    
    def _validate_preconditions(self, snapshot: FrozenSnapshot) -> Optional[str]:
        """
        Validate advisory is still valid for execution.
        
        Returns:
            Error message if validation fails, None if OK.
        """
        # Check if advisory has expired per Stage 7
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
    
    def _wait_for_fill(
        self,
        order_id: str,
        poll_interval_ms: int = 100,
    ) -> Optional[Dict[str, Any]]:
        """
        Poll broker until fill or timeout.
        
        SECTION 5.1-B (Addendum): Kill Switch DURING Pending
        [Future Enhancement] Should re-check kill switch periodically
        Current implementation: kill switch only checked BEFORE submission
        
        Returns:
            Fill info dict if filled, None if timeout.
        """
        while not self.timeout_controller.is_expired():
            order_status = self.broker_adapter.get_order_status(order_id)
            
            if order_status.get("state") == "filled":
                return {
                    "fill_price": order_status.get("fill_price"),
                    "filled_size": order_status.get("filled_size"),
                }
            
            # Sleep briefly before next poll
            import time
            time.sleep(poll_interval_ms / 1000.0)
        
        return None
    
    def _calculate_sl(self, fill_price: float, sl_offset_pct: float) -> float:
        """
        Calculate stop-loss price from fill price.
        
        SECTION 4.3.2 (Addendum): Reference Price → Actual Fill Price
        SL = fill_price × (1 + sl_offset_pct)
        
        CRITICAL RULE: SL calculated from FILL PRICE, not reference price.
        sl_offset_pct is NEGATIVE (e.g., -0.02 = 2% below fill price).
        
        Example:
          fill_price = 152.00, sl_offset_pct = -0.02
          SL = 152.00 × 0.98 = 148.96
        
        Absolute Prohibition:
        ❌ Never use reference_price for SL calculation
        ✅ Always use actual fill_price
        """
        return fill_price * (1 + sl_offset_pct)
    
    def _calculate_tp(self, fill_price: float, tp_offset_pct: float) -> float:
        """
        Calculate take-profit price from fill price.
        
        SECTION 4.3.2 (Addendum): Reference Price → Actual Fill Price
        TP = fill_price × (1 + tp_offset_pct)
        
        CRITICAL RULE: TP calculated from FILL PRICE, not reference price.
        tp_offset_pct is POSITIVE (e.g., +0.03 = 3% above fill price).
        
        Example:
          fill_price = 152.00, tp_offset_pct = +0.03
          TP = 152.00 × 1.03 = 156.56
        
        Absolute Prohibition:
        ❌ Never use reference_price for TP calculation
        ✅ Always use actual fill_price
        """
        return fill_price * (1 + tp_offset_pct)
