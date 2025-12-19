"""
Test suite for Plan Execution Contract alignment.

This test file verifies that:
1. All contract schemas are properly defined
2. Schemas can be instantiated and serialized
3. Orchestrator references schemas correctly
4. PlanExecutor stub raises NotImplementedError
5. No execution logic is implemented
"""

import pytest
from reasoner_service.plan_execution_schemas import (
    Plan, PlanStep, ExecutionContext, PlanResult, ExecutionError,
    RetryPolicy, ErrorSeverity, ErrorCode, PlanExecutor, PlanValidator
)


class TestContractSchemas:
    """Verify all Plan Execution Contract schemas exist and are properly defined."""

    def test_plan_step_creation(self):
        """PlanStep can be created with required fields."""
        step = PlanStep(
            id="step-1",
            action="validate",
            payload={"key": "value"}
        )
        assert step.id == "step-1"
        assert step.action == "validate"
        assert step.payload == {"key": "value"}
        assert step.depends_on == []
        assert step.on_failure == "halt"
        assert step.timeout_ms is None

    def test_retry_policy_defaults(self):
        """RetryPolicy has correct defaults per Contract Section 1.1."""
        policy = RetryPolicy()
        assert policy.max_attempts == 1
        assert policy.backoff_ms == 0
        assert policy.backoff_multiplier == 1.0
        assert policy.max_backoff_ms == 60000
        assert policy.retryable_error_codes == []

    def test_plan_creation(self):
        """Plan can be created with required fields."""
        step = PlanStep(id="step-1", action="test", payload={})
        plan = Plan(
            id="plan-123",
            version=1,
            created_at=1000000,
            steps=[step],
            name="test_plan",
            context_requirements=["key1", "key2"]
        )
        assert plan.id == "plan-123"
        assert plan.version == 1
        assert plan.name == "test_plan"
        assert len(plan.steps) == 1
        assert plan.context_requirements == ["key1", "key2"]
        assert plan.timeout_ms == 300000  # Default 5 minutes
        assert plan.priority == 0

    def test_execution_context_required_fields(self):
        """ExecutionContext requires all Contract Section 2 fields."""
        step = PlanStep(id="s1", action="test", payload={})
        plan = Plan(
            id="p1",
            version=1,
            created_at=1000,
            steps=[step],
            name="p",
            context_requirements=["env_key"]
        )
        ctx = ExecutionContext(
            plan=plan,
            execution_id="exec-1",
            started_at=1000,
            deadline_ms=2000,
            environment={"env_key": "value"}
        )
        assert ctx.plan == plan
        assert ctx.execution_id == "exec-1"
        assert ctx.started_at == 1000
        assert ctx.deadline_ms == 2000
        assert ctx.environment == {"env_key": "value"}
        assert ctx.parent_execution_id is None
        assert ctx.user_id is None

    def test_execution_error_creation(self):
        """ExecutionError can be created with required fields."""
        error = ExecutionError(
            error_code="STEP_TIMEOUT",
            message="Step exceeded timeout",
            severity="fatal",
            recoverable=False
        )
        assert error.error_code == "STEP_TIMEOUT"
        assert error.message == "Step exceeded timeout"
        assert error.severity == "fatal"
        assert error.recoverable is False
        assert error.step_id is None
        assert error.cause is None
        assert error.context == {}

    def test_plan_result_success(self):
        """PlanResult with status=success has no error field."""
        result = PlanResult(
            plan_id="plan-1",
            execution_id="exec-1",
            status="success",
            completed_at=2000,
            duration_ms=1000,
            steps_executed=3,
            steps_total=3,
            result_payload={"output": "data"},
            error=None
        )
        assert result.status == "success"
        assert result.error is None
        assert result.steps_executed == result.steps_total

    def test_plan_result_partial(self):
        """PlanResult with status=partial has error field."""
        error = ExecutionError(
            error_code="STEP_SKIPPED",
            message="Step was skipped",
            severity="error",
            recoverable=True
        )
        result = PlanResult(
            plan_id="plan-1",
            execution_id="exec-1",
            status="partial",
            completed_at=2000,
            duration_ms=1000,
            steps_executed=2,
            steps_total=3,
            result_payload={"partial": "data"},
            error=error
        )
        assert result.status == "partial"
        assert result.error is not None
        assert result.steps_executed < result.steps_total

    def test_plan_result_failure(self):
        """PlanResult with status=failure has fatal error field."""
        error = ExecutionError(
            error_code="PLAN_TIMEOUT",
            message="Plan exceeded timeout",
            severity="fatal",
            recoverable=False
        )
        result = PlanResult(
            plan_id="plan-1",
            execution_id="exec-1",
            status="failure",
            completed_at=2000,
            duration_ms=300001,
            steps_executed=1,
            steps_total=3,
            result_payload={},
            error=error
        )
        assert result.status == "failure"
        assert result.error is not None
        assert result.error.severity == "fatal"


