"""
Tests for signal loading and validation.
"""

import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from backtest_replay.signal_loader import ReplaySignal, SignalLoader


class TestSignalLoader:
    """Test signal loading from JSONL."""

    def test_load_jsonl_basic(self):
        """Test loading valid JSONL."""
        jsonl_content = """{"signal_id": "sig_001", "timestamp": "2024-01-01 10:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "long", "signal_type": "bearish_bos", "entry": 1.0850, "sl": 1.0820, "tp": 1.0900, "session": "london"}
{"signal_id": "sig_002", "timestamp": "2024-01-01 11:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "short", "signal_type": "bullish_choch", "entry": 1.0875, "sl": 1.0900, "tp": 1.0800, "session": "london"}
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(jsonl_content)
            f.flush()

            signals = SignalLoader.load_jsonl(f.name)

            assert len(signals) == 2
            assert signals[0].signal_id == "sig_001"
            assert signals[0].symbol == "EURUSD"
            assert signals[0].direction == "long"
            assert signals[0].entry == 1.0850
            assert signals[0].timestamp.tzinfo == timezone.utc

            Path(f.name).unlink()

    def test_signals_sorted_ascending(self):
        """Test that signals are sorted by timestamp."""
        jsonl_content = """{"signal_id": "sig_002", "timestamp": "2024-01-01 11:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "long", "signal_type": "bearish_bos", "entry": 1.0875, "sl": 1.0850, "tp": 1.0920}
{"signal_id": "sig_001", "timestamp": "2024-01-01 10:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "long", "signal_type": "bearish_bos", "entry": 1.0850, "sl": 1.0820, "tp": 1.0900}
{"signal_id": "sig_003", "timestamp": "2024-01-01 12:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "long", "signal_type": "bearish_bos", "entry": 1.0890, "sl": 1.0860, "tp": 1.0940}
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(jsonl_content)
            f.flush()

            signals = SignalLoader.load_jsonl(f.name)

            assert len(signals) == 3
            # Check sorted in ascending order by timestamp
            assert signals[0].signal_id == "sig_001"
            assert signals[1].signal_id == "sig_002"
            assert signals[2].signal_id == "sig_003"

            Path(f.name).unlink()

    def test_direction_lowercased(self):
        """Test that direction is lowercased."""
        jsonl_content = """{"signal_id": "sig_001", "timestamp": "2024-01-01 10:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "LONG", "signal_type": "bearish_bos", "entry": 1.0850, "sl": 1.0820, "tp": 1.0900}
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(jsonl_content)
            f.flush()

            signals = SignalLoader.load_jsonl(f.name)

            assert signals[0].direction == "long"

            Path(f.name).unlink()

    def test_file_not_found(self):
        """Test error on missing file."""
        with pytest.raises(FileNotFoundError):
            SignalLoader.load_jsonl("/nonexistent/path/to/file.jsonl")

    def test_empty_jsonl(self):
        """Test error on empty JSONL."""
        jsonl_content = ""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(jsonl_content)
            f.flush()

            with pytest.raises(ValueError, match="No valid signals"):
                SignalLoader.load_jsonl(f.name)

            Path(f.name).unlink()

    def test_malformed_json(self):
        """Test error on malformed JSON."""
        jsonl_content = """{"signal_id": "sig_001", "timestamp": "2024-01-01 10:00:00"}
{invalid json line}
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(jsonl_content)
            f.flush()

            with pytest.raises(ValueError, match="Error parsing JSONL line"):
                SignalLoader.load_jsonl(f.name)

            Path(f.name).unlink()

    def test_skip_blank_lines(self):
        """Test that blank lines are skipped."""
        jsonl_content = """{"signal_id": "sig_001", "timestamp": "2024-01-01 10:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "long", "signal_type": "bearish_bos", "entry": 1.0850, "sl": 1.0820, "tp": 1.0900}

{"signal_id": "sig_002", "timestamp": "2024-01-01 11:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "long", "signal_type": "bearish_bos", "entry": 1.0875, "sl": 1.0850, "tp": 1.0920}
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(jsonl_content)
            f.flush()

            signals = SignalLoader.load_jsonl(f.name)

            assert len(signals) == 2

            Path(f.name).unlink()

    def test_optional_fields(self):
        """Test that optional fields have defaults."""
        jsonl_content = """{"signal_id": "sig_001", "timestamp": "2024-01-01 10:00:00", "symbol": "EURUSD", "timeframe": "1h", "direction": "long", "signal_type": "bearish_bos", "entry": 1.0850, "sl": 1.0820, "tp": 1.0900}
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write(jsonl_content)
            f.flush()

            signals = SignalLoader.load_jsonl(f.name)

            assert signals[0].session is None
            assert signals[0].meta == {}

            Path(f.name).unlink()

    def test_signal_comparison(self):
        """Test ReplaySignal comparison for sorting."""
        ts1 = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)

        sig1 = ReplaySignal(
            "sig_001", ts1, "EURUSD", "1h", "long", "bearish_bos", 1.0850, 1.0820, 1.0900
        )
        sig2 = ReplaySignal(
            "sig_002", ts2, "EURUSD", "1h", "long", "bearish_bos", 1.0875, 1.0850, 1.0920
        )

        assert sig1 < sig2
        assert not (sig2 < sig1)
