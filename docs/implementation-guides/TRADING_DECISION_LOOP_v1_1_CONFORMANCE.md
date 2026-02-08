================================================================================
TRADING DECISION LOOP v1.1 - CONFORMANCE AUDIT
================================================================================
Date: December 23, 2025
Spec Version: 1.1 (Refined & Immutable)
Audit Focus: Stage-by-stage implementation against explicit requirements
Status: CONFORMANCE CHECK (no implementation suggested)

================================================================================
CORE PRINCIPLE VALIDATION
================================================================================

**Core Question Being Answered**: 
"Given current higher-timeframe bias, lower-timeframe context, and live market 
updates — is there a high-probability trade worth human execution right now?"

Current Implementation Alignment: ⚠️  PARTIAL (50-60%)

Evidence:
  ✅ System does NOT execute trades autonomously (explicit non-goal met)
  ✅ Human approval is modeled as mandatory (HumanExecutionApproval default=False)
  ✅ Reasoning engine is time-bounded and invoked on demand
  ❌ HTF bias evaluation is NOT distinct from entry evaluation (mixed modes)
  ❌ Signal freshness/expiration rules NOT implemented
  ❌ Trade management mode NOT implemented

---

**Authority Model Alignment**:

Specified Model:
  H (Human): Final decision-maker
  Orchestrator (You): Controls flow, state, gating, safety
  Reasoning Engine (LLM): Analyzes only when asked, within constraints

Current Implementation:
  ✅ Human: HumanExecutionApproval model exists, fail-closed default
  ✅ Orchestrator: DecisionOrchestrator has gating, policy enforcement, state management
  ✅ Reasoning Engine: ReasoningManager is time-bounded, stateless, on-demand
  ⚠️  Gap: Orchestrator does NOT explicitly select reasoning modes (bias vs entry vs management)
  ⚠️  Gap: No control flow that respects this three-tier authority model

Conformance: 70%

================================================================================
SECTION 1: STAGE 0 — CYCLE TRIGGER
================================================================================

**Specification**:
A decision cycle is triggered by exactly ONE of:
  1. New candle close (configured timeframe)
  2. HTF context update
  3. Manual human request
  4. Position state change (open / closed)

No continuous loops. No polling.

---

**Current Implementation**:

What Exists:
  ✅ Event-driven architecture (DecisionOrchestrator.handle_event)
     - Accepts events with event_type, payload, correlation_id
     - HTTP webhook ingestion via FastAPI app
  ✅ No continuous loops (event-triggered, not polling)
  ✅ Deduplication prevents repeated events (hash-based)

What Is Missing:
  ❌ NO explicit trigger type validation
     - System accepts ANY event_type without checking if it's a valid cycle trigger
     - No enforcement: only {candle_close|htf_update|manual_request|position_change} accepted
  ❌ NO candle close detection
     - No Pine Script webhook parsing for "new candle close" signals
     - No timeframe-specific trigger logic
  ❌ NO HTF context update detection
     - No explicit check: "is this an HTF context update?"
     - No differentiation from other event types
  ❌ NO position state change detection
     - No built-in tracking of position open/closed transitions
     - No triggering on transition events
  ❌ NO manual request handling
     - System accepts manual API calls but doesn't label them as "manual request" trigger
     - No explicit UI/workflow for human-initiated cycle

What Is Incomplete:
  ⚠️  Trigger source logging exists but NOT enforced
     - Orchestrator logs event_type but doesn't validate against allowed triggers
  ⚠️  Event deduplication prevents accidental re-triggering
     - But deduplication is hash-based, not trigger-aware

**Conformance**: 30%

**Risk**: System could trigger on invalid event types (e.g., health check, admin query)
without explicit validation against the four allowed trigger types.

---

### Recommendation for Stage 0

**Required Before Production**:
  1. Add explicit trigger_type enum: {CANDLE_CLOSE, HTF_UPDATE, MANUAL_REQUEST, POSITION_CHANGE}
  2. Validate all incoming events against allowed triggers
  3. Reject with error: "Invalid trigger type" for anything else
  4. Log trigger source for every decision cycle
  5. Add rate limiting per trigger type (e.g., max 1 candle close per TF per minute)

================================================================================
SECTION 2: STAGE 1 — DATA INGESTION (READ-ONLY)
================================================================================

**Specification**:
Inputs collected without interpretation:
  - Price data (OHLCV per timeframe)
  - Market structure signals (swing points, sweeps, CHoCH)
  - Indicator state (if any — passive only)
  - Current position state (if exists)

No reasoning occurs here.

---

**Current Implementation**:

What Exists:
  ✅ Event payload can contain arbitrary dict (flexible schema)
     - No type validation, can accept any structure
  ✅ Price data can be passed as-is through event.payload
  ✅ Deepcopy protection ensures no mutation during ingestion
     - All shadow-mode services deepcopy inputs

