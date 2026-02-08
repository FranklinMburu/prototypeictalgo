# Trade Governance Service Summary

## Overview

The `TradeGovernanceService` is an observational, informational-only component that evaluates whether hypothetical trades would comply with strict risk and session governance rules. It provides violation reports and governance assessments without any ability to block, execute, or influence trades.

## ⚠️ CRITICAL DISCLAIMER

**This component does not influence live decisions. It operates entirely in shadow mode.**

The `TradeGovernanceService` performs read-only analysis and generates informational reports only. It does **NOT**:
- Block trades (live or hypothetical)
- Execute any trades
- Modify orchestrator behavior
- Write to databases
- Trigger any enforcement mechanisms
- Influence live trading decisions in any way

All governance assessments are evidence for human review. Results are purely analytical and do not affect trade execution.

## Why Governance ≠ Strategy

**Governance** is fundamentally different from **strategy**:

| Aspect | Governance | Strategy |
|--------|-----------|----------|
| **Purpose** | Enforce risk and operational limits | Generate profitable trading signals |
| **Scope** | Rules-based, deterministic constraints | Signal-based, probability-driven logic |
| **Output** | Violations: "this trade violates rule X" | Recommendations: "this trade is profitable" |
| **Enforcement** | Would prevent bad behavior | Would enable good behavior |
| **This Component** | ✅ Governance only | ❌ No strategy logic |

Governance rules exist to prevent catastrophic outcomes, not to identify opportunities. A trade can have excellent governance compliance and poor expected profitability, or vice versa.

## Shadow Mode Guarantee

This component operates in **shadow mode**: it runs alongside live trading but:

1. ✅ Observes all historical outcomes
2. ✅ Evaluates hypothetical trades against rules
3. ✅ Generates informational reports
4. ❌ Never blocks actual trades
5. ❌ Never modifies any live state
6. ❌ Never interferes with execution

**Shadow mode is absolute:** Results are provided to external systems (dashboards, logging, audit) but never fed back into execution decisions.

## Governance Rules

The service evaluates trades against seven core governance rules:

### 1. Daily Trade Limit
**Rule:** Maximum number of trades allowed per calendar day.

- **Purpose:** Prevent overtrading and fatigue-driven decisions
- **Default:** 5 trades/day
- **Metric:** Count of trades executed on the same date
- **Violation:** "Daily trade limit reached: 5 trades already executed today"

### 2. Daily Loss Limit
**Rule:** Maximum cumulative loss allowed per calendar day (drawdown protection).

- **Purpose:** Stop losses before catastrophic drawdowns
- **Default:** -$500 per day
- **Metric:** Sum of all PnL (losses) on the same date
- **Violation:** "Daily loss limit exceeded: $650 loss already accrued today"

### 3. Killzone Hours
**Rule:** Specific hours when trading is prohibited (session windows).

- **Purpose:** Avoid low-liquidity or high-volatility periods
- **Default:** None (configurable)
- **Example:** `[(0, 8), (22, 24)]` blocks midnight-8AM and 10PM-midnight
- **Violation:** "Trade attempted during killzone: 03:15 UTC"

### 4. Cooldown After Loss
**Rule:** Mandatory waiting period after a losing trade before the next trade.

- **Purpose:** Prevent revenge trading and emotional decisions
- **Default:** 30 minutes
- **Metric:** Time elapsed since last losing trade
- **Violation:** "Cooldown period active: 15 minutes remaining after last loss"

### 5. Symbol Overtrading
**Rule:** Maximum number of trades on the same symbol per day.

- **Purpose:** Prevent over-concentration in a single instrument
- **Default:** 3 trades/symbol/day
- **Metric:** Count of trades on same symbol, same date
- **Violation:** "Symbol trade limit reached: 3 trades on EURUSD today"

### 6. Timeframe Overtrading
**Rule:** Maximum number of trades on the same timeframe per day.

- **Purpose:** Prevent over-reliance on single timeframe analysis
- **Default:** 4 trades/timeframe/day
- **Metric:** Count of trades on same timeframe, same date
- **Violation:** "Timeframe trade limit reached: 4 trades on 1H today"

### 7. Trade Spacing
**Rule:** Minimum time interval required between consecutive trades.

- **Purpose:** Ensure adequate analysis time between trades
- **Default:** 5 minutes
- **Metric:** Time elapsed since previous trade
- **Violation:** "Trade spacing violation: only 2.5m since last trade (min 5m)"

