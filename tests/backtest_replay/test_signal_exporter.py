"""
Tests for synthetic signal exporter.

Tests determinism, schema validity, and timestamp alignment.
"""

import pytest
import tempfile
import json
from datetime import datetime, timezone
from pathlib import Path

# Import the exporter
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.export_signals_to_jsonl import (
    get_session_from_hour,
    load_candles_csv,
    generate_signals,
    write_signals_jsonl,
)


class TestSessionMapping:
    """Test deterministic session mapping from UTC hour."""
    
    def test_asian_hours(self):
        """0-7 should map to 'asian'."""
        assert get_session_from_hour(0) == "asian"
        assert get_session_from_hour(3) == "asian"
        assert get_session_from_hour(7) == "asian"
    
    def test_london_hours(self):
        """8-15 should map to 'london'."""
        assert get_session_from_hour(8) == "london"
        assert get_session_from_hour(12) == "london"
        assert get_session_from_hour(15) == "london"
    
    def test_newyork_hours(self):
        """16-23 should map to 'new_york'."""
        assert get_session_from_hour(16) == "new_york"
        assert get_session_from_hour(20) == "new_york"
        assert get_session_from_hour(23) == "new_york"


class TestLoadCandles:
    """Test loading candles from CSV."""
    
    def test_load_candles_valid(self):
        """Test loading valid candle CSV."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
2026-01-01 11:00:00,1.17250,1.17350,1.17200,1.17300,15
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            assert len(candles) == 2
            assert candles[0]['close'] == 1.17250
            assert candles[1]['close'] == 1.17300
            assert candles[0]['timestamp'].tzinfo == timezone.utc
            
            Path(f.name).unlink()
    
    def test_load_candles_not_found(self):
        """Test error on missing file."""
        with pytest.raises(FileNotFoundError):
            load_candles_csv("/nonexistent/candles.csv")
    
    def test_load_candles_empty(self):
        """Test error on empty CSV."""
        csv_content = "timestamp,open,high,low,close,volume\n"
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            with pytest.raises(ValueError, match="No valid candles"):
                load_candles_csv(f.name)
            
            Path(f.name).unlink()


class TestGenerateSignals:
    """Test signal generation."""
    
    def test_direction_alternates(self):
        """Test that direction alternates deterministically."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
2026-01-01 11:00:00,1.17250,1.17350,1.17200,1.17300,15
2026-01-01 12:00:00,1.17300,1.17400,1.17250,1.17350,20
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            signals = generate_signals(candles, stride=1, max_signals=3)
            
            # Even index -> long, Odd index -> short
            assert signals[0]['direction'] == "long"
            assert signals[1]['direction'] == "short"
            assert signals[2]['direction'] == "long"
            
            Path(f.name).unlink()
    
    def test_signal_type_alternates(self):
        """Test that signal_type alternates deterministically."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
2026-01-01 11:00:00,1.17250,1.17350,1.17200,1.17300,15
2026-01-01 12:00:00,1.17300,1.17400,1.17250,1.17350,20
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            signals = generate_signals(candles, stride=1, max_signals=3)
            
            # Even index -> bullish_choch, Odd index -> bearish_bos
            assert signals[0]['signal_type'] == "bullish_choch"
            assert signals[1]['signal_type'] == "bearish_bos"
            assert signals[2]['signal_type'] == "bullish_choch"
            
            Path(f.name).unlink()
    
    def test_entry_equals_close(self):
        """Test that entry price equals candle close."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            signals = generate_signals(candles, stride=1, max_signals=1)
            
            assert signals[0]['entry'] == 1.17250
            
            Path(f.name).unlink()
    
    def test_sl_tp_long(self):
        """Test SL/TP calculation for long position."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            signals = generate_signals(candles, stride=1, max_signals=1)
            
            # First signal is long (index 0)
            sig = signals[0]
            assert sig['direction'] == "long"
            
            risk = 1.17300 - 1.17100  # 0.00200
            entry = 1.17250
            
            # long: sl = entry - risk, tp = entry + 2*risk
            assert abs(sig['sl'] - (entry - risk)) < 0.00001
            assert abs(sig['tp'] - (entry + 2 * risk)) < 0.00001
            
            Path(f.name).unlink()
    
    def test_sl_tp_short(self):
        """Test SL/TP calculation for short position."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
