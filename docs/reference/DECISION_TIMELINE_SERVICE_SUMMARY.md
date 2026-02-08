# Decision Timeline Service Summary

## Overview

The `DecisionTimelineService` is an immutable, append-only audit trail that records all decision-related events in chronological order. It provides complete traceability of trading decisions from signal detection through outcome recording, enabling compliance, debugging, and analysis without affecting live trading behavior.

## ⚠️ CRITICAL DISCLAIMER

**This service records events only and does not influence live decisions.**

The `DecisionTimelineService` is purely observational and archival. It does **NOT**:
- Execute trades
- Block or prevent trades
- Modify orchestrator behavior
- Write to trading databases
- Influence any live trading logic
- Trigger any enforcement mechanisms

All timelines are read-only records for historical analysis. No replay or analysis affects live trading.

## Why Event Sourcing Matters

Event sourcing provides fundamental benefits for trading systems:

### 1. **Compliance & Audit Trail**
Every trading decision is traceable to its origin signal and justification. Regulators can audit complete decision chains.

### 2. **Debugging & Analysis**
When unexpected outcomes occur, replay events to understand exactly what happened and why decisions were made at each step.

### 3. **Determinism Verification**
Replay the same event sequence and get identical results, proving decisions are reproducible and rule-based.

### 4. **Separation of Concerns**
Decision logic remains separate from execution. Governance and analysis can be added without affecting trade execution.

### 5. **Historical Analysis**
Analyze past decisions to improve signal quality, policy rules, and governance parameters.

## Event Sourcing Architecture

```
Live Trading System
        ↓
   (Executes trades)
        ↓
    Decision Events
   (Append-only)
        ↓
Timeline Service
   (Stores immutably)
        ↓
Audit Trail Created
   (Read-only access)
        ↓
Analysis/Compliance
   (Never affects execution)
```

## How Replay Works

Replay reconstructs decision history by replaying events chronologically:

```python
# Record events as decisions happen
service.record_event("SIGNAL_DETECTED", {...}, trade_id)
service.record_event("DECISION_PROPOSED", {...}, trade_id)
service.record_event("POLICY_EVALUATED", {...}, trade_id)
service.record_event("TRADE_EXECUTED", {...}, trade_id)
service.record_event("OUTCOME_RECORDED", {...}, trade_id)

# Later, replay to reconstruct full history
events = service.replay(trade_id)
# Returns: [signal_event, decision_event, policy_event, trade_event, outcome_event]

# Replay is:
# ✅ Deterministic (same events → same sequence every time)
# ✅ Immutable (events cannot be modified after recording)
# ✅ Chronological (events in order of occurrence)
# ✅ Non-affecting (never influences live trading)
```

### Replay Properties

- **Idempotent**: Replaying the same trade_id multiple times returns identical timelines
- **Complete**: Includes all events from signal to outcome with full context
- **Immutable**: Returned events are copies; modifying them doesn't affect stored timeline
- **Traceable**: Each event includes timestamp, sequence number, and correlation ID

## Supported Event Types

| Event Type | Purpose | Example Payload |
|-----------|---------|-----------------|
| `SIGNAL_DETECTED` | Trading signal identified | `{"symbol": "EURUSD", "signal": "BUY", "strength": 0.85}` |
| `DECISION_PROPOSED` | Decision based on signal | `{"action": "BUY", "quantity": 100000, "level": 1.0850}` |
| `POLICY_EVALUATED` | Policy compliance checked | `{"policy": "risk_limit", "status": "approved"}` |
| `POLICY_CONFIDENCE_SCORED` | Policy confidence calculated | `{"confidence": 0.82, "sample_size": 150}` |
| `GOVERNANCE_EVALUATED` | Governance rules checked | `{"allowed": true, "violations": []}` |
| `TRADE_EXECUTED` | Trade executed/hypothetical | `{"execution_time": "...", "fill_price": 1.0851}` |
| `OUTCOME_RECORDED` | Trade outcome recorded | `{"pnl": 250.0, "outcome": "win", "bars_held": 15}` |

