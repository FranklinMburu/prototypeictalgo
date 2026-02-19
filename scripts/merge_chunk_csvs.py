#!/usr/bin/env python3
"""
Merge multiple TwelveData CSV chunk files deterministically.

Handles:
- Multiple input files with consistent schema
- Removes duplicate rows (same datetime, keeps first occurrence)
- Deterministic stable sort by datetime
- CSV header validation and preservation
- Deterministic: same input → identical output regardless of chunk order

Usage:
    python scripts/merge_chunk_csvs.py \
        --inputs chunk1.csv chunk2.csv chunk3.csv \
        --output merged.csv
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from argparse import ArgumentParser
from collections import OrderedDict


def load_csv_with_header(csv_path: str) -> tuple:
    """Load CSV file and return (header, rows).
    
    Args:
        csv_path: Path to CSV file
        
    Returns:
        Tuple of (header_list, list_of_row_dicts)
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If CSV is empty
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV is empty or has no header: {csv_path}")
        
        header = list(reader.fieldnames)
        rows = list(reader)
    
    return header, rows


def validate_header_consistency(headers: list) -> None:
    """Validate that all headers are identical.
    
    Args:
        headers: List of header lists from each chunk
        
    Raises:
        ValueError: If headers differ
    """
    if not headers:
        return
    
    first_header = headers[0]
    for i, header in enumerate(headers[1:], start=2):
        if header != first_header:
            raise ValueError(
                f"Header mismatch: chunk 1 has {first_header}, "
                f"chunk {i} has {header}"
            )


def deduplicate_by_key(rows: list, key_field: str) -> tuple:
    """Remove duplicate rows by keeping first occurrence.
    
    Args:
        rows: List of row dicts
        key_field: Field name to check for duplicates (e.g., 'datetime')
        
    Returns:
        Tuple of (deduped_rows, dedup_count)
    """
    seen = set()
    deduped = []
    dedup_count = 0
    
    for row in rows:
        key = row.get(key_field, "")
        if key not in seen:
            seen.add(key)
            deduped.append(row)
        else:
            dedup_count += 1
    
    return deduped, dedup_count


def parse_datetime_flexible(dt_str: str) -> datetime:
    """Parse datetime string, trying multiple formats.
    
    TwelveData can return:
    - 2026-01-01 00:00:00
    - 2026-01-01T00:00:00Z
    
    Args:
        dt_str: Datetime string
        
    Returns:
        datetime object (naive, UTC assumed)
        
    Raises:
        ValueError: If no format matches
    """
    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_str.strip(), fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Cannot parse datetime: {dt_str}")


def sort_rows_by_datetime(rows: list, datetime_field: str = "datetime") -> list:
    """Sort rows by datetime field (stable, deterministic).
    
    Args:
        rows: List of row dicts
        datetime_field: Name of datetime column
        
    Returns:
        Sorted list
    """
    def sort_key(row):
        try:
            return parse_datetime_flexible(row.get(datetime_field, ""))
        except ValueError:
            # Put unparseable dates at end, sorted lexicographically
            return (datetime.max, row.get(datetime_field, ""))
    
    return sorted(rows, key=sort_key)


def merge_chunk_csvs(input_paths: list, output_path: str) -> None:
    """Merge multiple CSV chunks deterministically.
    
    Args:
        input_paths: List of input CSV file paths
        output_path: Path to output merged CSV
    """
    if not input_paths:
        raise ValueError("No input files provided")
    
    # Load all chunks
    all_rows = []
    headers = []
    input_counts = {}
    
    print(f"Loading {len(input_paths)} chunk files...")
    
    for csv_path in input_paths:
        try:
            header, rows = load_csv_with_header(csv_path)
            headers.append(header)
            input_counts[str(csv_path)] = len(rows)
            all_rows.extend(rows)
            print(f"  ✓ {csv_path}: {len(rows)} rows")
        except Exception as e:
            print(f"  ✗ {csv_path}: {e}")
            sys.exit(1)
    
    # Validate header consistency
    try:
        validate_header_consistency(headers)
        header = headers[0]
        print(f"✓ Header consistent across all chunks: {header}")
    except ValueError as e:
        print(f"✗ {e}")
        sys.exit(1)
    
    # Detect datetime column name
    datetime_col = None
    for col_name in ["datetime", "time", "timestamp"]:
        if col_name in header:
            datetime_col = col_name
            break
    
    if not datetime_col:
        print(f"✗ No datetime column found. Available: {header}")
        sys.exit(1)
    
    print(f"✓ Using datetime column: '{datetime_col}'")
    
    # Deduplicate
    total_before = len(all_rows)
    deduped_rows, dedup_count = deduplicate_by_key(all_rows, datetime_col)
    print(f"✓ Deduplicated: {total_before} → {len(deduped_rows)} rows (removed {dedup_count})")
    
    # Sort by datetime
    sorted_rows = sort_rows_by_datetime(deduped_rows, datetime_col)
    print(f"✓ Sorted by '{datetime_col}' (deterministic)")
    
    # Write output
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(sorted_rows)
        print(f"✓ Merged CSV written: {output_path}")
    except Exception as e:
        print(f"✗ Error writing output: {e}")
        sys.exit(1)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"MERGE SUMMARY")
    print(f"{'='*70}")
    print(f"Input chunks: {len(input_paths)}")
    for fpath, count in input_counts.items():
        print(f"  {fpath}: {count} rows")
    print(f"Total input rows: {sum(input_counts.values())}")
    print(f"Duplicates removed: {dedup_count}")
    print(f"Output rows: {len(sorted_rows)}")
    
    if sorted_rows:
        first_dt = sorted_rows[0].get(datetime_col, "")
        last_dt = sorted_rows[-1].get(datetime_col, "")
        print(f"DateTime range:")
        print(f"  First: {first_dt}")
        print(f"  Last:  {last_dt}")
    
    print(f"Output: {output_path}")


def main() -> None:
    """CLI entry point."""
    parser = ArgumentParser(
        description="Merge multiple TwelveData CSV chunk files deterministically"
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input CSV files (space-separated paths)"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output merged CSV file path"
    )
    
    args = parser.parse_args()
    merge_chunk_csvs(args.inputs, args.output)


if __name__ == "__main__":
    main()
