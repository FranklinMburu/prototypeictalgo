#!/usr/bin/env python3
"""
Merge multiple TwelveData CSV chunks into a single deterministic stitched CSV.

Input: Multiple TwelveData CSVs (semicolon or comma-delimited, no volume)
Output: Stitched raw TwelveData CSV (semicolon-delimited)
         Optional: Replay-ready processed CSV (via converter)

Behavior:
- Expand glob patterns deterministically
- Dedup rows by datetime (keep first occurrence)
- Sort by timestamp
- Validate schema strictly (hard fail on errors)
- Print comprehensive audit report
- Optionally generate replay format via converter
"""

import sys
import csv
import glob
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Set
from collections import OrderedDict


class TwelveDataMerger:
    """Merge multiple TwelveData CSV files deterministically."""
    
    REQUIRED_COLS = {"datetime", "open", "high", "low", "close"}
    RAW_HEADER = ["datetime", "open", "high", "low", "close"]
    
    def __init__(
        self,
        inputs: str,
        out_raw: str,
        out_processed: str = None,
        default_volume: float = 0.0,
    ):
        self.inputs_arg = inputs
        self.out_raw = out_raw
        self.out_processed = out_processed
        self.default_volume = default_volume
        
        self.input_files: List[str] = []
        self.rows_read_total = 0
        self.rows_after_dedupe = 0
        self.duplicates_removed = 0
        self.sorting_applied = False
        self.first_datetime = None
        self.last_datetime = None
    
    def expand_inputs(self) -> List[str]:
        """
        Expand --inputs argument into deterministic file list.
        
        Format: comma-separated paths/globs
        Example: "path1.csv,path2.csv,data/raw/*.csv"
        
        Returns: sorted list of existing files
        Raises: ValueError if list is empty or file missing
        """
        tokens = [t.strip() for t in self.inputs_arg.split(",")]
        expanded = set()
        
        for token in tokens:
            if not token:
                continue
            
            # Check if it's a glob pattern
            if any(c in token for c in ["*", "?", "["]):
                matches = glob.glob(token)
                if not matches:
                    raise ValueError(f"Glob pattern matched no files: {token}")
                expanded.update(matches)
            else:
                # Direct file path
                if not Path(token).exists():
                    raise ValueError(f"File does not exist: {token}")
                expanded.add(token)
        
        if not expanded:
            raise ValueError("No input files found after expanding --inputs")
        
        # Sort lexicographically for determinism
        result = sorted(list(expanded))
        self.input_files = result
        return result
    
    def detect_delimiter(self, file_path: str) -> str:
        """Auto-detect delimiter from first row."""
        with open(file_path, 'r') as f:
            first_line = f.readline()
        
        # Check for semicolon or comma
        if ';' in first_line:
            return ';'
        elif ',' in first_line:
            return ','
        else:
            raise ValueError(f"Cannot detect delimiter in {file_path}")
    
    def read_file(self, file_path: str) -> Tuple[List[Dict], str]:
        """
        Read and validate a single TwelveData CSV file.
        
        Returns: (rows as dicts, delimiter used)
        Raises: ValueError on schema validation errors
        """
        delimiter = self.detect_delimiter(file_path)
        
        rows = []
        with open(file_path, 'r', newline='') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            
            if reader.fieldnames is None:
                raise ValueError(f"Empty file: {file_path}")
            
            # Normalize fieldnames (strip whitespace)
            fieldnames = tuple(f.strip() for f in reader.fieldnames) if reader.fieldnames else ()
            reader.fieldnames = fieldnames
            
            # Validate header
            if not self.REQUIRED_COLS.issubset(set(fieldnames)):
                missing = self.REQUIRED_COLS - set(fieldnames)
                raise ValueError(
                    f"Missing required columns in {file_path}: {missing}\n"
                    f"Found: {fieldnames}"
                )
            
            for row_num, row in enumerate(reader, start=2):  # start=2 (1=header)
                # Normalize row keys
                row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
                
                # Validate datetime format
                dt_str = row.get("datetime", "")
                try:
                    datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    raise ValueError(
                        f"Invalid datetime format in {file_path} row {row_num}: "
                        f"'{dt_str}' (expected %Y-%m-%d %H:%M:%S)"
                    )
                
                # Validate OHLC are numeric
                for col in ["open", "high", "low", "close"]:
                    try:
                        float(row[col])
                    except (KeyError, ValueError):
                        raise ValueError(
                            f"Non-numeric {col} in {file_path} row {row_num}: '{row.get(col)}'"
                        )
                
                rows.append(row)
        
        return rows, delimiter
    
    def merge(self):
        """
        Merge all input files with deduplication and sorting.
        """
        # Expand inputs
        self.expand_inputs()
        
        # Collect all rows with dedup
        seen_datetimes: Set[str] = set()
        collected_rows: Dict[str, Dict] = OrderedDict()
        
        for file_path in self.input_files:
            rows, _ = self.read_file(file_path)
            self.rows_read_total += len(rows)
            
            for row in rows:
                dt_str = row["datetime"]
                
                # Dedup: keep first occurrence
                if dt_str not in seen_datetimes:
                    seen_datetimes.add(dt_str)
                    collected_rows[dt_str] = row
                else:
                    self.duplicates_removed += 1
        
        self.rows_after_dedupe = len(collected_rows)
        
        # Sort by parsed datetime
        sorted_items = sorted(
            collected_rows.items(),
            key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S")
        )
        
        # Detect if sorting was applied
        original_order = list(collected_rows.keys())
        sorted_order = [dt for dt, _ in sorted_items]
        self.sorting_applied = original_order != sorted_order
        
        # Extract sorted rows
        rows = [row for _, row in sorted_items]
        
        if not rows:
            raise ValueError("No rows to write after processing")
        
        # Record first/last datetime
        self.first_datetime = rows[0]["datetime"]
        self.last_datetime = rows[-1]["datetime"]
        
        # Write raw output
        self._write_raw_csv(rows)
        
        # Write processed output if requested
        if self.out_processed:
            self._convert_to_replay(self.out_raw, self.out_processed)
        
        # Print audit
        self._print_audit_report()
    
    def _write_raw_csv(self, rows: List[Dict]):
        """Write stitched raw TwelveData CSV (semicolon-delimited)."""
        Path(self.out_raw).parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.out_raw, 'w', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=self.RAW_HEADER,
                delimiter=';',
                extrasaction='ignore'
            )
            writer.writeheader()
            writer.writerows(rows)
    
    def _convert_to_replay(self, raw_path: str, processed_path: str):
        """Convert raw CSV to replay format via converter module."""
        try:
            # Import converter
            sys.path.insert(0, str(Path(__file__).parent))
            from convert_twelvedata_to_replay_csv import convert_csv_wrapper
            
            # Call converter
            convert_csv_wrapper(raw_path, processed_path, self.default_volume)
        except ImportError as e:
            raise ImportError(
                f"Cannot import converter: {e}\n"
                f"Expected: scripts/convert_twelvedata_to_replay_csv.py"
            )
        except Exception as e:
            raise RuntimeError(f"Conversion failed: {e}")
    
    def _print_audit_report(self):
        """Print comprehensive audit report."""
        print("\n" + "=" * 70)
        print("MERGE AUDIT REPORT")
        print("=" * 70)
        print(f"inputs_count:          {len(self.input_files)}")
        print("inputs_resolved:")
        for f in self.input_files:
            print(f"  - {f}")
        print(f"rows_read_total:       {self.rows_read_total}")
        print(f"rows_after_dedupe:     {self.rows_after_dedupe}")
        print(f"duplicates_removed:    {self.duplicates_removed}")
        print(f"sorting_applied:       {self.sorting_applied}")
        print(f"first_datetime:        {self.first_datetime}")
        print(f"last_datetime:         {self.last_datetime}")
        print(f"out_raw:               {self.out_raw}")
        print(f"out_processed:         {self.out_processed or 'None'}")
        print(f"default_volume:        {self.default_volume}")
        print("=" * 70 + "\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Merge multiple TwelveData CSV chunks deterministically"
    )
    parser.add_argument(
        "--inputs",
        required=True,
        help='Comma-separated file paths and/or glob patterns (e.g., "file1.csv,data/raw/*.csv")'
    )
    parser.add_argument(
        "--out-raw",
        required=True,
        help="Output path for stitched raw TwelveData CSV (semicolon-delimited)"
    )
    parser.add_argument(
        "--out-processed",
        default=None,
        help="Optional output path for replay-ready CSV (comma-delimited, volume injected)"
    )
    parser.add_argument(
        "--default-volume",
        type=float,
        default=0.0,
        help="Default volume value for replay CSV (default: 0.0)"
    )
    
    args = parser.parse_args()
    
    try:
        merger = TwelveDataMerger(
            inputs=args.inputs,
            out_raw=args.out_raw,
            out_processed=args.out_processed,
            default_volume=args.default_volume,
        )
        merger.merge()
        print("✓ Merge successful")
        return 0
    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
