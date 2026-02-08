"""
Execution Boundary Module

CRITICAL SAFETY LAYER:
This module defines the STRICT AUTHORITY BOUNDARY for execution intent approval
and state management. It is COMPLETELY ISOLATED from all shadow-mode services
(Phases 7-10) and contains NO trading logic, signal interpretation, or strategy.

PURPOSE:
- Define explicit data contracts for human-authored execution intents
- Manage kill switches and safety guards
- Require explicit human authorization before anything proceeds
- Maintain audit-first, append-only execution logs
- Treat all shadow-mode outputs as UNTRUSTED INPUT

KEY PRINCIPLE:
"This layer does NOT infer intent from shadow-mode outputs."

Execution requires an explicit HumanExecutionApproval object. Absence of approval
means "do nothing." This is a fail-closed system.

ARCHITECTURE:
- execution_models.py: Data contracts (ExecutionIntent, HumanExecutionApproval, etc.)
- kill_switch_controller.py: Kill switch state and manual override management
- execution_audit_logger.py: Append-only audit logging for all execution events
- safety_guards.py: Validation guards that REQUIRE explicit human authorization

FORBIDDEN IMPORTS:
- NO imports from reasoner_service.decision_trust_calibration_service
- NO imports from decision_*_service modules
- NO imports from counterfactual_enforcement_simulator
- NO imports from outcome_* modules
- NO imports from orchestration modules

FORBIDDEN USES:
- Do NOT use fields: recommendation, confidence, stability_index, veto
- Do NOT auto-approve or auto-reject anything
- Do NOT implement execution, broker APIs, or order placement
- Do NOT infer intent from shadow-mode metrics

DEFAULT BEHAVIOR: DO NOTHING (fail closed)
"""

from execution_boundary.execution_models import (
    ExecutionIntent,
    HumanExecutionApproval,
    KillSwitchState,
    ExecutionAuditRecord,
)
from execution_boundary.kill_switch_controller import KillSwitchController
from execution_boundary.execution_audit_logger import ExecutionAuditLogger
from execution_boundary.safety_guards import SafetyGuards

__all__ = [
    "ExecutionIntent",
    "HumanExecutionApproval",
    "KillSwitchState",
    "ExecutionAuditRecord",
    "KillSwitchController",
    "ExecutionAuditLogger",
    "SafetyGuards",
]