Additional event types can be recorded; these are the core supported types.

## Usage

### Basic Recording

```python
from reasoner_service.decision_timeline_service import DecisionTimelineService

service = DecisionTimelineService()

# Record events as they occur
service.record_event(
    "SIGNAL_DETECTED",
    {"symbol": "EURUSD", "signal": "BUY", "confidence": 0.9},
    "trade_20251219_001"
)

service.record_event(
    "DECISION_PROPOSED",
    {"action": "execute", "quantity": 100000},
    "trade_20251219_001"
)

service.record_event(
    "TRADE_EXECUTED",
    {"status": "filled", "price": 1.0851},
    "trade_20251219_001"
)
```

### Timeline Retrieval & Replay

```python
# Get complete timeline
timeline = service.get_timeline("trade_20251219_001")
print(f"Timeline has {len(timeline)} events")

# Explicit replay (semantically equivalent)
replayed_events = service.replay("trade_20251219_001")

# Export with metadata
export = service.export_timeline("trade_20251219_001")
# Returns: {
#     "correlation_id": "...",
#     "found": True,
#     "event_count": 5,
#     "event_types": ["SIGNAL_DETECTED", "DECISION_PROPOSED", ...],
#     "first_event_time": "2025-12-19T10:30:00Z",
#     "last_event_time": "2025-12-19T10:30:15Z",
#     "events": [...],
#     "disclaimer": "...",
# }
```

### Event Filtering

```python
# Get only signal events for a trade
signals = service.get_events_by_type("trade_20251219_001", "SIGNAL_DETECTED")

# Get only trade execution events
executions = service.get_events_by_type("trade_20251219_001", "TRADE_EXECUTED")
```

### Timeline Validation

```python
# Validate timeline integrity
validation = service.validate_timeline("trade_20251219_001")
# Returns: {
#     "correlation_id": "...",
#     "valid": True,
#     "event_count": 5,
#     "issues": [],
#     "validated_at": "2025-12-19T11:00:00Z",
# }

# Validation checks:
# ✅ Sequence numbers monotonic
# ✅ Timestamps chronological
# ✅ All required fields present
# ✅ No corrupted events
```

### Statistics & Management

```python
# Get event count
total_events = service.get_event_count()  # All events
trade_events = service.get_event_count("trade_20251219_001")  # For specific trade

# Get all recorded trades
all_trades = service.get_all_correlation_ids()

# Service statistics
stats = service.get_statistics()
# Returns: {
#     "total_events": 1250,
#     "total_correlations": 50,
#     "event_type_distribution": {
#         "SIGNAL_DETECTED": 500,
#         "DECISION_PROPOSED": 450,
#         "TRADE_EXECUTED": 300,
#     },
#     "stats_generated_at": "2025-12-19T11:00:00Z",
# }
```

## Example Timeline Output

### Single Trade Complete Lifecycle

