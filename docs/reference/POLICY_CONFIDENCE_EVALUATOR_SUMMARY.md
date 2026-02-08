# Policy Confidence Evaluator Summary

## Overview

The `PolicyConfidenceEvaluator` is an evidence-only analysis component that assesses whether a policy is statistically and operationally safe to enforce in future trading scenarios. It provides confidence scores and supporting metrics for decision-makers to evaluate policy worthiness.

## ⚠️ CRITICAL DISCLAIMER

**This component does not influence live decisions.**

The `PolicyConfidenceEvaluator` performs read-only analysis and generates informational reports only. It does **NOT**:
- Trigger policy enforcement
- Modify orchestrator behavior
- Write to databases
- Automatically block or allow trades
- Influence any live trading decisions

All confidence scores and reports are evidence for human review. Any decision to enforce a policy requires separate, explicit authorization outside this component.

## What is "Confidence"?

Confidence in this context represents a composite assessment of whether a policy **would likely improve trading outcomes if enforced**, based on historical analysis. It combines:

1. **Statistical Reliability** - Is the sample size large enough to trust the metrics?
2. **Precision Trade-off** - What's the balance between false positives and false negatives?
3. **Operational Consistency** - Does the policy degrade in different market regimes?
4. **Financial Impact** - Would enforcement create positive net PnL?

A high confidence score (≥0.70 by default) suggests the policy has strong evidence of being beneficial, but high confidence is **not automatic authorization** for enforcement.

## Confidence Scoring Formula

The confidence score starts at 1.0 and applies penalties/bonuses based on observed metrics:

```
score = 1.0

# Sample Size Penalty (if < 30 trades)
if sample_size < 30:
    score -= (1.0 - sample_size/30) * 0.5

# False Negative Penalty (severe - want to catch bad trades)
score -= false_negative_rate * 0.3  [default]

# False Positive Penalty (lighter - false alarms less critical than misses)
score -= false_positive_rate * 0.1  [default]

# Regime Instability Penalty (policy shouldn't break in different markets)
score -= regime_instability_score * 0.2  [default]

# Net PnL Bonus (if counterfactual PnL > $100)
if net_pnl_delta > 100:
    score += min(0.10, (net_pnl_delta - 100) / 2000.0)

# Final: Clamp to [0.0, 1.0]
score = max(0.0, min(1.0, score))
```

### Metric Definitions

- **sample_size**: Total number of trades analyzed for the policy
- **false_positive_rate**: 1 - veto_precision = percentage of vetoed trades that were actually winning (we unnecessarily blocked them)
- **false_negative_rate**: 1 - veto_recall = percentage of losers we failed to veto (we let them through)
- **regime_instability_score**: Coefficient of variation in performance across market regimes (0.0 = stable, 1.0+ = highly unstable)
- **net_pnl_delta_if_enforced**: Estimated profit if policy had been enforced (prevented losses, prevented gains)

### Default Thresholds

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `min_sample_size` | 30 trades | Minimum data before confidence > 0.70 |
| `min_confidence_threshold` | 0.70 | Threshold for "enforcement_ready" flag |
| `false_negative_penalty` | 0.3 | Weight: False negatives are 3× worse than false positives |
| `false_positive_penalty` | 0.1 | Weight: False alarms cost less than misses |
| `regime_instability_penalty` | 0.2 | Weight: Performance must be consistent across markets |
| `min_net_pnl_delta` | $100.0 | Minimum PnL delta to earn bonus (avoids spurious gains) |

All thresholds are configurable at initialization to support different risk preferences.

## Usage

### Basic Usage

```python
from reasoner_service.policy_confidence_evaluator import PolicyConfidenceEvaluator
from reasoner_service.outcome_analytics_service import OutcomeAnalyticsService

# Initialize evaluator with default thresholds
evaluator = PolicyConfidenceEvaluator()

# Obtain analytics from the analytics service
analytics = OutcomeAnalyticsService()
veto_impact = analytics.policy_veto_impact("BUY_MOMENTUM")
heatmap = analytics.signal_policy_heatmap("BUY_MOMENTUM")
regime_perf = analytics.regime_policy_performance("BUY_MOMENTUM")

# Register analytics for a policy
evaluator.add_policy_analytics(
    "BUY_MOMENTUM",
    veto_impact=veto_impact,
    heatmap=heatmap,
    regime_performance=regime_perf
)

# Evaluate single policy
report = evaluator.evaluate_policy("BUY_MOMENTUM")
print(f"Confidence: {report['confidence_score']}")
print(f"Enforcement Ready: {report['enforcement_ready']}")
print(f"Explanation: {report['explanation']}")

# Evaluate all registered policies
all_reports = evaluator.evaluate_all_policies()
```

### Custom Thresholds

```python
evaluator = PolicyConfidenceEvaluator(
    min_sample_size=50,  # Require more data
    min_confidence_threshold=0.80,  # Higher confidence bar
    false_negative_penalty=0.5,  # Penalize misses more
)
```

## Example Report

```python
{
    "policy_name": "BUY_MOMENTUM",
    "sample_size": 150,
    "false_positive_rate": 0.12,
    "false_negative_rate": 0.05,
    "net_pnl_delta_if_enforced": 1250.50,
    "regime_instability_score": 0.18,
    "confidence_score": 0.84,
    "enforcement_ready": True,
    "explanation": (
        "Policy shows strong evidence of profitability. 150 trades analyzed. "
        "Low false negative rate (5%) indicates good signal quality. "
        "Regime consistency is maintained across all market conditions. "
        "Estimated net PnL improvement of $1250.50 if enforced. "
        "High precision (88%) with acceptable recall (95%) suggests good trade filtering. "
        "Confidence: 0.84. Recommendation: Consider for enforcement with standard safeguards."
    ),
    "evaluated_at": "2025-01-20T15:43:21.123456+00:00",
    "disclaimer": (
        "This analysis is evidence-only. "
        "Enforcement decisions require separate authorization and do not occur automatically."
    )
}
```

