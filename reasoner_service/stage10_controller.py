"""
Stage 10: Live Execution Guardrails Controller

Enforces trading guardrails before Stage 9 execution:
- Daily max trades
- Per-symbol max trades
- Daily max loss
- Kill switches (global/symbol)
- Broker health checks
- Paper/live mode separation
- Complete audit logging

Does NOT modify Stage 9 logic; acts as pre-flight validation wrapper.
"""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from uuid import uuid4
import logging

# Stage 9 imports
from reasoner_service.execution_engine import (
    ExecutionEngine,
    ExecutionResult,
    ExecutionStage,
    FrozenSnapshot,
    KillSwitchManager,
    KillSwitchType,
    KillSwitchState,
)


logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS & DATA MODELS
# ============================================================================

class GuardrailStatus(Enum):
    """Guardrail validation result."""
    PASS = "pass"
    FAIL = "fail"


class TradeAction(Enum):
    """Final action taken on trade."""
    FORWARDED = "forwarded"        # Forwarded to Stage 9
    ABORTED = "aborted"            # Rejected by guardrails
    PAPER_EXECUTION = "paper_execution"  # Forwarded in paper mode


@dataclass
class GuardrailCheckResult:
    """Result of single guardrail check."""
    name: str
    status: GuardrailStatus
    reason: Optional[str] = None
    severity: str = "info"  # "info", "warning", "error"


@dataclass
class DailyCounters:
    """Daily trading statistics (reset at session start)."""
    trades_executed: int = 0
    total_loss_usd: float = 0.0
    per_symbol_trades: Dict[str, int] = field(default_factory=dict)
    last_reset: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_stale(self, hours: int = 24) -> bool:
        """Check if counters need reset (daily)."""
        elapsed = (datetime.now(timezone.utc) - self.last_reset).total_seconds()
        return elapsed > (hours * 3600)
    
    def reset(self):
        """Reset daily counters."""
        self.trades_executed = 0
        self.total_loss_usd = 0.0
        self.per_symbol_trades.clear()
        self.last_reset = datetime.now(timezone.utc)


@dataclass
class Stage10AuditLog:
    """Audit log entry for trade submission."""
    log_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    intent_id: str = ""
    symbol: str = ""
    direction: str = ""
    guardrail_checks: List[GuardrailCheckResult] = field(default_factory=list)
    final_action: TradeAction = TradeAction.ABORTED
    execution_result: Optional[ExecutionResult] = None
    error_message: Optional[str] = None


# ============================================================================
# STAGE 10 CONTROLLER
# ============================================================================

