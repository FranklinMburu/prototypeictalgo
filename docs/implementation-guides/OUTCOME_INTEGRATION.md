# Outcome-Aware Decision Tracking

## Overview

This document describes the **DecisionOutcome** system, a new persistent model for tracking trade outcomes when trades close. It bridges decision orchestration with outcome analysis, enabling outcome-aware decision feedback without introducing learning logic yet.

The system is designed to:
- **Persist trade outcomes** linked to decisions via `decision_id`
- **Enable outcome analysis** per symbol, signal type, and exit reason
- **Document integration points** for future enhancements (PolicyStore refinement, ReasoningManager feedback)
- **Maintain backward compatibility** with existing orchestration flow
- **Follow async patterns** consistent with DecisionOrchestrator

## Data Model

### DecisionOutcome (reasoner_service.storage)

New ORM model in `reasoner_service/storage.py`:

```python
class DecisionOutcome(Base):
    __tablename__ = "decision_outcomes"
    
    # Identifiers
    id: str (UUID, primary key)
    decision_id: str (FK to Decision, non-null, indexed)
    
    # Trade Context
    symbol: str (indexed) - Trading pair (e.g., "EURUSD")
    timeframe: str - Signal timeframe (e.g., "4H", "1D")
    signal_type: str - Type of signal (e.g., "bullish_choch", "bearish_bos")
    
    # Pricing & P&L
    entry_price: float - Entry price
    exit_price: float - Exit price (may differ from TP/SL)
    pnl: float - Profit/loss amount
    
    # Outcome Classification
    outcome: str - "win" (pnl > 0), "loss" (pnl < 0), "breakeven" (pnl == 0)
    exit_reason: str - "tp" (take profit), "sl" (stop loss), "manual", "timeout"
    
    # Timestamps
    closed_at: datetime - When trade closed (UTC, non-null)
    created_at: datetime - When record created (UTC, indexed)
```

**Rationale:**
- `decision_id` (non-null FK): Links outcome to the decision that triggered entry
- `outcome` (computed): Automatically derived from pnl sign for consistency
- `exit_reason`: Enables analysis by exit type (e.g., "80% of bullish_choch signals exit at TP")
- Indexed fields: `decision_id`, `symbol`, `created_at` for efficient queries

### Trade (ict_trading_system.src.models.database) - Extended

Existing Trade model enhanced with outcome-aware fields:

```python
class Trade(Base):
    __tablename__ = 'trades'
    
    # Existing fields (unchanged)
    id: int (primary key)
    signal_id: int (FK)
    entry_price: float
    sl: float
    tp: float
    outcome: str (nullable, for backward compat)
    pnl: float (nullable)
    notes: str (nullable)
    timestamp: datetime
    
    # NEW FIELDS (optional, for symmetry with DecisionOutcome)
    decision_id: str (nullable, indexed) - UUID from reasoner_service.Decision
    exit_price: float (nullable) - Actual exit price
    exit_reason: str (nullable) - "tp", "sl", "manual", "timeout"
    closed_at: datetime (nullable, indexed) - When trade closed
```

**Rationale:**
- Backward compatible (all new fields are nullable)
- Enables symmetry between ict_trading_system.Trade and reasoner_service.DecisionOutcome
- Allows legacy code to continue without modification
- Provides optional link to reasoner_service decisions

## API Reference

### Persistence Functions (reasoner_service.storage)

#### `insert_decision_outcome()`

Insert a trade outcome record linked to a decision.

```python
async def insert_decision_outcome(
    sessionmaker,
    decision_id: str,
    symbol: str,
    timeframe: str,
    signal_type: str,
    entry_price: float,
    exit_price: float,
    pnl: float,
    outcome: str,  # "win" | "loss" | "breakeven"
    exit_reason: str,  # "tp" | "sl" | "manual" | "timeout"
    closed_at: datetime.datetime,
) -> str:
    """Returns: outcome_id (UUID string)"""
```

**Usage Example:**

```python
outcome_id = await storage.insert_decision_outcome(
    sessionmaker=db_session,
    decision_id="550e8400-e29b-41d4-a716-446655440000",
    symbol="EURUSD",
    timeframe="4H",
    signal_type="bullish_choch",
    entry_price=1.0850,
    exit_price=1.0900,
    pnl=50.0,
    outcome="win",  # Auto-derived from pnl > 0
    exit_reason="tp",
    closed_at=datetime.now(timezone.utc),
)
```

#### `get_decision_outcome_by_id()`

Retrieve a single outcome by ID.

```python
async def get_decision_outcome_by_id(sessionmaker, outcome_id: str) -> Optional[dict]
    """Returns: dict with all outcome fields or None"""
```

#### `get_recent_decision_outcomes()`

Retrieve recent outcomes, optionally filtered by symbol.