## Key Design Principles

### 1. Evidence-Only Analysis
The component provides metrics and scores for human judgment. It does not make enforcement decisions or trigger any automatic behavior.

### 2. Configurable, Not Hardcoded
All thresholds are configurable at instantiation, allowing different strategies to have different risk profiles.

### 3. Deterministic
Same inputs produce identical outputs (except for timestamp). No randomness or learning.

### 4. Fail-Silent
If analytics are incomplete or malformed, the evaluator returns a report with error details rather than crashing.

### 5. Non-Mutating
Input analytics are never modified. The evaluator is purely read-only.

## Metrics Interpretation

### Confidence Score Ranges

| Range | Interpretation |
|-------|-----------------|
| 0.00 - 0.30 | Very weak evidence - policy likely harmful or unreliable |
| 0.30 - 0.50 | Weak evidence - insufficient data or poor metrics |
| 0.50 - 0.70 | Moderate evidence - mixed signals, more analysis needed |
| 0.70 - 0.85 | Strong evidence - good metrics across indicators |
| 0.85 - 1.00 | Very strong evidence - excellent metrics, high reliability |

### False Negative Impact

False negatives (missed losers) are weighted 3× heavier than false positives (blocked winners). This reflects trading priorities: preventing losses is more important than capturing every potential gain.

Example:
- Policy 1: 5% FN, 20% FP → Confidence heavily penalized
- Policy 2: 20% FN, 5% FP → Confidence moderately penalized

### Regime Instability

A policy showing great performance in trending markets but failing in ranges is unreliable. The instability score penalizes policies that degrade across regime changes, even if average performance is good.

## Enforcement Guarantee

**Under no circumstances can this component trigger enforcement.** Guarantees:

1. ✅ No orchestrator method calls
2. ✅ No database writes
3. ✅ No async/threading (deterministic only)
4. ✅ No enforcement-related side effects
5. ✅ `enforcement_ready` is an informational flag only

The `confidence_score` and `enforcement_ready` fields are provided for external decision systems to consider, not for automatic execution.

## Integration Points

This component is designed to integrate with:

- **OutcomeAnalyticsService**: Provides historical analytics (read-only)
- **Policy Framework**: Evaluates registered policy configurations
- **Reporting/Dashboard**: Displays confidence assessments to users
- **Decision System**: Human or system-level enforcement authorization

It does **NOT** integrate with:
- Trade execution
- Position management
- Risk controls
- Any live decision systems

## Configuration Best Practices

### Conservative Strategy (Low Risk)
```python
evaluator = PolicyConfidenceEvaluator(
    min_sample_size=100,
    min_confidence_threshold=0.85,
    false_negative_penalty=0.5,  # Penalize misses heavily
    false_positive_penalty=0.2,
)
```

### Balanced Strategy (Standard)
```python
evaluator = PolicyConfidenceEvaluator()  # Uses defaults
```

### Aggressive Strategy (High Risk)
```python
evaluator = PolicyConfidenceEvaluator(
    min_sample_size=30,
    min_confidence_threshold=0.60,
    false_negative_penalty=0.2,  # More tolerant of misses
    false_positive_penalty=0.15,
)
```

## Testing

The `PolicyConfidenceEvaluator` includes comprehensive test coverage:

- **Confidence Scoring Logic** (6 tests): Verify all penalty/bonus calculations
- **Regime Instability** (2 tests): Ensure cross-regime consistency detection
- **Edge Cases** (4 tests): Handle missing data, unknown policies gracefully
- **Determinism** (1 test): Confirm output consistency
- **Input Safety** (1 test): Verify input analytics not mutated
- **Enforcement Prevention** (2 tests): Confirm no orchestration occurs
- **Error Handling** (2 tests): Verify fail-silent behavior
- **Configurability** (2 tests): Test custom threshold application
- **Output Structure** (2 tests): Verify all required fields present

Total: **21 tests** - All passing

## Troubleshooting

### Confidence Score Lower Than Expected

Possible causes:
1. **High false negative rate** - Policy misses too many bad trades (penalty = 3× FP penalty)
2. **Small sample size** - Less than 30 trades analyzed (penalty up to -0.5)
3. **Regime degradation** - Policy performs poorly in specific market conditions
4. **Negative net PnL** - Counterfactual analysis suggests policy would worsen results

### Policy Returns enforcement_ready=False

Verify:
1. `confidence_score >= min_confidence_threshold` (default 0.70)
2. `sample_size >= min_sample_size` (default 30)

Both must be true for enforcement_ready=True.

### Missing Analytics Fields

If veto_impact lacks fields, defaults are:
- `veto_precision`: 1.0 (no false positives if no vetoes)
- `veto_recall`: 1.0 (no false negatives if no vetoes)
- `total_trades`: 0 (triggers sample size penalty)

If regime_performance is empty:
- `regime_instability_score`: 0.0 (assumed stable)

## Summary

The `PolicyConfidenceEvaluator` provides transparent, configurable, evidence-based assessments of policy quality. It is designed as a *decision support tool*, not an enforcement engine. All confidence scores are informational only and do not automatically trigger any trading behavior.

Use this component to evaluate policy candidates, support human decision-making, and maintain audit trails of policy assessment rationale.

**Remember: This component does not influence live decisions.**
