# Plan Execution Contract (v1)

## Overview

This document defines the strict contract governing plan execution within the ICT Trading System. The contract specifies the structure of plans, the execution context, result formats, and the deterministic rules the orchestrator must follow at each execution outcome state. This is a binding specification, not a guideline.

---

## 1. Plan Object Schema

### Required Fields

| Field | Type | Constraint | Description |
|-------|------|-----------|-------------|
| `id` | `str` | Non-empty UUID v4 | Unique identifier for the plan instance |
| `version` | `int` | ≥ 1 | Schema version; current: 1 |
| `created_at` | `int` | Unix timestamp (ms) | Plan instantiation time (immutable) |
| `steps` | `List[PlanStep]` | Non-empty, ≤ 1024 | Ordered sequence of execution steps |
| `name` | `str` | Non-empty, ≤ 255 chars | Human-readable plan identifier |
| `context_requirements` | `List[str]` | Non-empty | Names of context keys required by this plan |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `priority` | `int` | 0 | Execution priority; higher executes first |
| `timeout_ms` | `int` | 300000 | Maximum execution duration in milliseconds |
| `retry_policy` | `RetryPolicy` | See 1.1 | Retry configuration for failed steps |
| `metadata` | `Dict[str, Any]` | {} | User-defined auxiliary data (not interpreted by executor) |
| `tags` | `List[str]` | [] | Classification labels for filtering/audit |
| `estimated_duration_ms` | `int` | null | Best-effort execution estimate |

### RetryPolicy Sub-Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_attempts` | `int` | 1 | Total attempts per step (1 = no retry) |
| `backoff_ms` | `int` | 0 | Base delay between retries (ms) |
| `backoff_multiplier` | `float` | 1.0 | Exponential backoff factor (≥ 1.0) |
| `max_backoff_ms` | `int` | 60000 | Maximum retry delay (ms) |
| `retryable_error_codes` | `List[str]` | [] | Error codes eligible for retry |

### PlanStep Sub-Schema

| Field | Type | Constraint | Description |
|-------|------|-----------|-------------|
| `id` | `str` | Non-empty UUID v4 | Step identifier (unique within plan) |
| `action` | `str` | Non-empty, ≤ 100 chars | Action type (e.g., "validate", "execute", "notify") |
| `payload` | `Dict[str, Any]` | Required, can be {} | Action parameters |
| `depends_on` | `List[str]` | Default: [] | IDs of steps that must complete before this one |
| `on_failure` | `str` | One of: `halt`, `skip`, `retry` | Behavior when step fails |
| `timeout_ms` | `int` | null | Step-level timeout override (ms); inherits plan timeout if null |

---

## 2. ExecutionContext Schema

The ExecutionContext is the immutable read-only environment provided to the executor for plan execution.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `plan` | `Plan` | The Plan object being executed (immutable) |
| `execution_id` | `str` | Unique execution session identifier (UUID v4) |
| `started_at` | `int` | Execution start timestamp (Unix ms) |
| `deadline_ms` | `int` | Absolute deadline timestamp (Unix ms); plan must complete before this |
| `environment` | `Dict[str, Any]` | Runtime environment variables and configuration |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `parent_execution_id` | `str` (UUID v4) | Parent execution ID if this is a nested plan execution |
| `user_id` | `str` | User or system that initiated execution |
| `request_id` | `str` | Correlated request identifier for tracing |
| `correlation_context` | `Dict[str, str]` | Arbitrary key-value pairs for cross-system correlation |

### ExecutionContext Constraints

- **Immutability**: Executor must not modify any field in ExecutionContext
- **Duration**: `deadline_ms - started_at` must equal or exceed plan's `timeout_ms`
- **Environment Isolation**: Executor operates exclusively within provided environment; no access to system state outside this context
- **Environment Opacity**: The orchestrator MUST NOT validate, mutate, or interpret environment contents. The environment is opaque and treated as a black box by the orchestrator. All environment semantics are owned by the executor.

---

## 3. PlanResult Schema

The PlanResult describes the terminal outcome of plan execution.

### Result Object Structure

| Field | Type | Constraint | Required | Description |
|-------|------|-----------|----------|-------------|
| `plan_id` | `str` | UUID v4 | Yes | ID of the executed plan |
| `execution_id` | `str` | UUID v4 | Yes | Unique execution session identifier |
| `status` | `str` | One of: `success`, `partial`, `failure` | Yes | Terminal execution state |
| `completed_at` | `int` | Unix timestamp (ms) | Yes | Execution completion time |
| `duration_ms` | `int` | Non-negative | Yes | Total execution duration |
| `steps_executed` | `int` | 0 to plan.steps.length | Yes | Count of completed steps |
| `steps_total` | `int` | Equal to plan.steps.length | Yes | Total steps in plan |
| `result_payload` | `Dict[str, Any]` | Unrestricted | Yes | Executor-generated output data |
| `error` | `ExecutionError` | See 3.1 | Conditional | Present if status is `partial` or `failure` |

