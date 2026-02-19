#!/usr/bin/env python3
"""
Convert TwelveData CSV to Replay Engine M1 Candle Format

Transforms TwelveData OHLCV CSV into the candle CSV schema required by the
backtest replay engine, handling column renaming and optional precision adjustment.

Input Format (from TwelveData):
  datetime,open,high,low,close,volume
  (or with semicolon delimiter)

Output Format (replay engine standard from candle_loader.py):
  timestamp,open,high,low,close,volume

Deterministic: same input → identical output, stable sort by timestamp.

Usage:
    python scripts/convert_twelvedata_to_m1.py \
        --input data/raw/twelvedata/XAUUSD-merged.csv \
        --output data/processed/XAUUSD/M1/XAUUSD-2026-01_02-M1.csv
"""

import csv
import sys
from pathlib import Path
from datetime import datetime
from argparse import ArgumentParser


class TwelveDataConverter:
    """Convert TwelveData CSV to replay engine candle format."""
    
    # Possible datetime column names from different data sources
    DATETIME_COLUMNS = ["datetime", "timestamp", "time"]
    
    # Required OHLCV columns
    OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
    
    @staticmethod
    def detect_delimiter(csv_path: str) -> str:
        """Detect CSV delimiter (comma or semicolon).
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Delimiter character (',' or ';')
        """
        with open(csv_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()
        
        # Count delimiters
        comma_count = first_line.count(',')
        semicolon_count = first_line.count(';')
        
        if semicolon_count > comma_count:
            return ';'
        return ','
    
    @staticmethod
    def detect_datetime_column(fieldnames: list) -> str:
        """Detect datetime column name from header.
        
        Args:
            fieldnames: CSV header field names
            
        Returns:
            Name of datetime column
            
        Raises:
            ValueError: If no datetime column found
        """
        fieldnames_lower = [f.lower().strip() for f in fieldnames]
        
        for dt_col in TwelveDataConverter.DATETIME_COLUMNS:
            for i, fname in enumerate(fieldnames_lower):
                if dt_col in fname:
                    return fieldnames[i]
        
        raise ValueError(
            f"No datetime column found. Available: {fieldnames}"
        )
    
    @staticmethod
    def validate_schema(fieldnames: list) -> tuple:
        """Validate that input has required columns.
        
        Args:
            fieldnames: CSV header field names
            
        Returns:
            Tuple of (datetime_col, ohlcv_cols_dict)
            
        Raises:
            ValueError: If required columns missing
        """
        # Detect datetime column
        dt_col = TwelveDataConverter.detect_datetime_column(fieldnames)
        
        # Check for OHLCV columns (case-insensitive)
        fieldnames_lower = {f.lower().strip(): f for f in fieldnames}
        ohlcv_cols = {}
        
        for col in TwelveDataConverter.OHLCV_COLUMNS:
            if col.lower() not in fieldnames_lower:
                raise ValueError(
                    f"Missing required column: {col}. "
                    f"Available: {fieldnames}"
                )
            ohlcv_cols[col] = fieldnames_lower[col.lower()]
        
        return dt_col, ohlcv_cols
    
    @staticmethod
    def parse_row(row: dict, dt_col: str, ohlcv_cols: dict) -> dict:
        """Parse a TwelveData row into replay format.
        
        Args:
            row: CSV row as dict
            dt_col: Datetime column name
            ohlcv_cols: Dict mapping standard names to actual column names
            
        Returns:
            Dict with keys: timestamp, open, high, low, close, volume
            
        Raises:
            ValueError: If parsing fails
        """
        try:
            # Parse datetime
            dt_str = row[dt_col].strip()
            # Try to parse (flexible format handling)
            try:
                ts = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                ts = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
            
            # Convert back to standard format
            timestamp = ts.strftime("%Y-%m-%d %H:%M:%S")
            
            # Parse OHLCV
            return {
                "timestamp": timestamp,
                "open": float(row[ohlcv_cols["open"]]),
                "high": float(row[ohlcv_cols["high"]]),
                "low": float(row[ohlcv_cols["low"]]),
                "close": float(row[ohlcv_cols["close"]]),
                "volume": int(float(row[ohlcv_cols["volume"]])),
            }
        except (KeyError, ValueError) as e:
            raise ValueError(f"Cannot parse row: {e}\nRow: {row}")
    
    @staticmethod
    def convert(
        input_path: str,
        output_path: str,
        verbose: bool = True,
    ) -> None:
        """Convert TwelveData CSV to replay engine format.
        
        Args:
            input_path: Input CSV file path
            output_path: Output CSV file path
            verbose: Print progress if True
            
        Raises:
            FileNotFoundError: If input not found
            ValueError: If schema invalid or parsing fails
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Detect delimiter
        delimiter = TwelveDataConverter.detect_delimiter(str(input_path))
        if verbose:
            print(f"Detected delimiter: '{delimiter}'")
        
        # Load and validate
        if verbose:
            print(f"Reading: {input_path}")
        
        converted_rows = []
        row_count = 0
        error_count = 0
        
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=delimiter)
                
                # Validate schema
                if reader.fieldnames is None:
                    raise ValueError("Input CSV is empty")
                
                dt_col, ohlcv_cols = TwelveDataConverter.validate_schema(
                    reader.fieldnames
                )
                
                if verbose:
                    print(f"✓ Datetime column: {dt_col}")
                    print(f"✓ OHLCV columns: {ohlcv_cols}")
                
                # Parse rows
                for row_num, row in enumerate(reader, start=2):
                    row_count += 1
                    try:
                        converted_row = TwelveDataConverter.parse_row(
                            row, dt_col, ohlcv_cols
                        )
                        converted_rows.append(converted_row)
                    except ValueError as e:
                        if verbose:
                            print(f"  Warning: Row {row_num} skipped: {e}")
                        error_count += 1
        
        except Exception as e:
            print(f"✗ Error reading input: {e}")
            sys.exit(1)
        
        if not converted_rows:
            print(f"✗ No valid rows to convert")
            sys.exit(1)
        
        # Sort by timestamp (deterministic, should already be sorted)
        converted_rows.sort(key=lambda r: r["timestamp"])
        
        # Write output
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["timestamp", "open", "high", "low", "close", "volume"]
                )
                writer.writeheader()
                writer.writerows(converted_rows)
        
        except Exception as e:
            print(f"✗ Error writing output: {e}")
            sys.exit(1)
        
        # Summary
        if verbose:
            print(f"\n{'='*70}")
            print(f"CONVERSION SUMMARY")
            print(f"{'='*70}")
            print(f"Input rows: {row_count}")
            print(f"Errors/skipped: {error_count}")
            print(f"Output rows: {len(converted_rows)}")
            
            if converted_rows:
                print(f"Timestamp range:")
                print(f"  First: {converted_rows[0]['timestamp']}")
                print(f"  Last:  {converted_rows[-1]['timestamp']}")
            
            print(f"Output: {output_path}")
            print(f"✓ Schema validated for replay engine")


def main() -> None:
    """CLI entry point."""
    parser = ArgumentParser(
        description="Convert TwelveData CSV to replay engine candle format"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input TwelveData CSV file path"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output replay-ready M1 CSV file path"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )
    
    args = parser.parse_args()
    
    try:
        TwelveDataConverter.convert(
            args.input,
            args.output,
            verbose=not args.quiet
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"✗ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
