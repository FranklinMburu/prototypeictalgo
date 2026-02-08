<!-- COUNTERFACTUAL_ENFORCEMENT_SIMULATOR_SUMMARY.md -->

# Counterfactual Enforcement Simulator

## Critical Disclaimer

> **This component simulates enforcement only and cannot affect live decisions.**
>
> Counterfactual analysis shows hypothetically what would have happened if governance rules were enforced, but no actual blocking occurs. This is an informational tool for policy evaluation only.

---

## What Is This Component?

The **CounterfactualEnforcementSimulator** replays decision timelines and calculates hypothetical outcomes if governance rules were applied, without executing any enforcement.

It answers questions like:
- "What would P&L look like if we blocked trades in violation of Rule X?"
- "How much drawdown would we have prevented?"
- "Which rules would have blocked the most losing trades?"
- "Would stricter enforcement be beneficial?"

## Why Counterfactual Simulation Is Required

### 1. Evidence-Based Policy Decisions
Policies should be enforced only after evidence shows they improve outcomes. Counterfactual simulation provides this evidence **before** enforcement is enabled.

### 2. Risk Assessment Without Risk
Evaluate policy impact on a full historical dataset without modifying live trading. See the hypothetical cost/benefit with zero downside.

### 3. Compliance Scenario Modeling
Stakeholders need to understand enforcement impact before deployment. Simulation answers "what-if" questions with concrete numbers.

### 4. Regime-Aware Rule Tuning
Different market conditions may benefit from different rule configurations. Counterfactual analysis helps optimize rules per regime.

### 5. Veto Impact Analysis
When policies veto trades, we need to know if they were right. Counterfactual simulation shows counterfactual P&L of blocked trades.

## Why This Is NOT Enforcement

| Feature | Enforcement | This Simulator |
|---------|-------------|-----------------|
| Modifies trading | ✅ Blocks real trades | ❌ Analysis only |
| Changes outcomes | ✅ Prevents actual losses | ❌ Hypothetical only |
| Affects live system | ✅ Yes | ❌ No |
| Mutates timelines | ✅ Could block events | ❌ Read-only replay |
| Influences decisions | ✅ Yes | ❌ Informational |
| Can be undone | ❌ No | ✅ Always reversible |

---

## Architecture

### Data Flow

```
DecisionTimelineService (read-only)
        ↓
        [Replay events]
        ↓
TradeGovernanceService (violation detection)
        ↓
        [Evaluate each trade against rules]
        ↓
CounterfactualEnforcementSimulator (calculation)
        ↓
        [Calculate hypothetical P&L, drawdown]
        ↓
        [Generate report]
        ↓
Report (informational only)
```

### Design Principles

1. **Read-Only**: Never writes to any service or database
2. **Deterministic**: Same input → identical output, every time
3. **Fail-Silent**: Invalid inputs return graceful errors, never crash
4. **Immutable**: Timelines are never modified
5. **Replay-Based**: All analysis from historical event replay
6. **Pure Simulation**: No actual blocking or execution
7. **Informational**: Results are evidence for human decision-makers

---

## How Counterfactual Simulation Works

### Step 1: Replay Decision Timeline
Retrieve all events for a trade from `DecisionTimelineService`:
```
SIGNAL_DETECTED → DECISION_PROPOSED → GOVERNANCE_EVALUATED 
  → TRADE_EXECUTED → OUTCOME_RECORDED
```

### Step 2: Extract Violations
Identify any governance violations recorded in the timeline:
```python
for event in timeline:
    if event["event_type"] == "GOVERNANCE_EVALUATED":
        violations = event["payload"]["violations"]
```

### Step 3: Classify Trade
If violations exist: `blocked_hypothetically`
If no violations: `allowed_hypothetically`

### Step 4: Calculate Counterfactual Outcomes

#### For Blocked Trades:
- Remove from P&L calculation
- Reduce peak drawdown (no losing trade)
- Record rule violation

#### For Allowed Trades:
- Include in both actual and counterfactual P&L
- Use in both drawdown calculations

### Step 5: Compute Metrics

**P&L Delta:**
```
counterfactual_pnl = actual_pnl - (blocked_trades_pnl)
pnl_difference = counterfactual_pnl - actual_pnl
```

**Drawdown Delta:**
```
original_dd = max(peak - cumulative_pnl) across actual
counterfactual_dd = max(peak - cumulative_pnl) for allowed trades only
```

**Rule Impact:**
```
rule_impact = {
    "rule_name": violation_count,
    ...
}
```

---

## API Reference

### Main Methods

#### `simulate(correlation_id: str) -> dict`

Simulate enforcement for a single trade.

**Parameters:**
- `correlation_id`: Trade identifier from DecisionTimelineService