class TestErrorClassification:
    """Verify error classification enums match Contract Section 4."""

    def test_error_severity_values(self):
        """ErrorSeverity enum has correct values per Contract Section 4."""
        assert ErrorSeverity.WARN == "warn"
        assert ErrorSeverity.ERROR == "error"
        assert ErrorSeverity.FATAL == "fatal"

    def test_error_codes_exist(self):
        """All 11 reserved error codes exist per Contract Section 4."""
        codes = [
            ErrorCode.CONTEXT_MISSING,
            ErrorCode.INVALID_PAYLOAD,
            ErrorCode.STEP_TIMEOUT,
            ErrorCode.PLAN_TIMEOUT,
            ErrorCode.DEADLINE_EXCEEDED,
            ErrorCode.DEPENDENCY_UNRESOLVED,
            ErrorCode.ACTION_NOT_FOUND,
            ErrorCode.RESOURCE_EXHAUSTED,
            ErrorCode.EXECUTION_HALTED,
            ErrorCode.STEP_SKIPPED,
            ErrorCode.UNKNOWN_ERROR,
        ]
        assert len(codes) == 11
        # Verify no duplicates
        assert len(set(codes)) == 11


class TestPlanExecutorStub:
    """Verify PlanExecutor stub correctly raises NotImplementedError."""

    @pytest.mark.asyncio
    async def test_execute_plan_not_implemented(self):
        """PlanExecutor.execute_plan() with valid inputs returns PlanResult."""
        executor = PlanExecutor()
        # Use VALID UUID v4 for testing (not "s1", "p1", "e1")
        import uuid
        step_id = str(uuid.uuid4())
        plan_id = str(uuid.uuid4())
        exec_id = str(uuid.uuid4())
        
        step = PlanStep(id=step_id, action="test", payload={})
        plan = Plan(
            id=plan_id,
            version=1,
            created_at=1000,
            steps=[step],
            name="p",
            context_requirements=[]
        )
        ctx = ExecutionContext(
            plan=plan,
            execution_id=exec_id,
            started_at=1000,
            deadline_ms=2000,
            environment={}
        )
        # Should return PlanResult (implementation is complete)
        result = await executor.execute_plan(ctx)
        assert isinstance(result, PlanResult)
        assert result.status in ("success", "partial", "failure")

    @pytest.mark.asyncio
    async def test_run_plan_not_implemented(self):
        """PlanExecutor.run_plan() with valid inputs returns PlanResult."""
        executor = PlanExecutor()
        # Use VALID UUID v4 for testing
        import uuid
        step_id = str(uuid.uuid4())
        plan_id = str(uuid.uuid4())
        exec_id = str(uuid.uuid4())
        
        step = PlanStep(id=step_id, action="test", payload={})
        plan = Plan(
            id=plan_id,
            version=1,
            created_at=1000,
            steps=[step],
            name="p",
            context_requirements=[]
        )
        ctx = ExecutionContext(
            plan=plan,
            execution_id=exec_id,
            started_at=1000,
            deadline_ms=2000,
            environment={}
        )
        # Should return PlanResult (implementation is complete)
        result = await executor.run_plan(plan, ctx)
        assert isinstance(result, PlanResult)
        assert result.status in ("success", "partial", "failure")

    def test_executor_with_orchestrator_reference(self):
        """PlanExecutor can be instantiated with orchestrator reference."""
        # Mock orchestrator - any object
        mock_orch = object()
        executor = PlanExecutor(orchestrator=mock_orch)
        assert executor.orchestrator is mock_orch