```python
async def get_recent_decision_outcomes(
    sessionmaker,
    limit: int = 10,
    symbol: Optional[str] = None,
) -> List[dict]
    """Returns: list of outcome dicts, ordered by created_at DESC"""
```

**Usage Example:**

```python
# Get last 10 outcomes
recent = await storage.get_recent_decision_outcomes(sessionmaker, limit=10)

# Get last 20 outcomes for EURUSD
eurusd_recent = await storage.get_recent_decision_outcomes(
    sessionmaker, 
    limit=20, 
    symbol="EURUSD"
)
```

#### `get_outcomes_by_decision_id()`

Retrieve all outcomes linked to a specific decision (multi-leg trades).

```python
async def get_outcomes_by_decision_id(sessionmaker, decision_id: str) -> List[dict]
    """Returns: list of outcome dicts, ordered by created_at ASC"""
```

#### `get_outcomes_by_symbol()`

Retrieve outcomes for a symbol, useful for per-symbol performance analysis.

```python
async def get_outcomes_by_symbol(
    sessionmaker,
    symbol: str,
    limit: int = 100,
) -> List[dict]
    """Returns: list of outcome dicts, ordered by closed_at DESC"""
```

### DecisionOutcomeRecorder (reasoner_service.outcome_recorder)

High-level async recorder for recording trade outcomes. Primary API for producers.

#### `DecisionOutcomeRecorder.record_trade_outcome()`

Record a trade outcome when a trade closes. Non-blocking on database errors.

```python
async def record_trade_outcome(
    self,
    decision_id: str,
    symbol: str,
    timeframe: str,
    signal_type: str,
    entry_price: float,
    exit_price: float,
    pnl: float,
    exit_reason: str = "manual",  # "tp" | "sl" | "manual" | "timeout"
    closed_at: Optional[datetime] = None,  # Defaults to now()
) -> Optional[str]:
    """
    Returns: outcome_id (UUID string) or None on error
    
    Raises: ValueError on validation errors (invalid exit_reason, etc.)
    """
```

**Usage Example:**

```python
from reasoner_service.outcome_recorder import DecisionOutcomeRecorder

# Create recorder
recorder = DecisionOutcomeRecorder(sessionmaker)

# Record a winning trade
outcome_id = await recorder.record_trade_outcome(
    decision_id="550e8400-e29b-41d4-a716-446655440000",
    symbol="EURUSD",
    timeframe="4H",
    signal_type="bullish_choch",
    entry_price=1.0850,
    exit_price=1.0900,
    pnl=50.0,
    exit_reason="tp",
)

if outcome_id:
    print(f"Outcome recorded: {outcome_id}")
else:
    print("Failed to record outcome")
```

### Pydantic Schemas (reasoner_service.schemas)

```python
from reasoner_service.schemas import (
    DecisionOutcomeCreate,
    DecisionOutcome,
)

# Create from input
create_schema = DecisionOutcomeCreate(
    decision_id="...",
    symbol="EURUSD",
    timeframe="4H",
    signal_type="bullish_choch",
    entry_price=1.0850,
    exit_price=1.0900,
    pnl=50.0,
    outcome="win",
    exit_reason="tp",
    closed_at=datetime.now(timezone.utc),
)

# Retrieve from storage
outcome_schema = DecisionOutcome(
    id="outcome-uuid",
    decision_id="decision-uuid",
    symbol="EURUSD",
    ...
    created_at=datetime.now(timezone.utc),
)
```

## Integration Points (Future)

### 1. PolicyStore Refinement

**When:** After collecting 50+ outcomes per signal type/symbol

**How:** Analyze outcome patterns to refine policies

```
Example metrics per signal type:
- bullish_choch: 72% win rate, avg PnL +45 pips, 85% exit at TP
- bearish_bos: 58% win rate, avg PnL -12 pips, 40% exit at SL

Actions:
- Increase bullish_choch exposure (higher win rate)
- Add regime filter for bearish_bos (lower win rate)
- Extend TP targets (85% hit rate suggests room for more)
```

**Implementation:** Add outcome consumer to DecisionOrchestrator

```python
# Future: In orchestrator.py
async def _refine_policies_from_outcomes(self):
    outcomes = await storage.get_recent_decision_outcomes(
        self.sessionmaker, 
        limit=100
    )
    win_rate = sum(1 for o in outcomes if o['outcome'] == 'win') / len(outcomes)
    
    if win_rate < 0.50:
        logger.warning(f"Win rate {win_rate} below threshold, tightening policies")
        # Update PolicyStore exposure, cooldown parameters
```

### 2. ReasoningManager Feedback Loop

**When:** After collecting decision→outcome pairs for specific reasoning modes

**How:** Use outcomes to improve reasoning function quality