## Usage

### Basic Usage

```python
from reasoner_service.trade_governance_service import TradeGovernanceService
from reasoner_service.outcome_analytics_service import OutcomeAnalyticsService

# Initialize service with default rules
service = TradeGovernanceService()

# Obtain historical outcomes
analytics = OutcomeAnalyticsService()
outcomes = analytics.get_all_outcomes()  # or similar

# Register outcomes for evaluation
service.add_outcomes(outcomes)

# Evaluate a hypothetical trade
evaluation = service.evaluate_trade({
    "symbol": "EURUSD",
    "timeframe": "1H",
    "timestamp": "2025-12-19T10:30:00Z",
})

print(f"Allowed: {evaluation['allowed']}")
print(f"Violations: {evaluation['violations']}")
print(f"Explanation: {evaluation['explanation']}")

# Evaluate multiple trades
trades = [
    {"symbol": "EURUSD", "timeframe": "1H", "timestamp": "2025-12-19T10:30:00Z"},
    {"symbol": "GBPUSD", "timeframe": "15m", "timestamp": "2025-12-19T11:00:00Z"},
]
reports = service.evaluate_batch(trades)
```

### Custom Governance Rules

```python
service = TradeGovernanceService(
    max_trades_per_day=10,
    max_daily_loss=1000.0,
    killzone_hours=[(0, 8), (20, 24)],  # No trading midnight-8AM or 8PM-midnight
    cooldown_minutes_after_loss=60,
    max_trades_per_symbol=5,
    max_trades_per_timeframe=6,
    min_trade_spacing_minutes=10,
)
```

## Example Violation Report

### Trade Allowed

```json
{
    "allowed": true,
    "violations": [],
    "explanation": "Trade on EURUSD (1H) would comply with all governance rules. Status: 2/5 daily trades. Daily PnL: $150.00. No violations detected.",
    "evaluated_at": "2025-12-19T10:45:22.123456+00:00",
    "disclaimer": "This analysis is informational only. Results do not influence live trading decisions."
}
```

### Trade Violates Rules

```json
{
    "allowed": false,
    "violations": [
        "Daily loss limit exceeded: $625 loss already accrued today",
        "Cooldown period active: 8 minutes remaining after last loss"
    ],
    "explanation": "Trade on EURUSD (1H) would violate governance rules. Violations: • Daily loss limit exceeded: $625 loss already accrued today • Cooldown period active: 8 minutes remaining after last loss Status: 4/5 daily trades. Daily PnL: -$625.00.",
    "evaluated_at": "2025-12-19T10:45:22.123456+00:00",
    "disclaimer": "This analysis is informational only. Results do not influence live trading decisions."
}
```

## Key Design Principles

### 1. Read-Only Observation
The component never modifies any outcomes or state. It operates purely as an observer.

### 2. Configurable, Not Hardcoded
All rules are configurable at initialization. Different strategies can have different governance profiles.

### 3. Deterministic Evaluation
Same inputs always produce identical outputs (except timestamps). No randomness.

### 4. Fail-Silent Behavior
Malformed inputs, missing timestamps, or evaluation errors result in error reports rather than crashes.

### 5. No Enforcement
Violation reports are informational only. No actual blocking, stopping, or prevention mechanisms exist.

### 6. No Orchestration
No methods to stop, execute, or modify trades. No orchestrator calls.

### 7. Shadow Mode
Results are provided to external systems but never fed back into execution logic.

## Governance Violations vs. Risk Management

### Violations Don't Block Execution

A violation report indicates **what rules the trade would break**, not that execution should stop:

```
Rule: "Daily loss limit exceeded"
→ Meaning: "If this trade executes, cumulative daily loss would exceed threshold"
→ Action: Log for monitoring, alert human operator, update dashboard
→ NOT: "Block this trade from executing"
```

### Violations Are Informational

Violations inform decision-makers but don't prevent decisions:

| Violation | Information | Decision |
|-----------|-------------|----------|
| "Daily loss limit exceeded" | Risk: Further losses would exceed threshold | Human decides if this is acceptable |
| "Cooldown period active" | State: Waiting after loss (revenge prevention) | Human decides if exception applies |
| "Killzone hours" | Observation: Trading during low liquidity | Human decides if risk is worth opportunity |