### Status Definitions

- **`success`**: All steps completed and no errors occurred
- **`partial`**: Some steps completed; execution halted due to non-fatal error(s) or step skipping; plan achieved partial objectives
- **`failure`**: Execution could not proceed; plan objectives not met; fatal error or early termination

### ExecutionError Sub-Schema

| Field | Type | Constraint | Description |
|-------|------|-----------|-------------|
| `error_code` | `str` | Non-empty, ≤ 50 chars | Machine-readable error classification |
| `message` | `str` | ≤ 1000 chars | Human-readable error description |
| `step_id` | `str` (UUID v4) | null if plan-level error | ID of step where error occurred |
| `severity` | `str` | One of: `warn`, `error`, `fatal` | Error magnitude (see Section 4) |
| `recoverable` | `bool` | Derived from severity | Whether orchestrator may retry/recover |
| `cause` | `ExecutionError` | null | Nested error if chained |
| `context` | `Dict[str, Any]` | Default: {} | Error diagnostic data |

---

## 4. Error Classification

Errors are classified by severity and recoverability. This classification determines orchestrator behavior.

### Error Severity Levels

| Severity | Recoverable | Description | Orchestrator Response |
|----------|-------------|-------------|----------------------|
| `warn` | Yes | Non-critical issue; execution continues | Log warning; continue execution |
| `error` | Yes | Step-level failure; plan may continue per on_failure policy | Apply step on_failure policy |
| `fatal` | No | System-level failure; plan cannot continue | Halt execution; transition to failure |

### Recoverability Matrix

| Condition | Recoverable | Non-Recoverable |
|-----------|-------------|-----------------|
| Context requirement missing | ✗ | ✓ (fatal) |
| Step timeout exceeded | ✓ if retryable | ✗ if non-retryable (fatal) |
| Dependency resolution failed | ✗ | ✓ (fatal) |
| Execution deadline exceeded | ✗ | ✓ (fatal) |
| Payload validation failed | ✗ | ✓ (fatal) |
| Action handler missing | ✗ | ✓ (fatal) |
| Step logic error (non-system) | ✓ if on_failure permits | ✗ if on_failure = halt |
| Resource exhaustion | Depends on resource type | May be fatal |

### Error Code Registry

The following error codes are reserved and must be used by the executor:

| Error Code | Severity | Meaning |
|------------|----------|---------|
| `CONTEXT_MISSING` | fatal | Required context key not provided |
| `INVALID_PAYLOAD` | fatal | Step payload fails schema validation |
| `STEP_TIMEOUT` | error/fatal | Step exceeded timeout_ms |
| `PLAN_TIMEOUT` | fatal | Plan exceeded plan.timeout_ms |
| `DEADLINE_EXCEEDED` | fatal | Execution exceeded context.deadline_ms |
| `DEPENDENCY_UNRESOLVED` | fatal | Step dependency not found or failed |
| `ACTION_NOT_FOUND` | fatal | Step action handler not registered |
| `RESOURCE_EXHAUSTED` | fatal | Executor resource limit exceeded |
| `EXECUTION_HALTED` | error | Execution stopped by explicit halt |
| `STEP_SKIPPED` | warn | Step skipped per on_failure policy |
| `UNKNOWN_ERROR` | fatal | Unclassified error |

---

## 5. Orchestrator Deterministic Rules

The orchestrator is a deterministic state machine. For each outcome state, the orchestrator must execute the specified rules in the order given. No discretion is permitted.

### 5.0 Event Emission Guarantees

- Event emission (completion, partial, failure events) MUST be best-effort and non-blocking
- Failure to emit events MUST NOT change PlanResult status or outcome
- Execution MUST NOT be retried or halted due to event emission failure
- Event delivery is decoupled from execution completion; absence of event receipt does not invalidate execution result

### 5.1 Rule Set: Plan Succeeds (status = `success`)

**Preconditions:**
- All steps executed without error
- No error field present in ExecutionContext
- `steps_executed == steps_total`

**Mandatory Actions (in order):**

1. **Validate Completion**: Assert that all plan steps completed and no errors occurred
2. **Capture Metadata**: Record `completed_at` as current timestamp, calculate `duration_ms`
3. **Set Success Status**: `status = "success"`, `error = null`
4. **Persist Result**: Write PlanResult to persistent storage with status=success
5. **Emit Completion Event**: Dispatch `plan_execution_success` event with result payload
6. **Update Plan State**: Mark plan as completed in plan registry
7. **Release Resources**: Free any resources allocated to this execution context
8. **Return Result**: Return complete PlanResult to caller with status=success

