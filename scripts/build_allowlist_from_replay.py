#!/usr/bin/env python
"""
Build allowlist from historical replay summary.

Filters replay groups by deterministic thresholds:
- sample_size >= MIN_SAMPLES
- expectancy >= MIN_EXPECTANCY
- max_drawdown_r <= MAX_DD
- max_loss_streak <= MAX_STREAK

Outputs allowlist.json with allowed group keys and filtering rules used.

Usage:
    python scripts/build_allowlist_from_replay.py \\
        --replay-summary-json results/replay_summary.json \\
        --min-samples 50 \\
        --min-expectancy 0.20 \\
        --max-dd 10.0 \\
        --max-streak 7 \\
        --output results/allowlist.json

Deterministic: identical input + thresholds → identical output.
No randomness. All filtering is deterministic and reproducible.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


@dataclass
class AllowlistEntry:
    """Single allowed group entry."""
    symbol: str
    timeframe: str
    session: str
    signal_type: str
    direction: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "session": self.session,
            "signal_type": self.signal_type,
            "direction": self.direction,
        }
    
    def to_key(self) -> str:
        """Create group key for matching."""
        return f"{self.symbol}|{self.timeframe}|{self.session}|{self.signal_type}|{self.direction}"


def load_replay_summary(json_path: str) -> Dict[str, Any]:
    """Load replay summary JSON."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Replay summary not found: {json_path}")
    
    with open(path, "r") as f:
        return json.load(f)


def filter_groups(
    groups: List[Dict[str, Any]],
    min_samples: int,
    min_expectancy: float,
    max_dd: float,
    max_streak: int,
) -> List[AllowlistEntry]:
    """Filter groups by thresholds. Deterministic and sortable."""
    allowed = []
    
    for group in groups:
        # Extract fields with strict naming
        symbol = group.get("symbol", "")
        timeframe = group.get("timeframe", "")
        session = group.get("session", "")
        signal_type = group.get("signal_type", "")
        direction = group.get("direction", "")
        
        # Extract metrics
        sample_size = group.get("sample_size", 0)
        expectancy = group.get("expectancy", 0.0)
        max_drawdown_r = group.get("max_drawdown_r", float('inf'))
        max_loss_streak = group.get("max_loss_streak", float('inf'))
        
        # Apply thresholds (all must pass)
        if (sample_size >= min_samples and
            expectancy >= min_expectancy and
            max_drawdown_r <= max_dd and
            max_loss_streak <= max_streak):
            
            entry = AllowlistEntry(
                symbol=symbol,
                timeframe=timeframe,
                session=session,
                signal_type=signal_type,
                direction=direction,
            )
            allowed.append(entry)
    
    # Sort deterministically by group key for reproducibility
    allowed.sort(key=lambda e: e.to_key())
    return allowed


def build_allowlist(
    replay_summary: Dict[str, Any],
    min_samples: int,
    min_expectancy: float,
    max_dd: float,
    max_streak: int,
) -> Dict[str, Any]:
    """Build allowlist dictionary with metadata."""
    groups = replay_summary.get("groups", [])
    allowed_entries = filter_groups(groups, min_samples, min_expectancy, max_dd, max_streak)
    
    # Convert to serializable format
    allowed_dicts = [e.to_dict() for e in allowed_entries]
    
    allowlist = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source_replay_summary": replay_summary.get("timestamp", ""),
        "thresholds": {
            "min_samples": min_samples,
            "min_expectancy": min_expectancy,
            "max_drawdown_r": max_dd,
            "max_loss_streak": max_streak,
        },
        "total_allowed": len(allowed_dicts),
        "total_groups_evaluated": len(groups),
        "allowed_groups": allowed_dicts,
    }
    
    return allowlist


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Build allowlist from historical replay summary"
    )
    parser.add_argument(
        "--replay-summary-json",
        required=True,
        help="Path to replay_summary.json from run_replay_batch.py",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=50,
        help="Minimum sample size to allow (default: 50)",
    )
    parser.add_argument(
        "--min-expectancy",
        type=float,
        default=0.20,
        help="Minimum expectancy (R multiples) to allow (default: 0.20)",
    )
    parser.add_argument(
        "--max-dd",
        type=float,
        default=10.0,
        help="Maximum drawdown (R multiples) to allow (default: 10.0)",
    )
    parser.add_argument(
        "--max-streak",
        type=int,
        default=7,
        help="Maximum consecutive loss streak to allow (default: 7)",
    )
    parser.add_argument(
        "--output",
        default="results/allowlist.json",
        help="Output path for allowlist JSON (default: results/allowlist.json)",
    )

    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  Building Allowlist from Replay Summary")
    print(f"{'='*70}\n")

    # Load replay summary
    print(f"Loading: {args.replay_summary_json}")
    try:
        replay_summary = load_replay_summary(args.replay_summary_json)
        total_groups = len(replay_summary.get("groups", []))
        print(f"✓ Loaded {total_groups} groups from replay summary")
    except Exception as e:
        print(f"✗ Error loading replay summary: {e}")
        sys.exit(1)

    # Build allowlist
    print("\nApplying thresholds:")
    print(f"  min_samples:     {args.min_samples}")
    print(f"  min_expectancy:  {args.min_expectancy}R")
    print(f"  max_drawdown_r:  {args.max_dd}R")
    print(f"  max_streak:      {args.max_streak}")

    try:
        allowlist = build_allowlist(
            replay_summary,
            args.min_samples,
            args.min_expectancy,
            args.max_dd,
            args.max_streak,
        )
    except Exception as e:
        print(f"✗ Error building allowlist: {e}")
        sys.exit(1)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating: {args.output}")
    try:
        with open(output_path, "w") as f:
            json.dump(allowlist, f, indent=2, default=str)
        print(f"✓ Allowlist saved")
    except Exception as e:
        print(f"✗ Error writing allowlist: {e}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"Summary:")
    print(f"  Total groups evaluated: {allowlist['total_groups_evaluated']}")
    print(f"  Total allowed:          {allowlist['total_allowed']}")
    allowed_pct = (allowlist['total_allowed'] / max(1, allowlist['total_groups_evaluated'])) * 100
    print(f"  Allowed %:              {allowed_pct:.1f}%")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
