"""
Execution Boundary: Safety Guards

CRITICAL PRINCIPLE:
"This layer does NOT infer intent from shadow-mode outputs."

Safety guards are PURELY MECHANICAL VALIDATION:
- Check for required explicit human approvals
- Verify kill switch state
- Validate execution constraints
- Ensure audit trail continuity
- NO INFERENCE from shadow-mode outputs
- NO AUTO-APPROVAL or AUTO-EXECUTION

Guards fail CLOSED: if any check fails, execution is blocked.

This module contains VALIDATION ONLY.
No decision logic. No trading operations. No inference.

NO IMPORTS from shadow-mode modules.
"""

from typing import Optional, Tuple, List
from datetime import datetime, timezone
from execution_boundary.execution_models import (
    ExecutionIntent,
    HumanExecutionApproval,
    KillSwitchState,
)


class SafetyGuards:
    """
    Mechanical validation guards for execution boundary.

    CRITICAL:
    - Guards check for EXPLICIT human approval (not inference)
    - Guards verify kill switch state (not inferring from metrics)
    - Guards validate constraints (human-specified bounds)
    - Guards NEVER infer intent from shadow-mode outputs
    - Default behavior is DENY (absence of approval = no execution)

    This is purely VALIDATION with NO BUSINESS LOGIC.
    """

    @staticmethod
    def check_explicit_approval(
        intent: ExecutionIntent, approval: Optional[HumanExecutionApproval]
    ) -> Tuple[bool, str]:
        """
        Check that explicit human approval exists and is valid.

        CRITICAL: Approval MUST be present and MUST have approved=True.
        Absence of approval means "do nothing" (fail-closed).

        Args:
            intent: ExecutionIntent object
            approval: HumanExecutionApproval object (or None)

        Returns:
            (is_valid, reason) tuple
        """
        # Absence of approval = DENY
        if approval is None:
            return False, "No explicit human approval found. Execution blocked."

        # Approval must be for this specific intent
        if approval.intent_id != intent.intent_id:
            return (
                False,
                f"Approval intent_id {approval.intent_id} does not match "
                f"execution intent_id {intent.intent_id}",
            )

        # Approval must have approved=True (not rejected)
        if not approval.approved:
            return False, "Approval explicitly rejected (approved=False)"

        # Approval must be valid (not expired)
        if not approval.is_valid():
            return False, "Approval has expired"

        # Approval rationale must be present
        if not approval.approval_rationale:
            return False, "Approval missing required rationale"

        return True, "Explicit human approval is valid"

    @staticmethod
    def check_kill_switch(kill_switch: KillSwitchState) -> Tuple[bool, str]:
        """
        Check that kill switch is not active.

        If ANY kill switch is active, execution is blocked.
        No inference. No exceptions. Just check the state.

        Args:
            kill_switch: KillSwitchState object

        Returns:
            (is_valid, reason) tuple
        """
        if kill_switch.manual_kill_active:
            return (
                False,
                f"Manual kill switch is ACTIVE. Reason: {kill_switch.manual_kill_reason}",
            )

        if kill_switch.circuit_breaker_active:
            return (
                False,
                f"Circuit breaker is ACTIVE. Reason: {kill_switch.circuit_breaker_reason}",
            )

        if kill_switch.timeout_active:
            return (
                False,
                f"Timeout halt is ACTIVE. Duration: {kill_switch.timeout_duration_seconds}s",
            )

        return True, "All kill switches are inactive"

    @staticmethod
    def check_intent_constraints(intent: ExecutionIntent) -> Tuple[bool, str]:
        """
        Check that intent satisfies its own constraints.

        These are HUMAN-SPECIFIED bounds, not inferred from metrics.

        Args:
            intent: ExecutionIntent object

        Returns:
            (is_valid, reason) tuple
        """
        # Rationale must be present
        if not intent.human_rationale:
            return False, "Intent missing required human_rationale"

        # If max_loss is specified, verify it's positive
        if intent.max_loss is not None and intent.max_loss < 0:
            return False, f"max_loss must be non-negative, got {intent.max_loss}"

        # If max_position_size is specified, verify it's positive
        if intent.max_position_size is not None and intent.max_position_size <= 0:
            return (
                False,
                f"max_position_size must be positive, got {intent.max_position_size}",
            )

        # If expiration is specified, verify it's in the future
        if intent.expires_at is not None:
            if intent.expires_at < datetime.now(timezone.utc):
                return False, "Intent has expired"

        return True, "Intent constraints are satisfied"

    @staticmethod
    def check_approval_conditions(approval: HumanExecutionApproval) -> Tuple[bool, str]:
        """
        Check that approval conditions (if any) are explicitly satisfied.

        CRITICAL: Conditional approvals are human-specified constraints.
        We do NOT verify the conditions themselves (that's domain-specific).
        We ONLY check that the list exists and is non-empty if conditional.

        Args:
            approval: HumanExecutionApproval object

        Returns:
            (is_valid, reason) tuple
        """
        # If conditional_approval=True, conditions must be present
        if approval.conditional_approval:
            if not approval.approval_conditions:
                return (
                    False,
                    "Conditional approval requires non-empty approval_conditions list",
                )

            if len(approval.approval_conditions) == 0:
                return (
                    False,
                    "Conditional approval requires at least one condition",
                )

            # Conditions are human-specified strings; we log them but don't verify them
            return (
                True,
                f"Conditional approval has {len(approval.approval_conditions)} conditions "
                f"(conditions must be verified by domain-specific logic)",
            )

        return True, "No conditional constraints"

    @staticmethod
    def check_approval_authority(
        approval: HumanExecutionApproval, intent_type: str
    ) -> Tuple[bool, str]:
        """
        Check that approval authority is appropriate for intent type.

        CRITICAL: This is POLICY validation, not decision logic.
        Different intent types may require different approval levels.

        Args:
            approval: HumanExecutionApproval object
            intent_type: Type of intent being approved

        Returns:
            (is_valid, reason) tuple
        """
        # System admin can approve anything
        from execution_boundary.execution_models import ApprovalAuthority

        if approval.authority_level == ApprovalAuthority.SYSTEM_ADMIN:
            return True, "System admin approval is valid for all intent types"

        # Risk officer can approve most things (not for emergency overrides)
        if approval.authority_level == ApprovalAuthority.RISK_OFFICER:
            if intent_type == "manual_override":
                return (
                    False,
                    "Risk officer cannot approve emergency manual overrides. "
                    "Requires system admin approval.",
                )
            return True, "Risk officer approval is valid for this intent type"

        # Human trader can approve routine operations
        if approval.authority_level == ApprovalAuthority.HUMAN_TRADER:
            if intent_type in ["open_position", "close_position", "modify_position"]:
                return True, "Human trader approval is valid for this intent type"
            else:
                return (
                    False,
                    f"Human trader cannot approve {intent_type}. "
                    f"Requires risk officer or system admin approval.",
                )

        return False, f"Unknown authority level: {approval.authority_level}"

    @staticmethod
    def check_audit_trail(
        intent_id: str, approval_id: str, audit_log: List[dict]
    ) -> Tuple[bool, str]:
        """
        Check that audit trail is continuous and complete.

        This verifies that required events were logged (not their content).

        Args:
            intent_id: ID of intent
            approval_id: ID of approval
            audit_log: List of audit records

        Returns:
            (is_valid, reason) tuple
        """
        if not audit_log:
            return False, "No audit trail present"

        # Check for intent creation event
        intent_created_events = [
            e for e in audit_log if e.get("event_type") == "intent_created"
            and e.get("intent_id") == intent_id
        ]
        if not intent_created_events:
            return False, f"No 'intent_created' event in audit trail for {intent_id}"

        # Check for approval event
        approval_events = [
            e for e in audit_log if e.get("approval_id") == approval_id
        ]
        if not approval_events:
            return False, f"No approval event in audit trail for {approval_id}"

        return (
            True,
            f"Audit trail is continuous ({len(audit_log)} events recorded)",
        )

    @staticmethod
    def execute_all_checks(
        intent: ExecutionIntent,
        approval: Optional[HumanExecutionApproval],
        kill_switch: KillSwitchState,
        audit_log: List[dict],
    ) -> Tuple[bool, str, List[str]]:
        """
        Execute all safety checks and report results.

        If ANY check fails, execution is blocked. All checks are deterministic.

        Args:
            intent: ExecutionIntent object
            approval: HumanExecutionApproval object (or None)
            kill_switch: KillSwitchState object
            audit_log: List of audit records

        Returns:
            (all_passed, summary, details) tuple where:
            - all_passed: True if all checks passed
            - summary: Human-readable summary
            - details: List of individual check results
        """
        checks = []
        all_passed = True

        # Check 1: Explicit approval
        approval_ok, approval_msg = SafetyGuards.check_explicit_approval(
            intent, approval
        )
        checks.append(f"Explicit Approval: {'✅ PASS' if approval_ok else '❌ FAIL'} - {approval_msg}")
        all_passed = all_passed and approval_ok

        # Check 2: Kill switch
        kill_switch_ok, kill_switch_msg = SafetyGuards.check_kill_switch(kill_switch)
        checks.append(
            f"Kill Switch: {'✅ PASS' if kill_switch_ok else '❌ FAIL'} - {kill_switch_msg}"
        )
        all_passed = all_passed and kill_switch_ok

        # Check 3: Intent constraints
        intent_ok, intent_msg = SafetyGuards.check_intent_constraints(intent)
        checks.append(
            f"Intent Constraints: {'✅ PASS' if intent_ok else '❌ FAIL'} - {intent_msg}"
        )
        all_passed = all_passed and intent_ok

        # Check 4: Approval conditions
        if approval:
            conditions_ok, conditions_msg = SafetyGuards.check_approval_conditions(
                approval
            )
            checks.append(
                f"Approval Conditions: {'✅ PASS' if conditions_ok else '❌ FAIL'} - {conditions_msg}"
            )
            all_passed = all_passed and conditions_ok

            # Check 5: Approval authority
            authority_ok, authority_msg = SafetyGuards.check_approval_authority(
                approval, intent.intent_type.value
            )
            checks.append(
                f"Approval Authority: {'✅ PASS' if authority_ok else '❌ FAIL'} - {authority_msg}"
            )
            all_passed = all_passed and authority_ok

        # Check 6: Audit trail
        if approval:
            audit_ok, audit_msg = SafetyGuards.check_audit_trail(
                intent.intent_id, approval.approval_id, audit_log
            )
            checks.append(
                f"Audit Trail: {'✅ PASS' if audit_ok else '❌ FAIL'} - {audit_msg}"
            )
            all_passed = all_passed and audit_ok

        summary = (
            "✅ ALL CHECKS PASSED - Execution may proceed"
            if all_passed
            else "❌ SAFETY CHECK FAILED - Execution blocked"
        )

        return all_passed, summary, checks
