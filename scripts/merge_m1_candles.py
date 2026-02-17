#!/usr/bin/env python3
"""
Merge multiple M1 candle CSV files deterministically.

Inputs: Multiple M1 candle CSVs with header: timestamp,open,high,low,close,volume
Output: Single merged CSV with same header, sorted by timestamp, duplicates removed.

Deterministic: Preserves stable sort, keeps first occurrence of duplicate timestamps.
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from argparse import ArgumentParser


def validate_candle_csv(csv_path):
    """Validate CSV schema and return list of rows."""
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
            raise ValueError(
                f"{csv_path}: Invalid header. Expected "
                f"['timestamp', 'open', 'high', 'low', 'close', 'volume'], "
                f"got {reader.fieldnames}"
            )
        rows = list(reader)
        for i, row in enumerate(rows, start=2):
            try:
                datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                raise ValueError(
                    f"{csv_path}:{i}: Invalid timestamp format '{row['timestamp']}'. "
                    f"Expected YYYY-MM-DD HH:MM:SS"
                )
    return rows


def merge_candles(input_paths, output_path):
    """Merge multiple candle CSVs into one."""
    all_rows = []
    input_counts = {}
    
    # Load all rows from all input files
    for csv_path in input_paths:
        try:
            rows = validate_candle_csv(csv_path)
            input_counts[str(csv_path)] = len(rows)
            all_rows.extend(rows)
            print(f"✓ Loaded {len(rows)} candles from {csv_path}")
        except Exception as e:
            print(f"✗ Error loading {csv_path}: {e}")
            sys.exit(1)
    
    # Sort by timestamp (deterministic)
    all_rows.sort(key=lambda r: r['timestamp'])
    
    # Remove duplicates (keep first occurrence)
    seen_ts = set()
    deduped_rows = []
    for row in all_rows:
        ts = row['timestamp']
        if ts not in seen_ts:
            seen_ts.add(ts)
            deduped_rows.append(row)
    
    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        writer.writeheader()
        writer.writerows(deduped_rows)
    
    # Print summary
    total_input = sum(input_counts.values())
    duplicates = total_input - len(deduped_rows)
    
    print(f"\n=== MERGE SUMMARY ===")
    print(f"Input files: {len(input_paths)}")
    for fpath, count in input_counts.items():
        print(f"  {fpath}: {count} candles")
    print(f"Total input candles: {total_input}")
    print(f"Duplicates removed: {duplicates}")
    print(f"Output candles: {len(deduped_rows)}")
    
    if deduped_rows:
        print(f"\nTimestamp range:")
        print(f"  Min: {deduped_rows[0]['timestamp']}")
        print(f"  Max: {deduped_rows[-1]['timestamp']}")
    
    print(f"\n✓ Merged CSV written to: {output_path}")


def main():
    parser = ArgumentParser(description='Merge M1 candle CSV files deterministically')
    parser.add_argument(
        '--inputs',
        nargs='+',
        required=True,
        help='Input candle CSV files (space-separated paths)'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output merged CSV file path'
    )
    args = parser.parse_args()
    
    input_paths = [Path(p) for p in args.inputs]
    output_path = Path(args.output)
    
    merge_candles(input_paths, output_path)


if __name__ == '__main__':
    main()