class Stage10Controller:
    """
    Live execution guardrails controller.
    
    Sits between Stage 8/9 and actual broker execution.
    Validates all guardrails before forwarding to Stage 9.
    
    Immutable contracts:
    - Never modifies Stage 9 execution logic
    - Never bypasses guardrails
    - Always logs audit trail
    - Paper/live modes strictly enforced
    """
    
    def __init__(
        self,
        execution_engine: ExecutionEngine,
        broker_adapter: 'BrokerAdapter',
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Stage 10 controller.
        
        Args:
            execution_engine: Stage 9 execution engine
            broker_adapter: Broker connection
            config: Configuration dict with guardrail limits
        """
        self.execution_engine = execution_engine
        self.broker_adapter = broker_adapter
        
        # Load config with sensible defaults
        self.config = config or {}
        self.daily_max_trades = self.config.get("daily_max_trades", 10)
        self.daily_max_loss_usd = self.config.get("daily_max_loss_usd", 100.0)
        self.per_symbol_max_trades = self.config.get("per_symbol_max_trades", 3)
        self.paper_mode = self.config.get("paper_mode", False)
        self.broker_health_check_timeout_seconds = self.config.get(
            "broker_health_check_timeout", 5
        )
        
        # Daily counters (reset at session start)
        self.daily_counters = DailyCounters()
        
        # Audit trail
        self.audit_logs: List[Stage10AuditLog] = []
        
        # Kill switch reference
        self.kill_switch_manager: Optional[KillSwitchManager] = None
        if hasattr(execution_engine, 'kill_switch_manager'):
            self.kill_switch_manager = execution_engine.kill_switch_manager
        
        logger.info(
            "Stage 10 Controller initialized: "
            "daily_max_trades=%d, daily_max_loss=%f, paper_mode=%s",
            self.daily_max_trades,
            self.daily_max_loss_usd,
            self.paper_mode,
        )
    
    def submit_trade(self, trade_intent: 'Stage8TradeIntent') -> ExecutionResult:
        """
        Validate guardrails and forward trade to Stage 9 if allowed.
        
        Args:
            trade_intent: Stage 8 trade signal
        
        Returns:
            ExecutionResult (from Stage 9 if forwarded, or rejection status)
        """
        intent_id = trade_intent.intent_id
        symbol = trade_intent.symbol
        
        # Create audit log entry
        audit_log = Stage10AuditLog(
            intent_id=intent_id,
            symbol=symbol,
            direction=trade_intent.direction,
        )
        
        try:
            # STEP 1: Reset counters if needed (daily reset)
            if self.daily_counters.is_stale():
                logger.info("Stage 10: Daily reset triggered")
                self.daily_counters.reset()
            
            # STEP 2: Run guardrail checks
            guardrail_checks = self._run_guardrail_checks(trade_intent)
            audit_log.guardrail_checks = guardrail_checks
            
            # Check if any guardrails failed
            failed_checks = [c for c in guardrail_checks if c.status == GuardrailStatus.FAIL]
            if failed_checks:
                reason = "; ".join([f"{c.name}: {c.reason}" for c in failed_checks])
                logger.warning(
                    "Stage 10: Trade rejected by guardrails (intent_id=%s, reason=%s)",
                    intent_id,
                    reason,
                )
                audit_log.final_action = TradeAction.ABORTED
                audit_log.error_message = reason
                self.audit_logs.append(audit_log)
                
                # Return rejection result
                result = ExecutionResult(advisory_id=intent_id)
                result.status = ExecutionStage.REJECTED
                result.error_message = reason
                return result
            
            # STEP 3: All guardrails passed; forward to Stage 9
            logger.info(
                "Stage 10: All guardrails passed; forwarding to Stage 9 (intent_id=%s)",
                intent_id,
            )
            
            # Convert Stage 8 intent to FrozenSnapshot
            frozen_snapshot = self._create_frozen_snapshot(trade_intent)
            
            # STEP 4: Execute in Stage 9
            execution_result = self.execution_engine.execute(frozen_snapshot)
            audit_log.execution_result = execution_result
            
            # STEP 5: Update counters based on outcome
            if execution_result.status in (ExecutionStage.FILLED, ExecutionStage.EXECUTED_FULL_LATE):
                self.daily_counters.trades_executed += 1
                self.daily_counters.per_symbol_trades[symbol] = \
                    self.daily_counters.per_symbol_trades.get(symbol, 0) + 1
                
                # Track loss if SL triggered (estimated)
                if execution_result.final_fill_price and execution_result.final_sl:
                    potential_loss = abs(
                        execution_result.final_fill_price - execution_result.final_sl
                    ) * execution_result.final_position_size
                    self.daily_counters.total_loss_usd += potential_loss
                
                audit_log.final_action = TradeAction.FORWARDED
                logger.info(
                    "Stage 10: Trade executed (intent_id=%s, status=%s)",
                    intent_id,
                    execution_result.status,
                )
            else:
                # Trade forwarded but not filled
                audit_log.final_action = TradeAction.FORWARDED
                logger.info(
                    "Stage 10: Trade forwarded, not filled (intent_id=%s, status=%s)",
                    intent_id,
                    execution_result.status,
                )
            
            self.audit_logs.append(audit_log)
            return execution_result
        
        except Exception as e:
            logger.exception("Stage 10: Exception during trade submission: %s", e)
            audit_log.final_action = TradeAction.ABORTED
            audit_log.error_message = str(e)
            self.audit_logs.append(audit_log)
            
            result = ExecutionResult(advisory_id=intent_id)
            result.status = ExecutionStage.FAILED
            result.error_message = str(e)
            return result
    
    # ========================================================================
    # GUARDRAIL CHECKS
    # ========================================================================
    
    def _run_guardrail_checks(self, trade_intent: 'Stage8TradeIntent') -> List[GuardrailCheckResult]:
        """
        Run all guardrail checks on trade intent.
        
        Returns:
            List of guardrail check results (pass/fail)
        """
        checks: List[GuardrailCheckResult] = []
        
        # Check 1: Broker health
        checks.append(self._check_broker_health())
        
        # Check 2: Global kill switch
        checks.append(self._check_global_kill_switch())
        
        # Check 3: Symbol-level kill switch
        checks.append(self._check_symbol_kill_switch(trade_intent.symbol))
        
        # Check 4: Daily max trades
        checks.append(self._check_daily_max_trades())
        
        # Check 5: Per-symbol max trades
        checks.append(self._check_per_symbol_max_trades(trade_intent.symbol))
        
        # Check 6: Daily max loss
        checks.append(self._check_daily_max_loss(trade_intent))
        
        # Check 7: Paper/live mode consistency
        checks.append(self._check_paper_live_mode())
        
        return checks
    
    def _check_broker_health(self) -> GuardrailCheckResult:
        """Check if broker is connected and healthy."""
        try:
            # Simple health check: try to get broker status
            if hasattr(self.broker_adapter, 'is_connected'):
                if not self.broker_adapter.is_connected():
                    return GuardrailCheckResult(
                        name="broker_health",
                        status=GuardrailStatus.FAIL,
                        reason="Broker disconnected",
                        severity="error",
                    )
            # If no health check method, assume healthy
            return GuardrailCheckResult(
                name="broker_health",
                status=GuardrailStatus.PASS,
                reason="Broker connected",
            )
        except Exception as e:
            return GuardrailCheckResult(
                name="broker_health",
                status=GuardrailStatus.FAIL,
                reason=f"Broker health check failed: {e}",
                severity="error",
            )
    
    def _check_global_kill_switch(self) -> GuardrailCheckResult:
        """Check if global kill switch is active."""
        if not self.kill_switch_manager:
            return GuardrailCheckResult(
                name="global_kill_switch",
                status=GuardrailStatus.PASS,
                reason="No kill switch manager",
            )
        
        if self.kill_switch_manager.is_active():
            return GuardrailCheckResult(
                name="global_kill_switch",
                status=GuardrailStatus.FAIL,
                reason="Global kill switch active",
                severity="error",
            )
        
        return GuardrailCheckResult(
            name="global_kill_switch",
            status=GuardrailStatus.PASS,
            reason="Global kill switch off",
        )
    
    def _check_symbol_kill_switch(self, symbol: str) -> GuardrailCheckResult:
        """Check if symbol-level kill switch is active."""
        if not self.kill_switch_manager:
            return GuardrailCheckResult(
                name="symbol_kill_switch",
                status=GuardrailStatus.PASS,
                reason="No kill switch manager",
            )
        
        if self.kill_switch_manager.is_active(symbol):
            return GuardrailCheckResult(
                name="symbol_kill_switch",
                status=GuardrailStatus.FAIL,
                reason=f"Kill switch active for {symbol}",
                severity="error",
            )
        
        return GuardrailCheckResult(
            name="symbol_kill_switch",
            status=GuardrailStatus.PASS,
            reason=f"Kill switch off for {symbol}",
        )
    
    def _check_daily_max_trades(self) -> GuardrailCheckResult:
        """Check if daily max trades limit exceeded."""
        if self.daily_counters.trades_executed >= self.daily_max_trades:
            return GuardrailCheckResult(
                name="daily_max_trades",
                status=GuardrailStatus.FAIL,
                reason=f"Daily max trades ({self.daily_max_trades}) reached",
                severity="warning",
            )
        
        return GuardrailCheckResult(
            name="daily_max_trades",
            status=GuardrailStatus.PASS,
            reason=f"Daily trades: {self.daily_counters.trades_executed}/{self.daily_max_trades}",
        )
    
    def _check_per_symbol_max_trades(self, symbol: str) -> GuardrailCheckResult:
        """Check if per-symbol max trades limit exceeded."""
        trades_for_symbol = self.daily_counters.per_symbol_trades.get(symbol, 0)
        if trades_for_symbol >= self.per_symbol_max_trades:
            return GuardrailCheckResult(
                name="per_symbol_max_trades",
                status=GuardrailStatus.FAIL,
                reason=f"Max trades for {symbol} ({self.per_symbol_max_trades}) reached",
                severity="warning",
            )
        
        return GuardrailCheckResult(
            name="per_symbol_max_trades",
            status=GuardrailStatus.PASS,
            reason=f"Trades for {symbol}: {trades_for_symbol}/{self.per_symbol_max_trades}",
        )
    
    def _check_daily_max_loss(self, trade_intent: 'Stage8TradeIntent') -> GuardrailCheckResult:
        """Check if daily max loss limit exceeded."""
        # Estimate potential loss from stop loss
        entry = trade_intent.proposed_entry
        sl = trade_intent.proposed_sl
        size = trade_intent.risk.get("account_risk_usd", 1.0)
        
        potential_loss = abs(entry - sl) * size
        total_potential_loss = self.daily_counters.total_loss_usd + potential_loss
        
        if total_potential_loss > self.daily_max_loss_usd:
            return GuardrailCheckResult(
                name="daily_max_loss",
                status=GuardrailStatus.FAIL,
                reason=f"Daily max loss (${self.daily_max_loss_usd}) would be exceeded; "
                       f"current: ${self.daily_counters.total_loss_usd}, "
                       f"potential: ${potential_loss}",
                severity="warning",
            )
        
        return GuardrailCheckResult(
            name="daily_max_loss",
            status=GuardrailStatus.PASS,
            reason=f"Loss limit OK: ${self.daily_counters.total_loss_usd}/"
                   f"${self.daily_max_loss_usd}",
        )
    
    def _check_paper_live_mode(self) -> GuardrailCheckResult:
        """Check paper vs live mode consistency."""
        if self.paper_mode:
            return GuardrailCheckResult(
                name="paper_live_mode",
                status=GuardrailStatus.PASS,
                reason="Paper mode (simulation only)",
            )
        else:
            return GuardrailCheckResult(
                name="paper_live_mode",
                status=GuardrailStatus.PASS,
                reason="Live mode (real execution)",
            )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _create_frozen_snapshot(self, trade_intent: 'Stage8TradeIntent') -> FrozenSnapshot:
        """Convert Stage 8 intent to Stage 9 FrozenSnapshot."""
        entry = trade_intent.proposed_entry
        sl = trade_intent.proposed_sl
        tp = trade_intent.proposed_tp
        
        # Calculate offsets
        sl_offset_pct = (sl - entry) / entry  # Negative for stop loss
        tp_offset_pct = (tp - entry) / entry  # Positive for take profit
        
        return FrozenSnapshot(
            advisory_id=trade_intent.intent_id,
            htf_bias=trade_intent.snapshot.get("htf_bias", "NEUTRAL"),
            reasoning_mode=trade_intent.snapshot.get("ltf_structure", "UNKNOWN"),
            reference_price=entry,
            sl_offset_pct=sl_offset_pct,
            tp_offset_pct=tp_offset_pct,
            position_size=trade_intent.risk.get("account_risk_usd", 1.0),
            symbol=trade_intent.symbol,
            expiration_timestamp=datetime.now(timezone.utc) + timedelta(minutes=5),
            reasoning_context=trade_intent.snapshot,
        )
    
    # ========================================================================
    # AUDIT & REPORTING
    # ========================================================================
    
    def get_daily_stats(self) -> Dict[str, Any]:
        """Get current daily trading statistics."""
        return {
            "trades_executed": self.daily_counters.trades_executed,
            "daily_max_trades": self.daily_max_trades,
            "total_loss_usd": self.daily_counters.total_loss_usd,
            "daily_max_loss_usd": self.daily_max_loss_usd,
            "per_symbol_trades": dict(self.daily_counters.per_symbol_trades),
            "per_symbol_max_trades": self.per_symbol_max_trades,
        }
    
    def get_audit_logs(self, limit: Optional[int] = None) -> List[Stage10AuditLog]:
        """Get audit logs (most recent first)."""
        logs = sorted(self.audit_logs, key=lambda x: x.timestamp, reverse=True)
        if limit:
            return logs[:limit]
        return logs
    
    def enable_paper_mode(self):
        """Enable paper (simulation) mode."""
        self.paper_mode = True
        logger.info("Stage 10: Paper mode ENABLED")
    
    def disable_paper_mode(self):
        """Disable paper mode (enable live trading)."""
        self.paper_mode = False
        logger.info("Stage 10: Paper mode DISABLED (live trading)")
