#!/usr/bin/env python
"""
Batch Historical Replay with Per-Group Metrics.

Groups replay results by symbol, timeframe, session, signal_type, and direction.
Computes per-group metrics: sample_size, completed_trades, win_rate,
expectancy, max_drawdown_r, max_loss_streak.

Outputs:
  - results/replay_summary.json (structured per-group metrics)
  - results/replay_summary.md (sorted table by expectancy desc, sample_size desc)

Deterministic: identical input → identical output.

Usage:
    python scripts/run_replay_batch.py \\
        --candles-csv data/sample_backtest/candles.csv \\
        --signals-jsonl data/sample_backtest/signals.jsonl

Example with custom output:
    python scripts/run_replay_batch.py \\
        --candles-csv candles.csv \\
        --signals-jsonl signals.jsonl \\
        --output-dir custom_results
"""

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path to allow running as script
sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest_replay.signal_loader import SignalLoader, ReplaySignal
from backtest_replay.outcome_tagger import tag_from_candles
from backtest_replay.schemas import ReplayOutcome


@dataclass
class GroupMetrics:
    """Metrics for a single group (symbol+timeframe+session+signal_type+direction)."""

    symbol: str
    timeframe: str
    session: str
    signal_type: str
    direction: str
    sample_size: int
    completed_trades: int
    cancelled_trades: int
    win_rate: float
    loss_rate: float
    be_rate: float
    expectancy: float
    max_drawdown_r: float
    max_loss_streak: int
    max_win_streak: int


def load_candles_csv(csv_path: str) -> List[dict]:
    """Load candles from CSV with UTC timestamps."""
    candles = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts_str = row["timestamp"].strip()
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            candle = {
                "timestamp": ts,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0)) if "volume" in row else None,
            }
            candles.append(candle)
    # Sort by timestamp for deterministic processing
    candles.sort(key=lambda c: c["timestamp"])
    return candles


def group_outcomes(
    signals: List[ReplaySignal], outcomes: List[ReplayOutcome]
) -> Dict[str, List[Tuple[ReplaySignal, ReplayOutcome]]]:
    """
    Group outcomes by (symbol, timeframe, session, model, direction).

    Args:
        signals: List of ReplaySignal objects
        outcomes: List of corresponding ReplayOutcome objects

    Returns:
        Dict mapping group key to list of (signal, outcome) tuples
    """
    groups: Dict[str, List[Tuple[ReplaySignal, ReplayOutcome]]] = {}

    for signal, outcome in zip(signals, outcomes):
        # Create deterministic group key
        group_key = f"{signal.symbol}|{signal.timeframe}|{signal.session}|{signal.signal_type}|{signal.direction}"
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append((signal, outcome))

    return groups


def compute_group_metrics(
    signal: ReplaySignal, grouped: List[Tuple[ReplaySignal, ReplayOutcome]]
) -> GroupMetrics:
    """Compute metrics for a single group."""
    sample_size = len(grouped)
    completed_trades = sum(
        1 for _, outcome in grouped if outcome.outcome in ("WIN", "LOSS")
    )
    cancelled_trades = sum(
        1 for _, outcome in grouped if outcome.outcome == "UNKNOWN"
    )

    # Count wins, losses, breakevens
    wins = [outcome for _, outcome in grouped if outcome.r_multiple and outcome.r_multiple > 0]
    losses = [outcome for _, outcome in grouped if outcome.r_multiple and outcome.r_multiple < 0]
    bes = [outcome for _, outcome in grouped if outcome.r_multiple and outcome.r_multiple == 0]

    win_count = len(wins)
    loss_count = len(losses)
    be_count = len(bes)

    # Rates
    win_rate = win_count / completed_trades if completed_trades > 0 else 0.0
    loss_rate = loss_count / completed_trades if completed_trades > 0 else 0.0
    be_rate = be_count / completed_trades if completed_trades > 0 else 0.0

    # Expectancy
    if win_count > 0 and loss_count > 0:
        avg_win = sum(o.r_multiple for o in wins) / win_count
        avg_loss = sum(abs(o.r_multiple) for o in losses) / loss_count
        expectancy = (avg_win - avg_loss) * win_rate
    else:
        expectancy = 0.0

    # Max drawdown: cumulative peak-to-trough
    max_dd = 0.0
    max_loss_streak = 0
    max_win_streak = 0
    current_loss_streak = 0
    current_win_streak = 0

    cumulative = 0.0
    peak = 0.0

    for _, outcome in grouped:
        if outcome.r_multiple is None:
            continue
        cumulative += outcome.r_multiple
        # Update peak and max drawdown
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
        # Track streaks
        if outcome.r_multiple < 0:
            current_loss_streak += 1
            current_win_streak = 0
            if current_loss_streak > max_loss_streak:
                max_loss_streak = current_loss_streak
        elif outcome.r_multiple > 0:
            current_win_streak += 1
            current_loss_streak = 0
            if current_win_streak > max_win_streak:
                max_win_streak = current_win_streak
        else:  # breakeven
            current_loss_streak = 0
            current_win_streak = 0

    return GroupMetrics(
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        session=signal.session,
        signal_type=signal.signal_type,
        direction=signal.direction,
        sample_size=sample_size,
        completed_trades=completed_trades,
        cancelled_trades=cancelled_trades,
        win_rate=round(win_rate, 4),
        loss_rate=round(loss_rate, 4),
        be_rate=round(be_rate, 4),
        expectancy=round(expectancy, 4),
        max_drawdown_r=round(max_dd, 4),
        max_loss_streak=max_loss_streak,
        max_win_streak=max_win_streak,
    )


