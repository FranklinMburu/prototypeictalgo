#!/usr/bin/env python3
"""
Smoke test for run_real_eurusd_replay_pipeline.py

Minimal end-to-end test:
- Verifies pipeline structure can be parsed
- Checks all required scripts exist
- Validates expected output directories
"""

import pytest
import sys
from pathlib import Path


class TestRealPipelineSmokeTest:
    """Minimal e2e smoke test for replay pipeline."""
    
    @pytest.fixture
    def workspace_root(self):
        """Get workspace root directory."""
        return Path(__file__).parent.parent.parent
    
    def test_pipeline_script_exists(self, workspace_root):
        """Test that main pipeline script exists."""
        pipeline_script = workspace_root / "scripts" / "run_real_eurusd_replay_pipeline.py"
        assert pipeline_script.exists(), f"Pipeline script not found at {pipeline_script}"
    
    def test_merge_script_exists(self, workspace_root):
        """Test that merge_m1_candles script exists."""
        merge_script = workspace_root / "scripts" / "merge_m1_candles.py"
        assert merge_script.exists(), f"Merge script not found at {merge_script}"
    
    def test_filter_script_exists(self, workspace_root):
        """Test that filter_real_signals script exists."""
        filter_script = workspace_root / "scripts" / "filter_real_signals.py"
        assert filter_script.exists(), f"Filter script not found at {filter_script}"
    
    def test_required_scripts_exist(self, workspace_root):
        """Test that all required replay scripts exist."""
        required_scripts = [
            "convert_truefx_ticks_to_m1.py",
            "run_historical_replay.py",
            "run_replay_batch.py",
            "build_allowlist_from_replay.py",
        ]
        
        scripts_dir = workspace_root / "scripts"
        for script_name in required_scripts:
            script_path = scripts_dir / script_name
            assert script_path.exists(), f"Required script not found: {script_path}"
    
    def test_data_directories_exist(self, workspace_root):
        """Test that expected data directories exist."""
        data_paths = [
            workspace_root / "data" / "raw" / "truefx",
            workspace_root / "data" / "processed" / "EURUSD" / "M1",
        ]
        
        for data_path in data_paths:
            assert data_path.exists(), f"Expected directory not found: {data_path}"
    
    def test_jan_m1_candles_exist(self, workspace_root):
        """Test that Jan M1 candles file exists."""
        jan_candles = workspace_root / "data" / "processed" / "EURUSD" / "M1" / "EURUSD-2026-01-M1.csv"
        assert jan_candles.exists(), f"Jan M1 candles not found at {jan_candles}"
    
    def test_real_signals_exist(self, workspace_root):
        """Test that real signals file exists."""
        real_signals = workspace_root / "data" / "processed" / "EURUSD" / "real_signals.jsonl"
        assert real_signals.exists(), f"Real signals not found at {real_signals}"
    
    def test_pipeline_script_is_executable_python(self, workspace_root):
        """Test that pipeline script is valid Python."""
        pipeline_script = workspace_root / "scripts" / "run_real_eurusd_replay_pipeline.py"
        
        # Try to read and parse as Python
        with open(pipeline_script) as f:
            code = f.read()
            try:
                compile(code, str(pipeline_script), 'exec')
            except SyntaxError as e:
                pytest.fail(f"Pipeline script has syntax error: {e}")
    
    def test_merge_script_is_executable_python(self, workspace_root):
        """Test that merge script is valid Python."""
        merge_script = workspace_root / "scripts" / "merge_m1_candles.py"
        
        with open(merge_script) as f:
            code = f.read()
            try:
                compile(code, str(merge_script), 'exec')
            except SyntaxError as e:
                pytest.fail(f"Merge script has syntax error: {e}")
    
    def test_filter_script_is_executable_python(self, workspace_root):
        """Test that filter script is valid Python."""
        filter_script = workspace_root / "scripts" / "filter_real_signals.py"
        
        with open(filter_script) as f:
            code = f.read()
            try:
                compile(code, str(filter_script), 'exec')
            except SyntaxError as e:
                pytest.fail(f"Filter script has syntax error: {e}")
    
    def test_output_directories_can_be_created(self, workspace_root):
        """Test that pipeline output directories can be created."""
        output_dir = workspace_root / "data" / "processed" / "EURUSD"
        # Should already exist, but verify it's writable
        assert output_dir.is_dir()
        
        # Try to create a temp file to verify write access
        test_file = output_dir / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            pytest.fail(f"Cannot write to output directory {output_dir}: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
