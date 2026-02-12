# Historical Replay Validation Engine

## Overview

The Historical Replay Validation engine evaluates real trading signals against real OHLCV candles to compute outcome metrics (exit price, r_multiple, MAE, MFE) with **deterministic, reproducible results**. No randomness. No forced outcomes. Uses **SL-first tie-break** when both TP and SL hit in the same candle.

## Key Features

✅ **Deterministic**: Same inputs always produce identical outputs  
✅ **SL-First Tie-Break**: When both SL and TP hit in same candle → LOSS (risk-first approach)  
✅ **Edge-Proofed**: Handles all candle scenarios, missing exits, partial fills  
✅ **Async-Ready**: Signal loader supports async DB queries  
✅ **Fast**: Pure Python, minimal dependencies  
✅ **Well-Tested**: 23 comprehensive test cases  

## Module Structure

```
backtest_replay/
├── __init__.py                  # Package initialization
├── candle_loader.py             # Load OHLCV from CSV (sorted, UTC-aware)
├── signal_loader.py             # Load signals from JSONL or async DB
├── outcome_tagger.py            # Tag outcomes with deterministic tie-break
├── metrics.py                   # Compute expectancy, win_rate, distributions
├── replay_runner.py             # Orchestrate pipeline
└── schemas.py                   # Data structures

scripts/
└── run_historical_replay.py     # CLI interface with JSON report output

tests/backtest_replay/
├── test_candle_loader.py        # 7 tests: CSV loading, sorting, validation
├── test_signal_loader.py        # 9 tests: JSONL loading, filtering
├── test_outcome_tagger.py       # 5 tests: TP/SL hits, tie-break logic
└── test_metrics.py              # 2 tests: metric computation

data/sample_backtest/
├── candles.csv                  # 50 realistic EURUSD hourly candles
└── signals.jsonl                # 10 sample trading signals
```

## Quick Start

### 1. Run with Sample Data

```bash
cd /path/to/prototypeictalgo

# Run full replay with all signals
PYTHONPATH=. python scripts/run_historical_replay.py \
  --candles-csv data/sample_backtest/candles.csv \
  --signals-jsonl data/sample_backtest/signals.jsonl \
  --output results/replay_report.json

# Filter by symbol
PYTHONPATH=. python scripts/run_historical_replay.py \
  --candles-csv data/sample_backtest/candles.csv \
  --signals-jsonl data/sample_backtest/signals.jsonl \
  --symbol EURUSD \
  --output results/eurusd_report.json

# Filter by signal type and date range
PYTHONPATH=. python scripts/run_historical_replay.py \
  --candles-csv data/sample_backtest/candles.csv \
  --signals-jsonl data/sample_backtest/signals.jsonl \
  --symbol EURUSD \
  --signal-type bearish_bos \
  --from "2024-01-01" \
  --to "2024-02-01" \
  --output results/bearish_bos_2024.json
```

### 2. Output JSON Report

```json
{
  "metadata": {
    "generated_at": "2026-02-12T07:12:57.064500+00:00",
    "candles_csv": "data/sample_backtest/candles.csv",
    "signals_jsonl": "data/sample_backtest/signals.jsonl",
    "filters": {
      "symbol": "EURUSD",
      "signal_type": null,
      "from_date": null,
      "to_date": null
    }
  },
  "metrics": {
    "sample_size": 10,
    "completed_trades": 10,
    "unknown_trades": 0,
    "win_count": 0,
    "loss_count": 10,
    "be_count": 0,
    "win_rate": 0.0,
    "be_rate": 0.0,
    "expectancy": -1.0
  },
  "outcomes": [
    {
      "signal_id": "sig_001",
      "outcome": "LOSS",
      "r_multiple": -1.0,
      "mae": 0.003,
      "mfe": 0.001,
      "exit_price": 1.0805,
      "exit_time": "2024-01-01T09:00:00+00:00"
    },
    ...
  ]
}
```

### 3. Run Tests

```bash
# Run all backtest_replay tests
pytest tests/backtest_replay/ -v

# Run specific test file
pytest tests/backtest_replay/test_outcome_tagger.py -v

# Run tests with coverage
pytest tests/backtest_replay/ --cov=backtest_replay
```

**Output:**
```
======================== 23 passed in 0.06s ==========================
```

## Data Formats

### Candles CSV

```csv
timestamp,open,high,low,close,volume
2024-01-01 10:00:00,1.0850,1.0880,1.0840,1.0865,1000000
2024-01-01 11:00:00,1.0865,1.0895,1.0860,1.0875,1100000
```

