"""
Tests for replay pipeline runner.

End-to-end pipeline tests with fixture candles.
Verifies that runner generates all output files and that structure is valid.
"""

import pytest
import tempfile
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

# Import test utilities
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.export_signals_to_jsonl import write_signals_jsonl
from backtest_replay.signal_loader import SignalLoader


def create_test_candle_csv(tmpdir: str, num_candles: int = 100) -> str:
    """Create a test candle CSV file.
    
    Args:
        tmpdir: Temporary directory
        num_candles: Number of candles to generate
    
    Returns:
        Path to created CSV file
    """
    from datetime import timedelta
    
    csv_path = Path(tmpdir) / "test_candles.csv"
    
    with open(csv_path, 'w') as f:
        f.write("timestamp,open,high,low,close,volume\n")
        for i in range(num_candles):
            ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            ts = ts + timedelta(minutes=i)
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
            
            base_price = 1.17200 + (i % 100) * 0.0001
            f.write(f"{ts_str},{base_price:.5f},{base_price + 0.0002:.5f},{base_price - 0.0001:.5f},{base_price + 0.0001:.5f},1\n")
    
    return str(csv_path)


def create_test_signals_jsonl(tmpdir: str, num_signals: int = 10) -> str:
    """Create a test signals JSONL file.
    
    Args:
        tmpdir: Temporary directory
        num_signals: Number of signals to generate
    
    Returns:
        Path to created JSONL file
    """
    from datetime import timedelta
    
    signals = []
    for i in range(num_signals):
        ts = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        ts = ts + timedelta(minutes=i * 10)
        
        signal = {
            "signal_id": f"test_{i:03d}",
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": "EURUSD",
            "timeframe": "1m",
            "direction": "long" if i % 2 == 0 else "short",
            "signal_type": "bullish_choch" if i % 2 == 0 else "bearish_bos",
            "entry": 1.17250 + (i % 5) * 0.0001,
            "sl": 1.17200 + (i % 5) * 0.0001,
            "tp": 1.17300 + (i % 5) * 0.0001,
            "session": "london",
            "meta": {},
        }
        signals.append(signal)
    
    jsonl_path = Path(tmpdir) / "test_signals.jsonl"
    write_signals_jsonl(signals, str(jsonl_path))
    return str(jsonl_path)


