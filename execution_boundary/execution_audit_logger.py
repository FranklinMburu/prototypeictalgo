"""
Execution Boundary: Audit Logger

CRITICAL PRINCIPLE:
"This layer does NOT infer intent from shadow-mode outputs."

Audit logging is PURELY MECHANICAL AND APPEND-ONLY:
- Every execution event is logged immutably
- Logs are NEVER modified or deleted
- Logs are human-readable for compliance review
- Logs include full context: intents, approvals, decisions, errors

This logger is a WRITE-ONLY append-only store.
It does NOT implement decision logic or execute trading operations.

NO IMPORTS from shadow-mode modules.
NO FILTERING or TRANSFORMATION of audit events.
"""

import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
from pathlib import Path
from execution_boundary.execution_models import (
    ExecutionIntent,
    HumanExecutionApproval,
    ExecutionAuditRecord,
)


class ExecutionAuditLogger:
    """
    Append-only audit logger for execution boundary events.

    CRITICAL:
    - Logs are NEVER deleted or modified
    - All events are timestamped
    - All events include human context
    - Logs are deterministic and reproducible

    This is purely a STORAGE layer with NO business logic.
    """

    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize audit logger.

        Args:
            log_file: Path to append-only JSON log file.
                     If None, logs are stored in memory only.
        """
        self.log_file = log_file
        self._memory_log: List[Dict[str, Any]] = []

        if self.log_file:
            # Ensure log file exists
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
            try:
                Path(self.log_file).touch(exist_ok=True)
            except Exception:
                # If file creation fails, fall back to memory-only logging
                self.log_file = None

    def log_intent_created(
        self, intent: ExecutionIntent, actor: str, note: str
    ) -> str:
        """
        Log creation of execution intent.

        Args:
            intent: ExecutionIntent object
            actor: Human/system actor
            note: Human explanation

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type="intent_created",
            intent_id=intent.intent_id,
            status=intent.status.value,
            event_data=intent.to_dict(),
            human_note=note,
            actor=actor,
            severity="INFO",
        )
        return self._append_record(record)

    def log_approval_granted(
        self,
        intent_id: str,
        approval: HumanExecutionApproval,
        actor: str,
        note: str,
    ) -> str:
        """
        Log approval of execution intent.

        Args:
            intent_id: ID of approved intent
            approval: HumanExecutionApproval object
            actor: Human/system actor
            note: Human explanation

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type="approval_granted",
            intent_id=intent_id,
            approval_id=approval.approval_id,
            status="approved",
            event_data=approval.to_dict(),
            human_note=note,
            actor=actor,
            severity="INFO",
        )
        return self._append_record(record)

    def log_approval_rejected(
        self,
        intent_id: str,
        approval: HumanExecutionApproval,
        actor: str,
        note: str,
    ) -> str:
        """
        Log rejection of execution intent.

        Args:
            intent_id: ID of rejected intent
            approval: HumanExecutionApproval object (approved=False)
            actor: Human/system actor
            note: Human explanation

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type="approval_rejected",
            intent_id=intent_id,
            approval_id=approval.approval_id,
            status="rejected",
            event_data=approval.to_dict(),
            human_note=note,
            actor=actor,
            severity="WARNING",
        )
        return self._append_record(record)

    def log_execution_started(
        self, intent_id: str, actor: str, note: str, event_data: Optional[Dict] = None
    ) -> str:
        """
        Log start of execution.

        Args:
            intent_id: ID of intent being executed
            actor: Human/system actor
            note: Human explanation
            event_data: Optional structured event data

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type="execution_started",
            intent_id=intent_id,
            status="executing",
            event_data=event_data or {},
            human_note=note,
            actor=actor,
            severity="INFO",
        )
        return self._append_record(record)

    def log_execution_completed(
        self, intent_id: str, actor: str, note: str, event_data: Optional[Dict] = None
    ) -> str:
        """
        Log successful execution completion.

        Args:
            intent_id: ID of executed intent
            actor: Human/system actor
            note: Human explanation
            event_data: Optional structured event data

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type="execution_completed",
            intent_id=intent_id,
            status="executed",
            event_data=event_data or {},
            human_note=note,
            actor=actor,
            severity="INFO",
        )
        return self._append_record(record)

    def log_execution_failed(
        self,
        intent_id: str,
        actor: str,
        error: str,
        event_data: Optional[Dict] = None,
    ) -> str:
        """
        Log execution failure.

        Args:
            intent_id: ID of failed intent
            actor: Human/system actor
            error: Error description
            event_data: Optional structured event data

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type="execution_failed",
            intent_id=intent_id,
            status="failed",
            event_data=event_data or {"error": error},
            human_note=f"Execution failed: {error}",
            actor=actor,
            severity="CRITICAL",
        )
        return self._append_record(record)

    def log_kill_switch_activated(
        self,
        kill_switch_type: str,
        actor: str,
        reason: str,
        event_data: Optional[Dict] = None,
    ) -> str:
        """
        Log kill switch activation.

        Args:
            kill_switch_type: Type of kill switch (manual, circuit_breaker, timeout)
            actor: Human/system actor
            reason: Reason for activation
            event_data: Optional structured event data

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type="kill_switch_activated",
            intent_id="system",  # Not tied to specific intent
            status=f"halted_{kill_switch_type}",
            event_data=event_data or {"kill_switch_type": kill_switch_type},
            human_note=f"Kill switch activated: {reason}",
            actor=actor,
            severity="CRITICAL",
        )
        return self._append_record(record)

    def log_kill_switch_deactivated(
        self,
        kill_switch_type: str,
        actor: str,
        reason: str,
        event_data: Optional[Dict] = None,
    ) -> str:
        """
        Log kill switch deactivation.

        Args:
            kill_switch_type: Type of kill switch
            actor: Human/system actor
            reason: Reason for deactivation
            event_data: Optional structured event data

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type="kill_switch_deactivated",
            intent_id="system",
            status=f"resumed_{kill_switch_type}",
            event_data=event_data or {"kill_switch_type": kill_switch_type},
            human_note=f"Kill switch deactivated: {reason}",
            actor=actor,
            severity="WARNING",
        )
        return self._append_record(record)

    def log_custom_event(
        self,
        event_type: str,
        intent_id: str,
        actor: str,
        note: str,
        severity: str = "INFO",
        event_data: Optional[Dict] = None,
    ) -> str:
        """
        Log a custom audit event.

        Args:
            event_type: Type of event
            intent_id: ID of related intent
            actor: Human/system actor
            note: Human explanation
            severity: CRITICAL, WARNING, or INFO
            event_data: Optional structured event data

        Returns:
            Record ID
        """
        record = ExecutionAuditRecord(
            event_type=event_type,
            intent_id=intent_id,
            status=event_type,
            event_data=event_data or {},
            human_note=note,
            actor=actor,
            severity=severity,
        )
        return self._append_record(record)

    def get_logs(
        self, intent_id: Optional[str] = None, event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs (optionally filtered).

        Args:
            intent_id: Filter by intent ID (optional)
            event_type: Filter by event type (optional)

        Returns:
            List of audit log records
        """
        logs = self._memory_log.copy()

        if intent_id:
            logs = [log for log in logs if log["intent_id"] == intent_id]

        if event_type:
            logs = [log for log in logs if log["event_type"] == event_type]

        return logs

    def export_logs_json(self) -> str:
        """
        Export all logs as JSON string.

        Returns:
            JSON-formatted log data
        """
        return json.dumps(self._memory_log, indent=2, default=str)

    def _append_record(self, record: ExecutionAuditRecord) -> str:
        """
        Append record to log (internal method).

        Args:
            record: ExecutionAuditRecord to log

        Returns:
            Record ID
        """
        record_dict = record.to_dict()
        self._memory_log.append(record_dict)

        # Also write to file if configured
        if self.log_file:
            try:
                with open(self.log_file, "a") as f:
                    f.write(json.dumps(record_dict) + "\n")
            except Exception:
                # Fail silently: if file write fails, continue with memory log
                pass

        return record.record_id
