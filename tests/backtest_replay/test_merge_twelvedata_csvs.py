#!/usr/bin/env python3
"""
Unit tests for merge_twelvedata_csvs.py

Tests:
- Basic merge of multiple chunk files
- Deduplication of identical datetime rows
- Sorting when inputs are out of chronological order
- Glob pattern expansion
- Processed output generation with replay compatibility
"""

import tempfile
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.merge_twelvedata_csvs import TwelveDataMerger
from backtest_replay.candle_loader import CandleLoader


class TestTwelveDataMerger:
    """Test suite for TwelveData CSV merging."""
    
    @staticmethod
    def create_chunk_csv(path: Path, data: str):
        """Helper to create a test CSV chunk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
    
    def test_basic_merge_two_chunks(self, tmp_path):
        """Test basic merge of two sequential chunk files."""
        # Create two chunk files
        chunk1_path = tmp_path / "chunk1.csv"
        chunk2_path = tmp_path / "chunk2.csv"
        
        chunk1_data = """datetime;open;high;low;close
2026-01-01 08:00:00;4850.0000;4852.5000;4849.5000;4851.2500
2026-01-01 08:05:00;4851.2500;4854.0000;4851.0000;4853.7500
"""
        
        chunk2_data = """datetime;open;high;low;close
2026-01-01 08:10:00;4853.7500;4855.5000;4853.2500;4854.8000
2026-01-01 08:15:00;4854.8000;4856.2500;4854.5000;4855.5000
"""
        
        self.create_chunk_csv(chunk1_path, chunk1_data)
        self.create_chunk_csv(chunk2_path, chunk2_data)
        
        # Merge
        out_raw = tmp_path / "merged_raw.csv"
        merger = TwelveDataMerger(
            inputs=f"{chunk1_path},{chunk2_path}",
            out_raw=str(out_raw),
        )
        merger.merge()
        
        # Verify
        assert out_raw.exists(), "Output file not created"
        assert merger.rows_after_dedupe == 4, "Should have 4 rows"
        assert merger.duplicates_removed == 0, "No duplicates"
        assert merger.first_datetime == "2026-01-01 08:00:00"
        assert merger.last_datetime == "2026-01-01 08:15:00"
        
        # Verify output format (semicolon, correct header)
        content = out_raw.read_text()
        lines = content.strip().split('\n')
        assert lines[0] == "datetime;open;high;low;close", f"Header mismatch: {lines[0]}"
        assert len(lines) == 5, f"Expected 5 lines (1 header + 4 data), got {len(lines)}"
    
    def test_deduplication_same_datetime(self, tmp_path):
        """Test deduplication when both files include the same datetime."""
        chunk1_path = tmp_path / "chunk1.csv"
        chunk2_path = tmp_path / "chunk2.csv"
        
        # Both chunks have 2026-01-01 08:10:00
        chunk1_data = """datetime;open;high;low;close
2026-01-01 08:00:00;4850.0000;4852.5000;4849.5000;4851.2500
2026-01-01 08:10:00;4853.7500;4855.5000;4853.2500;4854.8000
"""
        
        chunk2_data = """datetime;open;high;low;close
2026-01-01 08:10:00;4853.7500;4855.5000;4853.2500;4854.8000
2026-01-01 08:15:00;4854.8000;4856.2500;4854.5000;4855.5000
"""
        
        self.create_chunk_csv(chunk1_path, chunk1_data)
        self.create_chunk_csv(chunk2_path, chunk2_data)
        
        # Merge
        out_raw = tmp_path / "merged_raw.csv"
        merger = TwelveDataMerger(
            inputs=f"{chunk1_path},{chunk2_path}",
            out_raw=str(out_raw),
        )
        merger.merge()
        
        # Verify dedup: should keep first occurrence from chunk1
        assert merger.rows_after_dedupe == 3, f"Expected 3 rows after dedup, got {merger.rows_after_dedupe}"
        assert merger.duplicates_removed == 1, f"Expected 1 duplicate removed, got {merger.duplicates_removed}"
        
        # Verify output has 3 data rows
        content = out_raw.read_text()
        lines = content.strip().split('\n')
        assert len(lines) == 4, f"Expected 4 lines (1 header + 3 data), got {len(lines)}"
    
    def test_sorting_out_of_order_inputs(self, tmp_path):
        """Test sorting when input chunks are chronologically out of order."""
        # Create chunks in reverse chronological order
        chunk1_path = tmp_path / "chunk_feb.csv"
        chunk2_path = tmp_path / "chunk_jan.csv"
        
        # February data (later)
        chunk1_data = """datetime;open;high;low;close