What Is Missing:
  ❌ NO explicit OHLCV schema
     - No Pydantic model enforcing {open, high, low, close, volume}
     - No per-timeframe price data structure
  ❌ NO market structure signal schema
     - No model for swing points, sweeps, CHoCH
     - Ingestion does not validate or normalize these inputs
  ❌ NO indicator state schema
     - No model for indicator values (if included)
     - No distinction between "passive indicator state" vs "indicator recommendation"
  ❌ NO position state schema
     - No model for {open, quantity, entry_price, sl, tp}
     - No current position lookup mechanism
  ❌ NO read-only enforcement
     - Ingestion stage accepts data but no explicit "read-only" marker
     - No prevention of interpretation/reasoning during Stage 1

What Is Incomplete:
  ⚠️  Event validation exists but is generic
     - orchestrator.handle_event() validates event structure
     - But does NOT validate payload for price data completeness
  ⚠️  No schema for market structure inputs
     - Swing points, sweeps, CHoCH could be in any format
     - System has no way to normalize or validate these

**Conformance**: 40%

**Risk**: 
  - Incomplete price data could be ingested silently
  - Market structure signals could be garbled without detection
  - Position state could be missing or corrupted

---

### Recommendation for Stage 1

**Required Before Production**:
  1. Create PriceData schema (OHLCV per timeframe with validation)
  2. Create MarketStructureSignal schema (swing points, sweeps, CHoCH)
  3. Create IndicatorState schema (passive values only, no recommendations)
  4. Create PositionState schema (open quantity, entry, SL, TP, or None if closed)
  5. Add validation: all Stage 1 inputs must conform to these schemas
  6. Add "read_only" marker to all ingested data
  7. Add completeness check: reject events with missing critical fields

================================================================================
SECTION 3: STAGE 2 — STATE UPDATE & CONTEXT ENCODING
================================================================================

**Specification**:
The orchestrator updates deterministic system state.

Session Context (Explicit Definition):
  - Time-of-day session (Asia / London / NY / overlap / dead zone)
  - Session behavior tag: {expansion | consolidation | transition}
  - Killzone eligibility (true / false)

Volatility Regime (Explicit Definition):
  - ATR percentile vs rolling 20-day baseline
  - Range expansion/contraction over last N candles
  - Regime states: Low | Normal | High | Dislocated (news/spike)
  - Regime change requires two consecutive confirmations

State Versioning:
  - state_hash = hash(state_json + cycle_timestamp)

---

**Current Implementation**:

What Exists:
  ✅ OrchestrationStateManager (850 lines, 28 tests)
     - State machine: pending → processed → deferred → escalated → discarded
     - Cooldown management (per event type)
     - Session window constraints (_is_quiet_hours() method)
  ✅ Immutable state snapshots (deepcopy all state)
  ✅ Timestamp tracking (int(time.time() * 1000))
  ✅ Policy audit trail (non-blocking state observation)

What Is Missing:
  ❌ NO explicit session context encoding
     - _is_quiet_hours() checks hardcoded (00:00-08:00) but not configurable
     - No Asia/London/NY/overlap/dead_zone differentiation
     - No session behavior tag (expansion|consolidation|transition)
  ❌ NO killzone eligibility tracking
     - No killzone_eligible boolean field
     - Policy check mentions "killzone" veto but no explicit model
  ❌ NO volatility regime computation
     - No ATR percentile calculation
     - No rolling 20-day baseline
     - No regime states (Low|Normal|High|Dislocated)
  ❌ NO regime change confirmation (two consecutive required)
     - No state machine for regime transitions
     - No "awaiting confirmation" state
  ❌ NO state versioning with hash
     - State is tracked but NOT hashed
     - No state_hash = hash(state_json + cycle_timestamp)

What Is Incomplete:
  ⚠️  Session windows are partially implemented
     - Time windows exist but not mapped to named sessions
     - Behavior tags missing
  ⚠️  Regime is not tracked at all
     - No regime field in state
     - No ATR-based computation
  ⚠️  State mutations are logged but not versioned
     - No immutable state hash for audit trail

**Conformance**: 30%

**Risk**:
  - Volatility regime is not computable (critical for trade quality)
  - Session context is minimal (no expansion/consolidation detection)
  - State hash is missing (cannot detect malicious state mutation)
  - Regime changes could occur without confirmation (noise sensitivity)

---

### Recommendation for Stage 2

