"""
Tests for candle loading and validation.
"""

import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backtest_replay.candle_loader import Candle, CandleLoader


class TestCandleLoader:
    """Test candle loading from CSV."""

    def test_load_csv_basic(self):
        """Test loading valid CSV."""
        csv_content = """timestamp,open,high,low,close,volume
2024-01-01 10:00:00,1.0850,1.0880,1.0840,1.0865,1000000
2024-01-01 11:00:00,1.0865,1.0895,1.0860,1.0875,1100000
2024-01-01 12:00:00,1.0875,1.0910,1.0870,1.0905,950000
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            candles = CandleLoader.load_csv(f.name)

            assert len(candles) == 3
            assert candles[0].open == 1.0850
            assert candles[0].high == 1.0880
            assert candles[0].close == 1.0865
            assert candles[0].volume == 1000000
            assert candles[0].timestamp.tzinfo == timezone.utc

            Path(f.name).unlink()

    def test_candles_sorted_ascending(self):
        """Test that candles are sorted by timestamp."""
        csv_content = """timestamp,open,high,low,close
2024-01-01 12:00:00,1.0875,1.0910,1.0870,1.0905
2024-01-01 10:00:00,1.0850,1.0880,1.0840,1.0865
2024-01-01 11:00:00,1.0865,1.0895,1.0860,1.0875
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            candles = CandleLoader.load_csv(f.name)

            assert len(candles) == 3
            # Check sorted in ascending order
            assert candles[0].open == 1.0850
            assert candles[1].open == 1.0865
            assert candles[2].open == 1.0875

            Path(f.name).unlink()

    def test_missing_required_column(self):
        """Test error on missing required column."""
        csv_content = """timestamp,open,high,low
2024-01-01 10:00:00,1.0850,1.0880,1.0840
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            with pytest.raises(ValueError, match="Missing required columns"):
                CandleLoader.load_csv(f.name)

            Path(f.name).unlink()

    def test_file_not_found(self):
        """Test error on missing file."""
        with pytest.raises(FileNotFoundError):
            CandleLoader.load_csv("/nonexistent/path/to/file.csv")

    def test_empty_csv(self):
        """Test error on empty CSV."""
        csv_content = "timestamp,open,high,low,close\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            with pytest.raises(ValueError, match="No valid candles"):
                CandleLoader.load_csv(f.name)

            Path(f.name).unlink()

    def test_optional_volume_column(self):
        """Test loading CSV without volume column."""
        csv_content = """timestamp,open,high,low,close
2024-01-01 10:00:00,1.0850,1.0880,1.0840,1.0865
2024-01-01 11:00:00,1.0865,1.0895,1.0860,1.0875
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            f.write(csv_content)
            f.flush()

            candles = CandleLoader.load_csv(f.name)

            assert len(candles) == 2
            assert candles[0].volume is None

            Path(f.name).unlink()

    def test_candle_comparison(self):
        """Test Candle comparison for sorting."""
        ts1 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)

        c1 = Candle(ts1, 1.0850, 1.0880, 1.0840, 1.0865)
        c2 = Candle(ts2, 1.0865, 1.0895, 1.0860, 1.0875)

        assert c1 < c2
        assert not (c2 < c1)