**Postconditions:**
- PlanResult is immutable; no further modifications permitted
- Plan transitions to terminal state in all downstream systems
- No retry logic is invoked
- Caller may safely assume all objectives achieved

---

### 5.2 Rule Set: Plan Partially Succeeds (status = `partial`)

**Preconditions:**
- One or more steps failed but did not halt execution
- Step failure triggered `on_failure = skip` or `on_failure = retry` and retry exhausted
- At least one step completed: `steps_executed >= 1`
- Some objectives achieved; some incomplete

**Mandatory Actions (in order):**

1. **Classify Failure**: Identify failed step(s) and non-fatal error(s)
2. **Aggregate Errors**: Collect all errors in execution trace; set `error` field to primary error
3. **Validate Partial Progress**: Assert `steps_executed < steps_total` and `steps_executed >= 1`
4. **Preserve Output**: Retain all result data from successfully completed steps
5. **Capture Metadata**: Record `completed_at`, calculate `duration_ms`, set `steps_executed` count
6. **Set Partial Status**: `status = "partial"`, include primary error in `error` field
7. **Persist Result**: Write PlanResult to persistent storage with status=partial and error details
8. **Emit Partial Event**: Dispatch `plan_execution_partial` event with result and error context
9. **Mark Incomplete**: Record which steps did not complete in audit trail
10. **Return Result**: Return complete PlanResult to caller with status=partial

**Postconditions:**
- PlanResult contains error details in `error` field
- Caller may partially use result_payload from completed steps
- Plan transitions to terminal state; MUST NOT be resumed or retried by the orchestrator
- Any future execution MUST require a new execution_id and new plan instance
- Caller MUST explicitly initiate new plan execution; orchestrator provides no resume capability

---

### 5.3 Rule Set: Plan Fails (status = `failure`)

**Preconditions:**
- Execution encountered fatal error OR
- Step failure triggered `on_failure = halt` OR
- Execution deadline exceeded OR
- Plan timeout exceeded OR
- Critical context requirement unmet

**Mandatory Actions (in order):**

1. **Identify Failure Cause**: Determine root error: fatal error code, missing context, timeout, halt signal
2. **Classify Severity**: Assert that error severity = `fatal` or flow violates contract
3. **Halt Execution**: Stop any in-flight operations immediately
4. **Capture Failure Context**: Record which step(s) failed, error message, error code, timestamp
5. **Truncate Result**: Preserve only successfully completed step results; discard incomplete state
6. **Validate Consistency**: Assert `steps_executed < steps_total` or `steps_executed == 0`
7. **Set Error**: Populate `error` field with ExecutionError containing code, message, severity=fatal
8. **Set Failure Status**: `status = "failure"`, `error` field must be non-null
9. **Persist Result**: Write PlanResult to persistent storage with status=failure and full error trace
10. **Emit Failure Event**: Dispatch `plan_execution_failure` event with error details
11. **Release Resources**: Free all execution resources; clean up any temporary state
12. **Notify Error Handler**: Signal fatal error to error handler if configured
13. **Return Result**: Return complete PlanResult to caller with status=failure

**Postconditions:**
- PlanResult contains fatal error in `error` field
- `result_payload` contains only successfully completed step results (may be partial or empty)
- Plan transitions to failed state; eligible for manual remediation or deletion only
- Automatic retry is prohibited; caller must initiate new plan execution
- All allocated resources are released; no cleanup required by caller

---

## 6. Explicit Non-Goals and Out-of-Scope Behaviors

The following behaviors are **explicitly out-of-scope** and must not be implemented in the orchestrator:

### 6.1 Automatic Retry at Plan Level

- The orchestrator does not automatically retry failed plans
- Retry logic operates only at the step level (via `RetryPolicy`) within a single plan execution
- Plan-level retry must be initiated by external caller or policy engine

### 6.2 Plan Modification During Execution

- Plans cannot be modified after instantiation
- Step insertion, removal, or reordering during execution is prohibited
- Payload modifications mid-execution are prohibited
- Any attempt to modify a plan in-flight results in fatal error and plan termination

### 6.3 Dynamic Dependency Resolution

- Dependencies are static and defined at plan creation time
- Circular dependency detection is a validation concern, not a runtime concern
- Executor does not compute implicit dependencies or optimize step ordering
- If circular dependency exists, plan validation must reject it pre-execution

### 6.4 Resource Provisioning or Allocation

- Orchestrator does not allocate compute resources (CPU, memory, storage)
- Resource limits are advisory; executor must operate within configured limits
- Out-of-memory or resource exhaustion results in fatal error; no graceful degradation

### 6.5 Nested Plan Execution (Auto-Expansion)

- Plans cannot spawn child plans automatically
- If a step requires plan execution, that must be handled via explicit `action = "execute_plan"` step
- Nested execution does not imply transaction-like guarantees across plan boundaries

