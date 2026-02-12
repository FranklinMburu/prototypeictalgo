#!/usr/bin/env python
"""
Historical Replay Validation CLI.

Evaluates real signals against real OHLCV candles to compute outcome +
r_multiple + expectancy metrics. Deterministic, no randomness, SL-first
tie-break when TP and SL hit in same candle.

Usage:
    python scripts/run_historical_replay.py \\
        --candles-csv data/sample_backtest/candles.csv \\
        --signals-jsonl data/sample_backtest/signals.jsonl \\
        --symbol EURUSD \\
        --output results/replay_report.json

Example with filters:
    python scripts/run_historical_replay.py \\
        --candles-csv candles.csv \\
        --signals-jsonl signals.jsonl \\
        --symbol EURUSD \\
        --signal-type bearish_bos \\
        --from "2024-01-01" \\
        --to "2024-02-01" \\
        --output results/bearish_bos_report.json
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path to allow running as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_replay.signal_loader import SignalLoader
from backtest_replay import outcome_tagger
from backtest_replay import metrics


def load_candles_csv(csv_path: str) -> list:
    """Load candles from CSV."""
    candles = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row['timestamp'].strip()
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            candle = {
                'timestamp': ts,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row.get('volume', 0)) if 'volume' in row else None,
            }
            candles.append(candle)
    # Sort by timestamp
    candles.sort(key=lambda c: c['timestamp'])
    return candles


def parse_iso_date(date_str: str) -> datetime:
    """Parse ISO date string to datetime."""
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError as e:
        raise ValueError(f"Invalid ISO date format: {date_str}") from e


def run_historical_replay(args) -> dict:
    """Run the replay pipeline."""
    print(f"\n{'='*70}")
    print(f"  Historical Replay Validation")
    print(f"{'='*70}\n")

    # Load candles
    print(f"Loading candles from: {args.candles_csv}")
    try:
        candles = load_candles_csv(args.candles_csv)
        print(f"✓ Loaded {len(candles)} candles")
    except Exception as e:
        print(f"✗ Error loading candles: {e}")
        sys.exit(1)

    # Load signals
    print(f"Loading signals from: {args.signals_jsonl}")
    try:
        signals = SignalLoader.load_jsonl(args.signals_jsonl)
        print(f"✓ Loaded {len(signals)} signals")
    except Exception as e:
        print(f"✗ Error loading signals: {e}")
        sys.exit(1)

    # Filter signals
    if args.symbol:
        signals = [s for s in signals if s.symbol == args.symbol]
        print(f"  Filtered by symbol '{args.symbol}': {len(signals)} signals")

    if args.signal_type:
        signals = [s for s in signals if s.signal_type == args.signal_type]
        print(f"  Filtered by signal_type '{args.signal_type}': {len(signals)} signals")

    from_date = None
    if args.from_date:
        from_date = parse_iso_date(args.from_date)
        signals = [s for s in signals if s.timestamp >= from_date]
        print(f"  Filtered from {args.from_date}: {len(signals)} signals")

    to_date = None
    if args.to_date:
        to_date = parse_iso_date(args.to_date)
        signals = [s for s in signals if s.timestamp <= to_date]
        print(f"  Filtered to {args.to_date}: {len(signals)} signals")

    if not signals:
        print(f"✗ No signals match criteria")
        sys.exit(1)

    print(f"\n{'─'*70}")

    # Tag outcomes
    print(f"\nTagging outcomes...")
    try:
        outcomes = outcome_tagger.tag_from_candles(signals, candles)
        print(f"✓ Tagged {len(outcomes)} outcomes")
    except Exception as e:
        print(f"✗ Error tagging outcomes: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Compute metrics
    print(f"\nComputing metrics...")
    try:
        expectancy = metrics.compute_expectancy(outcomes)
        win_rate = metrics.compute_win_rate(outcomes)
        be_rate = metrics.compute_break_even_rate(outcomes)
        r_dist = metrics.distribution(outcomes)
        
        # Count outcomes by type
        win_count = sum(1 for o in outcomes if o.outcome == 'WIN')
        loss_count = sum(1 for o in outcomes if o.outcome == 'LOSS')
        be_count = sum(1 for o in outcomes if o.outcome == 'BE')
        unknown_count = sum(1 for o in outcomes if o.outcome == 'UNKNOWN')
        completed_trades = win_count + loss_count + be_count
        
        print(f"✓ Computed metrics")
    except Exception as e:
        print(f"✗ Error computing metrics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"\n{'─'*70}")
    print(f"\nRESULTS:")
    print(f"  Sample Size: {len(outcomes)}")
    print(f"  Completed Trades: {completed_trades}")
    print(f"  Unknown/Cancelled: {unknown_count}")
    print(f"  Win Count: {win_count}")
    print(f"  Loss Count: {loss_count}")
    print(f"  BE Count: {be_count}")
    print(f"\n  Win Rate: {win_rate:.2%}")
    print(f"  BE Rate: {be_rate:.2%}")
    print(f"  Loss Rate: {1 - win_rate - be_rate:.2%}")
    print(f"\n  Expectancy: {expectancy:.4f} R")
    
    if r_dist:
        avg_r = sum(r_dist) / len(r_dist)
        max_r = max(r_dist)
        min_r = min(r_dist)
        print(f"  Average R: {avg_r:.4f}")
        print(f"  Max R: {max_r:.4f}")
        print(f"  Min R: {min_r:.4f}")
    
    print(f"\n{'='*70}")

    # Build report
    report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "candles_csv": str(args.candles_csv),
            "signals_jsonl": str(args.signals_jsonl),
            "filters": {
                "symbol": args.symbol,
                "signal_type": args.signal_type,
                "from_date": args.from_date,
                "to_date": args.to_date,
            },
        },
        "metrics": {
            "sample_size": len(outcomes),
            "completed_trades": completed_trades,
            "unknown_trades": unknown_count,
            "win_count": win_count,
            "loss_count": loss_count,
            "be_count": be_count,
            "win_rate": round(win_rate, 4),
            "be_rate": round(be_rate, 4),
            "expectancy": round(expectancy, 4),
        },
        "outcomes": [
            {
                "signal_id": o.signal_id,
                "outcome": o.outcome,
                "r_multiple": o.r_multiple,
                "mae": o.mae,
                "mfe": o.mfe,
                "exit_price": o.exit_price,
                "exit_time": o.exit_time.isoformat() if o.exit_time else None,
            }
            for o in outcomes
        ],
    }

    return report



def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--candles-csv",
        type=str,
        required=True,
        help="Path to OHLCV candles CSV file",
    )
    parser.add_argument(
        "--signals-jsonl",
        type=str,
        required=True,
        help="Path to signals JSONL file",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,
        help="Filter by symbol (optional)",
    )
    parser.add_argument(
        "--signal-type",
        type=str,
        default=None,
        help="Filter by signal type (optional)",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        type=str,
        default=None,
        help="Filter from ISO date (optional)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=str,
        default=None,
        help="Filter to ISO date (optional)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON report path (optional)",
    )

    args = parser.parse_args()

    # Validate files exist
    if not Path(args.candles_csv).exists():
        print(f"✗ Candles CSV not found: {args.candles_csv}")
        sys.exit(1)

    if not Path(args.signals_jsonl).exists():
        print(f"✗ Signals JSONL not found: {args.signals_jsonl}")
        sys.exit(1)

    # Run replay
    report = run_historical_replay(args)

    # Save report if output path specified
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n✓ Report saved to: {output_path}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
