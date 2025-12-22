# ICT AI Trading System: Complete Architecture & Implementation Guide

**Version:** 1.0.0  
**Date:** December 21, 2025  
**Status:** Production Ready  
**Test Coverage:** 653/653 tests passing (100%)  

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [The 10-Phase Model](#the-10-phase-model)
4. [Core Components](#core-components)
5. [Data Flow & Execution Order](#data-flow--execution-order)
6. [Core Invariants & Constraints](#core-invariants--constraints)
7. [Setup & Configuration](#setup--configuration)
8. [Running & Testing](#running--testing)
9. [Deployment Guide](#deployment-guide)
10. [Troubleshooting & Safety](#troubleshooting--safety)
11. [Authority Boundary](#authority-boundary)
12. [API Reference](#api-reference)

---

## Executive Summary

The **ICT AI Trading System** is a production-grade, event-driven trading intelligence platform that operates in **shadow-mode**: it analyzes market data and trading decisions but **never executes trades** and has **zero authority over execution**.

### Key Characteristics

| Property | Value |
|----------|-------|
| **Authority Model** | Non-authoritative (shadow-mode, read-only analysis) |
| **Default Behavior** | Fail-closed (absence of approval = no execution) |
| **Audit Model** | Append-only, immutable records |
| **Data Isolation** | Deep copy protection (no mutations) |
| **Error Handling** | Fail-silent (never crash, always return safe default) |
| **Test Coverage** | 653/653 tests passing |
| **Deployment** | Docker, Kubernetes, or standalone Python |

### Core Promise

```
This system will:
✅ Analyze trading signals and decisions
✅ Evaluate governance rules
✅ Provide historical insights
✅ Record all decisions immutably
✅ Never execute trades
✅ Never block decisions (has zero enforcement authority)
✅ Never modify audit records
```

---

## System Architecture

### Layered Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL INTERFACES                             │
│              (HTTP Webhooks, Notifications, APIs)                  │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│              ORCHESTRATION LAYER (Layer 5)                          │
│  • DecisionOrchestrator (event router & aggregator)                │
│  • ReasoningManager (bounded reasoning, time-constrained)          │
│  • PolicyStore (pluggable policy backends)                         │
│  • Event deduplication, metrics, notifications                     │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│        SHADOW-MODE INTELLIGENCE LAYER (Phases 7-10)                │
│  • 7 analysis services (informational, non-authoritative)          │
│  • DecisionTimelineService, TradeGovernanceService                 │
│  • PolicyConfidenceEvaluator, OutcomeAnalyticsService              │
│  • CounterfactualEnforcementSimulator                              │
│  • DecisionIntelligenceReportService, Archive Service              │
│  • DecisionTrustCalibrationService (Phase 10)                      │
│                                                                    │
│  ⚠️  CRITICAL: All outputs are INFORMATIONAL ONLY                  │
│  ⚠️  CRITICAL: Zero enforcement capability                         │
│  ⚠️  CRITICAL: All data deepcopy-protected                         │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│          EXECUTION BOUNDARY LAYER (Standalone Module)              │
│  • ExecutionIntent (human-authored trading action)                 │
│  • HumanExecutionApproval (explicit human authorization)           │
│  • KillSwitchController (emergency halt mechanism)                 │
│  • ExecutionAuditLogger (append-only audit trail)                  │
│  • SafetyGuards (6 validation checks, fail-closed)                │
│                                                                    │
│  🔒 CRITICAL: COMPLETELY ISOLATED from shadow-mode                │
│  🔒 CRITICAL: Default = DENY (no approval = no execution)         │
│  🔒 CRITICAL: All decisions immutably logged                       │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│              STATE & PERSISTENCE LAYER (Layer 3)                   │
│  • SQLAlchemy async ORM models                                     │
│  • Decision (trading decision record)                              │
│  • DecisionOutcome (trade result)                                  │
│  • Append-only archive semantics                                   │
│  • Optional Redis cache (with circuit-breaker fallback)            │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│              DATABASE & CACHE LAYER (Layer 2)                      │
│  • PostgreSQL / SQLite (async drivers)                             │
│  • Redis (optional, with graceful fallback)                        │
│  • Append-only write semantics                                     │
│  • Full query capability on historical data                        │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│              NOTIFICATION LAYER (Layer 1)                          │
│  • Slack, Discord, Telegram channels                               │
│  • Multi-channel fanout                                            │
│  • Configurable filtering (info|warn|all)                          │
│  • Non-blocking, best-effort delivery                              │
└────────────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram

```
EXTERNAL SOURCE (webhook, API, market feed)
  ↓
┌─────────────────────────────────────────┐
│ Event Validation                        │
│ • Schema validation (Pydantic)          │
│ • Deduplication check (hash-based)      │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│ Policy Constraint Check                 │
│ • Event-type cooldown (rate limiting)   │
│ • Session windows (time-based gates)    │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│ ReasoningManager (Bounded)              │
│ • Time-constrained (configurable ms)    │
│ • Non-throwing error handling           │
│ • Returns AdvisorySignal                │
│ • Payload validated                     │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│ Shadow-Mode Services (Read-Only Analysis)
│ • Analyze signals, governance, outcomes │
│ • Compute trust metrics                 │
│ • Generate reports                      │
│ • Deepcopy all data                     │
│ • Never modify state                    │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│ Signal Filtering                        │
│ • Apply policy-based filters            │
│ • Per-event-type filtering              │
│ • Audit trail of filtered signals       │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│ Persistence (Append-Only)               │
│ • Insert Decision record (SQLAlchemy)   │
│ • Compute decision hash                 │
│ • No updates, only inserts              │
│ • Redis cache (optional, with fallback) │
│ • DLQ fallback if persistence fails     │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│ Multi-Channel Notifications             │
│ • Slack, Discord, Telegram              │
│ • Non-blocking, concurrent              │
│ • Respects NOTIFY_LEVEL filter          │
│ • Full error logging                    │
└────────────┬────────────────────────────┘
             ↓
RESPONSE: EventResult
  • Correlation ID
  • Event state (pending/processed/deferred/escalated)
  • Processing time
  • Policy decisions (audit trail)
```

---

## The 10-Phase Model

The system is organized into 10 complete phases, each representing a distinct capability layer.

### Phase 1: Foundational Read-Only Architecture
**Purpose:** Establish the principle that the system will never execute trades, only analyze.

**Components:**
- Event ingestion (webhooks, APIs)
- Schema validation (Pydantic)
- Non-blocking processing

**Safety Property:** Zero execution capability

---

### Phase 2: Immutable Intent Tracking
**Purpose:** Record all decisions immutably; no retroactive modification.

**Components:**
- Decision ORM model (append-only semantics)
- DecisionOutcome model (trade results)
- Deterministic decision hashing

**Safety Property:** Immutable audit trail (no UPDATE/DELETE)

---

### Phase 3: Authority Boundary Definition
**Purpose:** Explicit separation between analysis (shadow-mode) and execution (external responsibility).

**Components:**
- AUTHORITY_BOUNDARY.md (governance document)
- Forbidden field list (explicit constraints)
- Semantic hardening (explicit disclaimers)

**Safety Property:** Clear boundary between read-only analysis and external execution

---

### Phase 4: Data Structure Validation
**Purpose:** All inputs and outputs validated via strict schemas; fail-closed on violation.

**Components:**
- Pydantic schemas (Event, Decision, Outcome, Plan, ExecutionContext)
- Schema validation on ingress
- Type checking throughout
- Deterministic error handling

**Safety Property:** No unvalidated data flows through the system

---

### Phase 5: Explicit Human Oversight
**Purpose:** Reasoning is bounded and time-constrained; humans control execution.

**Components:**
- ReasoningManager (time-bounded reasoning, 500-5000ms configurable)
- ExecutionIntent (explicit human directives)
- HumanExecutionApproval (requires explicit authorization)
- Plan/ExecutionContext/PlanResult contracts
- Fail-closed default (absence of approval = no execution)

**Safety Property:** All execution requires explicit human approval; default = DENY

---

### Phase 6: Audit Trail Implementation
**Purpose:** Append-only persistence of all decisions and outcomes; immutable historical record.

**Components:**
- DecisionIntelligenceArchiveService (append-only archival)
- JSON lines format (streaming, immutable)
- Deterministic read access (deepcopy all outputs)
- Zero-modification guarantee (no UPDATE/DELETE possible)

**Safety Property:** Complete immutable historical record

---

### Phase 7: Trust Calibration Intelligence
**Purpose:** Pure analysis services that evaluate historical signal performance, governance compliance, and outcome patterns.

**Components:**
- DecisionTimelineService (29 tests) - event timeline & replay
- TradeGovernanceService (31 tests) - governance rule evaluation
- PolicyConfidenceEvaluator (21 tests) - policy confidence scoring
- OutcomeAnalyticsService (29 tests) - historical outcome analysis

**Safety Property:** Read-only analysis; informational only; zero enforcement

---

### Phase 8: Decision Governance Framework
**Purpose:** Services that evaluate trades against governance rules and compute compliance metrics.

**Components:**
- TradeGovernanceService (governance violation detection)
- PolicyConfidenceEvaluator (policy performance assessment)
- Compliance rule evaluation (no execution capability)

**Safety Property:** Purely informational governance analysis

---

### Phase 9: Failure Mode Analysis
**Purpose:** What-if analysis and counterfactual simulation (what would have happened if...).

**Components:**
- CounterfactualEnforcementSimulator (25 tests) - enforcement scenario simulation
- Regret analysis (simulated vs. actual outcomes)
- Hypothetical enforcement impact

**Safety Property:** Purely informational simulation; never executes enforcement

---

### Phase 10: Production Readiness Hardening
**Purpose:** Comprehensive trust calibration metrics and semantic hardening.

**Components:**
- DecisionTrustCalibrationService (52 tests) - historical trust metrics
  - Signal consistency analysis (informational only)
  - Policy violation patterns (informational only)
  - Reviewer alignment metrics (informational only)
  - Stability and decay analysis (informational only)
- DecisionIntelligenceReportService (27 tests) - comprehensive reporting
- DecisionIntelligenceArchiveService (26 tests) - append-only persistence

**Phase 10 Guarantees:**
- All outputs include explicit disclaimers: "Informational analysis only"
- Zero authority over trading decisions
- Deepcopy protection (all inputs/outputs copied)
- Fail-silent behavior (never raise exceptions)
- Deterministic output (same input = same output)

---

### Phase 10.1: Semantic Hardening (NEW)
**Purpose:** Zero-logic-change documentation hardening to eliminate implicit authority leakage.

**Status:** ✅ Complete (December 20, 2025)

**Changes Made:**
- Strengthened all docstrings with explicit ⚠️ AUTHORITY WARNING sections
- Enhanced core disclaimers in all services
- Added explicit non-authority warnings to 8 private helper methods
- Banned keywords properly managed (execute, block, recommend, rank, optimize, weight, enforce, score)
- All 653 tests pass identically (zero behavior change)

**Safety Guarantee:** Explicit semantic barriers against authority leakage

---

## Core Components

### 1. DecisionOrchestrator (1,397 lines)

**Responsibility:** Central event router and aggregator; coordinates all services.

**Interfaces:**
```python
async def handle_event(event: Event) -> EventResult:
    """
    Main entry point. Routes event through all services and returns result.
    
    Steps:
    1. Validate event schema (Pydantic)
    2. Check deduplication (hash-based)
    3. Check event constraints (cooldown, session window)
    4. Invoke ReasoningManager (if enabled)
    5. Apply signal filters
    6. Persist Decision record (DB + Redis)
    7. Notify channels (Slack/Discord/Telegram)
    8. Return EventResult
    """
```

**Key Properties:**
- **Non-blocking:** Persistence failures fall back to in-memory DLQ
- **Observable:** Comprehensive metrics (decisions_processed_total, etc.)
- **Configurable:** Cooldowns, session windows, policy backends
- **Redis-aware:** Optional caching with graceful circuit-breaker fallback
- **Fail-safe:** DLQ retry mechanism for failed persistence

**Policy Store:**
```python
class PolicyStore:
    """
    Pluggable policy backend system with chained fallback.
    
    Backends tried in order:
    1. OrchestratorConfigBackend (orchestrator config)
    2. HTTPBackend (external HTTP service)
    3. RedisBackend (distributed cache)
    4. DefaultPolicyBackend (sensible defaults)
    
    First backend to return non-empty dict wins.
    """
```

---

### 2. ReasoningManager (bounded reasoning)

**Responsibility:** Time-bounded, stateless reasoning with automatic fallback.

**Interfaces:**
```python
async def reason(
    request: ReasoningRequest,
    mode: str = "default",
    timeout_ms: int = 500
) -> AdvisorySignal:
    """
    Bounded reasoning with time limit and non-throwing error handling.
    
    Modes:
    - "default": Standard reasoning
    - "action_suggestion": Suggest possible actions
    - "risk_flagging": Flag potential risks
    
    Returns AdvisorySignal (never raises exceptions).
    """
```

**Key Properties:**
- **Time-bounded:** Configurable timeout (default 500ms, max 5000ms)
- **Non-throwing:** All exceptions wrapped in AdvisorySignal
- **Stateless:** Request isolation; zero accumulated state
- **Confidence-validated:** All outputs must have confidence ∈ [0.0, 1.0]
- **Deterministic:** Same input = same output
- **Fallback:** Deterministic fallback if reasoning fails

---

### 3. Shadow-Mode Services (Phases 7-10)

**Collective Responsibility:** Provide pure, informational analysis with zero authority.

**The 7 Services:**

| Phase | Service | Tests | Purpose |
|-------|---------|-------|---------|
| 7 | DecisionTimelineService | 29 | Timeline & event replay |
| 7 | TradeGovernanceService | 31 | Governance rule evaluation |
| 7 | PolicyConfidenceEvaluator | 21 | Policy confidence scoring |
| 7 | OutcomeAnalyticsService | 29 | Historical outcome analysis |
| 8-9 | CounterfactualEnforcementSimulator | 25 | What-if scenario analysis |
| 10 | DecisionIntelligenceReportService | 27 | Comprehensive reporting |
| 10 | DecisionIntelligenceArchiveService | 26 | Append-only archival |
| 10 | DecisionTrustCalibrationService | 52 | Historical trust metrics |

**Universal Properties (All Services):**
- ✅ Read-only analysis (no state mutations)
- ✅ Deepcopy-protected (inputs and outputs)
- ✅ Fail-silent behavior (never raise exceptions)
- ✅ Deterministic output (same input = same output)
- ✅ Explicit disclaimers ("Informational analysis only")
- ✅ Zero execution capability
- ✅ Zero enforcement authority

---

### 4. Execution Boundary Module

**Location:** `/execution_boundary/`  
**Purpose:** Standalone safety layer, completely isolated from shadow-mode.

**Components:**

#### 4.1 ExecutionIntent (execution_models.py)
```python
@dataclass
class ExecutionIntent:
    """
    Human-authored trading action. NEVER INFERRED from shadow-mode outputs.
    
    Fields:
    - intent_id: UUID
    - intent_type: OPEN_POSITION | CLOSE_POSITION | MODIFY_POSITION | 
                   HALT_ALL_TRADING | RESUME_TRADING | MANUAL_OVERRIDE
    - status: PENDING_APPROVAL | APPROVED | REJECTED | EXECUTED | FAILED
    - symbol: Trading symbol (e.g., "AAPL")
    - quantity: Position size
    - price: Limit price (if applicable)
    - order_type: MARKET | LIMIT | STOP
    - human_rationale: Required human explanation (NOT inferred)
    - risk_limits: max_loss, max_position_size, required_profit_margin
    - expires_at: Expiration time
    - metadata: User-defined auxiliary data
    
    Key Invariant:
    - human_rationale is REQUIRED and must be human-authored
    - This intent is NOT derived from shadow-mode metrics
    """
```

#### 4.2 HumanExecutionApproval (execution_models.py)
```python
@dataclass
class HumanExecutionApproval:
    """
    Explicit human authorization. DEFAULT = DENY (absence of approval = no execution).
    
    Fields:
    - approval_id: UUID
    - intent_id: UUID (links to ExecutionIntent)
    - approved: bool (default=False)
    - approval_authority: HUMAN_TRADER | RISK_OFFICER | SYSTEM_ADMIN
    - authorized_by: User ID or name (who approved?)
    - approved_at: datetime
    - approval_rationale: Human explanation for approval/rejection
    - metadata: Additional approval context
    
    Key Invariant:
    - Default approved=False (DENY)
    - Absence of HumanExecutionApproval = NO EXECUTION
    - No auto-approval logic exists
    """
```

#### 4.3 KillSwitchController (kill_switch_controller.py)
```python
class KillSwitchController:
    """
    Emergency halt mechanism with 3 types and priority ordering.
    
    Kill Switch Types (priority order):
    1. MANUAL (manual user intervention, highest priority)
    2. CIRCUIT_BREAKER (automated failure detection)
    3. TIMEOUT (execution timeout)
    
    Key Methods:
    - activate(type_: KillSwitchType) → KillSwitchState
    - deactivate(type_: KillSwitchType) → KillSwitchState
    - get_state() → KillSwitchState
    - get_history() → List[KillSwitchEvent]
    
    Properties:
    - Manual kill cannot be programmatically overridden
    - State is immutable (deepcopy protected)
    - All state changes logged
    """
```

#### 4.4 ExecutionAuditLogger (execution_audit_logger.py)
```python
class ExecutionAuditLogger:
    """
    Append-only audit logging. JSON lines format (streaming, immutable).
    
    Methods:
    - log_intent_created(intent: ExecutionIntent)
    - log_approval_granted(approval: HumanExecutionApproval)
    - log_approval_denied(approval: HumanExecutionApproval)
    - log_execution_started(intent_id: str)
    - log_execution_succeeded(intent_id: str, result: dict)
    - log_execution_failed(intent_id: str, error: Exception)
    - log_kill_switch_activated(type_: KillSwitchType, reason: str)
    - log_kill_switch_deactivated(type_: KillSwitchType)
    - get_logs(intent_id: str = None, event_type: str = None)
    - export_logs_json() → str
    
    Properties:
    - Append-only (never modified or deleted)
    - JSON lines format (one event per line)
    - File-based storage + in-memory fallback
    - Queryable by intent_id or event_type
    - Immutable once written
    """
```

#### 4.5 SafetyGuards (safety_guards.py)
```python
class SafetyGuards:
    """
    6 fail-closed validation checks. Any check failure blocks execution.
    
    Checks:
    1. check_explicit_approval(intent: ExecutionIntent, approval: HumanExecutionApproval)
       → Verifies explicit human approval (default=DENY)
    
    2. check_kill_switch(controller: KillSwitchController)
       → Verifies no active kill switches
    
    3. check_intent_constraints(intent: ExecutionIntent)
       → Validates intent fields (symbol, quantity, etc.)
    
    4. check_approval_conditions(approval: HumanExecutionApproval)
       → Validates approval is fresh (not expired)
    
    5. check_approval_authority(approval: HumanExecutionApproval)
       → Validates approver has sufficient authority
    
    6. check_audit_trail(intent_id: str, logger: ExecutionAuditLogger)
       → Verifies complete audit trail exists
    
    Method:
    - validate_execution(
        intent: ExecutionIntent,
        approval: HumanExecutionApproval,
        controller: KillSwitchController,
        logger: ExecutionAuditLogger
      ) → (is_safe: bool, reason: str, violations: List[str])
    
    Properties:
    - Fail-closed (any check failure = no execution)
    - No implicit approval
    - Complete audit trail required
    - All checks logged
    """
```

**Isolation Verification (AST-verified):**
```
✅ execution_models.py: Only imports from dataclasses, enum, typing, datetime, uuid
✅ kill_switch_controller.py: Only imports from typing, datetime, execution_models
✅ execution_audit_logger.py: Only imports from json, typing, datetime, pathlib, execution_models
✅ safety_guards.py: Only imports from typing, datetime, execution_models

ZERO imports from reasoner_service modules ✅
ZERO imports from decision_*_service modules ✅
ZERO imports from counterfactual_enforcement_simulator ✅
ZERO imports from orchestration modules ✅
```

---

### 5. Storage Layer (SQLAlchemy ORM)

**Models:**

#### Decision
```python
class Decision(Base):
    """Persistent record of a trading decision."""
    id: UUID (primary key)
    correlation_id: str (unique, indexed)
    symbol: str (indexed)
    timeframe: str
    signal: JSON
    reasoning_mode: str
    confidence: float
    reasoning_time_ms: int
    created_at: datetime (indexed)
    # ... additional fields
    
    Properties:
    - Append-only semantics (no UPDATE/DELETE)
    - Full query capability on historical data
    - Indexed for efficient filtering
```

#### DecisionOutcome
```python
class DecisionOutcome(Base):
    """Trade outcome linked to a specific decision."""
    id: UUID (primary key)
    decision_id: UUID (foreign key → Decision.id, indexed)
    symbol: str (indexed)
    timeframe: str
    signal_type: str
    entry_price: float
    exit_price: float
    pnl: float
    outcome: Literal["win", "loss", "breakeven"]
    exit_reason: Literal["tp", "sl", "manual", "timeout"]
    closed_at: datetime
    created_at: datetime (indexed)
    
    Properties:
    - Links to Decision via foreign key
    - Tracks trade results
    - Enables outcome-aware decision analysis
    - Append-only semantics
```

---

### 6. Plan Execution Contract

**Purpose:** Deterministic, scope-locked specification for plan-based execution.

**Components:**

#### Plan Schema
```python
class Plan:
    """Structured workflow definition."""
    id: str (UUID v4)
    version: int (≥ 1)
    created_at: int (Unix timestamp, ms)
    steps: List[PlanStep] (non-empty, ≤ 1024)
    name: str (non-empty, ≤ 255 chars)
    context_requirements: List[str] (non-empty)
    
    Optional:
    - priority: int (default 0)
    - timeout_ms: int (default 300000)
    - retry_policy: RetryPolicy
    - metadata: Dict[str, Any]
    - tags: List[str]
    - estimated_duration_ms: int
```

#### ExecutionContext Schema
```python
class ExecutionContext:
    """Immutable read-only execution environment."""
    plan: Plan (immutable)
    execution_id: str (UUID v4)
    started_at: int (Unix timestamp, ms)
    deadline_ms: int (absolute deadline)
    environment: Dict[str, Any] (opaque, black box)
    
    Optional:
    - parent_execution_id: str
    - user_id: str
    - request_id: str
    - correlation_context: Dict[str, str]
    
    Constraints:
    - ExecutionContext is immutable (executor cannot modify)
    - environment is opaque (orchestrator doesn't validate/mutate)
    - deadline_ms ≥ started_at + plan.timeout_ms
```

#### PlanResult Schema
```python
class PlanResult:
    """Terminal outcome of plan execution."""
    plan_id: str
    execution_id: str
    status: Literal["success", "partial", "failure"]
    completed_at: int (Unix timestamp, ms)
    duration_ms: int
    steps_executed: int
    steps_total: int
    result_payload: Dict[str, Any] (executor-generated)
    error: Optional[ExecutionError]
    
    Status Definitions:
    - success: All steps completed, no errors
    - partial: Some steps completed, non-fatal errors
    - failure: Execution could not proceed, plan objectives not met
```

---

## Data Flow & Execution Order

### Standard Event Processing Pipeline

**Entry Point:** `DecisionOrchestrator.handle_event(event: Event) -> EventResult`

**Step 1: Schema Validation**
```
Input: Raw Event object
Action: Validate against Pydantic Event schema
Output: Validated Event or raise ValidationError
Safety: No unvalidated data proceeds
```

**Step 2: Deduplication**
```
Input: Validated Event
Action: Compute hash(event.correlation_id, event.symbol, event.signal)
        Check against _dedup cache
Output: Pass event if hash not seen, reject if duplicate
Safety: Prevents processing same event twice
```

**Step 3: Event Constraint Check**
```
Input: Deduplicated Event
Action: Check cooldown (CooldownManager)
        Check session window (SessionWindow)
Output: Pass event or defer with retry hint
Safety: Rate limiting, time-based gates
```

**Step 4: ReasoningManager Invocation**
```
Input: Validated event
Action: Invoke ReasoningManager with time limit (default 500ms)
        Request isolation (no state bleed)
        Non-throwing error handling
Output: AdvisorySignal (confidence-validated)
Safety: Time-bounded, never crashes
```

**Step 5: Shadow-Mode Analysis**
```
Input: AdvisorySignal from ReasoningManager
Action: Invoke read-only services:
        - TradeGovernanceService (governance analysis)
        - PolicyConfidenceEvaluator (policy scoring)
        - CounterfactualEnforcementSimulator (what-if)
        - DecisionTrustCalibrationService (trust metrics)
        - DecisionIntelligenceReportService (reporting)
Output: Analysis results (deepcopy-protected)
Safety: Read-only analysis, no state mutations
```

**Step 6: Signal Filtering**
```
Input: Analysis results
Action: Apply policy-based filters per event type
        Keep audit trail of filtered signals
Output: Filtered signals (policy decisions logged)
Safety: Audit trail of all filtering decisions
```

**Step 7: Persistence**
```
Input: Filtered signals + event data
Action: Insert Decision record (append-only)
        Compute decision hash
        Try Redis cache (optional)
        Fallback to in-memory DLQ if DB fails
Output: Decision ID
Safety: Non-blocking fallback if DB down
```

**Step 8: Notifications**
```
Input: Decision record
Action: Route to notification channels (Slack/Discord/Telegram)
        Apply NOTIFY_LEVEL filter (info|warn|all)
        Non-blocking, concurrent delivery
Output: Notification result (best-effort)
Safety: Failures don't interrupt main flow
```

**Step 9: Return Result**
```
Output: EventResult
  - correlation_id: request tracking ID
  - event_state: pending|processed|deferred|escalated|discarded
  - processing_time_ms: end-to-end latency
  - policy_decisions: audit trail
  - state_transitions: historical state changes
```

---

### Plan Execution Pipeline

**Entry Point:** `PlanExecutor.execute(context: ExecutionContext) -> PlanResult`

**Step 1: Context Validation**
```
Input: ExecutionContext
Action: Verify context_requirements met
        Check deadline not exceeded
        Validate immutability
Output: Valid context or raise fatal error
```

**Step 2: Dependency Resolution**
```
Input: PlanStep[] with depends_on constraints
Action: Topologically sort steps by dependencies
        Validate no circular dependencies
Output: Execution order
```

**Step 3: Step Execution Loop**
```
For each PlanStep in order:
  1. Check deadline not exceeded (fatal if exceeded)
  2. Invoke action handler with payload
  3. Validate output schema
  4. On success → continue
  5. On error → apply on_failure policy
     - halt → stop immediately (status=failure)
     - skip → skip this step (status=partial)
     - retry → retry with backoff (configurable)
```

**Step 4: Result Aggregation**
```
Collect all step results
Compute total duration
Determine status (success|partial|failure)
Build result_payload
Generate PlanResult
```

---

## Core Invariants & Constraints

### Non-Negotiable Invariants

**Invariant 1: Non-Authority**
```
∀ service ∈ [shadow-mode services]:
  service.output CANNOT influence execution decisions
  service.output MUST include "informational only" disclaimer
  service.output MUST NEVER be wired to order placement
```
**Enforcement:** Documentation + code review + tests

---

**Invariant 2: Fail-Closed Default**
```
∀ execution_decision:
  default_state = DENY
  absence_of_approval = no_execution
  no_auto_approval_logic_exists
```
**Enforcement:** ExecutionIntent + HumanExecutionApproval schema

---

**Invariant 3: Immutable Audit Trail**
```
∀ decision_record:
  no_update_possible (only INSERT + SELECT)
  no_delete_possible
  append_only_semantics
  immutable_forever
```
**Enforcement:** Database schema + ORM constraints

---

**Invariant 4: Execution Boundary Isolation**
```
execution_boundary module:
  ZERO imports from reasoner_service
  ZERO imports from shadow-mode services
  ZERO imports from orchestration
  COMPLETELY ISOLATED
```
**Enforcement:** AST-verified at deployment

---

**Invariant 5: Deterministic Output**
```
∀ service ∈ [all services]:
  same_input → same_output (always)
  deepcopy_on_input (no external corruption)
  deepcopy_on_output (consumers cannot mutate)
  no_external_state_modification
```
**Enforcement:** Tests verify determinism

---

**Invariant 6: Fail-Silent Behavior**
```
∀ shadow_mode_service:
  exceptions.raised = False
  exceptions.caught = True
  exceptions.logged = True
  method_continues = True
  safe_default_returned = True
```
**Enforcement:** All services have try/except with safe defaults

---

### Forbidden Patterns (CATASTROPHIC MISTAKES)

**❌ FORBIDDEN: Wiring Phase 10 outputs to execution**
```python
# THIS IS A FUNDAMENTAL VIOLATION:
trust_metrics = calibration_service.calibrate_signals(memory)
if trust_metrics["consistency_rate"] > 0.8:
    execute_trade()  # VIOLATES ENTIRE DESIGN
```

**❌ FORBIDDEN: Adding enforcement methods to shadow-mode services**
```python
# THIS IS NOT ALLOWED:
class DecisionTrustCalibrationService:
    def block_signal_if_consistency_low(self):
        ...
```

**❌ FORBIDDEN: Modifying frozen service logic**
```python
# Changing calibration algorithm violates Phase 10 contract
```

**❌ FORBIDDEN: Removing execution_boundary isolation**
```python
# Adding imports from decision_trust_calibration_service = collapse of boundary
```

**❌ FORBIDDEN: Auto-approving execution**
```python
# Auto-generating HumanExecutionApproval violates invariant
```

---

## Setup & Configuration

### Prerequisites

- **Python:** 3.11+
- **Database:** PostgreSQL (production) or SQLite (development)
- **Cache (Optional):** Redis 6.0+
- **Notification Channels:** Slack, Discord, Telegram (optional)

### Installation

```bash
# 1. Clone repository
git clone <repo-url>
cd prototypeictalgo

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings (see below)
```

### Environment Variables

**Database:**
```bash
POSTGRES_URI=postgresql+asyncpg://user:pass@localhost:5432/yourdb
# OR for SQLite (development):
POSTGRES_URI=sqlite+aiosqlite:///:memory:
```

**API & Authentication:**
```bash
WEBHOOK_SECRET=your-webhook-secret          # Validates incoming webhooks
REASONER_PROVIDER=openai                    # openai|gemini
REASONER_MODEL=gpt-4-turbo                  # Model to use
```

**Notifications:**
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_TOKEN=123456789:ABCdefGHIjklmnOPqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789

# Notification filtering
NOTIFY_LEVEL=info                           # info|warn|all
MIN_WARN_CONFIDENCE=0.7                     # Confidence threshold for warnings
```

**Caching & Performance:**
```bash
REDIS_URL=redis://localhost:6379            # Optional Redis cache
REDIS_CIRCUIT_BREAKER_THRESHOLD=5           # Failures before circuit opens
REDIS_CIRCUIT_BREAKER_TIMEOUT_S=60          # Circuit open timeout

# Request handling
NOTIFIER_MAX_CONCURRENCY=10                 # Concurrent notification workers
NOTIFIER_HTTP_TIMEOUT=30                    # HTTP request timeout (s)
NOTIFIER_RETRIES=3                          # Retry failed notifications
NOTIFIER_BACKOFF=2.0                        # Exponential backoff multiplier
```

**Reasoning & Execution:**
```bash
REASONING_TIMEOUT_MS=500                    # Max reasoning time
REASONING_MODE=default                      # default|action_suggestion|risk_flagging
EXECUTION_TIMEOUT_MS=5000                   # Max execution time

# Cooldown & rate limiting
COOLDOWN_MS_PER_EVENT_TYPE=1000             # Base cooldown
SESSION_WINDOW_ENABLED=true                 # Time-based gates
SESSION_WINDOW_START_HOUR=0
SESSION_WINDOW_END_HOUR=23
```

**Logging:**
```bash
LOG_LEVEL=INFO                              # DEBUG|INFO|WARNING|ERROR
LOG_FILE=/var/log/trading_system.log        # Log file path (optional)
```

### Database Initialization

```bash
# Create tables (if using new database)
python -c "
from reasoner_service.storage import init_models, create_engine_from_env_or_dsn
import asyncio

async def init():
    engine = create_engine_from_env_or_dsn()
    await init_models(engine)

asyncio.run(init())
"
```

---

## Running & Testing

### Run the System

**Option 1: Docker Compose (Recommended for Production)**

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f reasoner_service

# Stop services
docker-compose down
```

**Option 2: Standalone Python**

```bash
# Start the application
python reasoner_service/app.py

# Application listens on http://localhost:8000
# Webhook endpoint: POST /api/webhook/receive
```

**Option 3: Demo CLI**

```bash
# Run demo decision
python demo.py \
  --symbol XAUUSD \
  --recommendation enter \
  --bias bullish \
  --confidence 0.82 \
  --duration-ms 120 \
  --summary "demo trade" \
  --persist \
  --dsn "sqlite+aiosqlite:///:memory:"
```

### Send a Test Event

**Via cURL:**
```bash
curl -X POST http://localhost:8000/api/webhook/receive \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-webhook-secret" \
  -d '{
    "correlation_id": "test-001",
    "symbol": "AAPL",
    "timeframe": "1h",
    "signal": {"type": "bullish_choch", "strength": 0.85},
    "metadata": {"source": "market_analysis"}
  }'
```

**Via Python:**
```python
import httpx
import json

async def send_event():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/webhook/receive",
            json={
                "correlation_id": "test-001",
                "symbol": "AAPL",
                "timeframe": "1h",
                "signal": {"type": "bullish_choch", "strength": 0.85},
                "metadata": {"source": "market_analysis"}
            },
            headers={"X-Webhook-Secret": "your-webhook-secret"}
        )
        print(response.json())

asyncio.run(send_event())
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=reasoner_service --cov-report=html

# Run specific test file
pytest tests/test_orchestrator.py -v

# Run tests matching pattern
pytest -k "test_handle_event" -v

# Show test summary
pytest -q --tb=short
```

**Test Results Expected:**
```
653 passed, 6 skipped in 14.46s ✅
```

---

## Deployment Guide

### Production Deployment Checklist

**Pre-Deployment:**
- [ ] All 653 tests passing locally
- [ ] Environment variables configured (see Configuration section)
- [ ] Database initialized and accessible
- [ ] Redis running (if using caching)
- [ ] Webhook secret securely stored (not in .env)
- [ ] API keys securely stored (LLM provider, webhooks)
- [ ] Log file directory exists and is writable

**Deployment:**
- [ ] Push code to repository
- [ ] Build Docker image: `docker build -t trading-system:v1.0.0 .`
- [ ] Push to container registry
- [ ] Deploy using Kubernetes/Docker Compose/traditional server
- [ ] Verify health endpoint responds
- [ ] Send test webhook event
- [ ] Verify logs are being written
- [ ] Verify notifications are working

**Post-Deployment:**
- [ ] Monitor application logs
- [ ] Monitor metrics (Prometheus, if enabled)
- [ ] Test webhook with real market data
- [ ] Verify decision records in database
- [ ] Verify notification delivery
- [ ] Set up alerting (high error rates, slow processing, etc.)

### Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY reasoner_service/ ./reasoner_service/
COPY execution_boundary/ ./execution_boundary/
COPY utils/ ./utils/
COPY *.py ./

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "reasoner_service.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker Compose (development):**
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: secure_password
      POSTGRES_DB: trading_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  app:
    build: .
    environment:
      POSTGRES_URI: postgresql+asyncpg://trading:secure_password@postgres:5432/trading_db
      REDIS_URL: redis://redis:6379
      WEBHOOK_SECRET: ${WEBHOOK_SECRET}
      SLACK_WEBHOOK_URL: ${SLACK_WEBHOOK_URL}
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    volumes:
      - ./logs:/app/logs

volumes:
  postgres_data:
```

**Kubernetes Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: trading-system
  template:
    metadata:
      labels:
        app: trading-system
    spec:
      containers:
      - name: trading-system
        image: registry.example.com/trading-system:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_URI
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: postgres-uri
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: redis-url
        - name: WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: webhook-secret
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"

---
apiVersion: v1
kind: Service
metadata:
  name: trading-system-service
spec:
  selector:
    app: trading-system
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

---

## Troubleshooting & Safety

### Common Issues

**Issue 1: Database Connection Timeout**
```
Error: asyncpg.exceptions.ConnectorConnectorError: cannot connect to server
```
**Solution:**
1. Verify POSTGRES_URI is correct
2. Check PostgreSQL is running: `psql -U user -d database`
3. Verify network connectivity to database host
4. Check database user has correct permissions
5. Check PostgreSQL logs for errors

**Issue 2: Redis Connection Fails**
```
Error: ConnectionError: cannot connect to Redis
```
**Solution:**
1. Redis failures are non-critical (circuit-breaker fallback)
2. Verify Redis is running: `redis-cli ping`
3. Check REDIS_URL is correct
4. Check network connectivity to Redis host
5. Monitor application logs for circuit-breaker transitions

**Issue 3: Webhook Events Not Processing**
```
EventResult shows status: "discarded"
```
**Solution:**
1. Check WEBHOOK_SECRET matches client secret
2. Verify event schema is valid (see /api/webhook/schema)
3. Check event not deduplicated (same correlation_id)
4. Check cooldown/session window constraints
5. Review DecisionOrchestrator logs for validation errors

**Issue 4: Notifications Not Sending**
```
Notification delivery fails silently
```
**Solution:**
1. Verify webhook URLs (Slack, Discord, Telegram)
2. Test webhooks manually with curl
3. Check network connectivity (firewall, proxy)
4. Verify NOTIFY_LEVEL allows notification type
5. Review notification logs for detailed error messages

**Issue 5: Reasoning Timeouts**
```
ReasoningManager times out or returns error signal
```
**Solution:**
1. Increase REASONING_TIMEOUT_MS (default 500ms)
2. Check LLM API availability and response time
3. Verify LLM API key is valid
4. Check network latency to LLM provider
5. Review ReasoningManager logs for timeout details

---

### Safety Verification Checks

**Before Production Deployment, Verify:**

✅ **Isolation Check:**
```bash
# Verify execution_boundary has NO imports from reasoner_service
grep -r "from reasoner_service" execution_boundary/
# Should return ZERO matches
```

✅ **Authority Check:**
```bash
# Verify shadow-mode services have ZERO execution methods
grep -r "def execute_" reasoner_service/decision_*_service.py
# Should return ZERO matches
```

✅ **Audit Check:**
```bash
# Verify Decision model has no UPDATE/DELETE triggers
grep -r "UPDATE\|DELETE" reasoner_service/storage.py
# Should return ZERO matches
```

✅ **Test Check:**
```bash
# Run all tests
pytest -v
# Expected: 653 passed, 6 skipped
```

✅ **Configuration Check:**
```bash
# Verify no secrets in code
grep -r "password\|api_key\|secret" reasoner_service/ --include="*.py" \
  | grep -v "\.example" | grep -v "test" | grep -v "#"
# Should return ZERO matches
```

---

### Monitoring & Observability

**Health Check Endpoints:**
```
GET /health → System operational status
GET /ready → Ready to accept requests
GET /metrics → Prometheus metrics (if enabled)
```

**Key Metrics to Monitor:**

| Metric | Purpose | Alert Threshold |
|--------|---------|-----------------|
| `decisions_processed_total` | Total events processed | N/A (informational) |
| `deduplicated_decisions_total` | Duplicate events filtered | Monitor for high rates |
| `decision_processing_time_p95` | 95th percentile latency | > 1000ms |
| `reasoning_time_p95` | 95th percentile reasoning time | > 500ms |
| `notification_errors_total` | Failed notifications | > 5 per hour |
| `database_connection_errors` | DB connection failures | > 0 |
| `redis_circuit_breaker_open` | Redis is down (fallback active) | Informational |

**Sample Prometheus Configuration:**
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'trading-system'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

---

## Authority Boundary

**CRITICAL STATEMENT:** This system has **ZERO AUTHORITY** over trading execution.

### What This System Does

✅ **Analyzes** trading signals and decisions  
✅ **Evaluates** governance rules and compliance  
✅ **Provides** historical insights and patterns  
✅ **Records** all decisions immutably  
✅ **Notifies** relevant stakeholders  
✅ **Suggests** information for human review  

### What This System Does NOT Do

❌ **Execute** trades (zero execution capability)  
❌ **Block** decisions (zero enforcement authority)  
❌ **Modify** decisions or outcomes  
❌ **Auto-approve** anything (explicit human approval required)  
❌ **Enforce** policies (informational analysis only)  
❌ **Control** systems or resources  

### Forbidden Wiring Examples

**❌ FORBIDDEN:**
```python
# Using Phase 10 metrics to execute trades
if trust_metrics["consistency_rate"] > 0.8:
    execute_trade()  # VIOLATES SYSTEM DESIGN
```

**❌ FORBIDDEN:**
```python
# Using governance analysis to block trades
if governance_violations > 0:
    block_trade()  # VIOLATES SYSTEM DESIGN
```

**❌ FORBIDDEN:**
```python
# Using counterfactual simulation to modify decisions
if would_have_violated:
    reject_trade()  # VIOLATES SYSTEM DESIGN
```

### Correct Usage Patterns

**✅ ALLOWED:**
```python
# Using outputs for audit/reporting
report = decision_service.generate_report(decision_id)
audit_trail.append(report)  # Store for later review
```

**✅ ALLOWED:**
```python
# Using outputs for human dashboard
metrics = calibration_service.calibrate_signals(memory)
dashboard.display(metrics)  # Show to human traders
```

**✅ ALLOWED:**
```python
# Using outputs for compliance documentation
archive = archive_service.fetch_all()
compliance_report.generate_from(archive)  # Document decisions
```

---

## API Reference

### Webhook Events

**Endpoint:** `POST /api/webhook/receive`

**Authentication:** Header `X-Webhook-Secret` must match configured secret

**Request Body:**
```json
{
  "correlation_id": "unique-event-id-uuid",
  "symbol": "AAPL",
  "timeframe": "1h",
  "signal": {
    "type": "bullish_choch",
    "strength": 0.85,
    "confidence": 0.82
  },
  "metadata": {
    "source": "market_analysis",
    "custom_field": "value"
  }
}
```

**Response:**
```json
{
  "correlation_id": "unique-event-id-uuid",
  "event_state": "processed",
  "processing_time_ms": 234,
  "policy_decisions": [
    {
      "policy_name": "cooldown",
      "applied": false,
      "reason": "no cooldown active"
    }
  ],
  "state_transitions": [
    {
      "from_state": "pending",
      "to_state": "processed",
      "timestamp": 1703088234567
    }
  ]
}
```

---

### ReasoningManager Interface

**Python API:**
```python
from reasoner_service.reasoning_manager import ReasoningManager, ReasoningRequest

manager = ReasoningManager()
request = ReasoningRequest(
    event_id="event-123",
    symbol="AAPL",
    timeframe="1h",
    signal={"type": "bullish_choch", "strength": 0.85},
    context={"market_regime": "trending"}
)

signal = await manager.reason(
    request,
    mode="default",  # default|action_suggestion|risk_flagging
    timeout_ms=500
)

print(signal.confidence)     # float [0.0, 1.0]
print(signal.reasoning)      # str explanation
print(signal.is_error)       # bool
print(signal.error_message)  # str if error
```

---

### DecisionOrchestrator Interface

**Python API:**
```python
from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.orchestrator_events import Event

orchestrator = DecisionOrchestrator()
await orchestrator.setup()

event = Event(
    correlation_id="event-123",
    symbol="AAPL",
    timeframe="1h",
    signal={"type": "bullish_choch"},
    metadata={"source": "analysis"}
)

result = await orchestrator.handle_event(event)

print(result.correlation_id)      # str
print(result.event_state)         # pending|processed|deferred|escalated|discarded
print(result.processing_time_ms)  # int
print(result.policy_decisions)    # List[Dict]
```

---

### Execution Boundary Interface

**Python API:**
```python
from execution_boundary import (
    ExecutionIntent,
    HumanExecutionApproval,
    KillSwitchController,
    ExecutionAuditLogger,
    SafetyGuards,
    ExecutionIntentType,
    ApprovalAuthority
)

# Create human-authored intent (NEVER INFERRED)
intent = ExecutionIntent(
    intent_type=ExecutionIntentType.OPEN_POSITION,
    symbol="AAPL",
    quantity=100,
    order_type="MARKET",
    human_rationale="Close end-of-day position due to risk limits"
)

# Explicit human approval (required)
approval = HumanExecutionApproval(
    intent_id=intent.intent_id,
    approved=True,  # Must be explicitly True
    approval_authority=ApprovalAuthority.HUMAN_TRADER,
    authorized_by="trader-001",
    approval_rationale="Approved by risk officer"
)

# Kill switch management
controller = KillSwitchController()
controller.activate("manual", reason="Manual user halt")
state = controller.get_state()
print(state.is_halted)  # True

# Audit logging (append-only)
logger = ExecutionAuditLogger(log_file="/var/log/execution.jsonl")
logger.log_intent_created(intent)
logger.log_approval_granted(approval)
logger.log_execution_started(intent.intent_id)

# Safety validation (fail-closed)
guards = SafetyGuards()
is_safe, reason, violations = guards.validate_execution(
    intent=intent,
    approval=approval,
    controller=controller,
    logger=logger
)

if is_safe:
    print("All safety checks passed")
else:
    print(f"Execution blocked: {reason}")
    print(f"Violations: {violations}")
```

---

## Glossary

| Term | Definition |
|------|-----------|
| **Shadow-Mode** | Analysis-only, non-authoritative system; produces insights but never executes |
| **Fail-Closed** | Default behavior = do nothing; requires explicit action to proceed |
| **Authority** | Power to make operational changes (execute, block, modify); this system has zero authority |
| **Immutable** | Cannot be modified after creation; only readable |
| **Append-Only** | Only INSERT operations allowed; no UPDATE or DELETE |
| **Deepcopy-Protected** | Data copied before use; prevents external mutation |
| **Fail-Silent** | Errors caught internally; no exceptions raised; safe defaults returned |
| **Deterministic** | Same input always produces identical output |
| **Correlation ID** | Unique identifier tracking an event through the system |
| **Event State** | Current position in event lifecycle (pending, processed, deferred, escalated, discarded) |
| **Advisory Signal** | Non-binding suggestion from ReasoningManager; informational only |
| **Policy Backend** | Pluggable source for policy configuration (config, HTTP, Redis, defaults) |
| **Cooldown** | Rate limiting; minimum time between processing same event type |
| **Session Window** | Time-based gate (e.g., business hours only) |
| **Kill Switch** | Emergency halt mechanism; manual (highest priority), circuit_breaker, timeout |
| **Execution Intent** | Human-authored discrete trading action (NEVER INFERRED) |
| **Execution Boundary** | Isolated layer separating shadow-mode from execution; zero imports from reasoner_service |

---

## References

### Key Documents

- **AUTHORITY_BOUNDARY.md** - Explicit authority constraints and forbidden wiring patterns
- **PHASE_10.1_COMPLETION_REPORT.md** - Semantic hardening completion and test results
- **COMPLETE_ECOSYSTEM_STATUS.md** - Full shadow-mode 7-service ecosystem documentation
- **PLAN_EXECUTION_CONTRACT.md** - Deterministic plan execution specification
- **EXECUTION_BOUNDARY_ARCHITECTURE.md** - Isolated execution boundary layer design
- **ORCHESTRATION_SUMMARY.md** - Advanced orchestration features and event state machine

### External References

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Python asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [Prometheus Metrics](https://prometheus.io/docs/concepts/data_model/)

---

## License & Support

**Status:** Production Ready  
**Version:** 1.0.0  
**Last Updated:** December 21, 2025  

For issues, questions, or contributions, contact the development team.

---

**End of System Architecture & Implementation Guide**
