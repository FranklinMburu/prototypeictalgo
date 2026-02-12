"""
Load OHLCV candles from CSV files.

Handles:
- Timestamp parsing as UTC-aware datetime
- Candle sorting (ascending by timestamp)
- Required columns: timestamp, open, high, low, close
- Optional columns: volume
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class Candle:
    """OHLCV candle data with UTC-aware timestamp."""
    timestamp: datetime  # UTC-aware
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None

    def __lt__(self, other):
        """For sorting by timestamp."""
        return self.timestamp < other.timestamp


class CandleLoader:
    """Load and validate OHLCV candles from CSV."""

    REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close"}
    OPTIONAL_COLUMNS = {"volume"}

    @staticmethod
    def load_csv(
        csv_path: str,
        timestamp_fmt: str = "%Y-%m-%d %H:%M:%S",
    ) -> List[Candle]:
        """
        Load candles from CSV file.

        Args:
            csv_path: Path to CSV file
            timestamp_fmt: Timestamp format string for parsing

        Returns:
            List of Candle objects, sorted ascending by timestamp

        Raises:
            FileNotFoundError: If CSV not found
            ValueError: If required columns missing or data malformed
        """
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        candles = []
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV is empty")

            # Validate columns
            fieldnames = set(reader.fieldnames)
            missing = CandleLoader.REQUIRED_COLUMNS - fieldnames
            if missing:
                raise ValueError(
                    f"Missing required columns: {missing}. "
                    f"Found: {fieldnames}"
                )

            for row_num, row in enumerate(reader, start=2):  # start=2 (after header)
                try:
                    # Parse timestamp as UTC-aware
                    ts_str = row["timestamp"].strip()
                    ts = datetime.strptime(ts_str, timestamp_fmt)
                    # Make UTC-aware if naive
                    if ts.tzinfo is None:
                        from datetime import timezone
                        ts = ts.replace(tzinfo=timezone.utc)

                    candle = Candle(
                        timestamp=ts,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0)) if "volume" in row else None,
                    )
                    candles.append(candle)
                except (KeyError, ValueError) as e:
                    raise ValueError(
                        f"Error parsing row {row_num}: {e}\n"
                        f"Row data: {row}"
                    )

        # Sort ascending by timestamp
        candles.sort()

        if not candles:
            raise ValueError("No valid candles loaded from CSV")

        return candles
