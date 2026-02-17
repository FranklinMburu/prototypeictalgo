#!/usr/bin/env python3
"""
Real EURUSD Signal Replay Pipeline Orchestrator

Executes the full replay workflow:
1. Convert TrueFX Feb ticks to M1 candles
2. Merge Jan+Feb M1 candles
3. Filter real signals to EURUSD only
4. Run historical replay on filtered signals
5. Batch summary and allowlist generation

Deterministic: All operations preserve order, dups handled consistently.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_command(cmd, description):
    """Run a shell command and return success status."""
    print(f"\n{'='*60}")
    print(f"▶ {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"\n✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ {description} failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"\n✗ {description} failed: {e}")
        return False


def pipeline_eurusd_real_replay():
    """Execute full real EURUSD replay pipeline."""
    
    workspace_root = Path(__file__).parent.parent
    scripts_dir = workspace_root / "scripts"
    data_dir = workspace_root / "data"
    processed_dir = data_dir / "processed" / "EURUSD"
    raw_dir = data_dir / "raw" / "truefx"
    m1_dir = processed_dir / "M1"
    
    # Step 0: Validate prerequisites
    print(f"{'='*60}")
    print(f"REAL EURUSD SIGNAL REPLAY PIPELINE")
    print(f"{'='*60}\n")
    
    print("PREREQUISITE CHECK:")
    
    # Check Jan M1 candles
    jan_candles = m1_dir / "EURUSD-2026-01-M1.csv"
    if not jan_candles.exists():
        print(f"✗ Missing: {jan_candles}")
        sys.exit(1)
    print(f"✓ Jan M1 candles: {jan_candles}")
    
    # Check Feb raw ticks
    feb_ticks = raw_dir / "EURUSD-2026-02.csv"
    if not feb_ticks.exists():
        print(f"✗ Missing: {feb_ticks}")
        print(f"   Please download EURUSD-2026-02.csv and place at: {feb_ticks}")
        sys.exit(1)
    print(f"✓ Feb raw ticks: {feb_ticks}")
    
    # Check real signals
    real_signals = processed_dir / "real_signals.jsonl"
    if not real_signals.exists():
        print(f"✗ Missing: {real_signals}")
        sys.exit(1)
    print(f"✓ Real signals: {real_signals}")
    
    print("\nALL PREREQUISITES MET\n")
    
    # Step 1: Convert Feb ticks to M1
    feb_candles = m1_dir / "EURUSD-2026-02-M1.csv"
    cmd_convert = [
        sys.executable,
        str(scripts_dir / "convert_truefx_ticks_to_m1.py"),
        "--input", str(feb_ticks),
        "--output", str(feb_candles)
    ]
    if not run_command(cmd_convert, "Convert Feb TrueFX ticks to M1 candles"):
        sys.exit(1)
    
    # Step 2: Merge Jan+Feb M1 candles
    merged_candles = m1_dir / "EURUSD-2026-01-02-M1.csv"
    cmd_merge = [
        sys.executable,
        str(scripts_dir / "merge_m1_candles.py"),
        "--inputs", str(jan_candles), str(feb_candles),
        "--output", str(merged_candles)
    ]
    if not run_command(cmd_merge, "Merge Jan+Feb M1 candles"):
        sys.exit(1)
    
    # Step 3: Filter signals to EURUSD only
    eurusd_signals = processed_dir / "EURUSD-filtered-signals.jsonl"
    cmd_filter = [
        sys.executable,
        str(scripts_dir / "filter_real_signals.py"),
        "--input", str(real_signals),
        "--output", str(eurusd_signals),
        "--symbol", "EURUSD"
    ]
    if not run_command(cmd_filter, "Filter real signals to EURUSD"):
        sys.exit(1)
    
    # Step 4: Run historical replay
    replay_results = processed_dir / "replay-results-eurusd.jsonl"
    cmd_replay = [
        sys.executable,
        str(scripts_dir / "run_historical_replay.py"),
        "--candles", str(merged_candles),
        "--signals", str(eurusd_signals),
        "--output", str(replay_results)
    ]
    if not run_command(cmd_replay, "Run historical replay"):
        sys.exit(1)
    
    # Step 5: Batch summary
    batch_summary = processed_dir / "replay-summary-eurusd.txt"
    cmd_batch = [
        sys.executable,
        str(scripts_dir / "run_replay_batch.py"),
        "--replay-results", str(replay_results),
        "--output", str(batch_summary)
    ]
    if not run_command(cmd_batch, "Generate batch summary"):
        sys.exit(1)
    
    # Step 6: Build allowlist
    allowlist = processed_dir / "allowlist-eurusd.jsonl"
    cmd_allowlist = [
        sys.executable,
        str(scripts_dir / "build_allowlist_from_replay.py"),
        "--replay-results", str(replay_results),
        "--output", str(allowlist),
        "--min-win-rate", "0.6",
        "--min-profit-factor", "1.5"
    ]
    if not run_command(cmd_allowlist, "Build allowlist from replay"):
        sys.exit(1)
    
    # Final summary
    print(f"\n{'='*60}")
    print(f"✓ PIPELINE COMPLETE")
    print(f"{'='*60}\n")
    
    print("OUTPUT ARTIFACTS:")
    print(f"  Merged candles: {merged_candles}")
    print(f"  EURUSD signals: {eurusd_signals}")
    print(f"  Replay results: {replay_results}")
    print(f"  Batch summary: {batch_summary}")
    print(f"  Allowlist: {allowlist}")
    
    print(f"\nNEXT STEPS:")
    print(f"  1. Review batch summary: {batch_summary}")
    print(f"  2. Inspect allowlist: {allowlist}")
    print(f"  3. Use allowlist for live trading (Stage 9/10)")
    
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    pipeline_eurusd_real_replay()
