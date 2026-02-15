#!/usr/bin/env python
"""
Export signals to JSONL format for replay testing.

IMPORTANT: This is a SYNTHETIC PLUMBING-ONLY exporter.
Real signals source not found in repo. Generates deterministic signals
from M1 candles for testing the replay pipeline.

Behavior:
- Reads M1 candle CSV
- Selects every STRIDE_CANDLES (240 = 4 hours for M1)
- Generates signals with deterministic params:
  * direction: alternates long/short
  * signal_type: alternates bullish_choch/bearish_bos
  * entry: candle close
  * risk: candle (high - low), or previous risk if zero
  * sl/tp: computed from entry + risk
  * session: deterministic from hour

Deterministic: identical input → identical output (no randomness).

Usage:
    python scripts/export_signals_to_jsonl.py \\
        --candles-csv data/processed/EURUSD/M1/EURUSD-2026-01-M1.csv \\
        --output data/processed/EURUSD/signals.jsonl \\
        --stride 240 \\
        --max-signals 200

Output format (JSONL):
    {"signal_id": "syn_001", "timestamp": "2026-01-01 18:02:00", ...}
    {"signal_id": "syn_002", "timestamp": "2026-01-02 22:02:00", ...}
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_session_from_hour(hour: int) -> str:
    """Deterministic session mapping from hour (UTC).
    
    - 00-07: asian (Tokyo/Hong Kong)
    - 08-15: london
    - 16-23: new_york
    """
    if 0 <= hour < 8:
        return "asian"
    elif 8 <= hour < 16:
        return "london"
    else:
        return "new_york"


def load_candles_csv(csv_path: str) -> list:
    """Load candles from M1 CSV.
    
    Returns:
        List of dicts with keys: timestamp, open, high, low, close, volume
    """
    candles = []
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Candles CSV not found: {csv_path}")
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
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
                    'volume': float(row.get('volume', 1)) if 'volume' in row else 1,
                }
                candles.append(candle)
            except (ValueError, KeyError) as e:
                print(f"⚠ Skipping malformed candle row: {row}. Error: {e}", file=sys.stderr)
                continue
    
    if not candles:
        raise ValueError(f"No valid candles loaded from {csv_path}")
    
    # Sort by timestamp (should already be sorted, but ensure)
    candles.sort(key=lambda c: c['timestamp'])
    return candles


def generate_signals(candles: list, stride: int = 240, max_signals: int = 200) -> list:
    """Generate deterministic synthetic signals from candles.
    
    Args:
        candles: List of candle dicts
        stride: Sample every N candles (240 = 4 hours for M1)
        max_signals: Cap total signals generated
    
    Returns:
        List of signal dicts in JSONL-ready format
    """
    signals = []
    signal_count = 0
    last_risk = 0.0  # Track previous non-zero risk
    
    for idx in range(0, len(candles), stride):
        if signal_count >= max_signals:
            break
        
        candle = candles[idx]
        ts = candle['timestamp']
        
        # Deterministic params
        direction = "long" if signal_count % 2 == 0 else "short"
        signal_type = "bullish_choch" if signal_count % 2 == 0 else "bearish_bos"
        entry = candle['close']
        
        # Risk = high - low, or use previous if zero
        risk = candle['high'] - candle['low']
        if risk == 0:
            risk = last_risk if last_risk > 0 else 0.0001
        else:
            last_risk = risk
        
        # SL and TP
        if direction == "long":
            sl = entry - risk
            tp = entry + 2 * risk
        else:  # short
            sl = entry + risk
            tp = entry - 2 * risk
        
        # Session from hour
        session = get_session_from_hour(ts.hour)
        
        # Build signal
        signal = {
            "signal_id": f"syn_{signal_count + 1:03d}",
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": "EURUSD",
            "timeframe": "1m",
            "direction": direction,
            "signal_type": signal_type,
            "entry": float(f"{entry:.5f}"),
            "sl": float(f"{sl:.5f}"),
            "tp": float(f"{tp:.5f}"),
            "session": session,
            "meta": {
                "generated_from_candle_index": idx,
                "generation_method": "synthetic_deterministic",
            },
        }
        
        signals.append(signal)
        signal_count += 1
    
    if not signals:
        raise ValueError(f"No signals generated from {len(candles)} candles with stride={stride}")
    
    return signals


def write_signals_jsonl(signals: list, output_path: str) -> None:
    """Write signals to JSONL file.
    
    Args:
        signals: List of signal dicts
        output_path: Path to output JSONL file
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        for signal in signals:
            f.write(json.dumps(signal) + '\n')
    
    print(f"✓ Wrote {len(signals)} signals to: {output_path}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export synthetic signals to JSONL for replay testing"
    )
    parser.add_argument(
        "--candles-csv",
        required=True,
        help="Path to M1 candle CSV"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output JSONL file"
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=240,
        help="Sample every N candles (default 240 = 4 hours for M1)"
    )
    parser.add_argument(
        "--max-signals",
        type=int,
        default=200,
        help="Maximum signals to generate (default 200)"
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*70}")
    print(f"  Synthetic Signal Exporter (PLUMBING-ONLY)")
    print(f"{'='*70}\n")
    print(f"⚠ NOTE: This is synthetic deterministic signal generation.")
    print(f"         Real signals source not found in repo.\n")
    
    try:
        # Load candles
        print(f"Loading candles from: {args.candles_csv}")
        candles = load_candles_csv(args.candles_csv)
        print(f"✓ Loaded {len(candles)} candles")
        
        # Generate signals
        print(f"\nGenerating signals with stride={args.stride}, max={args.max_signals}...")
        signals = generate_signals(candles, stride=args.stride, max_signals=args.max_signals)
        print(f"✓ Generated {len(signals)} signals")
        
        # Write to JSONL
        print(f"\nWriting to JSONL...")
        write_signals_jsonl(signals, args.output)
        
        # Print sample
        print(f"\nFirst signal (sample):")
        print(json.dumps(signals[0], indent=2))
        
        print(f"\n{'='*70}")
        print(f"✓ Export complete!")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