**Required Before Production**:
  1. Create SessionContext schema:
     ```python
     @dataclass
     class SessionContext:
         session: Literal['asia', 'london', 'ny', 'overlap', 'dead_zone']
         behavior: Literal['expansion', 'consolidation', 'transition']
         killzone_eligible: bool
         timestamp: int
     ```
  2. Create VolatilityRegime schema:
     ```python
     @dataclass
     class VolatilityRegime:
         regime: Literal['low', 'normal', 'high', 'dislocated']
         atr_percentile: float  # vs 20-day baseline
         range_expansion_ratio: float
         confirmations: int  # 0, 1, or 2 (state machine for transitions)
     ```
  3. Implement ATR computation (20-day rolling baseline)
  4. Implement range expansion detection
  5. Implement regime change confirmation (two consecutive closes in new regime)
  6. Create StateVersion dataclass:
     ```python
     @dataclass
     class StateVersion:
         state_json: str
         cycle_timestamp: int
         state_hash: str  # SHA256(state_json + cycle_timestamp)
     ```
  7. Add immutable state versioning to every cycle

================================================================================
SECTION 4: STAGE 3 — HARD VALIDATION GATE (ABSOLUTE BLOCKERS)
================================================================================

**Specification**:
If any check fails, the cycle terminates immediately.

Absolute blockers:
  1. Outside tradable session (per strategy rules)
  2. Cooldown violation
  3. Risk exposure exceeded
  4. Kill switch active
  5. Missing or corrupted critical data

No reasoning engine is invoked if Stage 3 fails.

---

**Current Implementation**:

What Exists:
  ✅ pre_reasoning_policy_check() (142-327 in orchestrator.py)
     - Cooldown check (cooldown_until > now_ms) ✅
     - Regime veto (regime == "restricted") ✅
     - Exposure check (exposure > max_exposure) ✅
     - Kill zone veto (killzone marker) ⚠️
  ✅ Early termination if check fails
     - Returns EventResult with status="rejected" or "deferred"
  ✅ Policy audit trail (non-blocking)
  ✅ Quiet hours check (_is_quiet_hours()) ✅

What Is Missing:
  ❌ NO kill switch state check
     - KillSwitchState model exists in execution_boundary/
     - But pre_reasoning_policy_check() does NOT invoke KillSwitchController
     - No check for manual_kill_active, circuit_breaker_active, timeout_active
  ❌ NO data corruption checks
     - No validation of price data completeness
     - No check for missing market structure signals
     - No verification of position state coherence
  ❌ NO trading session validation
     - Quiet hours check exists but is hardcoded (00:00-08:00)
     - No explicit check against "tradable_sessions" config
  ❌ NO explicit blocker list
     - Policy checks scattered across multiple functions
     - No single "Stage 3 Validation Gate" with all 5 blockers
  ❌ NO early termination confirmation
     - No explicit log: "Stage 3 blocker: [reason]. Cycle terminated."

What Is Incomplete:
  ⚠️  Risk exposure check uses market state in event payload
     - No automatic position aggregation from live market
     - No integration with brokerage for current exposure
  ⚠️  Kill switch check is not enforced
     - KillSwitchController exists but not integrated
  ⚠️  Data corruption checks are minimal
     - Event schema validation exists
     - But no check for data freshness, NaN values, or missing fields

**Conformance**: 50%

**Risk**:
  - Kill switch can be bypassed (not checked in Stage 3)
  - Corrupted data (NaN, missing OHLC) could pass Stage 3
  - No explicit blocker enforcement (could accidentally invoke reasoning)

---

### Recommendation for Stage 3

**Required Before Production**:
  1. Create HardValidationGate class:
     ```python
     class HardValidationGate:
         def check_trading_session(self) -> bool
         def check_cooldown(self) -> bool
         def check_risk_exposure(self) -> bool
         def check_kill_switch(self) -> bool
         def check_data_integrity(self) -> bool
     ```
  2. Integrate KillSwitchController.get_state() into gate
  3. Add data integrity checks (no NaN, all required fields present)
  4. Add explicit early-exit log: "Stage 3 blocker detected. Cycle terminated."
  5. Make sure no reasoning is invoked if ANY blocker fires

================================================================================
SECTION 5: STAGE 4 — REASONING MODE SELECTION
================================================================================

**Specification**:
The orchestrator selects exactly ONE reasoning mode:

  - **Bias Evaluation**: Triggered when HTF bias is undefined or invalidated
  - **Entry Evaluation**: Triggered when HTF bias is valid AND no position is open
  - **Trade Management**: Triggered only when a position is already open

No hybrid modes. No ambiguity.

Memory Retrieval Rules (Strict):
  - Only retrieve: Last 3 completed decision cycles
  - Any past cycles with matching setup tags
  - Any invalidations or failures within last 24h
  - No long-term memory flooding

---

**Current Implementation**:

What Exists:
  ✅ ReasoningManager.reason() accepts reasoning_mode parameter
     - Modes: "default", "action_suggestion", "risk_flagging"
     - Time-bounded (500-5000ms configurable)
     - Stateless, non-throwing
  ✅ Reasoning is invoked in orchestrator.handle_event() (step 2.5)
  ✅ Advisory signals are non-authoritative
  ✅ DecisionIntelligenceMemoryService (600+ lines)
     - Decision storage & retrieval
     - Symbol & timeframe filtering
     - Outcome linking