```json
{
  "correlation_id": "trade_20251219_001",
  "found": true,
  "event_count": 7,
  "event_types": [
    "SIGNAL_DETECTED",
    "DECISION_PROPOSED",
    "POLICY_EVALUATED",
    "POLICY_CONFIDENCE_SCORED",
    "GOVERNANCE_EVALUATED",
    "TRADE_EXECUTED",
    "OUTCOME_RECORDED"
  ],
  "first_event_time": "2025-12-19T10:30:00.123456+00:00",
  "last_event_time": "2025-12-19T10:32:45.654321+00:00",
  "events": [
    {
      "event_type": "SIGNAL_DETECTED",
      "timestamp": "2025-12-19T10:30:00.123456+00:00",
      "payload": {
        "symbol": "EURUSD",
        "signal_type": "momentum",
        "strength": 0.85
      },
      "correlation_id": "trade_20251219_001",
      "sequence_number": 0
    },
    {
      "event_type": "DECISION_PROPOSED",
      "timestamp": "2025-12-19T10:30:01.234567+00:00",
      "payload": {
        "action": "BUY",
        "quantity": 100000,
        "level": 1.0850
      },
      "correlation_id": "trade_20251219_001",
      "sequence_number": 1
    },
    {
      "event_type": "POLICY_EVALUATED",
      "timestamp": "2025-12-19T10:30:02.345678+00:00",
      "payload": {
        "policy": "risk_limit",
        "status": "approved"
      },
      "correlation_id": "trade_20251219_001",
      "sequence_number": 2
    },
    {
      "event_type": "POLICY_CONFIDENCE_SCORED",
      "timestamp": "2025-12-19T10:30:03.456789+00:00",
      "payload": {
        "confidence": 0.82,
        "sample_size": 150,
        "regime_stability": 0.78
      },
      "correlation_id": "trade_20251219_001",
      "sequence_number": 3
    },
    {
      "event_type": "GOVERNANCE_EVALUATED",
      "timestamp": "2025-12-19T10:30:04.567890+00:00",
      "payload": {
        "allowed": true,
        "violations": []
      },
      "correlation_id": "trade_20251219_001",
      "sequence_number": 4
    },
    {
      "event_type": "TRADE_EXECUTED",
      "timestamp": "2025-12-19T10:30:05.678901+00:00",
      "payload": {
        "execution_time": "2025-12-19T10:30:05Z",
        "fill_price": 1.0851,
        "slippage": 0.0001
      },
      "correlation_id": "trade_20251219_001",
      "sequence_number": 5
    },
    {
      "event_type": "OUTCOME_RECORDED",
      "timestamp": "2025-12-19T10:32:45.654321+00:00",
      "payload": {
        "pnl": 250.0,
        "outcome": "win",
        "bars_held": 15,
        "exit_price": 1.0876
      },
      "correlation_id": "trade_20251219_001",
      "sequence_number": 6
    }
  ],
  "exported_at": "2025-12-19T11:00:00.000000+00:00",
  "disclaimer": "This timeline records decision events only. It does not influence live trading decisions."
}
```

## Key Design Principles

### 1. Append-Only
Events are never modified or deleted. New events append to the end of the timeline.

### 2. Immutable Records
Once recorded, events cannot be changed. Retrieved events are copies to prevent external mutation.

### 3. Deterministic Replay
Replaying the same event sequence always produces identical results.

### 4. Fail-Silent
Invalid inputs (bad correlation ID, null payload) are logged but don't raise exceptions.

### 5. Read-Only Access
All retrieval methods return read-only copies. No method can modify stored timeline.

### 6. Thread-Safe
Recording and retrieval are thread-safe using locks. Multiple concurrent operations are safe.

### 7. Correlation Isolation
Events from different trades are isolated. One trade's timeline doesn't affect another's.

## Timeline Validation

Timelines are validated for:

- **Monotonic Sequence Numbers**: Events must have increasing sequence numbers
- **Chronological Order**: Timestamps should progress forward
- **Required Fields**: All events must have event_type, timestamp, payload, correlation_id
- **No Corruption**: Fields must have correct types and formats

```python
validation = service.validate_timeline("trade_123")
if not validation["valid"]:
    for issue in validation["issues"]:
        print(f"⚠️  {issue}")
```

## Append-Only Guarantees

### No Deletion
```python
# Timeline cannot be shortened
events = service.replay(trade_id)  # Always has all recorded events
```

### No Modification
```python
# Events cannot be changed after recording
timeline = service.get_timeline(trade_id)
timeline[0]["payload"]["value"] = 999  # Does not affect stored events
replay = service.replay(trade_id)
assert replay[0]["payload"]["value"] != 999  # Original unchanged
```

