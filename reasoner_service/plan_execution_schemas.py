"""
Plan Execution Contract (v1) - Structural Definitions

This module defines the data structures required by PLAN_EXECUTION_CONTRACT.md.
These are pure declarations with no execution logic, validation, or branching.

All classes are stubs intended to be consumed by a future PlanExecutor implementation
that will be audited for compliance against the contract.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import uuid
import time


# ============================================================================
# ERROR CLASSIFICATION (Section 4)
# ============================================================================

class ErrorSeverity(str, Enum):
    """Error severity levels as defined in Contract Section 4."""
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class ErrorCode(str, Enum):
    """Reserved error codes from Contract Section 4, Error Code Registry."""
    CONTEXT_MISSING = "CONTEXT_MISSING"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    STEP_TIMEOUT = "STEP_TIMEOUT"
    PLAN_TIMEOUT = "PLAN_TIMEOUT"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    DEPENDENCY_UNRESOLVED = "DEPENDENCY_UNRESOLVED"
    ACTION_NOT_FOUND = "ACTION_NOT_FOUND"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    EXECUTION_HALTED = "EXECUTION_HALTED"
    STEP_SKIPPED = "STEP_SKIPPED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


# ============================================================================
# PLAN OBJECT SCHEMA (Section 1)
# ============================================================================

@dataclass
class RetryPolicy:
    """RetryPolicy sub-schema from Contract Section 1.1.
    
    Defines retry configuration for failed steps at the plan level.
    All fields are optional with defaults as specified in the contract.
    """
    max_attempts: int = 1
    backoff_ms: int = 0
    backoff_multiplier: float = 1.0
    max_backoff_ms: int = 60000
    retryable_error_codes: List[str] = field(default_factory=list)


@dataclass
class PlanStep:
    """PlanStep sub-schema from Contract Section 1.
    
    Represents a single step in a plan's execution sequence.
    All fields must match Contract Section 1 constraints.
    """
    id: str  # UUID v4
    action: str  # Non-empty, ≤ 100 chars
    payload: Dict[str, Any]  # Required, can be {}
    depends_on: List[str] = field(default_factory=list)  # IDs of dependency steps
    on_failure: str = "halt"  # One of: halt, skip, retry
    timeout_ms: Optional[int] = None  # Step-level timeout override


@dataclass
class Plan:
    """Plan object schema from Contract Section 1.
    
    Represents a complete execution plan with required and optional fields.
    All fields must match Contract Section 1 constraints exactly.
    """
    # REQUIRED FIELDS
    id: str  # Non-empty UUID v4
    version: int  # ≥ 1; currently 1
    created_at: int  # Unix timestamp (ms)
    steps: List[PlanStep]  # Non-empty, ≤ 1024
    name: str  # Non-empty, ≤ 255 chars
    context_requirements: List[str]  # Non-empty list of required context keys
    
    # OPTIONAL FIELDS
    priority: int = 0
    timeout_ms: int = 300000  # 5 minutes default
    retry_policy: Optional[RetryPolicy] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    estimated_duration_ms: Optional[int] = None


# ============================================================================
# EXECUTION CONTEXT SCHEMA (Section 2)
# ============================================================================

@dataclass
class ExecutionContext:
    """ExecutionContext schema from Contract Section 2.
    
    Immutable read-only environment provided to the executor.
    The orchestrator MUST NOT modify any field in ExecutionContext.
    The orchestrator MUST NOT validate, mutate, or interpret environment contents.
    """
    # REQUIRED FIELDS
    plan: Plan  # The Plan object being executed (immutable)
    execution_id: str  # Unique execution session identifier (UUID v4)
    started_at: int  # Execution start timestamp (Unix ms)
    deadline_ms: int  # Absolute deadline timestamp (Unix ms)
    environment: Dict[str, Any]  # Runtime environment (opaque to orchestrator)
    
    # OPTIONAL FIELDS
    parent_execution_id: Optional[str] = None  # Parent execution ID if nested
    user_id: Optional[str] = None  # User or system that initiated execution
    request_id: Optional[str] = None  # Correlated request identifier for tracing
    correlation_context: Optional[Dict[str, str]] = None  # Cross-system correlation


# ============================================================================
# PLAN RESULT SCHEMA (Section 3)
# ============================================================================

@dataclass
class ExecutionError:
    """ExecutionError sub-schema from Contract Section 3.1.
    
    Represents a single error that occurred during execution.
    Used when status is 'partial' or 'failure'.
    """
    error_code: str  # Machine-readable error classification (use ErrorCode enum)
    message: str  # Human-readable error description (≤ 1000 chars)
    step_id: Optional[str] = None  # UUID v4 of step where error occurred; null if plan-level
    severity: str = "fatal"  # One of: warn, error, fatal (use ErrorSeverity enum)
    recoverable: bool = False  # Derived from severity
    cause: Optional['ExecutionError'] = None  # Nested error if chained
    context: Dict[str, Any] = field(default_factory=dict)  # Error diagnostic data


@dataclass
class PlanResult:
    """PlanResult schema from Contract Section 3.
    
    Describes the terminal outcome of plan execution.
    All fields are required as specified; error field is conditional.
    """
    # REQUIRED FIELDS
    plan_id: str  # UUID v4 of executed plan
    execution_id: str  # Unique execution session identifier (UUID v4)
    status: str  # One of: success, partial, failure
    completed_at: int  # Execution completion time (Unix ms)
    duration_ms: int  # Total execution duration (non-negative)
    steps_executed: int  # Count of completed steps (0 to plan.steps.length)
    steps_total: int  # Total steps in plan (equals plan.steps.length)
    result_payload: Dict[str, Any]  # Executor-generated output data
    
    # CONDITIONAL FIELD
    error: Optional[ExecutionError] = None  # Present if status is 'partial' or 'failure'


# ============================================================================
# PLACEHOLDER STUBS (Not yet implemented)
# ============================================================================

class ExecutionValidationError(Exception):
    """Exception raised during plan or context validation.
    
    Wraps ExecutionError data and allows raising as exception.
    Per Contract Appendix: Validation errors are fatal and halt execution.
    """
    def __init__(self, execution_error: 'ExecutionError'):
        self.execution_error = execution_error
        super().__init__(execution_error.message)

class PlanValidator:
    """Stub for plan validation as required by Contract Appendix.
    
    Must validate:
    - All required fields present
    - UUID v4 format for plan.id and all step.id
    - steps list is non-empty and acyclic
    - context_requirements is non-empty
    - All depends_on references valid step IDs
    - on_failure values are valid
    - Timestamp fields are positive integers (Unix ms)
    
    Raises NotImplementedError: This is not yet implemented.
    """
    def validate_plan(self, plan: Plan) -> None:
        raise NotImplementedError("Plan validation not yet implemented")
    
    def validate_execution_context(self, ctx: ExecutionContext) -> None:
        raise NotImplementedError("ExecutionContext validation not yet implemented")
    
    def validate_plan_result(self, result: PlanResult) -> None:
        raise NotImplementedError("PlanResult validation not yet implemented")


class PlanExecutor:
    """Skeleton v1 executor for plan execution per PLAN_EXECUTION_CONTRACT.md.
    
    This is a CONTRACT-BOUNDARY implementation. No execution logic is present.
    
    Contract Requirements:
    - Deterministic rule sets (§5.1 success, §5.2 partial, §5.3 failure)
    - Hard stop timeouts (§6.9)
    - Error classification (§4)
    - Best-effort event emission (§5.0)
    - Environment opacity (§2)
    - Immutable ExecutionContext (§2)
    - Conditional error field (§3)
    
    All behavior must be implemented strictly per PLAN_EXECUTION_CONTRACT.md.
    No fallback behavior is permitted once implementation begins.
    """
    def __init__(self, orchestrator: Any = None):
        """Initialize executor.
        
        Args:
            orchestrator: Reference to DecisionOrchestrator (may be None in tests)
        """
        self.orchestrator = orchestrator
    
    async def execute(self, plan: Plan, ctx: ExecutionContext) -> PlanResult:
        """Execute a plan and return PlanResult per contract lifecycle.
        
        This method is the CONTRACT BOUNDARY between orchestrator and executor.
        All execution outcomes MUST be one of: success, partial, failure.
        
        Lifecycle mapping:
        
        § 5.1 SUCCESS PATH (8 actions)
        - Precondition: all steps completed, no errors
        - Actions: validate → capture metadata → set status → persist → emit event 
                   → update state → release resources → return result
        
        § 5.2 PARTIAL SUCCESS PATH (10 actions)
        - Precondition: some steps completed, non-fatal error(s)
        - Actions: classify failure → aggregate errors → validate progress → preserve output
                   → capture metadata → set status → persist → emit event → mark incomplete → return result
        - TERMINAL STATE: Must NOT be resumed or retried by orchestrator
        - New execution requires new execution_id and new plan instance
        
        § 5.3 FAILURE PATH (13 actions)
        - Precondition: fatal error, step halt, timeout, or deadline exceeded
        - Actions: identify cause → classify severity → halt execution → capture context
                   → truncate result → validate consistency → set error → set status → persist
                   → emit event → release resources → notify handler → return result
        
        Args:
            plan: Plan object (immutable)
            ctx: ExecutionContext (immutable environment)
        
        Returns:
            PlanResult with status ∈ (success, partial, failure)
            - status=success: error field is None
            - status=partial: error field is non-null (non-fatal)
            - status=failure: error field is non-null (fatal)
        
        Raises:
            NotImplementedError: This is a skeleton. All logic must be implemented
                per contract specification. No implementation exists yet.
        """
        # PHASE 1: VALIDATE PLAN SCHEMA (§1, Contract Appendix)
        # Raises ExecutionValidationError if invalid
        try:
            await self._validate_plan(plan)
        except ExecutionValidationError as e:
            # Validation failure = fatal error, return failure result
            error = e.execution_error  # ExecutionError wrapped in exception
            result = await self._build_plan_result(plan, ctx, steps_executed=0, error=error)
            return result
        
        # PHASE 2: VALIDATE EXECUTION CONTEXT (§2)
        # Raises ExecutionValidationError if invalid
        try:
            await self._validate_context(plan, ctx)
        except ExecutionValidationError as e:
            # Context validation failure = fatal error, return failure result
            error = e.execution_error
            result = await self._build_plan_result(plan, ctx, steps_executed=0, error=error)
            return result
        
        # PHASE 3: EXECUTE STEPS (§5 lifecycle orchestration)
        # Returns (steps_executed, first_error) tuple
        steps_executed: int
        execution_error: Optional[ExecutionError]
        steps_executed, execution_error = await self._execute_steps(plan, ctx)
        
        # PHASE 4: BUILD PLAN RESULT (§3 schema + §5.1-5.3 status inference)
        # Maps (steps_executed, error) → PlanResult with deterministic status
        result: PlanResult = await self._build_plan_result(
            plan=plan,
            ctx=ctx,
            steps_executed=steps_executed,
            error=execution_error
        )
        
        # RETURN RESULT
        # Status ∈ {success, partial, failure}
        # Error field non-null iff status != success
        # Per Contract §3: All fields MUST match PlanResult schema exactly
        return result
    
    async def execute_plan(self, ctx: ExecutionContext) -> PlanResult:
        """Execute a plan and return PlanResult.
        
        Entry point accepting ExecutionContext (which contains Plan).
        Delegates to execute() for structural execution.
        
        Must return a PlanResult with status in (success, partial, failure)
        and error field populated for non-success states.
        
        Raises NotImplementedError: Execution not yet implemented.
        """
        # ExecutionContext includes the Plan as ctx.plan
        # Delegate to execute() for full lifecycle orchestration
        return await self.execute(ctx.plan, ctx)
    
    async def run_plan(self, plan: Plan, execution_ctx: ExecutionContext) -> PlanResult:
        """Alias for execute() for backward compatibility.
        
        Raises NotImplementedError: Execution not yet implemented.
        """
        # Backward compatibility alias: run_plan = execute
        return await self.execute(plan, execution_ctx)
    
    # ========================================================================
    # PRIVATE HELPER STUBS (No logic - contract boundaries only)
    # ========================================================================
    
    async def _validate_plan(self, plan: Plan) -> None:
        """Pre-execution validation of Plan schema per Contract Appendix.
        
        Validates all Plan fields against PLAN_EXECUTION_CONTRACT.md Appendix rules:
        - All required fields present (§1: id, version, created_at, steps, name, context_requirements)
        - UUID v4 format for plan.id and all step.id
        - steps list is non-empty and acyclic (no circular dependencies)
        - context_requirements non-empty
        - All depends_on references valid step IDs
        - on_failure values ∈ (halt, skip, retry)
        - Timestamp fields are positive integers (Unix ms)
        - version ≥ 1
        - name length ≤ 255 chars
        - steps length ≤ 1024
        - action length ≤ 100 chars per step
        - Retry policy constraints if present
        
        Raises ExecutionValidationError wrapping ExecutionError with fatal severity.
        
        Args:
            plan: Plan object to validate
            
        Raises:
            ExecutionValidationError: Contains ExecutionError with error_code and severity=fatal
        """
        # Validate required Plan fields exist
        if not isinstance(plan, Plan):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message="Plan object is not instance of Plan dataclass",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate plan.id is UUID v4
        try:
            plan_uuid = uuid.UUID(plan.id, version=4)
        except (ValueError, AttributeError, TypeError):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.id is not valid UUID v4: {plan.id}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate plan.version ≥ 1
        if not isinstance(plan.version, int) or plan.version < 1:
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.version must be ≥ 1, got {plan.version}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate plan.created_at is positive Unix ms timestamp
        if not isinstance(plan.created_at, int) or plan.created_at <= 0:
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.created_at must be positive Unix ms timestamp, got {plan.created_at}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate plan.name is non-empty and ≤ 255 chars
        if not isinstance(plan.name, str) or len(plan.name) == 0 or len(plan.name) > 255:
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.name must be non-empty string ≤ 255 chars, got length {len(plan.name) if isinstance(plan.name, str) else 'non-string'}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate plan.context_requirements is non-empty list
        if not isinstance(plan.context_requirements, list) or len(plan.context_requirements) == 0:
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message="plan.context_requirements must be non-empty list",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate plan.steps is non-empty and ≤ 1024
        if not isinstance(plan.steps, list) or len(plan.steps) == 0 or len(plan.steps) > 1024:
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.steps must be non-empty list ≤ 1024 items, got {len(plan.steps) if isinstance(plan.steps, list) else 'non-list'}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Build set of valid step IDs for dependency validation
        step_ids = set()
        step_id_to_index = {}
        
        # Validate each step and collect IDs
        for idx, step in enumerate(plan.steps):
            if not isinstance(step, PlanStep):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.steps[{idx}] is not instance of PlanStep dataclass",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate step.id is UUID v4
            try:
                step_uuid = uuid.UUID(step.id, version=4)
            except (ValueError, AttributeError, TypeError):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.steps[{idx}].id is not valid UUID v4: {step.id}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Check for duplicate step IDs
            if step.id in step_ids:
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"Duplicate step.id: {step.id}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            step_ids.add(step.id)
            step_id_to_index[step.id] = idx
            
            # Validate step.action is non-empty and ≤ 100 chars
            if not isinstance(step.action, str) or len(step.action) == 0 or len(step.action) > 100:
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.steps[{idx}].action must be non-empty string ≤ 100 chars, got length {len(step.action) if isinstance(step.action, str) else 'non-string'}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate step.payload is dict (can be empty)
            if not isinstance(step.payload, dict):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.steps[{idx}].payload must be dict, got {type(step.payload).__name__}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate step.on_failure is valid
            if step.on_failure not in ("halt", "skip", "retry"):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.steps[{idx}].on_failure must be one of (halt, skip, retry), got {step.on_failure}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate step.depends_on references only valid step IDs
            if not isinstance(step.depends_on, list):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.steps[{idx}].depends_on must be list, got {type(step.depends_on).__name__}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            for dep_id in step.depends_on:
                if dep_id not in step_ids and dep_id != step.id:
                    # Forward reference to not-yet-seen step is allowed (will be checked after loop)
                    pass
            
            # Validate step.timeout_ms is either None or positive int
            if step.timeout_ms is not None:
                if not isinstance(step.timeout_ms, int) or step.timeout_ms <= 0:
                    raise ExecutionValidationError(ExecutionError(
                        error_code="INVALID_PAYLOAD",
                        message=f"plan.steps[{idx}].timeout_ms must be None or positive int, got {step.timeout_ms}",
                        severity=ErrorSeverity.FATAL,
                        recoverable=False
                    ))
        
        # Validate all depends_on references point to valid step IDs and no circular deps
        for idx, step in enumerate(plan.steps):
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    raise ExecutionValidationError(ExecutionError(
                        error_code="DEPENDENCY_UNRESOLVED",
                        message=f"plan.steps[{idx}].depends_on references non-existent step: {dep_id}",
                        severity=ErrorSeverity.FATAL,
                        recoverable=False
                    ))
                
                # Check no self-dependency
                if dep_id == step.id:
                    raise ExecutionValidationError(ExecutionError(
                        error_code="INVALID_PAYLOAD",
                        message=f"plan.steps[{idx}] has self-dependency: {dep_id}",
                        severity=ErrorSeverity.FATAL,
                        recoverable=False
                    ))
                
                # Check for backward reference violation (dependency must be earlier in list for acyclic)
                dep_index = step_id_to_index[dep_id]
                if dep_index > idx:
                    raise ExecutionValidationError(ExecutionError(
                        error_code="DEPENDENCY_UNRESOLVED",
                        message=f"plan.steps[{idx}] has forward dependency on later step: {dep_id} at index {dep_index}",
                        severity=ErrorSeverity.FATAL,
                        recoverable=False
                    ))
        
        # Validate retry_policy if present
        if plan.retry_policy is not None:
            if not isinstance(plan.retry_policy, RetryPolicy):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message="plan.retry_policy is not instance of RetryPolicy",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate max_attempts ≥ 1
            if not isinstance(plan.retry_policy.max_attempts, int) or plan.retry_policy.max_attempts < 1:
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.retry_policy.max_attempts must be ≥ 1, got {plan.retry_policy.max_attempts}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate backoff_ms ≥ 0
            if not isinstance(plan.retry_policy.backoff_ms, int) or plan.retry_policy.backoff_ms < 0:
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.retry_policy.backoff_ms must be ≥ 0, got {plan.retry_policy.backoff_ms}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate backoff_multiplier ≥ 1.0
            if not isinstance(plan.retry_policy.backoff_multiplier, (int, float)) or plan.retry_policy.backoff_multiplier < 1.0:
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.retry_policy.backoff_multiplier must be ≥ 1.0, got {plan.retry_policy.backoff_multiplier}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate max_backoff_ms ≥ 0
            if not isinstance(plan.retry_policy.max_backoff_ms, int) or plan.retry_policy.max_backoff_ms < 0:
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.retry_policy.max_backoff_ms must be ≥ 0, got {plan.retry_policy.max_backoff_ms}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            
            # Validate retryable_error_codes is list
            if not isinstance(plan.retry_policy.retryable_error_codes, list):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.retry_policy.retryable_error_codes must be list, got {type(plan.retry_policy.retryable_error_codes).__name__}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
        
        # Validate optional fields have correct types
        if not isinstance(plan.priority, int):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.priority must be int, got {type(plan.priority).__name__}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        if not isinstance(plan.timeout_ms, int) or plan.timeout_ms <= 0:
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.timeout_ms must be positive int, got {plan.timeout_ms}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        if not isinstance(plan.metadata, dict):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.metadata must be dict, got {type(plan.metadata).__name__}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        if not isinstance(plan.tags, list):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"plan.tags must be list, got {type(plan.tags).__name__}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        if plan.estimated_duration_ms is not None:
            if not isinstance(plan.estimated_duration_ms, int) or plan.estimated_duration_ms <= 0:
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"plan.estimated_duration_ms must be None or positive int, got {plan.estimated_duration_ms}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
    
    async def _validate_context(self, ctx: ExecutionContext) -> None:
        """Pre-execution validation of ExecutionContext per Contract Appendix and §2.
        
        Validates ExecutionContext immutability constraints and deadline/requirement consistency:
        - All required fields present (§2: plan, execution_id, started_at, deadline_ms, environment)
        - execution_id is UUID v4
        - started_at is positive Unix ms timestamp
        - deadline_ms is positive Unix ms timestamp
        - deadline_ms > started_at
        - deadline_ms - started_at >= plan.timeout_ms (sufficient window for execution)
        - environment is dict (opaque to orchestrator, not validated)
        - All plan.context_requirements keys exist in environment dict
        - Optional fields have correct types if present (parent_execution_id UUID, user_id str, request_id str, correlation_context dict)
        - ExecutionContext is treated as immutable (no modifications)
        
        Raises ExecutionValidationError wrapping ExecutionError with fatal severity.
        
        Args:
            ctx: ExecutionContext object to validate
            
        Raises:
            ExecutionValidationError: Contains ExecutionError with error_code and severity=fatal
        """
        # Validate required ExecutionContext fields exist
        if not isinstance(ctx, ExecutionContext):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message="ExecutionContext is not instance of ExecutionContext dataclass",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate ctx.plan is Plan object
        if not isinstance(ctx.plan, Plan):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message="ctx.plan is not instance of Plan dataclass",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate ctx.execution_id is UUID v4
        try:
            exec_uuid = uuid.UUID(ctx.execution_id, version=4)
        except (ValueError, AttributeError, TypeError):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"ctx.execution_id is not valid UUID v4: {ctx.execution_id}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate ctx.started_at is positive Unix ms timestamp
        if not isinstance(ctx.started_at, int) or ctx.started_at <= 0:
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"ctx.started_at must be positive Unix ms timestamp, got {ctx.started_at}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate ctx.deadline_ms is positive Unix ms timestamp
        if not isinstance(ctx.deadline_ms, int) or ctx.deadline_ms <= 0:
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"ctx.deadline_ms must be positive Unix ms timestamp, got {ctx.deadline_ms}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate deadline_ms > started_at (deadline must be in future)
        if ctx.deadline_ms <= ctx.started_at:
            raise ExecutionValidationError(ExecutionError(
                error_code="DEADLINE_EXCEEDED",
                message=f"ctx.deadline_ms ({ctx.deadline_ms}) must be > ctx.started_at ({ctx.started_at})",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate deadline window is sufficient for plan timeout
        # deadline_ms - started_at >= plan.timeout_ms
        available_window = ctx.deadline_ms - ctx.started_at
        if available_window < ctx.plan.timeout_ms:
            raise ExecutionValidationError(ExecutionError(
                error_code="DEADLINE_EXCEEDED",
                message=f"Execution window ({available_window}ms) insufficient for plan timeout ({ctx.plan.timeout_ms}ms)",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate ctx.environment is dict (opaque to orchestrator, not interpreted)
        if not isinstance(ctx.environment, dict):
            raise ExecutionValidationError(ExecutionError(
                error_code="INVALID_PAYLOAD",
                message=f"ctx.environment must be dict, got {type(ctx.environment).__name__}",
                severity=ErrorSeverity.FATAL,
                recoverable=False
            ))
        
        # Validate all plan.context_requirements keys exist in environment
        for req_key in ctx.plan.context_requirements:
            if req_key not in ctx.environment:
                raise ExecutionValidationError(ExecutionError(
                    error_code="CONTEXT_MISSING",
                    message=f"Required context key not provided: {req_key}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
        
        # Validate optional fields have correct types if present
        if ctx.parent_execution_id is not None:
            if not isinstance(ctx.parent_execution_id, str):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"ctx.parent_execution_id must be str or None, got {type(ctx.parent_execution_id).__name__}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
            # If provided, must be valid UUID v4
            try:
                parent_uuid = uuid.UUID(ctx.parent_execution_id, version=4)
            except (ValueError, AttributeError, TypeError):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"ctx.parent_execution_id is not valid UUID v4: {ctx.parent_execution_id}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
        
        if ctx.user_id is not None:
            if not isinstance(ctx.user_id, str):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"ctx.user_id must be str or None, got {type(ctx.user_id).__name__}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
        
        if ctx.request_id is not None:
            if not isinstance(ctx.request_id, str):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"ctx.request_id must be str or None, got {type(ctx.request_id).__name__}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
        
        if ctx.correlation_context is not None:
            if not isinstance(ctx.correlation_context, dict):
                raise ExecutionValidationError(ExecutionError(
                    error_code="INVALID_PAYLOAD",
                    message=f"ctx.correlation_context must be dict or None, got {type(ctx.correlation_context).__name__}",
                    severity=ErrorSeverity.FATAL,
                    recoverable=False
                ))
    
    async def _execute_steps(self, plan: Plan, ctx: ExecutionContext) -> Tuple[int, Optional[ExecutionError]]:
        """Execute plan steps in dependency order per Contract §5 lifecycle rules.
        
        Executes steps in acyclic dependency order, tracking execution progress and errors.
        Does NOT interpret step payloads, modify plan, or mutate environment.
        
        Execution flow per contract:
        - §5.1 SUCCESS PATH: All steps complete without error
          Actions: validate completion → capture metadata → set status → persist → emit event 
                   → update state → release resources → return result
        
        - §5.2 PARTIAL SUCCESS PATH: Some steps complete, non-fatal error(s) occur
          Actions: classify failure → aggregate errors → validate progress → preserve output
                   → capture metadata → set status → persist → emit event → mark incomplete → return result
          Terminal state: Must NOT be resumed or retried by orchestrator
        
        - §5.3 FAILURE PATH: Fatal error, step halt, timeout, or deadline exceeded
          Actions: identify cause → classify severity → halt execution → capture context
                   → truncate result → validate consistency → set error → set status → persist
                   → emit event → release resources → notify handler → return result
        
        Step execution rules (§1):
        - Dependencies must be satisfied (depends_on steps completed first)
        - on_failure policies: halt (stop execution), skip (continue), retry (not implemented here)
        - Timeout enforcement (§6.9): Hard stop on step timeout (not implemented here)
        
        Error classification (§4):
        - All errors are wrapped in ExecutionError with error_code and severity
        - Severity: warn (continue), error (apply on_failure policy), fatal (halt immediately)
        - Recoverable status drives retry eligibility
        
        Args:
            plan: Plan object with steps to execute (immutable)
            ctx: ExecutionContext with environment and deadline (immutable)
        
        Returns:
            Tuple[int, Optional[ExecutionError]]:
            - steps_executed: count of successfully completed steps (0 to len(plan.steps))
            - error: First non-skipped error encountered, or None if all steps succeeded
        
        Raises:
            ExecutionValidationError: If step data is malformed (should not occur post-validation)
        """
        # Track execution state
        steps_executed = 0
        first_error = None
        completed_step_ids = set()
        
        # Step-by-step execution loop (acyclic ordering guaranteed by validation)
        for step_idx, step in enumerate(plan.steps):
            # § 5.1 / 5.2 / 5.3: Validate step dependencies are met before execution
            dependencies_satisfied = True
            for dep_id in step.depends_on:
                if dep_id not in completed_step_ids:
                    dependencies_satisfied = False
                    # Dependency not yet completed - mark as unresolved
                    first_error = ExecutionError(
                        error_code="DEPENDENCY_UNRESOLVED",
                        message=f"Step {step.id} dependency {dep_id} not completed",
                        step_id=step.id,
                        severity=ErrorSeverity.ERROR,
                        recoverable=False
                    )
                    # Apply on_failure policy for dependency failure
                    if step.on_failure == "halt":
                        # § 5.3 FAILURE PATH: halt execution immediately
                        return (steps_executed, first_error)
                    elif step.on_failure == "skip":
                        # § 5.2 PARTIAL: Skip this step, continue execution
                        first_error = ExecutionError(
                            error_code="STEP_SKIPPED",
                            message=f"Step {step.id} skipped due to dependency failure",
                            step_id=step.id,
                            severity=ErrorSeverity.WARN,
                            recoverable=False
                        )
                        break  # Skip to next step
                    elif step.on_failure == "retry":
                        # Retry not implemented in skeleton; treat as fatal
                        first_error = ExecutionError(
                            error_code="EXECUTION_HALTED",
                            message=f"Step {step.id} retry policy not implemented",
                            step_id=step.id,
                            severity=ErrorSeverity.FATAL,
                            recoverable=False
                        )
                        # § 5.3 FAILURE PATH: halt execution
                        return (steps_executed, first_error)
            
            # If dependencies satisfied, mark step as executed
            if dependencies_satisfied:
                # § 5.1 SUCCESS PATH: Step execution succeeds (stub - no actual execution)
                # This is where actual action execution would occur
                # For skeleton: assume step completes successfully
                completed_step_ids.add(step.id)
                steps_executed += 1
                # No error recorded for this step
                continue
            
            # If we get here, step was skipped due to on_failure policy
            if step.on_failure == "skip" and first_error is not None:
                # Already handled above; continue to next step
                continue
        
        # Return final execution state
        # steps_executed: count of completed steps
        # first_error: first non-skipped error (None if all succeeded)
        return (steps_executed, first_error)
    
    async def _build_plan_result(
        self, 
        plan: Plan, 
        ctx: ExecutionContext, 
        steps_executed: int, 
        error: Optional[ExecutionError]
    ) -> PlanResult:
        """Construct PlanResult per contract lifecycle paths (§5.1, §5.2, §5.3).
        
        Deterministic status inference:
        - If error is None and steps_executed == len(plan.steps) → success (§5.1)
        - If error is not None and error.severity != fatal and steps_executed > 0 → partial (§5.2)
        - If error is not None and error.severity == fatal → failure (§5.3)
        
        All fields MUST match PlanResult schema (§3) exactly:
        - plan_id, execution_id: UUID v4 from inputs
        - status: success | partial | failure
        - completed_at: current timestamp (Unix ms)
        - duration_ms: completed_at - ctx.started_at
        - steps_executed: provided count
        - steps_total: len(plan.steps)
        - result_payload: executor-generated output (initially {})
        - error: non-null iff status != success
        
        Args:
            plan: Plan being executed (immutable)
            ctx: ExecutionContext (immutable)
            steps_executed: count of completed steps (0 to len(plan.steps))
            error: primary error or None
        
        Returns:
            PlanResult with proper schema and status mapping
        
        Raises NotImplementedError: Result building not yet implemented.
        """
        # Calculate completion timestamp (Unix milliseconds)
        completed_at: int = int(time.time() * 1000)
        
        # Calculate execution duration
        duration_ms: int = completed_at - ctx.started_at
        
        # Deterministic status inference per §5.1, §5.2, §5.3
        # §5.1 SUCCESS: error is None AND all steps executed
        if error is None and steps_executed == len(plan.steps):
            status: str = "success"
        # §5.2 PARTIAL: error exists AND non-fatal AND some steps executed
        elif error is not None and error.severity != ErrorSeverity.FATAL and steps_executed > 0:
            status: str = "partial"
        # §5.3 FAILURE: error exists AND fatal (OR no steps executed with error)
        elif error is not None:
            status: str = "failure"
        # Edge case: no steps executed, no error (empty plan or all skipped)
        else:
            # All steps skipped (on_failure=skip throughout) = partial success
            status: str = "partial" if steps_executed > 0 else "partial"
        
        # Construct PlanResult per Contract §3
        return PlanResult(
            plan_id=plan.id,                           # UUID v4 from Plan
            execution_id=ctx.execution_id,             # UUID v4 from ExecutionContext
            status=status,                             # Inferred: success | partial | failure
            completed_at=completed_at,                 # Unix milliseconds (now)
            duration_ms=duration_ms,                   # Elapsed time
            steps_executed=steps_executed,             # Completed step count
            steps_total=len(plan.steps),               # Total steps in plan
            result_payload={},                         # Executor output (skeleton: empty)
            error=error                                # Non-null iff status != success
        )