```
Example feedback:
- Mode "aggressive_entry": 65% win rate when confidence > 0.8
- Mode "conservative_entry": 72% win rate when confidence > 0.6

Action:
- Recommend conservative_entry mode for production
- Adjust confidence thresholds based on outcome correlation
```

**Implementation:** Add outcome feedback to ReasoningManager

```python
# Future: In reasoning_manager.py
async def feedback_from_outcomes(self, outcomes: List[dict]):
    """Update reasoning function weights based on outcomes."""
    for outcome in outcomes:
        if outcome['outcome'] == 'win':
            # Increase weight for this signal type / confidence range
            self._mode_weights[outcome['signal_type']] += 0.01
        else:
            # Decrease weight
            self._mode_weights[outcome['signal_type']] -= 0.01
```

### 3. EventTracker Lifecycle Completion

**When:** After trade closes and outcome is recorded

**How:** Link outcome back to EventTracker to complete decision lifecycle

```python
# Future: In orchestration_advanced.py
async def close_event_with_outcome(self, event_id: str, outcome: dict):
    """Close event lifecycle with final outcome."""
    event = self._events[event_id]
    event.state = EventState.CLOSED
    event.outcome = outcome
    event.pnl = outcome['pnl']
    event.closed_at = outcome['closed_at']
```

### 4. Observability Enhancement

**When:** Real-time as outcomes are recorded

**How:** Aggregate outcomes in Prometheus metrics

```python
# Future: In metrics.py
decisions_outcome_total = Counter(
    'decisions_outcome_total',
    'Total decision outcomes by result',
    ['symbol', 'signal_type', 'outcome']
)

decisions_outcome_pnl = Histogram(
    'decisions_outcome_pnl',
    'P&L distribution by outcome',
    ['signal_type']
)

# Usage in outcome recorder:
decisions_outcome_total.labels(
    symbol=outcome['symbol'],
    signal_type=outcome['signal_type'],
    outcome=outcome['outcome']
).inc()

decisions_outcome_pnl.labels(
    signal_type=outcome['signal_type']
).observe(outcome['pnl'])
```

### 5. A/B Testing Framework (Future)

**When:** After collecting outcomes for multiple policy versions

**How:** Compare outcomes across policy variants

```python
# Future: Multi-policy testing
class ABTestFramework:
    async def compare_policies(self, policy_a_id: str, policy_b_id: str):
        outcomes_a = await storage.get_outcomes_by_policy(policy_a_id)
        outcomes_b = await storage.get_outcomes_by_policy(policy_b_id)
        
        win_rate_a = sum(1 for o in outcomes_a if o['outcome'] == 'win') / len(outcomes_a)
        win_rate_b = sum(1 for o in outcomes_b if o['outcome'] == 'win') / len(outcomes_b)
        
        # Statistical significance test
        return {
            'winner': 'policy_b' if win_rate_b > win_rate_a else 'policy_a',
            'confidence': calculate_confidence(win_rate_a, win_rate_b),
        }
```

## Migration & Schema Evolution

### Initial Deployment (No Breaking Changes)

1. **reasoner_service.storage**: Add DecisionOutcome model
   - New table `decision_outcomes` created on first run
   - Existing Decision, NotificationLog tables unchanged

2. **ict_trading_system.src.models.Trade**: Add optional fields
   - New columns: `decision_id`, `exit_price`, `exit_reason`, `closed_at` (all nullable)
   - Existing Trade records unaffected
   - Old code continues to work unchanged

3. **reasoner_service.schemas**: Add DecisionOutcome schemas
   - New models don't affect existing Decision, Triggers, Versions
   - Backward compatible

### Enabling DecisionOutcomeRecorder

```python
# In DecisionOrchestrator.setup():
from reasoner_service.outcome_recorder import create_outcome_recorder

self.outcome_recorder = await create_outcome_recorder(self.sessionmaker)
```

### Recording Outcomes

When trade closes (external system trigger):

```python
# External system (e.g., trading bot) calls:
outcome_id = await orchestrator.outcome_recorder.record_trade_outcome(
    decision_id=original_decision_id,
    symbol="EURUSD",
    timeframe="4H",
    signal_type="bullish_choch",
    entry_price=1.0850,
    exit_price=1.0900,
    pnl=50.0,
    exit_reason="tp",
)
```

## Testing

Comprehensive tests in `tests/test_decision_outcome.py`:

- **Model creation**: Basic insertion and persistence
- **Retrieval**: By ID, recent, by symbol, by decision_id
- **Validation**: outcome values, exit_reason values
- **Async patterns**: Session handling, concurrent operations
- **Recorder API**: Non-blocking error handling
- **Integration**: Multi-leg trades, symbol filtering

Run tests:

```bash
pytest tests/test_decision_outcome.py -v
pytest tests/test_decision_outcome.py::TestDecisionOutcomeRecorder -v
```

## Non-Breaking, Minimal Changes

### Backward Compatibility

- ✅ No modifications to DecisionOrchestrator business logic
- ✅ No modifications to ReasoningManager
- ✅ No modifications to PlanExecutor
- ✅ No modifications to PolicyStore
- ✅ All existing tests pass unchanged
- ✅ New tests isolated in `test_decision_outcome.py`
- ✅ Optional fields on Trade model (nullable)
- ✅ New tables only created on first run

### Reversibility

- Remove DecisionOutcome from storage.py (just drop the class)
- Remove outcome_recorder.py
- Drop `decision_outcomes` table from database
- Set new Trade fields to default values in existing records

## Observability & Logging

### DecisionOutcomeRecorder Logging

- **INFO**: Successful outcome recording with decision_id, symbol, outcome, PnL
- **DEBUG**: Integration points being logged (for future features)
- **ERROR**: Validation or database errors (non-blocking, error logged)

Example log output:

```
INFO: Recorded trade outcome: decision_id=550e8400-e29b-41d4-a716-446655440000 symbol=EURUSD outcome=win pnl=50.0 exit_reason=tp id=123e4567-e89b-12d3-a456-426614174000

DEBUG: [INTEGRATION] Outcome recorded: Decision 550e8... → win (PnL=50.0). Symbol=EURUSD, Signal=bullish_choch. Future: Use for PolicyStore refinement, ReasoningManager feedback...
```

## Future Enhancements

### Short-term (1-2 sprints)

1. **PolicyStore Integration**: Analyze outcomes to refine policies
2. **Prometheus Metrics**: Per-symbol, per-signal-type outcome aggregates
3. **EventTracker Lifecycle**: Link outcomes to events

### Medium-term (1-2 quarters)

1. **ReasoningManager Feedback**: Use outcomes to improve reasoning
2. **Performance Dashboard**: Grafana dashboard for outcome analysis
3. **A/B Testing**: Compare policy versions by outcome

### Long-term (2-3 quarters+)

1. **Machine Learning**: Train models on outcome patterns
2. **Anomaly Detection**: Flag unusual outcome distributions
3. **Risk Modeling**: Predict PnL distributions from decision patterns

## References

- **Storage Layer**: `reasoner_service/storage.py` (DecisionOutcome class, CRUD functions)
- **Recorder API**: `reasoner_service/outcome_recorder.py` (DecisionOutcomeRecorder)
- **Schemas**: `reasoner_service/schemas.py` (Pydantic models)
- **Tests**: `tests/test_decision_outcome.py` (comprehensive test suite)
- **Trade Extension**: `ict_trading_system/src/models/database.py` (Trade model)

## Appendix: Configuration & Defaults

No new environment variables required. All defaults:

- Database location: Inherited from existing `DATABASE_URL`
- Session timeout: Same as existing DecisionOrchestrator sessions
- Retry policy: Non-blocking (errors logged, not raised)
- Outcome classification: Automatic from PnL sign

## Appendix: Common Queries

### Get win rate for a symbol

```python
outcomes = await storage.get_outcomes_by_symbol(sessionmaker, "EURUSD", limit=100)
win_count = sum(1 for o in outcomes if o['outcome'] == 'win')
win_rate = win_count / len(outcomes) if outcomes else 0
print(f"EURUSD win rate: {win_rate:.1%}")
```

### Get avg PnL by signal type

```python
from collections import defaultdict

recent = await storage.get_recent_decision_outcomes(sessionmaker, limit=200)
by_signal = defaultdict(list)
for outcome in recent:
    by_signal[outcome['signal_type']].append(outcome['pnl'])

for signal_type, pnls in by_signal.items():
    avg_pnl = sum(pnls) / len(pnls)
    print(f"{signal_type}: avg PnL = {avg_pnl:.1f}")
```

### Get TP vs SL exit rates

```python
outcomes = await storage.get_outcomes_by_symbol(sessionmaker, "EURUSD", limit=100)
tp_count = sum(1 for o in outcomes if o['exit_reason'] == 'tp')
sl_count = sum(1 for o in outcomes if o['exit_reason'] == 'sl')
tp_rate = tp_count / len(outcomes) if outcomes else 0
sl_rate = sl_count / len(outcomes) if outcomes else 0
print(f"TP rate: {tp_rate:.1%}, SL rate: {sl_rate:.1%}")
```

---

**Status:** ✅ Complete, Non-Breaking, Production-Ready  
**Reversible:** ✅ Yes (drop tables + remove code)  
**Tested:** ✅ 20+ comprehensive tests  
**Backward Compatible:** ✅ Yes (optional fields, new models only)