**Returns:**
```python
{
    "correlation_id": "trade_123",
    "original_outcome": {
        "pnl": 125.0,
        "trades_executed": 1,
        "outcomes_recorded": 1,
    },
    "would_have_been_allowed": False,
    "violated_rules": ["max_daily_loss", "cooldown_period"],
    "counterfactual_pnl": 175.0,
    "pnl_difference": 50.0,  # Would have been better
    
    "execution_impact": {
        "trades_executed": 1,
        "trades_blocked": 0,  # Hypothetically
        "max_drawdown_original": 100.0,
        "max_drawdown_counterfactual": 50.0,
        "drawdown_improvement": 50.0,
    },
    
    "rule_impact": {
        "max_daily_loss": 1,
        "cooldown_period": 1,
    },
    
    "explanation": "Trade violated 2 rules...",
    "disclaimer": "This simulation is informational only...",
    "simulated_at": "2025-12-19T10:30:45.123Z",
}
```

#### `simulate_batch(correlation_ids: List[str]) -> List[dict]`

Simulate enforcement across multiple trades.

**Parameters:**
- `correlation_ids`: List of trade identifiers

**Returns:**
- List of individual simulation results
- Last item is batch summary with aggregates:
  ```python
  {
      "_batch_summary": True,
      "total_simulations": 100,
      "allowed_count": 75,
      "blocked_count": 25,
      "average_pnl_difference": 12.5,
      "total_pnl_difference": 1250.0,
      "rule_violation_totals": {
          "max_daily_loss": 18,
          "cooldown_period": 12,
          "killzone_hours": 5,
      },
  }
  ```

#### `export_simulation(result: dict) -> dict`

Export simulation with metadata and disclaimer.

**Parameters:**
- `result`: Output from `simulate()` or `simulate_batch()`

**Returns:**
- Same result with added metadata:
  ```python
  {
      ...original_result...,
      "_export_metadata": {
          "exported_at": "2025-12-19T10:30:45.123Z",
          "service": "CounterfactualEnforcementSimulator",
          "version": "1.0",
      },
      "disclaimer": "This component simulates enforcement only...",
  }
  ```

---

## Usage Examples

### Example 1: Analyze Single Trade

```python
from reasoner_service.counterfactual_enforcement_simulator import CounterfactualEnforcementSimulator
from reasoner_service.decision_timeline_service import DecisionTimelineService
from reasoner_service.trade_governance_service import TradeGovernanceService

# Initialize services
timeline_service = DecisionTimelineService()
governance_service = TradeGovernanceService()

# Create simulator
simulator = CounterfactualEnforcementSimulator(
    timeline_service,
    governance_service,
)

# Simulate single trade
result = simulator.simulate("trade_12345")

print(f"Original PnL: {result['original_outcome']['pnl']}")
print(f"Counterfactual PnL: {result['counterfactual_pnl']}")
print(f"Would have been allowed: {result['would_have_been_allowed']}")
print(f"Violated rules: {result['violated_rules']}")
```

### Example 2: Batch Analysis Across Trading Day

```python
# Simulate all trades from a trading day
trade_ids = timeline_service.get_all_correlation_ids()
results = simulator.simulate_batch(trade_ids)

# Extract batch summary (last item)
summary = results[-1]

print(f"Total trades: {summary['total_simulations']}")
print(f"Would have been blocked: {summary['blocked_count']}")
print(f"P&L improvement if enforced: {summary['total_pnl_difference']}")
print(f"Most common violation: {max(summary['rule_violation_totals'], key=summary['rule_violation_totals'].get)}")
```

### Example 3: Policy Effectiveness Evaluation

```python
# Simulate enforcement of one rule at a time
rules = ["max_daily_loss", "cooldown_period", "killzone_hours"]

for rule in rules:
    results = simulator.simulate_batch(all_trade_ids)
    summary = results[-1]
    
    # Filter for this rule's impact
    rule_violations = summary["rule_violation_totals"].get(rule, 0)
    
    print(f"Rule '{rule}' violations: {rule_violations}")
    print(f"Potential P&L impact: {summary['total_pnl_difference']}")
```

### Example 4: Risk Scenario Modeling

```python
# What if we tightened drawdown limits?
stricter_governance = TradeGovernanceService(max_daily_loss=300.0)
simulator_strict = CounterfactualEnforcementSimulator(
    timeline_service,
    stricter_governance,
)

# Run simulation with stricter rules
results_strict = simulator_strict.simulate_batch(trade_ids)
summary_strict = results_strict[-1]

# Compare to baseline
results_baseline = simulator.simulate_batch(trade_ids)
summary_baseline = results_baseline[-1]

print(f"Baseline drawdown impact: {summary_baseline['total_pnl_difference']}")
print(f"Strict rules impact: {summary_strict['total_pnl_difference']}")
```

