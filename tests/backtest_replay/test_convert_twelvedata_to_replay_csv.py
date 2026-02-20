#!/usr/bin/env python3
"""
Unit tests for convert_twelvedata_to_replay_csv.py

Tests:
- Semicolon-delimited TwelveData CSV conversion
- Output header validation
- CandleLoader compatibility
- Row count preservation
- Timestamp sorting
- Duplicate detection
- Gap detection
- Volume injection
"""

import tempfile
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.convert_twelvedata_to_replay_csv import TwelveDataConverter
from backtest_replay.candle_loader import CandleLoader


class TestTwelveDataConverter:
    """Test suite for TwelveData CSV conversion."""
    
    @staticmethod
    def test_basic_semicolon_conversion():
        """Test basic conversion of semicolon-delimited TwelveData CSV."""
        # Create temp input file (semicolon-delimited, no volume)
        input_data = """datetime;open;high;low;close
2026-01-31 15:10:00;4865.1111;4865.5555;4865.0000;4865.3728
2026-01-31 15:15:00;4865.3728;4865.5615;4865.3502;4865.3502
2026-01-31 15:20:00;4865.3500;4865.7000;4865.3000;4865.4500
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_f.write(input_data)
            input_path = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_path = output_f.name
        
        try:
            # Convert
            converter = TwelveDataConverter(
                input_path=input_path,
                output_path=output_path,
                default_volume=0.0,
            )
            converter.convert()
            
            # Verify output exists
            output_file = Path(output_path)
            assert output_file.exists(), "Output file not created"
            
            # Verify output header
            with open(output_path, 'r') as f:
                header = f.readline().strip()
                expected_header = "timestamp,open,high,low,close,volume"
                assert header == expected_header, f"Header mismatch: {header} != {expected_header}"
            
            # Verify CandleLoader can load it
            candles = CandleLoader.load_csv(output_path)
            assert len(candles) == 3, f"Row count mismatch: {len(candles)} != 3"
            
            # Verify timestamps are sorted ascending
            for i in range(len(candles) - 1):
                assert candles[i].timestamp < candles[i + 1].timestamp, \
                    f"Timestamps not sorted: {candles[i].timestamp} >= {candles[i + 1].timestamp}"
            
            # Verify volume was injected
            for candle in candles:
                assert candle.volume == 0.0, f"Volume mismatch: {candle.volume} != 0.0"
            
            print("✓ test_basic_semicolon_conversion PASSED")
        
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)
    
    @staticmethod
    def test_unsorted_input():
        """Test conversion when input is not sorted by timestamp."""
        input_data = """datetime;open;high;low;close
2026-01-31 15:20:00;4865.3500;4865.7000;4865.3000;4865.4500
2026-01-31 15:10:00;4865.1111;4865.5555;4865.0000;4865.3728
2026-01-31 15:15:00;4865.3728;4865.5615;4865.3502;4865.3502
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_f.write(input_data)
            input_path = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_path = output_f.name
        
        try:
            converter = TwelveDataConverter(
                input_path=input_path,
                output_path=output_path,
                default_volume=1.0,
            )
            converter.convert()
            
            # Verify sorting was applied
            assert converter.sorting_applied, "Sorting should have been applied"
            
            # Verify output is sorted
            candles = CandleLoader.load_csv(output_path)
            for i in range(len(candles) - 1):
                assert candles[i].timestamp < candles[i + 1].timestamp, \
                    "Output not properly sorted"
            
            print("✓ test_unsorted_input PASSED")
        
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)
    
    @staticmethod
    def test_iso8601_timestamp():
        """Test conversion with ISO8601 timestamp format."""
        input_data = """datetime;open;high;low;close
2026-01-31T15:10:00Z;4865.1111;4865.5555;4865.0000;4865.3728
2026-01-31T15:15:00Z;4865.3728;4865.5615;4865.3502;4865.3502
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_f.write(input_data)
            input_path = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_path = output_f.name
        
        try:
            converter = TwelveDataConverter(
                input_path=input_path,
                output_path=output_path,
                default_volume=0.0,
            )
            converter.convert()
            
            # Verify timestamps are normalized
            with open(output_path, 'r') as f:
                lines = f.readlines()
                # Skip header
                for line in lines[1:]:
                    timestamp = line.split(',')[0]
                    # Should be in %Y-%m-%d %H:%M:%S format
                    assert ' ' in timestamp and ':' in timestamp, \
                        f"Timestamp not normalized: {timestamp}"
            
            print("✓ test_iso8601_timestamp PASSED")
        
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)
    
    @staticmethod
    def test_duplicate_timestamp_fails():
        """Test that duplicate timestamps cause hard failure."""
        input_data = """datetime;open;high;low;close