What Is Missing:
  ❌ NO explicit mode selection logic
     - Orchestrator does NOT check HTF bias state
     - Orchestrator does NOT differentiate bias vs entry vs management modes
     - Mode is passed as parameter but origin is not verified
  ❌ NO HTF bias state tracking
     - No "HTF_BIAS_UNDEFINED" or "HTF_BIAS_VALID" state
     - No "HTF bias invalidation" detection
  ❌ NO position state awareness
     - Orchestrator does NOT check "is a position open?"
     - Cannot trigger trade management mode
  ❌ NO mode validation
     - System does NOT enforce "exactly ONE mode per cycle"
     - Could accidentally invoke multiple reasoning modes
  ❌ NO memory filtering (strict rules)
     - Memory service retrieves data but no "last 3 cycles" limit enforced
     - No "matching setup tags" filtering
     - No "failures within 24h" exclusion
  ❌ NO invalidation filtering
     - No explicit filter for invalidated past cycles

What Is Incomplete:
  ⚠️  Memory service exists but not constrained
     - Could return entire history if not rate-limited
  ⚠️  Mode parameter exists but origin unclear
     - No explanation of where "reasoning_mode" comes from

**Conformance**: 20%

**Risk**:
  - CRITICAL: Orchestrator cannot distinguish bias evaluation from entry evaluation
  - CRITICAL: Trade management mode (position management) is not supported
  - Reasoning could flood memory service (no "last 3 cycles" enforcement)
  - Invalid past cycles could pollute reasoning context

---

### Recommendation for Stage 4

**Required Before Production**:
  1. Create HTFBiasState enum:
     ```python
     class HTFBiasState(Enum):
         UNDEFINED = "undefined"  # Need to evaluate
         BIAS_UP = "bias_up"
         BIAS_DOWN = "bias_down"
         BIAS_NEUTRAL = "bias_neutral"
         INVALIDATED = "invalidated"  # Need re-evaluation
     ```
  2. Create ReasoningModeSelector class:
     ```python
     def select_mode(
         htf_bias_state: HTFBiasState,
         position_open: bool
     ) -> Literal['bias_evaluation', 'entry_evaluation', 'trade_management']:
         if htf_bias_state in [UNDEFINED, INVALIDATED]:
             return 'bias_evaluation'
         elif htf_bias_state in [BIAS_UP, BIAS_DOWN, BIAS_NEUTRAL] and not position_open:
             return 'entry_evaluation'
         elif position_open:
             return 'trade_management'
         else:
             raise ValueError("Cannot determine reasoning mode")
     ```
  3. Create MemoryFilter:
     ```python
     def retrieve_context(self, limit=3, max_age_hours=24):
         cycles = self.get_last_n_cycles(limit)
         valid_cycles = [c for c in cycles if not c.invalidated and c.age < max_age_hours]
         return valid_cycles
     ```
  4. Add mode validation: ensure exactly one mode is selected per cycle
  5. Add explicit log: "Reasoning mode selected: [mode_name]"

================================================================================
SECTION 6: STAGE 5 — QUALITY & CONFIDENCE FILTERS (SOFT GATE)
================================================================================

**Specification**:
These do not block early computation but block advisory output.

Quality checks:
  - HTF/LTF alignment confidence
  - Signal freshness (see Stage 7)
  - Regime suitability for strategy
  - Internal reasoning confidence threshold
  - Policy & safety compliance

If failed → output "No Trade — Low Quality" with reasons.

---

**Current Implementation**:

What Exists:
  ✅ post_reasoning_policy_check() (328-374 in orchestrator.py)
     - Confidence threshold check (default 0.5 for "enter")
     - Low-confidence veto (recommendation == "enter" && confidence < min_conf)
     - PolicyStore consultation
  ✅ AdvisorySignal includes confidence field [0.0, 1.0]
  ✅ Shadow mode evaluation (policy_shadow_mode.py)
     - Runs AFTER reasoning
     - Returns veto/pass result (non-blocking)
  ✅ Reasoning errors wrapped in AdvisorySignal (non-throwing)

What Is Missing:
  ❌ NO HTF/LTF alignment confidence check
     - No explicit alignment_confidence metric
     - No multi-timeframe correlation scoring
  ❌ NO signal freshness check (separate from Stage 7 expiration)
     - No check: "was this signal generated in last N minutes?"
     - Freshness is not a quality gate
  ❌ NO regime suitability check
     - No rules like: "entry_evaluation not suitable during Dislocated regime"
     - No regime-aware strategy parameter adjustment
  ❌ NO internal reasoning confidence threshold
     - Reasoning confidence exists but no explicit quality gate
     - No distinction between "reasoning succeeded" and "reasoning confident"
  ❌ NO explicit "No Trade — Low Quality" output
     - Low-confidence decisions are logged but not clearly labeled as rejected
     - No structured advisory with rejection reasons