---

## Complete Example: Full Trade Lifecycle

### Recorded Timeline

```json
[
  {
    "event_type": "SIGNAL_DETECTED",
    "timestamp": "2025-12-19T09:15:00Z",
    "payload": {"signal": "momentum", "strength": 0.87},
    "correlation_id": "trade_001",
    "sequence_number": 0
  },
  {
    "event_type": "DECISION_PROPOSED",
    "timestamp": "2025-12-19T09:15:05Z",
    "payload": {"action": "BUY", "symbol": "EURUSD"},
    "correlation_id": "trade_001",
    "sequence_number": 1
  },
  {
    "event_type": "POLICY_EVALUATED",
    "timestamp": "2025-12-19T09:15:10Z",
    "payload": {"result": "passed", "confidence": 0.85},
    "correlation_id": "trade_001",
    "sequence_number": 2
  },
  {
    "event_type": "GOVERNANCE_EVALUATED",
    "timestamp": "2025-12-19T09:15:15Z",
    "payload": {
      "violations": ["max_daily_loss_exceeded"],
      "explanation": "Cumulative loss exceeded $500 limit"
    },
    "correlation_id": "trade_001",
    "sequence_number": 3
  },
  {
    "event_type": "TRADE_EXECUTED",
    "timestamp": "2025-12-19T09:15:20Z",
    "payload": {"entry": 1.1050, "size": 100},
    "correlation_id": "trade_001",
    "sequence_number": 4
  },
  {
    "event_type": "OUTCOME_RECORDED",
    "timestamp": "2025-12-19T09:45:00Z",
    "payload": {"pnl": 125.0, "exit": 1.1062},
    "correlation_id": "trade_001",
    "sequence_number": 5
  }
]
```

### Simulation Output

```json
{
  "correlation_id": "trade_001",
  "original_outcome": {
    "pnl": 125.0,
    "trades_executed": 1,
    "outcomes_recorded": 1
  },
  "would_have_been_allowed": false,
  "violated_rules": ["max_daily_loss_exceeded"],
  "counterfactual_pnl": 0.0,
  "pnl_difference": -125.0,
  "execution_impact": {
    "trades_executed": 1,
    "trades_blocked": 1,
    "max_drawdown_original": 0.0,
    "max_drawdown_counterfactual": 0.0,
    "drawdown_improvement": 0.0
  },
  "rule_impact": {
    "max_daily_loss_exceeded": 1
  },
  "explanation": "Trade trade_001 violated 1 governance rule: max_daily_loss_exceeded. If enforced, would have worsened PnL by 125.0. Trade was profitable despite violations.",
  "disclaimer": "This simulation is informational only and does not influence live trading. Counterfactual analysis shows what would have happened if governance rules were enforced, but no actual blocking occurs.",
  "simulated_at": "2025-12-19T10:00:00Z"
}
```

### Interpretation

| Metric | Value | Meaning |
|--------|-------|---------|
| `would_have_been_allowed` | `false` | Trade violated a rule |
| `violated_rules` | `["max_daily_loss_exceeded"]` | Which rule(s) were violated |
| `original_outcome.pnl` | `125.0` | Trade actually made +125.0 |
| `counterfactual_pnl` | `0.0` | If blocked, would have made nothing |
| `pnl_difference` | `-125.0` | Would have *lost* this profit |
| `trades_blocked` | `1` | Hypothetically blocked |

**Conclusion:** This trade was actually profitable (+125.0) but violated a governance rule. Enforcing the rule would have prevented this profit. **This trade suggests the rule might be too strict**, or the threshold (max_daily_loss) needs adjustment.

---

## Key Design Decisions

### 1. Replay-Only Architecture
We never execute trades or modify state. We only replay events and calculate hypotheticals. This is the only way to guarantee zero impact on live trading.

### 2. Deterministic Event Ordering
Events are immutable and ordered by sequence number. Same timeline always produces identical simulation results.

### 3. Conservative Drawdown Calculation
For counterfactual scenario, we only count winning trades in peak calculation. This is conservative but prevents overstating risk improvements.

### 4. Rule Violation Aggregation
All violations from the timeline are collected, even if they occurred at different steps. This shows complete rule interactions.

### 5. Fail-Silent Error Handling
Invalid inputs return graceful results, never raise exceptions. This ensures simulations complete even with messy data.

---

## Performance Characteristics

| Operation | Complexity | Time (approx) |
|-----------|-----------|---------------|
| Single simulation | O(n) | ~5ms (n = events) |
| Batch simulation (100 trades) | O(100 × n) | ~500ms |
| Memory per trade | O(n) | ~1KB per event |
| Cache overhead | O(m) | ~1MB per 1000 simulations |

