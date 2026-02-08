"""
Execution Boundary: Kill Switch Controller

CRITICAL PRINCIPLE:
"This layer does NOT infer intent from shadow-mode outputs."

Kill switch management is PURELY MECHANICAL:
- Manual override ALWAYS works (requires explicit human action)
- Circuit breaker is AUTOMATED but deterministic (threshold-based)
- Timeouts are DETERMINISTIC (elapsed time-based)
- NO INFERENCE from shadow-mode metrics
- NO AUTO-APPROVAL or AUTO-EXECUTION

This controller manages state transitions for kill switches ONLY.
It does NOT implement execution, decision logic, or trading operations.

NO IMPORTS from shadow-mode modules.
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timezone, timedelta
from execution_boundary.execution_models import KillSwitchState, KillSwitchType


class KillSwitchController:
    """
    Manages kill switch state for emergency halting and manual override.

    CRITICAL:
    - Manual kill switch is ALWAYS respected (requires explicit human action)
    - Circuit breaker engages on explicitly defined catastrophic conditions
    - Timeouts are deterministic (elapsed time)
    - Default is OFF (absence of activation means "proceed")

    This is a STATE MACHINE, not a decision engine.
    """

    def __init__(self):
        """Initialize kill switch controller with default (off) state."""
        self.state = KillSwitchState()
        self._history: List[Dict[str, Any]] = []
        self._log_state_change("INIT", "Controller initialized")

    def activate_manual_kill(self, activated_by: str, reason: str) -> bool:
        """
        Activate manual kill switch (HIGHEST PRIORITY).

        This REQUIRES explicit human action. No inference. No automation.

        Args:
            activated_by: Human identifier (username, employee ID)
            reason: Human explanation for activation

        Returns:
            True if activation successful
        """
        if not activated_by or not reason:
            return False

        self.state.activate_manual_kill(activated_by, reason)
        self._log_state_change("MANUAL_KILL_ACTIVATED", reason, activated_by)
        return True

    def deactivate_manual_kill(self, deactivated_by: str, reason: str) -> bool:
        """
        Deactivate manual kill switch.

        This REQUIRES explicit human action to resume operations.

        Args:
            deactivated_by: Human identifier
            reason: Human explanation for deactivation

        Returns:
            True if deactivation successful
        """
        if not deactivated_by or not reason:
            return False

        self.state.deactivate_manual_kill()
        self._log_state_change("MANUAL_KILL_DEACTIVATED", reason, deactivated_by)
        return True

    def activate_circuit_breaker(self, reason: str) -> bool:
        """
        Activate circuit breaker for catastrophic system state.

        This MUST only be called when system has detected a critical condition
        that requires immediate halt. Examples:
        - Uncaught exception in core service
        - Database connection loss
        - Broker API failure
        - Invalid state detected

        Args:
            reason: Explanation for circuit breaker engagement

        Returns:
            True if activation successful
        """
        if not reason:
            return False

        self.state.activate_circuit_breaker(reason)
        self._log_state_change(
            "CIRCUIT_BREAKER_ACTIVATED",
            reason,
            "system",
            severity="CRITICAL",
        )
        return True

    def deactivate_circuit_breaker(self, deactivated_by: str, reason: str) -> bool:
        """
        Deactivate circuit breaker.

        This REQUIRES explicit human action after circuit breaker is engaged.
        System will NOT automatically resume.

        Args:
            deactivated_by: Human identifier
            reason: Human explanation for deactivation

        Returns:
            True if deactivation successful
        """
        if not deactivated_by or not reason:
            return False

        self.state.deactivate_circuit_breaker()
        self._log_state_change(
            "CIRCUIT_BREAKER_DEACTIVATED", reason, deactivated_by
        )
        return True

    def activate_timeout(
        self, reason: str, duration_seconds: int = 300
    ) -> bool:
        """
        Activate timeout halt (deterministic timing-based halt).

        This is used to halt execution after a timeout period has elapsed.
        It does NOT infer state from shadow-mode outputs.

        Args:
            reason: Explanation for timeout activation
            duration_seconds: Duration of timeout (default 5 minutes)

        Returns:
            True if activation successful
        """
        if not reason or duration_seconds <= 0:
            return False

        self.state.activate_timeout(reason, duration_seconds)
        self._log_state_change(
            "TIMEOUT_ACTIVATED",
            f"{reason} (duration: {duration_seconds}s)",
            "system",
            severity="WARNING",
        )
        return True

    def deactivate_timeout(self, deactivated_by: str, reason: str) -> bool:
        """
        Deactivate timeout halt.

        Args:
            deactivated_by: Human identifier
            reason: Human explanation for deactivation

        Returns:
            True if deactivation successful
        """
        if not deactivated_by or not reason:
            return False

        self.state.deactivate_timeout()
        self._log_state_change("TIMEOUT_DEACTIVATED", reason, deactivated_by)
        return True

    def is_halted(self) -> bool:
        """
        Check if system is halted (ANY kill switch is active).

        Returns:
            True if manual kill, circuit breaker, or timeout is active
        """
        return self.state.is_halted

    def get_halt_reason(self) -> Optional[str]:
        """
        Get reason for current halt (if any).

        If multiple kill switches are active, manual kill takes priority.

        Returns:
            Reason string if halted, None if not halted
        """
        if self.state.manual_kill_active:
            return f"MANUAL: {self.state.manual_kill_reason}"
        if self.state.circuit_breaker_active:
            return f"CIRCUIT_BREAKER: {self.state.circuit_breaker_reason}"
        if self.state.timeout_active:
            return f"TIMEOUT: {self.state.timeout_duration_seconds}s"
        return None

    def check_timeout_expired(self) -> bool:
        """
        Check if timeout period has elapsed.

        This is a DETERMINISTIC check based on elapsed wall-clock time.
        No inference. No state guessing.

        Returns:
            True if timeout was active and duration has elapsed
        """
        if not self.state.timeout_active or not self.state.timeout_triggered_at:
            return False

        elapsed = datetime.now(timezone.utc) - self.state.timeout_triggered_at
        duration = timedelta(seconds=self.state.timeout_duration_seconds)

        return elapsed >= duration

    def get_state(self) -> Dict[str, Any]:
        """
        Get current kill switch state as dictionary.

        Returns:
            Dict representation of KillSwitchState
        """
        return self.state.to_dict()

    def get_history(self) -> List[Dict[str, Any]]:
        """
        Get complete history of kill switch state changes.

        This is append-only: changes are logged but never modified.

        Returns:
            List of state change records (oldest first)
        """
        return self._history.copy()

    def _log_state_change(
        self,
        event_type: str,
        reason: str,
        actor: str = "system",
        severity: str = "INFO",
    ):
        """
        Log a kill switch state change to history.

        Args:
            event_type: Type of state change event
            reason: Human explanation
            actor: Who/what triggered the change
            severity: CRITICAL, WARNING, or INFO
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "reason": reason,
            "actor": actor,
            "severity": severity,
            "state_snapshot": self.get_state(),
        }
        self._history.append(record)