2026-02-01 08:00:00;4860.0000;4861.0000;4859.0000;4860.5000
2026-02-01 08:05:00;4860.5000;4862.0000;4860.0000;4861.5000
"""
        
        # January data (earlier)
        chunk2_data = """datetime;open;high;low;close
2026-01-01 08:00:00;4850.0000;4852.5000;4849.5000;4851.2500
2026-01-01 08:05:00;4851.2500;4854.0000;4851.0000;4853.7500
"""
        
        self.create_chunk_csv(chunk1_path, chunk1_data)
        self.create_chunk_csv(chunk2_path, chunk2_data)
        
        # Merge
        out_raw = tmp_path / "merged_raw.csv"
        merger = TwelveDataMerger(
            inputs=f"{chunk1_path},{chunk2_path}",
            out_raw=str(out_raw),
        )
        merger.merge()
        
        # Verify sorting was applied
        assert merger.sorting_applied, "Sorting should have been applied"
        
        # Verify output is in ascending order (Jan first)
        assert merger.first_datetime == "2026-01-01 08:00:00", "First should be January"
        assert merger.last_datetime == "2026-02-01 08:05:00", "Last should be February"
        
        # Verify data order in file
        content = out_raw.read_text()
        lines = content.strip().split('\n')
        assert "2026-01-01" in lines[1], "First data row should be January"
        assert "2026-02-01" in lines[-1], "Last data row should be February"
    
    def test_processed_output_header_and_candle_loader(self, tmp_path):
        """Test processed output can be loaded by CandleLoader with correct header."""
        chunk_path = tmp_path / "chunk.csv"
        
        chunk_data = """datetime;open;high;low;close
2026-01-01 08:00:00;4850.0000;4852.5000;4849.5000;4851.2500
2026-01-01 08:05:00;4851.2500;4854.0000;4851.0000;4853.7500
2026-01-01 08:10:00;4853.7500;4855.5000;4853.2500;4854.8000
"""
        
        self.create_chunk_csv(chunk_path, chunk_data)
        
        # Merge with processed output
        out_raw = tmp_path / "raw.csv"
        out_processed = tmp_path / "processed.csv"
        
        merger = TwelveDataMerger(
            inputs=str(chunk_path),
            out_raw=str(out_raw),
            out_processed=str(out_processed),
            default_volume=0.0,
        )
        merger.merge()
        
        # Verify processed file was created
        assert out_processed.exists(), "Processed CSV not created"
        
        # Verify header is correct
        processed_content = out_processed.read_text()
        header_line = processed_content.split('\n')[0]
        assert header_line == "timestamp,open,high,low,close,volume", \
            f"Header mismatch: {header_line}"
        
        # Verify CandleLoader can parse it
        candles = CandleLoader.load_csv(str(out_processed))
        assert len(candles) == 3, f"Expected 3 candles, got {len(candles)}"
        assert candles[0].close == 4851.25
        assert candles[-1].close == 4854.8
    
    def test_glob_pattern_expansion(self, tmp_path):
        """Test glob pattern expansion in --inputs."""
        # Create multiple files matching a pattern
        data_dir = tmp_path / "data"
        
        for i in range(1, 4):
            chunk_path = data_dir / f"chunk_{i:02d}.csv"
            chunk_data = f"""datetime;open;high;low;close