class TestPipelineRunner:
    """Test the replay pipeline runner."""
    
    def test_pipeline_creates_all_outputs(self):
        """Test that pipeline runner creates all expected output files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test data
            candles_csv = create_test_candle_csv(tmpdir, num_candles=50)
            signals_jsonl = create_test_signals_jsonl(tmpdir, num_signals=5)
            
            # Verify inputs exist
            assert Path(candles_csv).exists()
            assert Path(signals_jsonl).exists()
            
            # Load to verify schema is correct
            candle_lines = []
            with open(candles_csv, 'r') as f:
                for i, line in enumerate(f):
                    if i > 0:  # Skip header
                        candle_lines.append(line)
            
            assert len(candle_lines) >= 50  # At least 50 candles
            
            # Load signals
            signals = SignalLoader.load_jsonl(signals_jsonl)
            assert len(signals) == 5
            assert all(hasattr(s, 'signal_id') for s in signals)
            assert all(hasattr(s, 'timestamp') for s in signals)
            assert all(hasattr(s, 'entry') for s in signals)
    
    def test_signal_exporter_creates_valid_jsonl(self):
        """Test that signal exporter creates valid JSONL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test candles
            candles_csv = create_test_candle_csv(tmpdir, num_candles=100)
            signals_jsonl = Path(tmpdir) / "signals.jsonl"
            
            # Run exporter
            result = subprocess.run(
                [
                    "python",
                    "scripts/export_signals_to_jsonl.py",
                    "--candles-csv", candles_csv,
                    "--output", str(signals_jsonl),
                    "--stride", "10",
                    "--max-signals", "5",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            
            # Should succeed
            assert result.returncode == 0, f"Exporter failed: {result.stderr}"
            
            # Output file should exist
            assert signals_jsonl.exists()
            
            # Load and validate signals
            signals = SignalLoader.load_jsonl(str(signals_jsonl))
            assert len(signals) == 5
            
            # Check schema
            for sig in signals:
                assert sig.signal_id.startswith("syn_")
                assert sig.symbol == "EURUSD"
                assert sig.timeframe == "1m"
                assert sig.direction in ["long", "short"]
                assert sig.signal_type in ["bullish_choch", "bearish_bos"]
                assert sig.entry > 0
                assert sig.sl > 0
                assert sig.tp > 0
                assert sig.session in ["asian", "london", "new_york"]
    
    def test_signal_exporter_determinism(self):
        """Test that exporter produces identical output on same input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test candles
            candles_csv = create_test_candle_csv(tmpdir, num_candles=100)
            signals1_jsonl = Path(tmpdir) / "signals1.jsonl"
            signals2_jsonl = Path(tmpdir) / "signals2.jsonl"
            
            # Run exporter twice
            for signals_file in [signals1_jsonl, signals2_jsonl]:
                result = subprocess.run(
                    [
                        "python",
                        "scripts/export_signals_to_jsonl.py",
                        "--candles-csv", candles_csv,
                        "--output", str(signals_file),
                        "--stride", "20",
                        "--max-signals", "3",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=Path(__file__).parent.parent.parent,
                )
                assert result.returncode == 0
            
            # Load both
            with open(signals1_jsonl, 'r') as f:
                content1 = f.read()
            with open(signals2_jsonl, 'r') as f:
                content2 = f.read()
            
            # Should be identical
            assert content1 == content2
    
    def test_exporter_respects_stride_and_max_signals(self):
        """Test that exporter respects stride and max_signals parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 200 candles
            candles_csv = create_test_candle_csv(tmpdir, num_candles=200)
            signals_jsonl = Path(tmpdir) / "signals.jsonl"
            
            # Run with stride=50, max=3 (should get 3 signals even though stride could produce more)
            result = subprocess.run(
                [
                    "python",
                    "scripts/export_signals_to_jsonl.py",
                    "--candles-csv", candles_csv,
                    "--output", str(signals_jsonl),
                    "--stride", "50",
                    "--max-signals", "3",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            
            assert result.returncode == 0
            
            # Load signals
            signals = SignalLoader.load_jsonl(str(signals_jsonl))
            
            # Should have exactly 3 signals
            assert len(signals) == 3
    
    def test_signals_have_required_fields(self):
        """Test that all generated signals have required JSONL fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles_csv = create_test_candle_csv(tmpdir, num_candles=100)
            signals_jsonl = Path(tmpdir) / "signals.jsonl"
            
            result = subprocess.run(
                [
                    "python",
                    "scripts/export_signals_to_jsonl.py",
                    "--candles-csv", candles_csv,
                    "--output", str(signals_jsonl),
                    "--stride", "10",
                    "--max-signals", "5",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            
            assert result.returncode == 0
            
            # Read raw JSONL
            with open(signals_jsonl, 'r') as f:
                for line in f:
                    if line.strip():
                        sig = json.loads(line)
                        
                        # Check required fields
                        assert 'signal_id' in sig
                        assert 'timestamp' in sig
                        assert 'symbol' in sig
                        assert 'timeframe' in sig
                        assert 'direction' in sig
                        assert 'signal_type' in sig
                        assert 'entry' in sig
                        assert 'sl' in sig
                        assert 'tp' in sig
    
    def test_timestamps_are_properly_formatted(self):
        """Test that signal timestamps match M1 candle format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles_csv = create_test_candle_csv(tmpdir, num_candles=100)
            signals_jsonl = Path(tmpdir) / "signals.jsonl"
            
            result = subprocess.run(
                [
                    "python",
                    "scripts/export_signals_to_jsonl.py",
                    "--candles-csv", candles_csv,
                    "--output", str(signals_jsonl),
                    "--stride", "10",
                    "--max-signals", "5",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            
            assert result.returncode == 0
            
            # Read raw JSONL
            with open(signals_jsonl, 'r') as f:
                for line in f:
                    if line.strip():
                        sig = json.loads(line)
                        
                        # Timestamp should be in format YYYY-MM-DD HH:MM:SS
                        ts_str = sig['timestamp']
                        try:
                            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                            assert ts is not None
                        except ValueError as e:
                            pytest.fail(f"Invalid timestamp format: {ts_str}, error: {e}")


class TestExportedSignalsSchema:
    """Test schema of exported signals."""
    
    def test_direction_values_valid(self):
        """Test that direction is either 'long' or 'short'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles_csv = create_test_candle_csv(tmpdir, num_candles=100)
            signals_jsonl = Path(tmpdir) / "signals.jsonl"
            
            result = subprocess.run(
                [
                    "python",
                    "scripts/export_signals_to_jsonl.py",
                    "--candles-csv", candles_csv,
                    "--output", str(signals_jsonl),
                    "--stride", "5",
                    "--max-signals", "10",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            
            assert result.returncode == 0
            
            with open(signals_jsonl, 'r') as f:
                for line in f:
                    if line.strip():
                        sig = json.loads(line)
                        assert sig['direction'] in ["long", "short"]
    
    def test_signal_type_values_valid(self):
        """Test that signal_type is either 'bullish_choch' or 'bearish_bos'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles_csv = create_test_candle_csv(tmpdir, num_candles=100)
            signals_jsonl = Path(tmpdir) / "signals.jsonl"
            
            result = subprocess.run(
                [
                    "python",
                    "scripts/export_signals_to_jsonl.py",
                    "--candles-csv", candles_csv,
                    "--output", str(signals_jsonl),
                    "--stride", "5",
                    "--max-signals", "10",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            
            assert result.returncode == 0
            
            with open(signals_jsonl, 'r') as f:
                for line in f:
                    if line.strip():
                        sig = json.loads(line)
                        assert sig['signal_type'] in ["bullish_choch", "bearish_bos"]
    
    def test_session_values_valid(self):
        """Test that session is one of valid sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles_csv = create_test_candle_csv(tmpdir, num_candles=100)
            signals_jsonl = Path(tmpdir) / "signals.jsonl"
            
            result = subprocess.run(
                [
                    "python",
                    "scripts/export_signals_to_jsonl.py",
                    "--candles-csv", candles_csv,
                    "--output", str(signals_jsonl),
                    "--stride", "5",
                    "--max-signals", "10",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            
            assert result.returncode == 0
            
            with open(signals_jsonl, 'r') as f:
                for line in f:
                    if line.strip():
                        sig = json.loads(line)
                        assert sig['session'] in ["asian", "london", "new_york"]
    
    def test_price_fields_are_floats(self):
        """Test that entry, sl, tp are valid floats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            candles_csv = create_test_candle_csv(tmpdir, num_candles=100)
            signals_jsonl = Path(tmpdir) / "signals.jsonl"
            
            result = subprocess.run(
                [
                    "python",
                    "scripts/export_signals_to_jsonl.py",
                    "--candles-csv", candles_csv,
                    "--output", str(signals_jsonl),
                    "--stride", "5",
                    "--max-signals", "10",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
            )
            
            assert result.returncode == 0
            
            with open(signals_jsonl, 'r') as f:
                for line in f:
                    if line.strip():
                        sig = json.loads(line)
                        assert isinstance(sig['entry'], (int, float))
                        assert isinstance(sig['sl'], (int, float))
                        assert isinstance(sig['tp'], (int, float))
                        assert sig['entry'] > 0
                        assert sig['sl'] > 0
                        assert sig['tp'] > 0