## Configuration Examples

### Conservative (Low Risk)
```python
service = TradeGovernanceService(
    max_trades_per_day=3,
    max_daily_loss=250.0,
    killzone_hours=[(0, 10), (18, 24)],
    cooldown_minutes_after_loss=45,
    max_trades_per_symbol=2,
    max_trades_per_timeframe=2,
    min_trade_spacing_minutes=10,
)
```

### Balanced (Standard)
```python
service = TradeGovernanceService()  # Uses defaults
```

### Aggressive (High Risk Tolerance)
```python
service = TradeGovernanceService(
    max_trades_per_day=10,
    max_daily_loss=1000.0,
    killzone_hours=[],  # No killzones
    cooldown_minutes_after_loss=5,
    max_trades_per_symbol=6,
    max_trades_per_timeframe=8,
    min_trade_spacing_minutes=1,
)
```

## Testing Coverage

The `TradeGovernanceService` includes comprehensive test coverage:

- **Daily Limits** (2 tests): Trade count and loss limits
- **Session Rules** (3 tests): Killzone enforcement including wraparound
- **Loss Protection** (3 tests): Cooldown period behavior
- **Concentration Limits** (4 tests): Symbol and timeframe overtrading
- **Spacing Rules** (2 tests): Minimum interval enforcement
- **Multiple Violations** (1 test): Comprehensive rule checking
- **Edge Cases** (4 tests): New day resets, empty data, invalid inputs
- **Determinism** (1 test): Output consistency
- **No Mutation** (1 test): Input preservation
- **Batch Operations** (2 tests): Multiple trade evaluation
- **Guarantees** (2 tests): Disclaimers and no enforcement triggers
- **Configurability** (2 tests): Custom rule application
- **Output Structure** (2 tests): Required fields present

Total: **31 tests** - All passing

## Integration Points

This component integrates with:

- **OutcomeAnalyticsService**: Reads historical outcomes (read-only)
- **Monitoring/Dashboard**: Displays governance assessments
- **Audit Logging**: Records violation reports
- **Human Decision Systems**: Provides informational input to human judgment
- **Risk Framework**: Coordinates with risk management (not enforcement)

It does **NOT** integrate with:

- Trade execution systems
- Position management
- Orchestration engines
- Any live decision systems
- Any code that blocks or prevents trades

## Enforcement Guarantee

**Under no circumstances can this component trigger enforcement or block trades.** Explicit guarantees:

1. ✅ No orchestrator method calls
2. ✅ No database writes
3. ✅ No trade execution methods
4. ✅ No state modifications
5. ✅ No enforcement-related side effects
6. ✅ All results are read-only informational flags

The `allowed` field is a boolean flag indicating governance compliance, not a trigger for blocking. No enforcement is possible because:
- No methods to execute trades exist
- No methods to block trades exist
- No methods to modify orchestrator state exist
- All outputs are purely informational

## Shadow Mode Implementation

Shadow mode is enforced at the architectural level:

```
Live Trading System
        ↓
    (Executes trades)
        ↓
    ┌─────────────────────┐
    │ Trade Governance    │
    │ Service (Shadow)     │
    │ - Observes outcomes  │
    │ - Generates reports  │
    │ - NEVER blocks       │
    └─────────────────────┘
        ↓
    (Reports to dashboard, logs, audit)
    
No feedback loop to execution ✅
```

## Troubleshooting

### Why is a trade marked as violating?

Check the `violations` list in the report. Each entry explains which rule(s) the trade would break.

### Can I override a violation?

Violations are informational. External systems (human operators, management dashboards) decide whether to override. This service provides information, not decisions.

### What if I want different rules?

Pass custom parameters at initialization:
```python
service = TradeGovernanceService(
    max_trades_per_day=15,
    cooldown_minutes_after_loss=10,
    # ... other parameters
)
```

### What if a trade context is missing fields?

The service returns an error report with the missing field noted in violations. No exceptions are raised (fail-silent).

## Summary

The `TradeGovernanceService` provides transparent, rule-based governance assessment without any ability to influence execution. It operates in shadow mode alongside live trading, offering informational insights for monitoring, auditing, and decision support.

All governance evaluations are read-only. No enforcement is possible. No live trading is ever affected.

**Remember: This service observes trading behavior and provides governance insights. It does not and cannot block, modify, or influence any trades.**