2026-01-0{i} 08:00:00;4850.0{i};4852.5{i};4849.5{i};4851.2{i}
"""
            self.create_chunk_csv(chunk_path, chunk_data)
        
        # Merge using glob pattern
        out_raw = tmp_path / "merged.csv"
        merger = TwelveDataMerger(
            inputs=f"{data_dir}/chunk_*.csv",
            out_raw=str(out_raw),
        )
        merger.merge()
        
        # Verify all files were found and merged
        assert len(merger.input_files) == 3, f"Expected 3 files, got {len(merger.input_files)}"
        assert merger.rows_after_dedupe == 3, f"Expected 3 rows, got {merger.rows_after_dedupe}"
    
    def test_comma_delimited_input(self, tmp_path):
        """Test that merger handles comma-delimited inputs correctly."""
        chunk_path = tmp_path / "chunk_comma.csv"
        
        # Comma-delimited input
        chunk_data = """datetime,open,high,low,close
2026-01-01 08:00:00,4850.0,4852.5,4849.5,4851.25
2026-01-01 08:05:00,4851.25,4854.0,4851.0,4853.75
"""
        
        self.create_chunk_csv(chunk_path, chunk_data)
        
        out_raw = tmp_path / "merged.csv"
        merger = TwelveDataMerger(
            inputs=str(chunk_path),
            out_raw=str(out_raw),
        )
        merger.merge()
        
        # Verify raw output is semicolon-delimited (conversion from comma)
        raw_content = out_raw.read_text()
        header_line = raw_content.split('\n')[0]
        assert header_line == "datetime;open;high;low;close", f"Header should be semicolon-delimited: {header_line}"
        assert ';' in raw_content, "Output should be semicolon-delimited"
    
    def test_hard_fail_missing_file(self, tmp_path):
        """Test that merger fails when file does not exist."""
        merger = TwelveDataMerger(
            inputs=str(tmp_path / "nonexistent.csv"),
            out_raw=str(tmp_path / "out.csv"),
        )
        
        with pytest.raises(ValueError, match="does not exist"):
            merger.merge()
    
    def test_hard_fail_empty_glob(self, tmp_path):
        """Test that merger fails when glob matches no files."""
        merger = TwelveDataMerger(
            inputs=f"{tmp_path}/nonexistent*.csv",
            out_raw=str(tmp_path / "out.csv"),
        )
        
        with pytest.raises(ValueError, match="matched no files"):
            merger.merge()
    
    def test_hard_fail_missing_column(self, tmp_path):
        """Test that merger fails when required column is missing."""
        chunk_path = tmp_path / "chunk.csv"
        
        # Missing 'close' column
        chunk_data = """datetime;open;high;low
2026-01-01 08:00:00;4850.0;4852.5;4849.5
"""
        
        self.create_chunk_csv(chunk_path, chunk_data)
        
        merger = TwelveDataMerger(
            inputs=str(chunk_path),
            out_raw=str(tmp_path / "out.csv"),
        )
        
        with pytest.raises(ValueError, match="Missing required columns"):
            merger.merge()
    
    def test_hard_fail_invalid_datetime_format(self, tmp_path):
        """Test that merger fails on invalid datetime format."""
        chunk_path = tmp_path / "chunk.csv"
        
        # Invalid datetime format
        chunk_data = """datetime;open;high;low;close
2026/01/01 08:00:00;4850.0;4852.5;4849.5;4851.25
"""
        
        self.create_chunk_csv(chunk_path, chunk_data)
        
        merger = TwelveDataMerger(
            inputs=str(chunk_path),
            out_raw=str(tmp_path / "out.csv"),
        )
        
        with pytest.raises(ValueError, match="Invalid datetime format"):
            merger.merge()
    
    def test_hard_fail_non_numeric_ohlc(self, tmp_path):
        """Test that merger fails on non-numeric OHLC values."""
        chunk_path = tmp_path / "chunk.csv"
        
        # Non-numeric 'open' value
        chunk_data = """datetime;open;high;low;close
2026-01-01 08:00:00;invalid;4852.5;4849.5;4851.25
"""
        
        self.create_chunk_csv(chunk_path, chunk_data)
        
        merger = TwelveDataMerger(
            inputs=str(chunk_path),
            out_raw=str(tmp_path / "out.csv"),
        )
        
        with pytest.raises(ValueError, match="Non-numeric"):
            merger.merge()


def run_all_tests():
    """Run all tests."""
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    run_all_tests()
