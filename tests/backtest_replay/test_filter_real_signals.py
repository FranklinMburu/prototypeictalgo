#!/usr/bin/env python3
"""
Unit tests for filter_real_signals.py

Tests:
- Filter signals by symbol
- Preserve chronological order
- Handle malformed JSON gracefully
"""

import tempfile
import pytest
import json
from pathlib import Path
import sys

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from filter_real_signals import filter_signals


class TestFilterRealSignals:
    """Test suite for signal filtering."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def create_test_jsonl(self, filepath, signals):
        """Create a test JSONL file with given signals."""
        with open(filepath, 'w') as f:
            for signal in signals:
                f.write(json.dumps(signal) + '\n')
    
    def test_filter_by_eurusd(self, temp_dir):
        """Test filtering signals by EURUSD symbol."""
        signals = [
            {'signal_id': 'real_001', 'symbol': 'BTCUSD', 'timestamp': '2026-01-01 00:00:00'},
            {'signal_id': 'real_002', 'symbol': 'EURUSD', 'timestamp': '2026-01-02 00:00:00'},
            {'signal_id': 'real_003', 'symbol': 'XAUUSD', 'timestamp': '2026-01-03 00:00:00'},
            {'signal_id': 'real_004', 'symbol': 'EURUSD', 'timestamp': '2026-01-04 00:00:00'},
        ]
        
        input_path = temp_dir / "all_signals.jsonl"
        output_path = temp_dir / "eurusd_signals.jsonl"
        
        self.create_test_jsonl(input_path, signals)
        
        # Filter to EURUSD
        filter_signals(input_path, output_path, 'EURUSD')
        
        # Verify output
        with open(output_path) as f:
            filtered = [json.loads(line) for line in f]
            assert len(filtered) == 2
            assert all(s['symbol'] == 'EURUSD' for s in filtered)
            assert filtered[0]['signal_id'] == 'real_002'
            assert filtered[1]['signal_id'] == 'real_004'
    
    def test_filter_preserves_order(self, temp_dir):
        """Test that filtering preserves chronological order."""
        signals = [
            {'signal_id': 'real_001', 'symbol': 'EURUSD', 'timestamp': '2026-01-01 10:00:00'},
            {'signal_id': 'real_002', 'symbol': 'BTCUSD', 'timestamp': '2026-01-02 00:00:00'},
            {'signal_id': 'real_003', 'symbol': 'EURUSD', 'timestamp': '2026-01-03 05:00:00'},
            {'signal_id': 'real_004', 'symbol': 'EURUSD', 'timestamp': '2026-01-02 20:00:00'},
        ]
        
        input_path = temp_dir / "signals.jsonl"
        output_path = temp_dir / "filtered_signals.jsonl"
        
        self.create_test_jsonl(input_path, signals)
        
        # Filter to EURUSD
        filter_signals(input_path, output_path, 'EURUSD')
        
        # Verify order is preserved (not re-sorted!)
        with open(output_path) as f:
            filtered = [json.loads(line) for line in f]
            assert len(filtered) == 3
            # Order should match input file order, not timestamp order
            assert filtered[0]['signal_id'] == 'real_001'
            assert filtered[1]['signal_id'] == 'real_003'
            assert filtered[2]['signal_id'] == 'real_004'
    
    def test_filter_empty_result(self, temp_dir):
        """Test filtering when no signals match."""
        signals = [
            {'signal_id': 'real_001', 'symbol': 'BTCUSD', 'timestamp': '2026-01-01 00:00:00'},
            {'signal_id': 'real_002', 'symbol': 'XAUUSD', 'timestamp': '2026-01-02 00:00:00'},
        ]
        
        input_path = temp_dir / "signals.jsonl"
        output_path = temp_dir / "filtered_signals.jsonl"
        
        self.create_test_jsonl(input_path, signals)
        
        # Filter to EURUSD (should be empty)
        filter_signals(input_path, output_path, 'EURUSD')
        
        # Verify empty output
        with open(output_path) as f:
            filtered = [json.loads(line) for line in f]
            assert len(filtered) == 0
    
    def test_filter_skips_malformed_json(self, temp_dir):
        """Test that malformed JSON lines are skipped."""
        input_path = temp_dir / "signals.jsonl"
        output_path = temp_dir / "filtered_signals.jsonl"
        
        # Create JSONL with one malformed line
        with open(input_path, 'w') as f:
            f.write(json.dumps({'signal_id': 'real_001', 'symbol': 'EURUSD'}) + '\n')
            f.write('{ MALFORMED JSON \n')  # Malformed
            f.write(json.dumps({'signal_id': 'real_003', 'symbol': 'EURUSD'}) + '\n')
        
        # Filter - should skip malformed line and continue
        filter_signals(input_path, output_path, 'EURUSD')
        
        # Verify 2 valid signals written (malformed skipped)
        with open(output_path) as f:
            filtered = [json.loads(line) for line in f]
            assert len(filtered) == 2
    
    def test_filter_missing_symbol_field(self, temp_dir):
        """Test handling of signals missing symbol field."""
        input_path = temp_dir / "signals.jsonl"
        output_path = temp_dir / "filtered_signals.jsonl"
        
        # Create JSONL with signal missing symbol field
        with open(input_path, 'w') as f:
            f.write(json.dumps({'signal_id': 'real_001', 'symbol': 'EURUSD'}) + '\n')
            f.write(json.dumps({'signal_id': 'real_002'}) + '\n')  # Missing symbol
            f.write(json.dumps({'signal_id': 'real_003', 'symbol': 'EURUSD'}) + '\n')
        
        # Filter - should skip signal without symbol
        filter_signals(input_path, output_path, 'EURUSD')
        
        # Verify 2 valid signals written
        with open(output_path) as f:
            filtered = [json.loads(line) for line in f]
            assert len(filtered) == 2
            assert all('symbol' in s for s in filtered)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