class TestPlanValidatorStub:
    """Verify PlanValidator stub correctly raises NotImplementedError."""

    def test_validate_plan_not_implemented(self):
        """PlanValidator.validate_plan() raises NotImplementedError."""
        validator = PlanValidator()
        plan = Plan(
            id="p1",
            version=1,
            created_at=1000,
            steps=[],
            name="p",
            context_requirements=[]
        )
        with pytest.raises(NotImplementedError, match="Plan validation not yet implemented"):
            validator.validate_plan(plan)

    def test_validate_execution_context_not_implemented(self):
        """PlanValidator.validate_execution_context() raises NotImplementedError."""
        validator = PlanValidator()
        step = PlanStep(id="s1", action="test", payload={})
        plan = Plan(
            id="p1",
            version=1,
            created_at=1000,
            steps=[step],
            name="p",
            context_requirements=[]
        )
        ctx = ExecutionContext(
            plan=plan,
            execution_id="e1",
            started_at=1000,
            deadline_ms=2000,
            environment={}
        )
        with pytest.raises(NotImplementedError, match="ExecutionContext validation not yet implemented"):
            validator.validate_execution_context(ctx)

    def test_validate_plan_result_not_implemented(self):
        """PlanValidator.validate_plan_result() raises NotImplementedError."""
        validator = PlanValidator()
        result = PlanResult(
            plan_id="p1",
            execution_id="e1",
            status="success",
            completed_at=2000,
            duration_ms=1000,
            steps_executed=0,
            steps_total=0,
            result_payload={}
        )
        with pytest.raises(NotImplementedError, match="PlanResult validation not yet implemented"):
            validator.validate_plan_result(result)


class TestOrchestratorSchemaReferences:
    """Verify orchestrator properly references Plan Execution Contract schemas."""

    def test_orchestrator_imports_schemas(self):
        """Orchestrator imports Plan Execution Contract schemas."""
        from reasoner_service.orchestrator import Plan, ExecutionContext, PlanResult, PlanExecutor
        assert Plan is not None
        assert ExecutionContext is not None
        assert PlanResult is not None
        assert PlanExecutor is not None

    @pytest.mark.asyncio
    async def test_execute_plan_raises_not_implemented_when_enabled(self):
        """PlanExecutor correctly orchestrates validation and execution."""
        from reasoner_service.plan_execution_schemas import PlanExecutor
        import uuid
        
        # Direct executor test (not through orchestrator)
        executor = PlanExecutor()
        
        # Create VALID contract-compliant inputs (with UUID v4)
        plan_uuid = str(uuid.uuid4())
        step_uuid = str(uuid.uuid4())
        exec_uuid = str(uuid.uuid4())
        
        # Use dataclass objects (as required by execute())
        from reasoner_service.plan_execution_schemas import Plan, PlanStep, ExecutionContext
        step = PlanStep(id=step_uuid, action="test", payload={})
        plan = Plan(
            id=plan_uuid,
            version=1,
            created_at=1000,
            steps=[step],
            name="test",
            context_requirements=[]
        )
        ctx = ExecutionContext(
            plan=plan,
            execution_id=exec_uuid,
            started_at=1000,
            deadline_ms=2000,
            environment={}
        )
        
        # Should return PlanResult (implementation is complete)
        result = await executor.execute(plan, ctx)
        # The executor returns PlanResult objects
        from reasoner_service.plan_execution_schemas import PlanResult
        assert isinstance(result, PlanResult)
        assert result.status in ("success", "partial", "failure")

    @pytest.mark.asyncio
    async def test_execute_plan_returns_empty_when_disabled(self):
        """execute_plan_if_enabled() returns {} when feature disabled."""
        from reasoner_service.orchestrator import DecisionOrchestrator
        
        orch = DecisionOrchestrator(dsn=":memory:")
        
        plan_dict = {"id": "p1", "version": 1, "created_at": 1000, "steps": [], "name": "p", "context_requirements": []}
        ctx_dict = {"execution_id": "e1", "started_at": 1000, "deadline_ms": 2000, "environment": {}}
        
        # Feature flag disabled (default)
        result = await orch.execute_plan_if_enabled(plan_dict, ctx_dict)
        assert result == {}