### No Reordering
```python
# Events maintain chronological order
replay1 = service.replay(trade_id)
replay2 = service.replay(trade_id)
assert replay1 == replay2  # Same order every time
```

## Performance Characteristics

- **Recording**: O(1) append operation (very fast)
- **Retrieval**: O(n) to fetch n events for a correlation (acceptable for analysis)
- **Memory**: Stored in-memory; suitable for historical queries on recent trades
- **Scalability**: Thread-safe; handles concurrent recording from multiple threads

For high-volume trading, consider:
- Archiving old timelines to persistent storage
- Sharding by date or trade ID ranges
- Periodic cleanup of resolved/completed trades

## Integration Points

This service integrates with:

- **Signal Generators**: Record `SIGNAL_DETECTED` events
- **Decision Engines**: Record `DECISION_PROPOSED` events
- **PolicyConfidenceEvaluator**: Record `POLICY_CONFIDENCE_SCORED` events
- **TradeGovernanceService**: Record `GOVERNANCE_EVALUATED` events
- **Trade Execution**: Record `TRADE_EXECUTED` events
- **OutcomeAnalyticsService**: Record `OUTCOME_RECORDED` events
- **Compliance/Audit**: Query timelines for verification
- **Analytics/Debugging**: Replay events for analysis

## Testing Coverage

The `DecisionTimelineService` includes comprehensive test coverage:

- **Append-Only Behavior** (4 tests): Single events, multiple events, sequencing, immutability
- **Event Ordering** (2 tests): Timestamp ordering, correlation isolation
- **Replay Determinism** (3 tests): Deterministic replay, immutable copies, get_timeline alias
- **No Mutation** (1 test): Past events immutable through multiple operations
- **Event Types** (2 tests): Valid types, unknown types recorded anyway
- **Error Handling** (4 tests): Invalid inputs handled gracefully
- **Read-Only Guarantees** (2 tests): Multiple readers consistent, export read-only
- **Event Filtering** (1 test): Filter events by type
- **Timeline Validation** (2 tests): Valid timeline passes, missing timeline fails
- **Event Count** (2 tests): Count by correlation, count all events
- **Correlation Management** (1 test): Get all correlation IDs
- **Statistics** (1 test): Collect service statistics
- **Complete Lifecycle** (2 tests): Full trade lifecycle, replay reconstruction
- **Thread Safety** (1 test): Concurrent recording preserves order
- **Disclaimer** (1 test): Disclaimer present in exports

Total: **29 tests** - All passing

## Troubleshooting

### Timeline Is Empty for a Trade

Verify:
1. Events were recorded with correct `correlation_id`
2. Event type and payload were valid
3. Service hasn't been cleared (for testing)

### Replay Shows Unexpected Event Sequence

Check:
1. All events were recorded (use `get_event_count()`)
2. Timestamps are in correct order (`validate_timeline()`)
3. Events weren't modified externally

### Performance Degradation with Large Timelines

Consider:
1. Archiving old timelines (trades > N days old)
2. Using event filtering instead of replaying entire timeline
3. Implementing timeline batching by date range

## Event Sourcing Best Practices

1. **Record Events Early**: Record events as they occur, not retrospectively
2. **Include Full Context**: Payloads should contain all relevant data
3. **Use Meaningful Correlation IDs**: IDs should uniquely identify trades/decisions
4. **Validate Timelines**: Regularly validate timeline integrity
5. **Archive Old Timelines**: Move old timelines to persistent storage periodically
6. **Monitor Timeline Growth**: Track service statistics to detect anomalies

## Summary

The `DecisionTimelineService` provides a complete, immutable audit trail of trading decisions. It enables traceability, debugging, and compliance verification without affecting live trading. All timelines are append-only, deterministic, and read-only, guaranteeing historical accuracy and preventing tampering.

**Remember: This service records events only and does not influence live decisions.**

Use it to understand why decisions were made, verify their correctness, and maintain audit compliance.