2026-01-31 15:10:00;4865.1111;4865.5555;4865.0000;4865.3728
2026-01-31 15:10:00;4865.3728;4865.5615;4865.3502;4865.3502
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_f.write(input_data)
            input_path = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_path = output_f.name
        
        try:
            converter = TwelveDataConverter(
                input_path=input_path,
                output_path=output_path,
            )
            
            try:
                converter.convert()
                assert False, "Should have raised ValueError for duplicate timestamps"
            except ValueError as e:
                assert "duplicate" in str(e).lower(), \
                    f"Error message should mention duplicates: {e}"
            
            print("✓ test_duplicate_timestamp_fails PASSED")
        
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)
    
    @staticmethod
    def test_missing_column_fails():
        """Test that missing required columns cause hard failure."""
        input_data = """datetime;open;high;low
2026-01-31 15:10:00;4865.1111;4865.5555;4865.0000
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_f.write(input_data)
            input_path = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_path = output_f.name
        
        try:
            converter = TwelveDataConverter(
                input_path=input_path,
                output_path=output_path,
            )
            
            try:
                converter.convert()
                assert False, "Should have raised ValueError for missing column"
            except ValueError as e:
                assert "missing" in str(e).lower() or "close" in str(e).lower(), \
                    f"Error should mention missing 'close' column: {e}"
            
            print("✓ test_missing_column_fails PASSED")
        
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)
    
    @staticmethod
    def test_non_numeric_ohlc_fails():
        """Test that non-numeric OHLC values cause hard failure."""
        input_data = """datetime;open;high;low;close
2026-01-31 15:10:00;invalid;4865.5555;4865.0000;4865.3728
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_f.write(input_data)
            input_path = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_path = output_f.name
        
        try:
            converter = TwelveDataConverter(
                input_path=input_path,
                output_path=output_path,
            )
            
            try:
                converter.convert()
                assert False, "Should have raised ValueError for non-numeric value"
            except ValueError as e:
                assert "numeric" in str(e).lower() or "invalid" in str(e).lower(), \
                    f"Error should mention non-numeric value: {e}"
            
            print("✓ test_non_numeric_ohlc_fails PASSED")
        
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)
    
    @staticmethod
    def test_gap_detection():
        """Test that gaps in timestamps are detected (but don't fail)."""
        input_data = """datetime;open;high;low;close
2026-01-31 15:10:00;4865.1111;4865.5555;4865.0000;4865.3728
2026-01-31 15:15:00;4865.3728;4865.5615;4865.3502;4865.3502
2026-01-31 15:30:00;4865.3500;4865.7000;4865.3000;4865.4500
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as input_f:
            input_f.write(input_data)
            input_path = input_f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as output_f:
            output_path = output_f.name
        
        try:
            converter = TwelveDataConverter(
                input_path=input_path,
                output_path=output_path,
            )
            converter.convert()
            
            # Verify gap was detected
            assert converter.gap_count > 0, "Gap should have been detected"
            assert len(converter.gap_details) > 0, "Gap details should be populated"
            
            # Verify conversion succeeded despite gap
            candles = CandleLoader.load_csv(output_path)
            assert len(candles) == 3, "All rows should be preserved despite gap"
            
            print("✓ test_gap_detection PASSED")
        
        finally:
            Path(input_path).unlink(missing_ok=True)
            Path(output_path).unlink(missing_ok=True)


def run_all_tests():
    """Run all tests."""
    test_methods = [
        TestTwelveDataConverter.test_basic_semicolon_conversion,
        TestTwelveDataConverter.test_unsorted_input,
        TestTwelveDataConverter.test_iso8601_timestamp,
        TestTwelveDataConverter.test_duplicate_timestamp_fails,
        TestTwelveDataConverter.test_missing_column_fails,
        TestTwelveDataConverter.test_non_numeric_ohlc_fails,
        TestTwelveDataConverter.test_gap_detection,
    ]
    
    print("\n" + "=" * 70)
    print("RUNNING TESTS: convert_twelvedata_to_replay_csv.py")
    print("=" * 70 + "\n")
    
    passed = 0
    failed = 0
    
    for test_method in test_methods:
        try:
            test_method()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_method.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_method.__name__} ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70 + "\n")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