- **timestamp**: ISO format, will be converted to UTC
- **open/high/low/close**: Prices as floats
- **volume**: Optional

### Signals JSONL

One JSON object per line:

```jsonl
{"signal_id": "sig_001", "timestamp": "2024-01-01 10:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "long", "signal_type": "bearish_bos", "entry": 1.0850, "sl": 1.0820, "tp": 1.0900, "session": "london", "meta": {...}}
{"signal_id": "sig_002", "timestamp": "2024-01-01 11:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "short", "signal_type": "bullish_choch", "entry": 1.0875, "sl": 1.0900, "tp": 1.0800, "session": "london"}
```

**Required fields:**
- `signal_id`, `timestamp`, `symbol`, `timeframe`, `direction`, `signal_type`, `entry`, `sl`, `tp`

**Optional fields:**
- `session`, `meta`

## Outcome Tagging Algorithm

### Deterministic Scan

For each signal:

1. Find all candles strictly after signal entry timestamp
2. Scan candles in order (ascending by timestamp)
3. For each candle, check if SL or TP is hit:
   - **Long**: SL hit if `low <= sl_price`, TP hit if `high >= tp_price`
   - **Short**: SL hit if `high >= sl_price`, TP hit if `low <= tp_price`
4. **Tie-Break Rule** (if both hit in same candle): Exit at SL → LOSS
5. Stop scanning when either level hit or max_bars exceeded

### R-Multiple Calculation

```
risk = entry - sl    (for long)
risk = sl - entry    (for short)

r_multiple = (exit_price - entry) / risk    (for long)
r_multiple = (entry - exit_price) / risk    (for short)
```

- Positive r_multiple = Win
- Negative r_multiple = Loss
- Zero r_multiple = Break-even

### MAE/MFE (in R)

**MAE (Max Adverse Excursion)**: Worst unrealized loss
```
For long:  mae = (entry - low) / risk
For short: mae = (high - entry) / risk
```

**MFE (Max Favorable Excursion)**: Best unrealized profit
```
For long:  mfe = (high - entry) / risk
For short: mfe = (entry - low) / risk
```

## Metrics

### Basic Metrics

- **sample_size**: Total signals processed
- **completed_trades**: Trades with definitive exit (WIN/LOSS/BE)
- **unknown_trades**: Trades with no exit found
- **win_rate**: completed_trades with outcome=WIN / completed_trades
- **expectancy**: Average r_multiple across all trades

### Risk Metrics

- **average_r**: Mean r_multiple
- **max_r**: Best single trade
- **min_r**: Worst single trade
- **max_drawdown_r**: Largest cumulative loss from peak equity
- **max_loss_streak**: Longest consecutive losses

## API Usage

### Load Candles

```python
from backtest_replay.candle_loader import CandleLoader

candles = CandleLoader.load_csv('data/candles.csv')
# Returns: List[Candle] with timestamp (UTC), open, high, low, close, volume
```

### Load Signals

```python
from backtest_replay.signal_loader import SignalLoader

# From JSONL
signals = SignalLoader.load_jsonl('data/signals.jsonl')

# From DB (async)
signals = await SignalLoader.load_from_db(
    sessionmaker,
    symbol='EURUSD',
    signal_type='bearish_bos',
    from_ts=datetime(...),
    to_ts=datetime(...)
)
```

### Tag Outcomes

```python
from backtest_replay import outcome_tagger

outcomes = outcome_tagger.tag_from_candles(signals, candles)
# Returns: List[ReplayOutcome] with outcome, r_multiple, mae, mfe, etc.
```

### Compute Metrics

```python
from backtest_replay import metrics

expectancy = metrics.compute_expectancy(outcomes)
win_rate = metrics.compute_win_rate(outcomes)
r_distribution = metrics.distribution(outcomes)
```

## Edge Cases Handled