For typical trading patterns:
- Single trade: <10ms
- 100 trades/day: <500ms
- 1000 trades/month: <5s

---

## Integration Points

### Upstream (Read-Only Inputs)
1. **DecisionTimelineService**: Replay events
2. **TradeGovernanceService**: Identify violations
3. **OutcomeAnalyticsService**: Optional, for enrichment

### Downstream (Information Consumers)
1. **Analytics Dashboard**: Visualize "what-if" scenarios
2. **Policy Review Interface**: Evidence for enforcement decisions
3. **Compliance Reports**: Regulatory simulation evidence
4. **Risk Management**: Scenario analysis and planning

### Database Integration
- **Write**: NONE (this is read-only simulation)
- **Read**: Only from DecisionTimelineService (in-memory timeline)

---

## Best Practices

### ✅ Do
- Run counterfactual simulation **before** enabling enforcement
- Compare against multiple time periods
- Test with different rule configurations
- Archive simulation reports for auditing
- Include counterfactual analysis in policy decisions
- Run batch simulations overnight for full month analysis

### ❌ Don't
- Use counterfactual results to block trades (it doesn't execute)
- Modify the simulator to actually enforce rules (violates design)
- Assume counterfactual = actual (they're different by definition)
- Cache results across trading days without re-running
- Rely solely on counterfactual for enforcement decisions (combine with other evidence)

---

## Troubleshooting

### Issue: Empty Timeline for a Trade

**Symptom:** `"No timeline found for correlation_id: trade_123"`

**Causes:**
1. Trade ID is misspelled or doesn't exist
2. Timeline service hasn't recorded events yet
3. Trade is from a different system

**Solution:**
1. Verify correlation_id matches actual trades
2. Check DecisionTimelineService has recorded events
3. Confirm event recording was called

### Issue: P&L Difference Is Always Zero

**Symptom:** `counterfactual_pnl == original_outcome.pnl` always

**Causes:**
1. No violations detected (trades are allowed)
2. Governance rules are not being evaluated

**Solution:**
1. Check if trades have GOVERNANCE_EVALUATED events
2. Verify violations are present in payloads
3. Ensure TradeGovernanceService is properly integrated

### Issue: Drawdown Never Improves

**Symptom:** `drawdown_improvement` is always zero or negative

**Causes:**
1. All trades are winning (no drawing down)
2. Violations only on winning trades (not helpful)

**Solution:**
1. Verify losing trades exist in timeline
2. Check if violations align with losing trades
3. Review rule configuration for alignment with risk goals

---

## Testing Coverage

| Area | Coverage | Status |
|------|----------|--------|
| Deterministic replay | 2 tests | ✅ |
| No mutation | 2 tests | ✅ |
| Blocked/allowed classification | 3 tests | ✅ |
| P&L calculations | 3 tests | ✅ |
| Drawdown metrics | 2 tests | ✅ |
| Batch simulation | 5 tests | ✅ |
| Non-enforcement guarantee | 4 tests | ✅ |
| Missing timeline handling | 1 test | ✅ |
| Export metadata | 2 tests | ✅ |
| Complete scenarios | 1 test | ✅ |
| **Total** | **25 tests** | **✅ All passing** |

---

## Safety Guarantees

This simulator is designed with multiple layers of protection to ensure it can never affect live trading:

1. **No Execution Methods**
   - No methods exist that can execute trades
   - No database writes
   - No side effects

2. **Read-Only Timeline Access**
   - Only calls `timeline_service.get_timeline()`
   - Immediately deepcopies all data
   - Cannot modify historical events

3. **Immutability by Design**
   - All outputs are hypothetical
   - Never modifies actual outcomes
   - Event replays are stateless

4. **Fail-Silent Behavior**
   - Invalid inputs return errors, not exceptions
   - Never crashes other services
   - Always returns valid result structure

5. **Deterministic Output**
   - Same input always produces same output
   - No random behavior
   - No async state changes

---

## Summary

The **CounterfactualEnforcementSimulator** enables evidence-based policy decisions by showing what would have happened if governance rules were enforced, **without actually enforcing anything**. It is purely analytical, completely read-only, and designed to never influence live trading in any way.

Use it to:
- ✅ Evaluate policy effectiveness
- ✅ Answer "what-if" questions
- ✅ Build regulatory evidence
- ✅ Model risk scenarios
- ✅ Inform enforcement decisions

Never use it to:
- ❌ Block trades
- ❌ Modify historical data
- ❌ Predict future performance
- ❌ Replace risk management
- ❌ Guarantee outcomes

All results are **informational only** for human review and decision-making.
