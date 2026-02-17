"""
TrueFX Tick to M1 Candle Converter

Converts raw TrueFX tick-by-tick data into 1-minute OHLCV candles.

Input format (CSV, no header):
  EUR/USD,20260101 18:02:25.204,1.17286,1.17567
  Columns: symbol,timestamp,bid,ask

Output format (CSV, with header):
  timestamp,open,high,low,close,volume
  2026-01-01 18:02:00,1.17286,1.17290,1.17280,1.17288,42

- Deterministic: same input → identical output
- Efficient: streams input line-by-line
- Safe: skips malformed lines (no crash)
- Uses BID price only for OHLC
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class M1Candle:
    """Single 1-minute candle."""

    def __init__(self, timestamp: datetime, open_price: float):
        """Initialize candle with first tick's bid price.
        
        Args:
            timestamp: Candle bucket timestamp (minute floor, UTC)
            open_price: First bid price in the minute
        """
        self.timestamp = timestamp
        self.open = open_price
        self.high = open_price
        self.low = open_price
        self.close = open_price
        self.volume = 1

    def update(self, bid: float) -> None:
        """Update candle with new tick.
        
        Args:
            bid: Bid price from the tick
        """
        self.high = max(self.high, bid)
        self.low = min(self.low, bid)
        self.close = bid
        self.volume += 1

    def to_csv_row(self) -> Tuple[str, str, str, str, str, int]:
        """Convert to CSV row tuple.
        
        Returns:
            Tuple: (timestamp_str, open, high, low, close, volume)
        """
        timestamp_str = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        # Format prices with 5 decimal places (standard FX precision)
        return (
            timestamp_str,
            f"{self.open:.5f}",
            f"{self.high:.5f}",
            f"{self.low:.5f}",
            f"{self.close:.5f}",
            self.volume
        )


def parse_truefx_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse TrueFX timestamp format: YYYYMMDD HH:MM:SS.mmm (UTC).
    
    Args:
        timestamp_str: Raw timestamp string from TrueFX file
    
    Returns:
        datetime object (UTC), or None if parsing fails
    """
    try:
        # Format: 20260101 18:02:25.204
        return datetime.strptime(timestamp_str, "%Y%m%d %H:%M:%S.%f")
    except ValueError:
        return None


def get_minute_bucket(dt: datetime) -> datetime:
    """Get the minute bucket floor (YYYY-MM-DD HH:MM:00).
    
    Args:
        dt: Any datetime within the minute
    
    Returns:
        datetime with second and microsecond set to 0
    """
    return dt.replace(second=0, microsecond=0)


def convert_truefx_to_m1(
    input_path: Path,
    output_path: Path,
    verbose: bool = True,
) -> None:
    """Convert TrueFX ticks to M1 candles.
    
    Streams input file line-by-line for memory efficiency.
    
    Args:
        input_path: Path to input TrueFX CSV (no header)
        output_path: Path to output M1 candles CSV (with header)
        verbose: Print processing stats if True
    """
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    candles: Dict[datetime, M1Candle] = {}
    lines_read = 0
    lines_skipped = 0
    
    try:
        with open(input_path, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                lines_read += 1
                
                # Parse row: symbol, timestamp, bid, ask
                if len(row) < 4:
                    lines_skipped += 1
                    continue
                
                symbol, timestamp_str, bid_str, ask_str = row[:4]
                
                # Parse timestamp
                dt = parse_truefx_timestamp(timestamp_str)
                if dt is None:
                    lines_skipped += 1
                    continue
                
                # Parse bid price
                try:
                    bid = float(bid_str)
                except ValueError:
                    lines_skipped += 1
                    continue
                
                # Get minute bucket
                bucket = get_minute_bucket(dt)
                
                # Update or create candle
                if bucket not in candles:
                    candles[bucket] = M1Candle(bucket, bid)
                else:
                    candles[bucket].update(bid)
    
    except Exception as e:
        raise IOError(f"Error reading input file {input_path}: {e}")
    
    # Write output in sorted order (deterministic)
    sorted_buckets = sorted(candles.keys())
    
    try:
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
            # Write candles
            for bucket in sorted_buckets:
                candle = candles[bucket]
                writer.writerow(candle.to_csv_row())
    
    except Exception as e:
        raise IOError(f"Error writing output file {output_path}: {e}")
    
    if verbose:
        print(f"Processed: {lines_read} lines")
        print(f"Skipped:   {lines_skipped} lines")
        print(f"Candles:   {len(candles)} M1 candles")
        print(f"Output:    {output_path}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Convert TrueFX tick data to 1-minute OHLCV candles"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to input TrueFX CSV file (no header)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output M1 candles CSV file",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    
    args = parser.parse_args()
    convert_truefx_to_m1(args.input, args.output, verbose=not args.quiet)


if __name__ == "__main__":
    main()
