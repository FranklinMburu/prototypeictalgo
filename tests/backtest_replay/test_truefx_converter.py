"""
Tests for TrueFX tick to M1 candle converter.

Validates:
- Correct minute grouping (bucket floor)
- Correct OHLCV values
- Deterministic output (same input → identical output)
- Malformed line skipping
"""

import csv
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from scripts.convert_truefx_ticks_to_m1 import (
    M1Candle,
    parse_truefx_timestamp,
    get_minute_bucket,
    convert_truefx_to_m1,
)


class TestTimestampParsing:
    """Test TrueFX timestamp parsing."""

    def test_parse_valid_timestamp(self):
        """Verify correct parsing of valid TrueFX timestamp."""
        ts = parse_truefx_timestamp("20260101 18:02:25.204")
        assert ts is not None
        assert ts.year == 2026
        assert ts.month == 1
        assert ts.day == 1
        assert ts.hour == 18
        assert ts.minute == 2
        assert ts.second == 25
        assert ts.microsecond == 204000

    def test_parse_invalid_timestamp_returns_none(self):
        """Verify None returned for invalid timestamp."""
        assert parse_truefx_timestamp("invalid") is None
        assert parse_truefx_timestamp("2026-01-01 18:02:25") is None
        assert parse_truefx_timestamp("") is None

    def test_parse_edge_case_times(self):
        """Verify parsing of edge case times."""
        # Midnight
        ts = parse_truefx_timestamp("20260101 00:00:00.000")
        assert ts.hour == 0
        assert ts.minute == 0

        # 23:59:59
        ts = parse_truefx_timestamp("20261231 23:59:59.999")
        assert ts.hour == 23
        assert ts.minute == 59
        assert ts.second == 59


class TestMinuteBucket:
    """Test minute bucket floor calculation."""

    def test_bucket_floor(self):
        """Verify minute bucket is floored correctly."""
        dt = datetime(2026, 1, 1, 18, 2, 25, 204000)
        bucket = get_minute_bucket(dt)
        assert bucket == datetime(2026, 1, 1, 18, 2, 0, 0)

    def test_bucket_same_for_any_second_in_minute(self):
        """Verify all times in same minute map to same bucket."""
        base = datetime(2026, 1, 1, 18, 2, 0, 0)
        for sec in range(60):
            for usec in [0, 500000, 999999]:
                dt = datetime(2026, 1, 1, 18, 2, sec, usec)
                bucket = get_minute_bucket(dt)
                assert bucket == base


class TestM1Candle:
    """Test M1 candle aggregation."""

    def test_candle_initialization(self):
        """Verify candle initializes with first tick."""
        dt = datetime(2026, 1, 1, 18, 2, 0, 0)
        candle = M1Candle(dt, 1.17286)
        assert candle.timestamp == dt
        assert candle.open == 1.17286
        assert candle.high == 1.17286
        assert candle.low == 1.17286
        assert candle.close == 1.17286
        assert candle.volume == 1

    def test_candle_update_high(self):
        """Verify high is updated correctly."""
        candle = M1Candle(datetime(2026, 1, 1, 18, 2, 0, 0), 1.17286)
        candle.update(1.17290)
        assert candle.high == 1.17290
        assert candle.close == 1.17290
        assert candle.volume == 2

    def test_candle_update_low(self):
        """Verify low is updated correctly."""
        candle = M1Candle(datetime(2026, 1, 1, 18, 2, 0, 0), 1.17286)
        candle.update(1.17280)
        assert candle.low == 1.17280
        assert candle.close == 1.17280
        assert candle.volume == 2

    def test_candle_ohlc_sequence(self):
        """Verify OHLC with multiple updates."""
        candle = M1Candle(datetime(2026, 1, 1, 18, 2, 0, 0), 1.17286)
        candle.update(1.17290)  # high
        candle.update(1.17280)  # low
        candle.update(1.17288)  # close
        assert candle.open == 1.17286
        assert candle.high == 1.17290
        assert candle.low == 1.17280
        assert candle.close == 1.17288
        assert candle.volume == 4

    def test_candle_to_csv_row(self):
        """Verify CSV row format."""
        candle = M1Candle(datetime(2026, 1, 1, 18, 2, 0, 0), 1.17286)
        candle.update(1.17290)
        row = candle.to_csv_row()
        assert row[0] == "2026-01-01 18:02:00"
        assert row[1] == "1.17286"
        assert row[2] == "1.17290"
        assert row[3] == "1.17286"
        assert row[4] == "1.17290"
        assert row[5] == 2