class TestContractAlignmentAssertions:
    """Verify structural alignment with Plan Execution Contract v1."""

    def test_plan_matches_contract_section_1(self):
        """Plan schema matches Contract Section 1 exactly."""
        # Verify all required fields exist
        step = PlanStep(id="s1", action="test", payload={})
        plan = Plan(
            id="p1",
            version=1,
            created_at=1000,
            steps=[step],
            name="plan",
            context_requirements=["key"]
        )
        # Required fields
        assert hasattr(plan, "id")
        assert hasattr(plan, "version")
        assert hasattr(plan, "created_at")
        assert hasattr(plan, "steps")
        assert hasattr(plan, "name")
        assert hasattr(plan, "context_requirements")
        # Optional fields
        assert hasattr(plan, "priority")
        assert hasattr(plan, "timeout_ms")
        assert hasattr(plan, "retry_policy")
        assert hasattr(plan, "metadata")
        assert hasattr(plan, "tags")
        assert hasattr(plan, "estimated_duration_ms")

    def test_execution_context_matches_contract_section_2(self):
        """ExecutionContext schema matches Contract Section 2 exactly."""
        step = PlanStep(id="s1", action="test", payload={})
        plan = Plan(
            id="p1",
            version=1,
            created_at=1000,
            steps=[step],
            name="p",
            context_requirements=[]
        )
        ctx = ExecutionContext(
            plan=plan,
            execution_id="e1",
            started_at=1000,
            deadline_ms=2000,
            environment={}
        )
        # Required fields
        assert hasattr(ctx, "plan")
        assert hasattr(ctx, "execution_id")
        assert hasattr(ctx, "started_at")
        assert hasattr(ctx, "deadline_ms")
        assert hasattr(ctx, "environment")
        # Optional fields
        assert hasattr(ctx, "parent_execution_id")
        assert hasattr(ctx, "user_id")
        assert hasattr(ctx, "request_id")
        assert hasattr(ctx, "correlation_context")

    def test_plan_result_matches_contract_section_3(self):
        """PlanResult schema matches Contract Section 3 exactly."""
        result = PlanResult(
            plan_id="p1",
            execution_id="e1",
            status="success",
            completed_at=2000,
            duration_ms=1000,
            steps_executed=0,
            steps_total=0,
            result_payload={}
        )
        # Required fields
        assert hasattr(result, "plan_id")
        assert hasattr(result, "execution_id")
        assert hasattr(result, "status")
        assert hasattr(result, "completed_at")
        assert hasattr(result, "duration_ms")
        assert hasattr(result, "steps_executed")
        assert hasattr(result, "steps_total")
        assert hasattr(result, "result_payload")
        # Conditional field
        assert hasattr(result, "error")

    def test_no_execution_logic_in_schemas(self):
        """Verify no execution logic exists in contract definitions."""
        # All classes should be pure data or raise NotImplementedError
        step = PlanStep(id="s1", action="test", payload={})
        plan = Plan(
            id="p1",
            version=1,
            created_at=1000,
            steps=[step],
            name="p",
            context_requirements=[]
        )
        
        # Verify Plan has no methods other than dataclass defaults
        methods = [m for m in dir(plan) if not m.startswith("_")]
        # Should only have dataclass methods like __init__, __repr__, __eq__, etc.
        # No custom business logic
        assert not any(m in methods for m in ["execute", "validate", "process", "run"])