def generate_json_report(metrics_list: List[GroupMetrics], output_path: Path) -> None:
    """Generate JSON report with all group metrics."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total_groups": len(metrics_list),
        "groups": [asdict(m) for m in metrics_list],
    }
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def generate_markdown_report(metrics_list: List[GroupMetrics], output_path: Path) -> None:
    """Generate Markdown report with sorted table."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort by expectancy (desc), then sample_size (desc)
    sorted_metrics = sorted(
        metrics_list,
        key=lambda m: (-m.expectancy, -m.sample_size),
    )

    lines = [
        "# Batch Replay Summary",
        "",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        "",
        f"Total Groups: {len(sorted_metrics)}",
        "",
        "## Results by Group",
        "",
        "| Symbol | Timeframe | Session | Signal Type | Direction | N | Trades | Win% | Expectancy | Max DD | Max Loss Streak |",
        "|--------|-----------|---------|-------------|-----------|---|--------|------|------------|--------|-------------|",
    ]

    for m in sorted_metrics:
        row = (
            f"| {m.symbol} | {m.timeframe} | {m.session} | {m.signal_type} | {m.direction} "
            f"| {m.sample_size} | {m.completed_trades} | {m.win_rate:.1%} "
            f"| {m.expectancy:.4f}R | {m.max_drawdown_r:.4f}R | {m.max_loss_streak} |"
        )
        lines.append(row)

    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch replay with per-group metrics and JSON/MD output"
    )
    parser.add_argument(
        "--candles-csv",
        required=True,
        help="Path to candles CSV file",
    )
    parser.add_argument(
        "--signals-jsonl",
        required=True,
        help="Path to signals JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        default="results",
        help="Output directory for JSON and Markdown reports (default: results/)",
    )

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  Batch Historical Replay")
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

    if not signals:
        print("✗ No signals to process")
        sys.exit(1)

    # Tag outcomes
    print("Tagging outcomes...")
    try:
        outcomes = tag_from_candles(signals, candles)
        print(f"✓ Tagged {len(outcomes)} outcomes")
    except Exception as e:
        print(f"✗ Error tagging outcomes: {e}")
        sys.exit(1)

    # Group and compute metrics
    print("Grouping by symbol/timeframe/session/model/direction...")
    groups = group_outcomes(signals, outcomes)
    print(f"✓ Found {len(groups)} groups")

    metrics_list = []
    for group_key, grouped_outcomes in groups.items():
        # Find a signal from this group to extract metadata
        sample_signal = grouped_outcomes[0][0]
        group_metrics = compute_group_metrics(sample_signal, grouped_outcomes)
        metrics_list.append(group_metrics)

    # Generate reports
    output_dir = Path(args.output_dir)

    json_path = output_dir / "replay_summary.json"
    print(f"\nGenerating: {json_path}")
    generate_json_report(metrics_list, json_path)
    print(f"✓ JSON report saved")

    md_path = output_dir / "replay_summary.md"
    print(f"Generating: {md_path}")
    generate_markdown_report(metrics_list, md_path)
    print(f"✓ Markdown report saved")

    print(f"\n{'='*70}\n")
    print(f"Summary: {len(metrics_list)} groups processed")
    print(f"Best expectancy: {max((m.expectancy for m in metrics_list), default=0):.4f}R")
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
