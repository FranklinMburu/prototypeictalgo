#!/usr/bin/env python3
"""
Unit tests for merge_m1_candles.py

Tests:
- Merge two small candle CSVs
- Verify output schema and order
- Check duplicate removal
"""

import tempfile
import pytest
from pathlib import Path
from datetime import datetime
import sys
import csv

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from merge_m1_candles import merge_candles, validate_candle_csv


class TestMergeM1Candles:
    """Test suite for M1 candle merging."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def create_test_csv(self, filepath, rows):
        """Create a test CSV file with given rows."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            writer.writeheader()
            writer.writerows(rows)
    
    def test_merge_two_small_csvs(self, temp_dir):
        """Test merging two small candle CSVs."""
        # Create test data
        csv1_data = [
            {'timestamp': '2026-01-01 00:00:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
            {'timestamp': '2026-01-01 00:01:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
        ]
        csv2_data = [
            {'timestamp': '2026-01-01 00:02:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
            {'timestamp': '2026-01-01 00:03:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
        ]
        
        csv1_path = temp_dir / "candles_01.csv"
        csv2_path = temp_dir / "candles_02.csv"
        output_path = temp_dir / "merged.csv"
        
        self.create_test_csv(csv1_path, csv1_data)
        self.create_test_csv(csv2_path, csv2_data)
        
        # Merge
        merge_candles([csv1_path, csv2_path], output_path)
        
        # Verify output
        assert output_path.exists()
        
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 4
            assert rows[0]['timestamp'] == '2026-01-01 00:00:00'
            assert rows[-1]['timestamp'] == '2026-01-01 00:03:00'
    
    def test_merge_with_duplication(self, temp_dir):
        """Test that duplicate timestamps are removed."""
        csv1_data = [
            {'timestamp': '2026-01-01 00:00:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
            {'timestamp': '2026-01-01 00:01:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
        ]
        csv2_data = [
            {'timestamp': '2026-01-01 00:01:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},  # Duplicate
            {'timestamp': '2026-01-01 00:02:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
        ]
        
        csv1_path = temp_dir / "candles_01.csv"
        csv2_path = temp_dir / "candles_02.csv"
        output_path = temp_dir / "merged.csv"
        
        self.create_test_csv(csv1_path, csv1_data)
        self.create_test_csv(csv2_path, csv2_data)
        
        # Merge
        merge_candles([csv1_path, csv2_path], output_path)
        
        # Verify: should have 3 rows (1 duplicate removed)
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3  # 2 + 2 - 1 duplicate
    
    def test_merge_maintains_sort_order(self, temp_dir):
        """Test that merge result is sorted by timestamp."""
        # Create reversed order input
        csv1_data = [
            {'timestamp': '2026-01-01 00:03:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
            {'timestamp': '2026-01-01 00:01:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
        ]
        csv2_data = [
            {'timestamp': '2026-01-01 00:04:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
            {'timestamp': '2026-01-01 00:00:00', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
        ]
        
        csv1_path = temp_dir / "candles_01.csv"
        csv2_path = temp_dir / "candles_02.csv"
        output_path = temp_dir / "merged.csv"
        
        self.create_test_csv(csv1_path, csv1_data)
        self.create_test_csv(csv2_path, csv2_data)
        
        # Merge
        merge_candles([csv1_path, csv2_path], output_path)
        
        # Verify sorted order
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            timestamps = [row['timestamp'] for row in rows]
            assert timestamps == sorted(timestamps)
    
    def test_validate_invalid_header(self, temp_dir):
        """Test that invalid header raises error."""
        csv_data = [
            {'bad': 'header'},
        ]
        
        csv_path = temp_dir / "bad_candles.csv"
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['bad'])
            writer.writeheader()
            writer.writerows(csv_data)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Invalid header"):
            validate_candle_csv(csv_path)
    
    def test_validate_invalid_timestamp_format(self, temp_dir):
        """Test that invalid timestamp format raises error."""
        csv_data = [
            {'timestamp': 'not-a-timestamp', 'open': '1.10', 'high': '1.11', 'low': '1.09', 'close': '1.10', 'volume': '100'},
        ]
        
        csv_path = temp_dir / "bad_timestamp.csv"
        self.create_test_csv(csv_path, csv_data)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            validate_candle_csv(csv_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