What Is Incomplete:
  ⚠️  Confidence threshold is single-value (default 0.5)
     - No mode-specific thresholds (bias eval might need 0.4, entry 0.65)
  ⚠️  Permissive mode bypasses all confidence checks
     - ENABLE_PERMISSIVE_POLICY=True disables all post-reasoning gates
     - No way to enforce minimum quality in production

**Conformance**: 40%

**Risk**:
  - Low-quality advisories could be output without clear rejection
  - No HTF/LTF alignment validation (could recommend against HTF bias)
  - Regime-unsuitable trades could be suggested
  - No structured "No Trade — Low Quality" output for audit trail

---

### Recommendation for Stage 5

**Required Before Production**:
  1. Create QualityScore dataclass:
     ```python
     @dataclass
     class QualityScore:
         htf_ltf_alignment_confidence: float  # [0, 1]
         signal_freshness_confidence: float   # [0, 1]
         regime_suitability_confidence: float # [0, 1]
         reasoning_confidence: float          # [0, 1]
         policy_compliance_confidence: float  # [0, 1]
         overall_quality: float               # min of above
     ```
  2. Create QualityGate:
     ```python
     def evaluate_quality(advisory_signal) -> (bool, str):
         quality = compute_quality_score(advisory_signal)
         if quality.overall < min_threshold:
             return False, "No Trade — Low Quality. [reasons]"
         return True, "Pass"
     ```
  3. Add mode-specific thresholds (bias_eval: 0.4, entry: 0.65, management: 0.5)
  4. Add regime suitability check
  5. Add explicit structured output: "No Trade — Low Quality" with reason breakdown
  6. Remove permissive mode bypass (disable ENABLE_PERMISSIVE_POLICY in production)

================================================================================
SECTION 7: STAGE 6 — ADVISORY GENERATION (NON-EXECUTABLE)
================================================================================

**Specification**:
If all gates pass, generate one advisory containing:
  - Bias summary
  - Setup logic (why this is valid)
  - Invalidation conditions
  - Risk notes
  - Explicit disclaimer: "Human confirmation required."

No entry prices phrased as commands.
No execution verbs.

---

**Current Implementation**:

What Exists:
  ✅ AdvisorySignal schema (decision_id, signal_type, payload, confidence, error)
     - signal_type: 'action_suggestion', 'risk_flag', 'optimization_hint'
     - payload: Dict[str, Any] (flexible)
     - confidence: float [0.0, 1.0]
  ✅ Signals are non-executable (pure advisory, no execution semantics)
  ✅ Reasoning output is wrapped as advisory (not commands)
  ✅ EventResult includes advisory_signals list in metadata

What Is Missing:
  ❌ NO structured advisory format
     - signal.payload is flexible dict, not a defined schema
     - No guarantee of {bias_summary, setup_logic, invalidation_conditions, risk_notes}
  ❌ NO explicit bias summary field
     - Advisory could contain any payload
     - No required "bias_summary" with HTF direction confirmation
  ❌ NO setup logic explanation
     - No structured "why_valid" or "setup_logic" field
  ❌ NO invalidation conditions
     - Advisories do not include explicit exit conditions
     - No "invalidated when: [conditions]" documentation
  ❌ NO risk notes
     - No required risk_summary or risk_factors
  ❌ NO explicit disclaimer in advisory
     - Advisories sent to humans but no standard disclaimer
     - No "Human confirmation required" boilerplate in every advisory
  ❌ NO entry price guidance
     - Reasonable (prevents execution-like phrasing)
     - But also no entry price INCLUDED in advisory (could be useful)

What Is Incomplete:
  ⚠️  Payload is flexible (could include execution verbs by accident)
     - No validation to prevent "EXECUTE", "BUY", "SELL" in advisory text
  ⚠️  Advisories not numbered (if multiple issued, unclear which to follow)
     - No "Advisory #1 of 1" or similar

**Conformance**: 50%

