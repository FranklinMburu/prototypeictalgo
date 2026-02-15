#!/usr/bin/env python
"""
End-to-end Replay Pipeline Runner for EURUSD TrueFX Jan 2026 M1 candles.

Pipeline:
  1. Verify M1 candles exist: data/processed/EURUSD/M1/EURUSD-2026-01-M1.csv
  2. Generate signals: data/processed/EURUSD/signals.jsonl
  3. Run historical replay: script/run_historical_replay.py
  4. Run batch summary: scripts/run_replay_batch.py
  5. Build allowlist: scripts/build_allowlist_from_replay.py
  6. Print proof summary

Deterministic: same inputs always produce same outputs.

Usage:
    python scripts/run_replay_pipeline_eurusd_truefx_jan2026.py

Outputs:
  - data/processed/EURUSD/signals.jsonl (generated)
  - results/replay_report.json (from replay)
  - results/replay_summary.json (from batch)
  - results/replay_summary.md (from batch)
  - results/allowlist.json (from builder)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


# Configuration for EURUSD Jan 2026
CANDLES_CSV = "data/processed/EURUSD/M1/EURUSD-2026-01-M1.csv"
SIGNALS_JSONL = "data/processed/EURUSD/signals.jsonl"
REPLAY_REPORT_JSON = "results/replay_report.json"
SUMMARY_JSON = "results/replay_summary.json"
SUMMARY_MD = "results/replay_summary.md"
ALLOWLIST_JSON = "results/allowlist.json"


def check_file_exists(path: str) -> bool:
    """Check if file exists."""
    return Path(path).exists()


def run_command(cmd: list, description: str) -> bool:
    """Run a command and report status.
    
    Args:
        cmd: Command list for subprocess
        description: Human-readable description
    
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'─'*70}")
    print(f"  {description}")
    print(f"{'─'*70}")
    print(f"Command: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        print(f"✓ {description} succeeded")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed with exit code {e.returncode}")
        if e.stdout:
            print(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            print(f"STDERR:\n{e.stderr}")
        return False
    except Exception as e:
        print(f"✗ Error running {description}: {e}")
        return False


def print_proof_summary() -> None:
    """Print summary of results."""
    print(f"\n{'='*70}")
    print(f"  PROOF SUMMARY")
    print(f"{'='*70}\n")
    
    # Load and validate outputs
    results_summary = {}
    
    # Signals count
    if Path(SIGNALS_JSONL).exists():
        with open(SIGNALS_JSONL, 'r') as f:
            signal_lines = [line.strip() for line in f if line.strip()]
            results_summary['signals_exported'] = len(signal_lines)
            print(f"✓ Signals exported: {len(signal_lines)}")
    else:
        print(f"✗ Signals JSONL not found")
        results_summary['signals_exported'] = 0
    
    # Replay report
    if Path(REPLAY_REPORT_JSON).exists():
        with open(REPLAY_REPORT_JSON, 'r') as f:
            report = json.load(f)
            outcomes = report.get('outcomes', [])
            results_summary['outcomes_produced'] = len(outcomes)
            print(f"✓ Replay outcomes produced: {len(outcomes)}")
    else:
        print(f"✗ Replay report not found")
        results_summary['outcomes_produced'] = 0
    
    # Batch summary
    if Path(SUMMARY_JSON).exists():
        with open(SUMMARY_JSON, 'r') as f:
            summary = json.load(f)
            groups = summary.get('groups', [])
            results_summary['total_groups'] = len(groups)
            print(f"✓ Total groups in summary: {len(groups)}")
    else:
        print(f"✗ Batch summary not found")
        results_summary['total_groups'] = 0
    
    # Allowlist
    if Path(ALLOWLIST_JSON).exists():
        with open(ALLOWLIST_JSON, 'r') as f:
            allowlist = json.load(f)
            allowed = allowlist.get('allowed', [])
            results_summary['allowelist_total_allowed'] = len(allowed)
            print(f"✓ Allowlist total allowed: {len(allowed)}")
            
            # Show first 5 keys
            if allowed:
                print(f"\nFirst 5 allowlist keys:")
                for key in allowed[:5]:
                    print(f"  - {key}")
            else:
                print(f"\n⚠ Warning: Allowlist is EMPTY (no groups passed filters)")
    else:
        print(f"✗ Allowlist not found")
        results_summary['allowelist_total_allowed'] = 0
    
    print(f"\n{'='*70}\n")


def main():
    """Run the full pipeline."""
    parser = argparse.ArgumentParser(
        description="End-to-end replay pipeline for EURUSD TrueFX Jan 2026"
    )
    parser.add_argument(
        "--candles-csv",
        default=CANDLES_CSV,
        help=f"Path to M1 candles (default: {CANDLES_CSV})"
    )
    parser.add_argument(
        "--signals-output",
        default=SIGNALS_JSONL,
        help=f"Path to output signals JSONL (default: {SIGNALS_JSONL})"
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Skip signal export step"
    )
    
    args = parser.parse_args()
    
    print(f"\n{'='*70}")
    print(f"  END-TO-END REPLAY PIPELINE")
    print(f"  EURUSD TrueFX Jan 2026 M1 Candles")
    print(f"{'='*70}\n")
    
    # Step 1: Verify input candles exist
    print(f"Verifying input files...")
    if not check_file_exists(args.candles_csv):
        print(f"✗ Candles CSV not found: {args.candles_csv}")
        sys.exit(1)
    print(f"✓ Candles CSV exists: {args.candles_csv}")
    
    # Step 2: Generate signals (unless --skip-export)
    if not args.skip_export:
        print(f"\n{'─'*70}")
        print(f"  STEP 1: Generate Synthetic Signals")
        print(f"{'─'*70}")
        
        export_cmd = [
            "python",
            "scripts/export_signals_to_jsonl.py",
            "--candles-csv", args.candles_csv,
            "--output", args.signals_output,
            "--stride", "240",
            "--max-signals", "200",
        ]
        if not run_command(export_cmd, "Signal export"):
            sys.exit(1)
    else:
        print(f"\nSkipping signal export (--skip-export)")
        if not check_file_exists(args.signals_output):
            print(f"✗ Signals JSONL not found: {args.signals_output}")
            sys.exit(1)
        print(f"✓ Using existing signals: {args.signals_output}")
    
    # Step 3: Run historical replay
    print(f"\n{'─'*70}")
    print(f"  STEP 2: Run Historical Replay")
    print(f"{'─'*70}")
    
    replay_cmd = [
        "python",
        "scripts/run_historical_replay.py",
        "--candles-csv", args.candles_csv,
        "--signals-jsonl", args.signals_output,
        "--output", REPLAY_REPORT_JSON,
    ]
    if not run_command(replay_cmd, "Historical replay"):
        sys.exit(1)
    
    # Step 4: Run batch summary
    print(f"\n{'─'*70}")
    print(f"  STEP 3: Run Batch Summary")
    print(f"{'─'*70}")
    
    batch_cmd = [
        "python",
        "scripts/run_replay_batch.py",
        "--candles-csv", args.candles_csv,
        "--signals-jsonl", args.signals_output,
        "--output-dir", "results",
    ]
    if not run_command(batch_cmd, "Batch summary"):
        sys.exit(1)
    
    # Step 5: Build allowlist
    print(f"\n{'─'*70}")
    print(f"  STEP 4: Build Allowlist")
    print(f"{'─'*70}")
    
    allowlist_cmd = [
        "python",
        "scripts/build_allowlist_from_replay.py",
        "--replay-summary-json", SUMMARY_JSON,
        "--output", ALLOWLIST_JSON,
    ]
    if not run_command(allowlist_cmd, "Allowlist builder"):
        sys.exit(1)
    
    # Step 6: Print proof summary
    print_proof_summary()
    
    print(f"{'='*70}")
    print(f"✓✓✓ PIPELINE COMPLETE ✓✓✓")
    print(f"{'='*70}\n")
    print(f"Next steps:")
    print(f"  1. Review results/allowlist.json for approved signal groups")
    print(f"  2. Enable in agent/constraints.yaml: allowlist.enabled = true")
    print(f"  3. Live trades will be vetted against allowlist\n")


if __name__ == "__main__":
    main()