2026-01-01 11:00:00,1.17250,1.17350,1.17200,1.17300,15
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            signals = generate_signals(candles, stride=1, max_signals=2)
            
            # Second signal is short (index 1)
            sig = signals[1]
            assert sig['direction'] == "short"
            
            risk = 1.17350 - 1.17200  # 0.00150
            entry = 1.17300
            
            # short: sl = entry + risk, tp = entry - 2*risk
            assert abs(sig['sl'] - (entry + risk)) < 0.00001
            assert abs(sig['tp'] - (entry - 2 * risk)) < 0.00001
            
            Path(f.name).unlink()
    
    def test_stride_sampling(self):
        """Test that stride parameter correctly samples candles."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
2026-01-01 11:00:00,1.17250,1.17350,1.17200,1.17300,15
2026-01-01 12:00:00,1.17300,1.17400,1.17250,1.17350,20
2026-01-01 13:00:00,1.17350,1.17450,1.17300,1.17400,25
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            signals = generate_signals(candles, stride=2, max_signals=100)
            
            # With stride=2 and 4 candles, should get 2 signals (0, 2)
            assert len(signals) == 2
            assert signals[0]['entry'] == 1.17250  # candle 0
            assert signals[1]['entry'] == 1.17350  # candle 2
            
            Path(f.name).unlink()
    
    def test_max_signals_cap(self):
        """Test that max_signals cap is respected."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
2026-01-01 11:00:00,1.17250,1.17350,1.17200,1.17300,15
2026-01-01 12:00:00,1.17300,1.17400,1.17250,1.17350,20
2026-01-01 13:00:00,1.17350,1.17450,1.17300,1.17400,25
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            signals = generate_signals(candles, stride=1, max_signals=2)
            
            # Even with stride=1, max_signals=2 should cap at 2
            assert len(signals) == 2
            
            Path(f.name).unlink()
    
    def test_determinism(self):
        """Test that same input produces identical output."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
2026-01-01 11:00:00,1.17250,1.17350,1.17200,1.17300,15
2026-01-01 12:00:00,1.17300,1.17400,1.17250,1.17350,20
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            
            # Generate signals twice with same input
            signals1 = generate_signals(candles, stride=1, max_signals=3)
            signals2 = generate_signals(candles, stride=1, max_signals=3)
            
            # Should be identical
            assert len(signals1) == len(signals2)
            for s1, s2 in zip(signals1, signals2):
                assert s1['signal_id'] == s2['signal_id']
                assert s1['direction'] == s2['direction']
                assert s1['signal_type'] == s2['signal_type']
                assert s1['entry'] == s2['entry']
                assert s1['sl'] == s2['sl']
                assert s1['tp'] == s2['tp']
            
            Path(f.name).unlink()
    
    def test_timestamp_alignment(self):
        """Test that all signal timestamps exist in candle timestamps."""
        csv_content = """timestamp,open,high,low,close,volume
2026-01-01 10:00:00,1.17200,1.17300,1.17100,1.17250,10
2026-01-01 11:00:00,1.17250,1.17350,1.17200,1.17300,15
2026-01-01 12:00:00,1.17300,1.17400,1.17250,1.17350,20
2026-01-01 13:00:00,1.17350,1.17450,1.17300,1.17400,25
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            f.flush()
            
            candles = load_candles_csv(f.name)
            signals = generate_signals(candles, stride=1, max_signals=4)
            
            candle_timestamps = {c['timestamp'].strftime("%Y-%m-%d %H:%M:%S") for c in candles}
            signal_timestamps = {s['timestamp'] for s in signals}
            
            # All signal timestamps must exist in candles
            assert signal_timestamps.issubset(candle_timestamps)
            
            Path(f.name).unlink()


class TestWriteSignalsJsonl:
    """Test writing signals to JSONL."""
    
    def test_write_creates_file(self):
        """Test that write creates output file."""
        signals = [
            {
                "signal_id": "test_001",
                "timestamp": "2026-01-01 10:00:00",
                "symbol": "EURUSD",
                "timeframe": "1m",
                "direction": "long",
                "signal_type": "bullish_choch",
                "entry": 1.17250,
                "sl": 1.17200,
                "tp": 1.17350,
                "session": "london",
                "meta": {},
            }
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "signals.jsonl")
            write_signals_jsonl(signals, output_path)
            
            assert Path(output_path).exists()
            
            # Verify content
            with open(output_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
                assert len(lines) == 1
                loaded = json.loads(lines[0])
                assert loaded['signal_id'] == 'test_001'
                assert loaded['entry'] == 1.17250
    
    def test_write_multiple_signals(self):
        """Test writing multiple signals."""
        signals = [
            {"signal_id": f"test_{i:03d}", "entry": 1.17250 + i * 0.0001, "timestamp": f"2026-01-01 {i:02d}:00:00"}
            for i in range(5)
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "signals.jsonl")
            write_signals_jsonl(signals, output_path)
            
            with open(output_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
                assert len(lines) == 5
