#!/usr/bin/env python3
"""
Filter real signals by symbol, preserving order and JSON validity.

Input: signals.jsonl file (one JSON signal per line)
Output: Filtered signals.jsonl (only specified symbol)

Deterministic: Preserves chronological order, no reordering.
"""

import json
import sys
from pathlib import Path
from argparse import ArgumentParser


def filter_signals(input_path, output_path, symbol):
    """Filter signals by symbol."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    if not input_path.exists():
        print(f"✗ Input file not found: {input_path}")
        sys.exit(1)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    filtered = []
    total_lines = 0
    malformed_lines = 0
    
    with open(input_path) as f:
        for line_num, line in enumerate(f, start=1):
            total_lines += 1
            line = line.strip()
            
            if not line:
                continue  # Skip empty lines
            
            try:
                signal = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"✗ Malformed JSON at line {line_num}: {e}")
                malformed_lines += 1
                continue
            
            # Check if signal has symbol field
            if 'symbol' not in signal:
                print(f"✗ Line {line_num}: Missing 'symbol' field")
                malformed_lines += 1
                continue
            
            # Filter by symbol
            if signal['symbol'] == symbol:
                filtered.append(signal)
    
    # Write filtered signals in same JSONL format
    with open(output_path, 'w') as f:
        for signal in filtered:
            f.write(json.dumps(signal) + '\n')
    
    # Print summary
    print(f"=== FILTER SUMMARY ===")
    print(f"Input file: {input_path}")
    print(f"Total lines: {total_lines}")
    print(f"Malformed: {malformed_lines}")
    print(f"Valid signals: {total_lines - malformed_lines}")
    print(f"Filtered by symbol '{symbol}': {len(filtered)}")
    
    if filtered:
        print(f"\nSignal timestamps:")
        print(f"  Min: {filtered[0].get('timestamp', 'N/A')}")
        print(f"  Max: {filtered[-1].get('timestamp', 'N/A')}")
    
    print(f"\n✓ Filtered signals written to: {output_path}")


def main():
    parser = ArgumentParser(description='Filter real signals by symbol')
    parser.add_argument(
        '--input',
        required=True,
        help='Input signals.jsonl file'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output filtered signals.jsonl file'
    )
    parser.add_argument(
        '--symbol',
        default='EURUSD',
        help='Symbol to filter by (default: EURUSD)'
    )
    args = parser.parse_args()
    
    filter_signals(args.input, args.output, args.symbol)


if __name__ == '__main__':
    main()
