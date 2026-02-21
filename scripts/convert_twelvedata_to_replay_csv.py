#!/usr/bin/env python3
"""
TwelveData to Replay CSV Converter

Transforms TwelveData semicolon-delimited OHLC CSV into replay engine format.

Input example:
  datetime;open;high;low;close
  2026-01-31 15:15:00;4865.3728;4865.56149;4865.35015;4865.35015

Output format (EXACT):
  timestamp,open,high,low,close,volume
  2026-01-31 15:15:00,4865.3728,4865.56149,4865.35015,4865.35015,0

Constraints:
  - Auto-detect delimiter (; or ,)
  - Normalize datetime column to timestamp
  - Inject volume column (default value or from input)
  - Hard fail on: duplicate timestamps, missing OHLC, non-numeric values
  - Sort ascending if needed (report if applied)
  - Validate 5-minute spacing consistency (report gaps)

Usage:
    python scripts/convert_twelvedata_to_replay_csv.py \
        --in input.csv \
        --out output.csv \
        --default-volume 0
"""

import argparse
import csv
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Optional, Set

# Version tracking for data normalization
DATA_NORMALIZER_VERSION = "XAUUSD_M5_REAL_v1"


class TwelveDataConverter:
    """Convert TwelveData CSV to replay engine format with validation."""
    
    REPLAY_HEADER = ["timestamp", "open", "high", "low", "close", "volume"]
    REQUIRED_COLS = {"open", "high", "low", "close"}
    TIMESTAMP_COLS = {"datetime", "timestamp", "time"}
    
    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        default_volume: float = 0.0,
    ):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.default_volume = default_volume
        
        # Audit tracking
        self.delimiter = None
        self.input_headers = None
        self.input_rows = 0
        self.output_rows = 0
        self.first_timestamp = None
        self.last_timestamp = None
        self.sorting_applied = False
        self.volume_injected = False
        self.duplicate_timestamps = 0
        self.gap_count = 0
        self.gap_details = []
    
    def detect_delimiter(self) -> str:
        """Auto-detect CSV delimiter (semicolon or comma).
        
        Returns:
            ';' or ','
            
        Raises:
            ValueError: If delimiter cannot be determined
        """
        with open(self.input_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        
        if not first_line:
            raise ValueError("Input file is empty")
        
        semicolon_count = first_line.count(';')
        comma_count = first_line.count(',')
        
        # Prefer semicolon if more prevalent
        if semicolon_count > comma_count:
            return ';'
        elif comma_count > 0:
            return ','
        else:
            raise ValueError(f"Cannot detect delimiter in line: {first_line}")
    
    def normalize_timestamp(self, ts_str: str) -> str:
        """Parse and normalize timestamp to %Y-%m-%d %H:%M:%S.
        
        Accepts:
        - 2026-01-31 15:15:00
        - 2026-01-31T15:15:00Z
        
        Returns:
            Normalized string in %Y-%m-%d %H:%M:%S format
            
        Raises:
            ValueError: If timestamp format unrecognized
        """
        ts_str = ts_str.strip()
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(ts_str, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        
        raise ValueError(f"Unrecognized timestamp format: {ts_str}")
    
    def validate_and_load(self) -> Tuple[List[Dict], str]:
        """Load and validate input CSV.
        
        Returns:
            Tuple of (rows_list, datetime_column_name)
            
        Raises:
            FileNotFoundError: If input not found
            ValueError: If schema invalid or data malformed
        """
        if not self.input_path.exists():
            raise FileNotFoundError(f"Input file not found: {self.input_path}")
        
        # Detect delimiter
        self.delimiter = self.detect_delimiter()
        
        # Load CSV
        rows = []
        with open(self.input_path, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f, delimiter=self.delimiter)
            
            if not reader.fieldnames:
                raise ValueError("Input CSV has no header")
            
            self.input_headers = list(reader.fieldnames)
            
            # Detect datetime column
            dt_col = None
            for col in self.input_headers:
                if col.lower().strip() in self.TIMESTAMP_COLS:
                    dt_col = col
                    break
            
            if not dt_col:
                raise ValueError(
                    f"No datetime column found. Available: {self.input_headers}"
                )
            
            # Validate required columns exist
            available_lower = {h.lower().strip(): h for h in self.input_headers}
            for required in self.REQUIRED_COLS:
                if required.lower() not in available_lower:
                    raise ValueError(
                        f"Missing required column: {required}. "
                        f"Available: {self.input_headers}"
                    )
            
            # Load and validate rows
            for row_num, row in enumerate(reader, start=2):
                try:
                    # Validate required columns are non-empty
                    if not row.get(dt_col, "").strip():
                        raise ValueError(f"Empty datetime in row {row_num}")
                    
                    # Validate OHLC are numeric
                    for col in self.REQUIRED_COLS:
                        actual_col = available_lower.get(col.lower())
                        val = row.get(actual_col, "").strip()
                        if not val:
                            raise ValueError(
                                f"Empty {col} in row {row_num}"
                            )
                        try:
                            float(val)
                        except ValueError:
                            raise ValueError(
                                f"Non-numeric {col}={val} in row {row_num}"
                            )
                    
                    rows.append(row)
                    self.input_rows += 1
                
                except ValueError as e:
                    raise ValueError(f"Row {row_num}: {e}")
        
        if not rows:
            raise ValueError("No valid rows in input CSV")
        
        return rows, dt_col
    
    def detect_duplicate_timestamps(self, rows: List[Dict], dt_col: str) -> Set[str]:
        """Detect duplicate timestamps.
        
        Returns:
            Set of duplicate timestamp strings
        """
        seen = {}
        duplicates = set()
        
        for row_num, row in enumerate(rows, start=2):
            ts_str = row.get(dt_col, "").strip()
            if ts_str in seen:
                duplicates.add(ts_str)
            else:
                seen[ts_str] = row_num
        
        self.duplicate_timestamps = len(duplicates)
        return duplicates
    
    def detect_gaps(self, timestamps: List[str], interval_minutes: int = 5) -> List[Tuple[str, str, int]]:
        """Detect gaps in 5-minute timestamp sequence.
        
        Args:
            timestamps: Sorted list of timestamp strings
            interval_minutes: Expected interval between candles
        
        Returns:
            List of (from_ts, to_ts, missing_count) tuples
        """
        gaps = []
        
        for i in range(len(timestamps) - 1):
            current = datetime.strptime(timestamps[i], "%Y-%m-%d %H:%M:%S")
            next_ts = datetime.strptime(timestamps[i + 1], "%Y-%m-%d %H:%M:%S")
            
            expected_next = current + timedelta(minutes=interval_minutes)
            
            if next_ts > expected_next:
                minutes_gap = int((next_ts - expected_next).total_seconds() / 60)
                candles_missing = minutes_gap // interval_minutes
                
                gaps.append(
                    (timestamps[i], timestamps[i + 1], candles_missing)
                )
        
        self.gap_count = len(gaps)
        self.gap_details = gaps
        return gaps
    
    def convert(self) -> None:
        """Execute full conversion pipeline."""
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load and validate input
        rows, dt_col = self.validate_and_load()
        
        # Check for duplicates (hard fail)
        duplicates = self.detect_duplicate_timestamps(rows, dt_col)
        if duplicates:
            raise ValueError(
                f"Duplicate timestamps found (hard fail): {duplicates}"
            )
        
        # Get available column mappings (case-insensitive)
        available_lower = {h.lower().strip(): h for h in self.input_headers}
        col_map = {
            'datetime': dt_col,
            'open': available_lower.get('open'),
            'high': available_lower.get('high'),
            'low': available_lower.get('low'),
            'close': available_lower.get('close'),
            'volume': available_lower.get('volume'),
        }
        
        # Convert rows
        converted = []
        timestamps_seen = []
        
        for row in rows:
            try:
                ts_normalized = self.normalize_timestamp(
                    row.get(col_map['datetime'], "")
                )
                
                converted_row = {
                    'timestamp': ts_normalized,
                    'open': float(row.get(col_map['open'], 0)),
                    'high': float(row.get(col_map['high'], 0)),
                    'low': float(row.get(col_map['low'], 0)),
                    'close': float(row.get(col_map['close'], 0)),
                    'volume': (
                        float(row.get(col_map['volume'], self.default_volume))
                        if col_map['volume']
                        else self.default_volume
                    ),
                }
                
                converted.append(converted_row)
                timestamps_seen.append(ts_normalized)
            
            except (ValueError, KeyError) as e:
                raise ValueError(f"Conversion error: {e}")
        
        # Mark if volume was injected (no volume column in input)
        self.volume_injected = col_map['volume'] is None
        
        # Check sorting and sort if needed
        sorted_converted = sorted(converted, key=lambda r: r['timestamp'])
        if sorted_converted != converted:
            self.sorting_applied = True
            converted = sorted_converted
        
        # Update sorted timestamps for gap detection
        sorted_timestamps = [r['timestamp'] for r in converted]
        
        # Detect gaps (report only, don't fail)
        self.detect_gaps(sorted_timestamps, interval_minutes=5)
        
        # Set audit tracking
        self.output_rows = len(converted)
        self.first_timestamp = sorted_timestamps[0] if sorted_timestamps else None
        self.last_timestamp = sorted_timestamps[-1] if sorted_timestamps else None
        
        # Write output
        with open(self.output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=self.REPLAY_HEADER,
                extrasaction='ignore',  # Ignore any extra columns
            )
            writer.writeheader()
            writer.writerows(converted)
    
    def print_audit_report(self) -> None:
        """Print comprehensive audit report."""
        print("\n" + "=" * 70)
        print("DATASET AUDIT REPORT")
        print("=" * 70)
        print(f"Version:              {DATA_NORMALIZER_VERSION}")
        print(f"Input file:           {self.input_path}")
        print(f"Output file:          {self.output_path}")
        print(f"Detected delimiter:   '{self.delimiter}'")
        print(f"Input headers:        {self.input_headers}")
        print(f"Input rows:           {self.input_rows}")
        print(f"Output rows:          {self.output_rows}")
        print(f"First timestamp:      {self.first_timestamp}")
        print(f"Last timestamp:       {self.last_timestamp}")
        print(f"Sorting applied:      {self.sorting_applied}")
        print(f"Volume injected:      {self.volume_injected} (default={self.default_volume})")
        print(f"Duplicate timestamps: {self.duplicate_timestamps}")
        print(f"Gap count:            {self.gap_count}")
        if self.gap_details and self.gap_count <= 10:
            for from_ts, to_ts, missing in self.gap_details[:10]:
                print(f"  {from_ts} → {to_ts} ({missing} candles missing)")
        print("=" * 70 + "\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert TwelveData CSV to replay engine format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/convert_twelvedata_to_replay_csv.py \\
    --in raw_data.csv \\
    --out processed.csv \\
    --default-volume 0
        """,
    )
    
    parser.add_argument(
        "--in",
        dest="input_file",
        required=True,
        help="Input TwelveData CSV file path",
    )
    parser.add_argument(
        "--out",
        dest="output_file",
        required=True,
        help="Output replay-ready CSV file path",
    )
    parser.add_argument(
        "--default-volume",
        type=float,
        default=0.0,
        help="Default volume value if not in input (default: 0.0)",
    )
    
    args = parser.parse_args()
    
    try:
        converter = TwelveDataConverter(
            input_path=args.input_file,
            output_path=args.output_file,
            default_volume=args.default_volume,
        )
        
        converter.convert()
        converter.print_audit_report()
        
        print("✓ Conversion successful")
    
    except (FileNotFoundError, ValueError) as e:
        print(f"✗ Conversion failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