✅ **No candles after signal**: Outcome = UNKNOWN (no exit)  
✅ **Tie-break**: Both SL & TP hit same candle → Exit at SL (LOSS)  
✅ **Max bars exceeded**: If no exit within N bars → UNKNOWN  
✅ **Negative risk**: If SL = entry, use fallback (shouldn't happen with valid data)  
✅ **Partial fills**: All candles scanned until one level hit  
✅ **Zero r_multiple**: Handled as break-even (be_count += 1)  

## File Changes Summary

| File | Type | Lines | Purpose |
|------|------|-------|---------|
| `backtest_replay/candle_loader.py` | Module | 109 | Load CSV candles, UTC-aware timestamps, sorted |
| `backtest_replay/signal_loader.py` | Module | 181 | Load JSONL signals or query DB |
| `backtest_replay/replay_runner.py` | Module | 303 | Orchestrate pipeline, compute metrics |
| `scripts/run_historical_replay.py` | CLI | 350 | Entry point with args parsing, JSON report |
| `data/sample_backtest/candles.csv` | Data | 51 | 50 EURUSD 1h candles |
| `data/sample_backtest/signals.jsonl` | Data | 10 | 10 sample trading signals |
| `tests/backtest_replay/test_candle_loader.py` | Test | 160 | 7 tests for candle loading |
| `tests/backtest_replay/test_signal_loader.py` | Test | 190 | 9 tests for signal loading |

## Constraints Satisfied

✅ **Additive Only**: No modifications to existing Stage 9/10 code  
✅ **Isolated**: Changes confined to `backtest_replay/` and `scripts/` and `tests/`  
✅ **Pytest Native**: All tests run with `pytest tests/backtest_replay/`  
✅ **Minimal Dependencies**: Uses only stdlib + existing SQLAlchemy/pytest  
✅ **Deterministic**: Same inputs → same outputs (no randomness)  
✅ **Well-Documented**: Docstrings, tests, and this README  

## Testing

**23 Test Cases:**

```
test_candle_loader.py (7):
  ✓ test_load_csv_basic
  ✓ test_candles_sorted_ascending
  ✓ test_missing_required_column
  ✓ test_file_not_found
  ✓ test_empty_csv
  ✓ test_optional_volume_column
  ✓ test_candle_comparison

test_signal_loader.py (9):
  ✓ test_load_jsonl_basic
  ✓ test_signals_sorted_ascending
  ✓ test_direction_lowercased
  ✓ test_file_not_found
  ✓ test_empty_jsonl
  ✓ test_malformed_json
  ✓ test_skip_blank_lines
  ✓ test_optional_fields
  ✓ test_signal_comparison

test_outcome_tagger.py (5):
  ✓ test_long_tp_hit_first
  ✓ test_long_sl_first_tie_break
  ✓ test_short_tp_hit_first
  ✓ test_short_sl_first_tie_break
  ✓ test_long_no_exit

test_metrics.py (2):
  ✓ test_compute_metrics_basic
  ✓ test_group_metrics
```

## Next Steps

1. **Load your own data** into CSV/JSONL format
2. **Run replay** against historical candles
3. **Analyze outcomes** for signal quality validation
4. **Filter by signal_type** to evaluate specific models
5. **Compare expectancy** across timeframes or sessions
6. **Integrate with orchestrator** via `outcome_tagger.tag_from_candles()`

## Example: Complete Workflow

```python
from backtest_replay.candle_loader import CandleLoader
from backtest_replay.signal_loader import SignalLoader
from backtest_replay import outcome_tagger, metrics

# 1. Load data
candles = CandleLoader.load_csv('candles.csv')
signals = SignalLoader.load_jsonl('signals.jsonl')

# 2. Filter (optional)
signals = [s for s in signals if s.symbol == 'EURUSD' and s.signal_type == 'bearish_bos']

# 3. Tag outcomes
outcomes = outcome_tagger.tag_from_candles(signals, candles)

# 4. Compute metrics
exp = metrics.compute_expectancy(outcomes)
wr = metrics.compute_win_rate(outcomes)
r_vals = metrics.distribution(outcomes)

print(f"Expectancy: {exp:.4f} R")
print(f"Win Rate: {wr:.2%}")
print(f"R Distribution: {sorted(r_vals)}")
```

## Deterministic Tie-Break Deep Dive

### Why SL-First?

When both SL and TP are touched in the same candle, real execution semantics are ambiguous. Without tick-by-tick data, we assume:

1. **Risk-First Principle**: Stop-loss is tighter to entry, so it likely fills first
2. **Conservative Bias**: For backtesting, assume worst outcome (loss)
3. **Deterministic**: No randomness - everyone gets same result

### Implementation

**File**: `backtest_replay/outcome_tagger.py`, lines 115-125

```python
# Tie-break: if both hit, LOSS (SL-first)
if sl_hit and tp_hit:
    exit_price = sl
    exit_time = candle["timestamp"]
    outcome = "LOSS"
    r_multiple = -1.0
    break
```

This ensures consistent, reproducible backtests across all signal types.

---

**Last Updated**: 2026-02-12  
**Version**: 1.0.0  
**Status**: Production Ready ✅