class TestConverterBasic:
    """Test basic conversion functionality."""

    def test_convert_single_minute(self):
        """Verify conversion of ticks within single minute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "ticks.csv"
            output_file = Path(tmpdir) / "candles.csv"

            # Write sample ticks (all in same minute: 18:02)
            with open(input_file, "w") as f:
                f.write("EUR/USD,20260101 18:02:00.100,1.17286,1.17567\n")
                f.write("EUR/USD,20260101 18:02:00.200,1.17290,1.17571\n")
                f.write("EUR/USD,20260101 18:02:00.300,1.17280,1.17561\n")

            convert_truefx_to_m1(input_file, output_file, verbose=False)

            # Verify output
            with open(output_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            row = rows[0]
            assert row["timestamp"] == "2026-01-01 18:02:00"
            assert float(row["open"]) == 1.17286
            assert float(row["high"]) == 1.17290
            assert float(row["low"]) == 1.17280
            assert float(row["close"]) == 1.17280
            assert int(row["volume"]) == 3

    def test_convert_multiple_minutes(self):
        """Verify conversion across multiple minutes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "ticks.csv"
            output_file = Path(tmpdir) / "candles.csv"

            # Write ticks spanning 3 minutes
            with open(input_file, "w") as f:
                # Minute 18:02
                f.write("EUR/USD,20260101 18:02:00.100,1.17286,1.17567\n")
                f.write("EUR/USD,20260101 18:02:00.200,1.17290,1.17571\n")
                # Minute 18:03
                f.write("EUR/USD,20260101 18:03:00.100,1.17300,1.17581\n")
                f.write("EUR/USD,20260101 18:03:00.200,1.17295,1.17576\n")
                # Minute 18:04
                f.write("EUR/USD,20260101 18:04:00.100,1.17310,1.17591\n")

            convert_truefx_to_m1(input_file, output_file, verbose=False)

            # Verify output
            with open(output_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 3
            assert rows[0]["timestamp"] == "2026-01-01 18:02:00"
            assert rows[1]["timestamp"] == "2026-01-01 18:03:00"
            assert rows[2]["timestamp"] == "2026-01-01 18:04:00"
            assert int(rows[0]["volume"]) == 2
            assert int(rows[1]["volume"]) == 2
            assert int(rows[2]["volume"]) == 1

    def test_convert_skips_malformed_lines(self):
        """Verify malformed lines are skipped safely."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "ticks.csv"
            output_file = Path(tmpdir) / "candles.csv"

            # Write mix of valid and malformed lines
            with open(input_file, "w") as f:
                f.write("EUR/USD,20260101 18:02:00.100,1.17286,1.17567\n")
                f.write("INVALID LINE\n")  # Malformed
                f.write("EUR/USD,invalid_timestamp,1.17290,1.17571\n")  # Bad timestamp
                f.write("EUR/USD,20260101 18:02:00.200,not_a_number,1.17571\n")  # Bad price
                f.write("EUR/USD,20260101 18:02:00.300,1.17280,1.17561\n")  # Valid

            convert_truefx_to_m1(input_file, output_file, verbose=False)

            # Verify output has only valid candles
            with open(output_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert int(rows[0]["volume"]) == 2  # 2 valid ticks

    def test_convert_deterministic(self):
        """Verify same input produces identical output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "ticks.csv"
            output_file1 = Path(tmpdir) / "candles1.csv"
            output_file2 = Path(tmpdir) / "candles2.csv"

            # Write sample ticks
            with open(input_file, "w") as f:
                f.write("EUR/USD,20260101 18:02:00.100,1.17286,1.17567\n")
                f.write("EUR/USD,20260101 18:02:00.200,1.17290,1.17571\n")
                f.write("EUR/USD,20260101 18:02:00.300,1.17280,1.17561\n")

            # Convert twice
            convert_truefx_to_m1(input_file, output_file1, verbose=False)
            convert_truefx_to_m1(input_file, output_file2, verbose=False)

            # Verify identical content
            with open(output_file1) as f:
                content1 = f.read()
            with open(output_file2) as f:
                content2 = f.read()

            assert content1 == content2

    def test_convert_creates_output_directory(self):
        """Verify output directory is created if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "ticks.csv"
            # Nested output directory that doesn't exist
            output_file = Path(tmpdir) / "nested" / "deep" / "candles.csv"

            # Write sample ticks
            with open(input_file, "w") as f:
                f.write("EUR/USD,20260101 18:02:00.100,1.17286,1.17567\n")

            # Verify output directory doesn't exist yet
            assert not output_file.parent.exists()

            convert_truefx_to_m1(input_file, output_file, verbose=False)

            # Verify directory was created and file exists
            assert output_file.parent.exists()
            assert output_file.exists()

    def test_convert_output_sorted_by_timestamp(self):
        """Verify output candles are sorted by timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "ticks.csv"
            output_file = Path(tmpdir) / "candles.csv"

            # Write ticks out of chronological order
            with open(input_file, "w") as f:
                f.write("EUR/USD,20260101 18:04:00.100,1.17310,1.17591\n")
                f.write("EUR/USD,20260101 18:02:00.100,1.17286,1.17567\n")
                f.write("EUR/USD,20260101 18:03:00.100,1.17300,1.17581\n")

            convert_truefx_to_m1(input_file, output_file, verbose=False)

            # Verify output is sorted
            with open(output_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 3
            assert rows[0]["timestamp"] == "2026-01-01 18:02:00"
            assert rows[1]["timestamp"] == "2026-01-01 18:03:00"
            assert rows[2]["timestamp"] == "2026-01-01 18:04:00"

    def test_convert_empty_file(self):
        """Verify empty input produces empty output (only header)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "ticks.csv"
            output_file = Path(tmpdir) / "candles.csv"

            # Write empty file
            input_file.write_text("")

            convert_truefx_to_m1(input_file, output_file, verbose=False)

            # Verify output has only header
            with open(output_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 0


class TestConverterEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_large_bid_spread(self):
        """Verify correct OHLC with large price movements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = Path(tmpdir) / "ticks.csv"
            output_file = Path(tmpdir) / "candles.csv"

            # Write ticks with large spread
            with open(input_file, "w") as f:
                f.write("EUR/USD,20260101 18:02:00.100,1.17000,1.17567\n")
                f.write("EUR/USD,20260101 18:02:00.200,1.17500,1.17571\n")
                f.write("EUR/USD,20260101 18:02:00.300,1.17100,1.17561\n")

            convert_truefx_to_m1(input_file, output_file, verbose=False)

            with open(output_file) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            row = rows[0]
            assert float(row["open"]) == 1.17000
            assert float(row["high"]) == 1.17500
            assert float(row["low"]) == 1.17000  # Minimum of the three bids
            assert float(row["close"]) == 1.17100  # Last bid