### 6.6 Distributed Consensus or Checkpointing

- Executor does not support distributed consensus for step outcomes
- No checkpointing mechanism for mid-execution resume
- Execution state is maintained in-memory only during active execution
- After termination, execution state is immutable in result record

### 6.7 Custom Logging or Observability

- Orchestrator does not implement logging; all diagnostics must be captured in `ExecutionError.context`
- Observability (metrics, traces, spans) is caller's responsibility
- Error context is the sole mechanism for diagnostic data

### 6.8 Step Output Chaining (Parameter Substitution)

- Step results cannot be automatically fed into subsequent step payloads
- Each step receives only its defined payload from the plan
- If step A output should inform step B, that must be embedded in the plan definition, not inferred by executor
- Orchestrator does not perform variable substitution or output chaining

### 6.9 Soft Timeouts or Graceful Degradation

- Timeouts are hard stops; no graceful degradation permitted
- Step exceeds `timeout_ms` → immediate error (not warning)
- Plan exceeds `plan.timeout_ms` → immediate termination (not pause)
- No timeout recovery or escalation; only retry per `RetryPolicy`

### 6.10 Conditional Logic or Branching

- Steps execute in dependency order; no if/then/else branching
- `on_failure` policies are fixed at plan definition time (not conditional)
- Orchestrator does not evaluate runtime conditions to determine step execution
- Complex branching must be modeled as multiple independent plans or managed externally

### 6.11 Partial Retry (Replay)

- Failed plans cannot be resumed from the failure point
- Partial execution cannot be "replayed" with the same execution_id
- New plan execution requires new execution_id and new plan instance
- Caller must manually reconstruct partial results if needed

### 6.12 Plan Versioning or Evolution

- Plans are immutable; no version migration during execution
- Schema version is fixed at plan creation
- If plan schema must change, new plan instance with new version must be created
- Executor does not perform backwards compatibility translation

### 6.13 Cross-Plan Dependencies or Orchestration

- Orchestrator manages single plan execution only
- No multi-plan sequencing, batching, or inter-plan synchronization
- Each plan is independent; no shared state between concurrent plans
- Plan coordination (if needed) is external caller's responsibility

### 6.14 Execution Cancellation or Interruption

- Once execution begins, it cannot be cancelled mid-stream
- Only action available is to await completion or force timeout
- Graceful cancellation is not supported

### 6.15 Plan Caching or Memoization

- Identical plans are not deduplicated or cached
- Executor does not assume plan re-execution yields same result
- Each execution is treated as independent, even for identical plan definitions

### 6.16 Step Semantics and Execution Logic

- The orchestrator does NOT interpret, validate, or execute step logic
- Step semantics (action types, payload interpretation, execution behavior) are owned entirely by the executor
- The orchestrator reacts only to terminal execution outcomes (success, partial, failure) from the executor
- The orchestrator MUST NOT make decisions based on step content, payload structure, or action type
- Step-level retry logic and on_failure policies are executor concerns; orchestrator only enforces plan-level lifecycle rules

---

## 7. Compliance and Amendments

### Compliance Requirements

- All executor implementations must comply with this contract in totality
- Non-compliance with any rule in Sections 5.1, 5.2, or 5.3 constitutes a critical bug
- Non-compliance with non-goals (Section 6) may result in undefined behavior

### Amendment Process

- This contract is versioned (current: v1)
- Future amendments require version increment and explicit migration path
- Backwards incompatibility must be documented and justified

---

## Appendix: Schema Validation Rules

### Plan Validation (Pre-Execution)

- All required fields in Plan, PlanStep, RetryPolicy must be present
- `plan.id`, all `step.id` must be valid UUID v4
- `plan.steps` must be non-empty and acyclic (no circular dependencies)
- `plan.context_requirements` must be non-empty
- Each step's `depends_on` must reference valid step IDs or be empty
- `on_failure` must be one of: `halt`, `skip`, `retry`
- Timestamp fields must be positive integers (Unix milliseconds)

### ExecutionContext Validation (Pre-Execution)

- All required fields must be present
- `context.deadline_ms > context.started_at`
- `context.deadline_ms - context.started_at >= plan.timeout_ms`
- All context requirements from plan must exist in `environment`

### PlanResult Validation (Post-Execution)

- `plan_id`, `execution_id` must be valid UUID v4
- `status` must be one of: `success`, `partial`, `failure`
- If `status = success`, `error` must be null
- If `status = partial` or `failure`, `error` must be non-null
- `steps_executed <= steps_total`
- `duration_ms` must be non-negative
- `completed_at >= started_at` (from ExecutionContext)

---

**Document Version:** 1.0  
**Last Updated:** December 18, 2025  
**Status:** Active and Binding