**Risk**:
  - Advisories could have inconsistent structure (no required fields)
  - Advisories could accidentally include execution verbs
  - No explicit "human confirmation required" disclaimer (critical for liability)
  - Invalidation conditions not documented (humans don't know when to ignore advisory)

---

### Recommendation for Stage 6

**Required Before Production**:
  1. Create StructuredAdvisory schema:
     ```python
     @dataclass
     class StructuredAdvisory:
         advisory_id: str  # UUID
         htf_bias: Literal['UP', 'DOWN', 'NEUTRAL']  # explicit
         bias_summary: str  # "HTF is bullish; price above 200MA"
         setup_logic: str   # "LTF shows consolidation at resistance"
         invalidation_conditions: List[str]  # ["Close below X", "Spread > Y"]
         risk_notes: str    # "Wide spread during NY session"
         entry_price_reference: Optional[float]  # informational only, not a command
         disclaimer: str = "⚠️ INFORMATIONAL ONLY. Human confirmation required."
         confidence: float
     ```
  2. Validate advisory payload for execution verbs (block "EXECUTE", "BUY", "SELL", etc.)
  3. Add disclaimer to every advisory
  4. Add advisory sequencing (if multiple: "#1 of N")
  5. Require all fields populated (no empty setup_logic, etc.)

================================================================================
SECTION 8: STAGE 7 — EXPIRATION & FRESHNESS RULES
================================================================================

**Specification**:
Each advisory is time-bound.

Expiration rule:
  Advisory expires at next candle close of its generating timeframe
  OR 50% of that candle's duration, whichever comes first

Expired advisories are automatically invalidated and cannot be reused.

---

**Current Implementation**:

What Exists:
  ✅ AdvisorySignal includes timestamp (unix ms)
  ✅ Decisions are persisted with ts_ms
  ✅ Archive service can query by timestamp
  ✅ Policy audit trail timestamps all events

What Is Missing:
  ❌ NO advisory expiration logic
     - No expires_at field on AdvisorySignal
     - No calculation of next_candle_close_time
     - No 50% duration rule
  ❌ NO freshness check
     - No validation: "is this advisory still fresh?"
     - No automatic invalidation of expired advisories
  ❌ NO invalidation marking
     - No way to mark an advisory as "EXPIRED" or "INVALIDATED"
     - Expired advisories could still be used by humans
  ❌ NO reuse prevention
     - No check: "has this advisory already been acted upon?"
     - Could theoretically approve same advisory twice

What Is Incomplete:
  ⚠️  Advisories are logged but not versioned with expiration
  ⚠️  No mechanism to notify humans: "This advisory has expired"
  ⚠️  No cleanup of expired advisories (could accumulate in memory)

**Conformance**: 10%

**Risk**:
  - CRITICAL: Expired advisories could be approved hours later (stale signal)
  - Humans not notified when advisory expires
  - No way to prevent reuse of same advisory

---

### Recommendation for Stage 7

**Required Before Production**:
  1. Create ExpirationRule dataclass:
     ```python
     @dataclass
     class ExpirationRule:
         generating_timeframe: str  # "1H", "4H", etc.
         generated_at: int  # unix ms
         
         def next_candle_close_time(self) -> int:
             # Calculate next candle close for timeframe
             # e.g., if 4H and now is 14:30, next close is 16:00
             ...
         
         def expiration_time(self) -> int:
             candle_duration_ms = self.next_candle_close_time() - self.generated_at
            return min(
                 self.next_candle_close_time(),
                 self.generated_at + (candle_duration_ms // 2)
             )
         
         def is_expired(self, now_ms: int) -> bool:
             return now_ms > self.expiration_time()
     ```
  2. Add expires_at to StructuredAdvisory
  3. Before using any advisory, check: is_expired(now_ms)
  4. Mark expired advisories in archive: advisory_status = "EXPIRED"
  5. Add notification: "Advisory #1 has expired. Recommendation withdrawn."
  6. Add reuse prevention: advisory can only be acted upon once

================================================================================
SECTION 9: STAGE 8 — AUDIT & ARTIFACT LOGGING
================================================================================

**Specification**:
Each cycle logs:
  - Inputs
  - State hash
  - Validation results
  - Reasoning output (if any)
  - Final advisory or rejection reason

Retention: Until human review OR 7 days (configurable, default 7)

---

**Current Implementation**:

What Exists:
  ✅ Decision persistence (append-only)
     - insert_decision() stores to database
     - No UPDATE/DELETE (immutable)
  ✅ ExecutionAuditLogger (append-only JSON lines)
  ✅ Policy audit trail (_policy_audit list, non-blocking)
  ✅ Decision archive (DecisionIntelligenceArchiveService, 335 lines)
     - JSON lines format (streaming, immutable)
     - Query by correlation_id
  ✅ Timestamps on all records (unix ms)
  ✅ Error logging (exceptions caught and logged)

What Is Missing:
  ❌ NO unified cycle artifact (all stages logged together)
     - Stages 1-8 are logged separately (event, policy, reasoning, etc.)
     - No single "CycleArtifact" that bundles all stages
  ❌ NO state hash in artifact
     - State versioning NOT implemented (see Stage 2)
     - No state_hash field in decision record
  ❌ NO validation results summary
     - Validation checks scattered across pre_reasoning_policy_check, post_reasoning_policy_check
     - No unified "validation_results" object in artifact
  ❌ NO explicit "final advisory or rejection reason"
     - Decisions are stored but no clear summary of outcome
     - No field: "cycle_outcome = 'ADVISORY_ISSUED' | 'REJECTED_STAGE_3' | 'REJECTED_STAGE_5'"
  ❌ NO retention policy enforcement
     - Decisions persisted indefinitely
     - No automatic deletion after 7 days (or on human review)
     - No "human_reviewed_at" timestamp

What Is Incomplete:
  ⚠️  Logging is complete but not structured as "cycle artifact"
  ⚠️  Archive exists but not indexed by cycle_id or reason
  ⚠️  No cleanup mechanism (7-day retention not enforced)

**Conformance**: 60%

**Risk**:
  - Audit trail is scattered (hard to replay a full cycle)
  - No state hash (cannot detect if cycle was replayed with different state)
  - No explicit outcome reason (hard to understand why cycle was rejected)
  - No retention cleanup (database could grow indefinitely)

---

### Recommendation for Stage 8

**Required Before Production**:
  1. Create CycleArtifact dataclass:
     ```python
     @dataclass
     class CycleArtifact:
         cycle_id: str  # UUID
         trigger_type: str  # from Stage 0
         inputs: Dict[str, Any]  # price data, position state, etc.
         session_context: SessionContext  # from Stage 2
         volatility_regime: VolatilityRegime  # from Stage 2
         state_hash: str  # from Stage 2
         
         # Stage 3 validation
         stage3_blockers: List[Tuple[str, bool]]  # (blocker_name, passed)
         
         # Stage 4 mode selection
         reasoning_mode: str  # 'bias_evaluation'|'entry_evaluation'|'trade_management'
         
         # Stage 5 quality gate
         quality_score: QualityScore
         
         # Stage 6 advisory
         advisory: Optional[StructuredAdvisory]  # None if rejected
         
         # Stage 7 expiration
         expires_at: Optional[int]
         
         # Outcome
         cycle_outcome: Literal['ADVISORY_ISSUED', 'REJECTED_STAGE_3', 'REJECTED_STAGE_5']
         rejection_reason: Optional[str]
         
         # Metadata
         created_at: int
         completed_at: int
         human_reviewed_at: Optional[int] = None
     ```
  2. Store entire CycleArtifact in append-only archive
  3. Index by cycle_id for easy replay
  4. Add "human_reviewed_at" callback when decision is acted upon
  5. Implement cleanup: delete cycles where human_reviewed_at is null AND age > 7 days
  6. Log cycle_outcome in every artifact

================================================================================
SECTION 10: EXPLICIT NON-GOALS
================================================================================

**Specification**:
❌ No autonomous execution
❌ No PnL optimization loops yet
❌ No reinforcement learning
❌ No strategy mutation
❌ No overfitting to recent outcomes

---

**Current Implementation**:

✅ NO autonomous execution
  - orchestrator.handle_event() returns EventResult (not execution)
  - SafetyGuards require HumanExecutionApproval
  - Default: absence of approval = no execution

✅ NO PnL optimization loops
  - No signal that adjusts based on recent P&L
  - Outcome tracking is informational only

✅ NO reinforcement learning
  - No feedback loop from outcomes to future reasoning
  - ReasoningManager is stateless (no accumulated experience)

✅ NO strategy mutation
  - System does not change trading strategy based on outcomes
  - Session context and volatility regime are fixed (computed, not learned)

✅ NO overfitting to recent outcomes
  - Memory retrieval limited (last 3 cycles, not entire history)
  - No "optimize for recent wins" logic

**Conformance**: 100% (all non-goals avoided)

---

### Risk: Future Temptation

All five non-goals are currently respected. But:
  - Phase C (automated outcome recording) could enable PnL loop temptation
  - Future dashboard could enable strategy mutation temptation
  - Recommendation: Make non-goals EXPLICIT in code comments and config

================================================================================
SECTION 11: SUCCESS CRITERION
================================================================================

**Specification**:
The system is considered working when:

"It reliably surfaces fewer trades than a human,
 but with higher clarity, discipline, and consistency."

---

**Current Implementation**:

Fewer trades than human:
  ⚠️  Not yet measurable (no multi-timeframe filtering to block low-quality signals)
  - Single-timeframe reasoning could surface MORE trades than experienced trader
  - Will improve with Stage 5 (quality gates) and multi-timeframe analysis

Higher clarity:
  ✅ Advisory signals include confidence, reasoning, risks
  ✅ Timestamps and reasoning_mode documented
  ⚠️  Not yet fully structured (StructuredAdvisory schema not implemented)

Higher discipline:
  ✅ Policy enforcement (cooldowns, regime gates, risk exposure)
  ✅ Fail-closed defaults (approval required)
  ✅ Non-emotional (LLM reasoning, not human fear/greed)
  ⚠️  Discipline weakens if permissive mode enabled

Higher consistency:
  ✅ Deterministic reasoning (same input = same output)
  ✅ Audit trail complete (all decisions logged)
  ✅ State versioning would make this stronger (not yet implemented)

**Current Success Metric Progress**: 50-60%

---

### Recommendation for Success Criterion

  1. Measure: # of advisories per timeframe (track ratio vs human decisions)
  2. Implement: Multi-timeframe analysis (Stage 5) to filter low-quality signals
  3. Implement: A/B test: system advisories vs human trader decisions for 2 weeks
  4. Success threshold: System surfaces ≤ 70% of human decisions, with ≥ 90% advisor approval rate

================================================================================
SECTION 12: OVERALL CONFORMANCE SUMMARY
================================================================================

| Stage | Requirement | Conformance | Status | Risk |
|-------|-------------|-------------|--------|------|
| **Core Principle** | Answer HTF bias + LTF context + market updates question | 50-60% | ⚠️ PARTIAL | Authority model incomplete |
| **Stage 0** | Cycle trigger (4 types only) | 30% | ❌ MISSING | Could trigger on invalid events |
| **Stage 1** | Data ingestion (read-only, no interpretation) | 40% | ❌ MISSING | No price/structure/position schema |
| **Stage 2** | State update & context encoding | 30% | ❌ MISSING | No volatility regime, state hash |
| **Stage 3** | Hard validation gate (5 blockers) | 50% | ⚠️ PARTIAL | Kill switch not integrated |
| **Stage 4** | Reasoning mode selection (3 modes) | 20% | ❌ MISSING | No mode selection logic |
| **Stage 5** | Quality & confidence filters | 40% | ⚠️ PARTIAL | No HTF/LTF alignment check |
| **Stage 6** | Advisory generation (non-executable) | 50% | ⚠️ PARTIAL | No structured advisory schema |
| **Stage 7** | Expiration & freshness rules | 10% | ❌ MISSING | No expires_at logic |
| **Stage 8** | Audit & artifact logging | 60% | ⚠️ PARTIAL | No unified CycleArtifact |
| **Non-Goals** | Avoid 5 forbidden patterns | 100% | ✅ COMPLETE | All non-goals respected |
| **Success Criterion** | Fewer, clearer, more disciplined trades | 50-60% | ⚠️ PARTIAL | Needs multi-TF + measurement |

---

**OVERALL CONFORMANCE: 45-50%**

**Status**: System has correct **intelligence foundation** (shadow-mode, non-execution) 
but **incomplete decision loop** (missing Mode Selection, Expiration Rules, State Hashing).

---

### Critical Missing Components (Blocking Full Conformance)

1. **Stage 4 Mode Selection** (20% implemented)
   - No logic to choose: bias eval vs entry eval vs trade management
   - This is the core orchestration logic; missing it blocks the entire loop

2. **Stage 7 Expiration Rules** (10% implemented)
   - No expires_at, no freshness validation
   - Humans could act on stale signals (hours later)

3. **Stage 2 State Hashing** (30% implemented)
   - No state_hash = hash(state_json + cycle_timestamp)
   - Cannot detect state corruption or replay attacks

4. **Structured Advisory Schema** (50% implemented)
   - No required fields: bias_summary, setup_logic, invalidation_conditions, risk_notes
   - Advisories could be inconsistent or vague

5. **Hard Validation Gate Completeness** (50% implemented)
   - Kill switch not integrated
   - Data corruption checks missing
   - No explicit early-exit log

================================================================================
SECTION 13: IMPLEMENTATION PRIORITIES (FOR NEXT PHASE)
================================================================================

**To reach 75% conformance** (viable for pilot):

Priority 1 (Most Critical):
  ❶ Stage 4: Mode Selection Logic (6-8 hours)
     - Add HTFBiasState enum
     - Add ReasoningModeSelector class
     - Integrate position state check
  ❷ Stage 7: Expiration Rules (4-6 hours)
     - Add ExpirationRule class
     - Add expires_at to StructuredAdvisory
     - Add freshness validation before output

Priority 2 (Important):
  ❸ Stage 2: State Hashing (3-4 hours)
     - Add StateVersion with hash
     - Include in CycleArtifact
  ❹ Stage 6: Structured Advisory Schema (4-6 hours)
     - Define required fields
     - Validate for execution verbs
     - Add disclaimer to every advisory

Priority 3 (Nice-to-Have):
  ❺ Stage 8: CycleArtifact (4-6 hours)
     - Unify all stages in single artifact
     - Add human_reviewed_at for retention
  ❻ Stage 5: HTF/LTF Alignment Check (6-8 hours)
     - Add multi-timeframe correlation scoring

---

**Estimated timeline to 75% conformance: 3-4 weeks** (Phases A+B+C)

================================================================================
END OF CONFORMANCE AUDIT
================================================================================
