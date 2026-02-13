"""
Tests for allowlist builder functionality.

Verifies:
- Correct rename from model→signal_type
- Allowlist includes only groups meeting thresholds
- Output JSON is stable/deterministic
- Headers/keys match specification
- Group key construction is correct
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from scripts.build_allowlist_from_replay import (
    AllowlistEntry,
    build_allowlist,
    filter_groups,
    load_replay_summary,
)


@pytest.fixture
def sample_replay_summary():
    """Create sample replay summary for testing."""
    return {
        "timestamp": "2026-02-13T00:00:00Z",
        "total_groups": 5,
        "groups": [
            # Group 1: PASS (meets all thresholds)
            {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "session": "london",
                "signal_type": "bearish_bos",
                "direction": "long",
                "sample_size": 100,
                "completed_trades": 100,
                "cancelled_trades": 0,
                "win_rate": 0.55,
                "loss_rate": 0.45,
                "be_rate": 0.0,
                "expectancy": 0.50,
                "max_drawdown_r": 5.0,
                "max_loss_streak": 3,
                "max_win_streak": 5,
            },
            # Group 2: FAIL (sample_size too low)
            {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "session": "asian",
                "signal_type": "bullish_choch",
                "direction": "long",
                "sample_size": 20,
                "completed_trades": 20,
                "cancelled_trades": 0,
                "win_rate": 0.60,
                "loss_rate": 0.40,
                "be_rate": 0.0,
                "expectancy": 0.30,
                "max_drawdown_r": 3.0,
                "max_loss_streak": 2,
                "max_win_streak": 4,
            },
            # Group 3: FAIL (expectancy too low)
            {
                "symbol": "GBPUSD",
                "timeframe": "4h",
                "session": "newyork",
                "signal_type": "bearish_bos",
                "direction": "short",
                "sample_size": 80,
                "completed_trades": 80,
                "cancelled_trades": 0,
                "win_rate": 0.48,
                "loss_rate": 0.52,
                "be_rate": 0.0,
                "expectancy": 0.05,
                "max_drawdown_r": 6.0,
                "max_loss_streak": 4,
                "max_win_streak": 3,
            },
            # Group 4: FAIL (max_drawdown_r too high)
            {
                "symbol": "EURUSD",
                "timeframe": "4h",
                "session": "london",
                "signal_type": "choch",
                "direction": "long",
                "sample_size": 120,
                "completed_trades": 120,
                "cancelled_trades": 0,
                "win_rate": 0.52,
                "loss_rate": 0.48,
                "be_rate": 0.0,
                "expectancy": 0.25,
                "max_drawdown_r": 12.0,
                "max_loss_streak": 5,
                "max_win_streak": 6,
            },
            # Group 5: FAIL (max_loss_streak too high)
            {
                "symbol": "GBPUSD",
                "timeframe": "1h",
                "session": "london",
                "signal_type": "bos",
                "direction": "short",
                "sample_size": 90,
                "completed_trades": 90,
                "cancelled_trades": 0,
                "win_rate": 0.53,
                "loss_rate": 0.47,
                "be_rate": 0.0,
                "expectancy": 0.35,
                "max_drawdown_r": 7.0,
                "max_loss_streak": 9,
                "max_win_streak": 4,
            },
        ],
    }


class TestNamingCorrectness:
    """Test that signal_type is used (not model)."""

    def test_json_key_is_signal_type(self, sample_replay_summary):
        """Verify JSON keys use signal_type, not model."""
        allowlist = build_allowlist(sample_replay_summary, 50, 0.2, 10.0, 7)
        
        # Check that all allowed groups have signal_type key
        for group in allowlist["allowed_groups"]:
            assert "signal_type" in group
            assert "model" not in group
            assert group["signal_type"] in ["bearish_bos", "bullish_choch", "choch", "bos"]

    def test_allowlist_entry_to_dict_uses_signal_type(self):
        """Verify AllowlistEntry.to_dict() uses signal_type."""
        entry = AllowlistEntry(
            symbol="EURUSD",
            timeframe="1h",
            session="london",
            signal_type="bearish_bos",
            direction="long",
        )
        d = entry.to_dict()
        assert "signal_type" in d
        assert "model" not in d
        assert d["signal_type"] == "bearish_bos"


class TestThresholdFiltering:
    """Test threshold-based filtering logic."""

    def test_sample_size_threshold(self, sample_replay_summary):
        """Verify groups below min_samples are filtered."""
        # Default min_samples=50; Group 2 has sample_size=20
        allowed = filter_groups(sample_replay_summary["groups"], 50, 0.0, 1000.0, 1000)
        
        group_keys = [g.to_key() for g in allowed]
        assert "EURUSD|1h|london|bearish_bos|long" in group_keys
        assert "EURUSD|1h|asian|bullish_choch|long" not in group_keys  # Failed size check

    def test_expectancy_threshold(self, sample_replay_summary):
        """Verify groups below min_expectancy are filtered."""
        allowed = filter_groups(sample_replay_summary["groups"], 0, 0.20, 1000.0, 1000)
        
        group_keys = [g.to_key() for g in allowed]
        assert "EURUSD|1h|london|bearish_bos|long" in group_keys  # 0.50 >= 0.20
        assert "GBPUSD|4h|newyork|bearish_bos|short" not in group_keys  # 0.05 < 0.20

    def test_max_drawdown_threshold(self, sample_replay_summary):
        """Verify groups above max_dd are filtered."""
        allowed = filter_groups(sample_replay_summary["groups"], 0, 0.0, 10.0, 1000)
        
        group_keys = [g.to_key() for g in allowed]
        assert "EURUSD|1h|london|bearish_bos|long" in group_keys  # 5.0 <= 10.0
        assert "EURUSD|4h|london|choch|long" not in group_keys  # 12.0 > 10.0

    def test_max_loss_streak_threshold(self, sample_replay_summary):
        """Verify groups above max_loss_streak are filtered."""
        allowed = filter_groups(sample_replay_summary["groups"], 0, 0.0, 1000.0, 7)
        
        group_keys = [g.to_key() for g in allowed]
        assert "EURUSD|1h|london|bearish_bos|long" in group_keys  # 3 <= 7
        assert "GBPUSD|1h|london|bos|short" not in group_keys  # 9 > 7

    def test_all_thresholds_together(self, sample_replay_summary):
        """Verify only one group passes all thresholds."""
        allowed = filter_groups(sample_replay_summary["groups"], 50, 0.20, 10.0, 7)
        
        # Only first group should pass all thresholds
        assert len(allowed) == 1
        assert allowed[0].to_key() == "EURUSD|1h|london|bearish_bos|long"


class TestDeterminism:
    """Test deterministic and reproducible behavior."""

    def test_deterministic_filtering(self, sample_replay_summary):
        """Verify same input produces same output."""
        allowed1 = filter_groups(sample_replay_summary["groups"], 50, 0.2, 10.0, 7)
        allowed2 = filter_groups(sample_replay_summary["groups"], 50, 0.2, 10.0, 7)
        
        keys1 = [g.to_key() for g in allowed1]
        keys2 = [g.to_key() for g in allowed2]
        assert keys1 == keys2

    def test_allowlist_stable_json(self, sample_replay_summary):
        """Verify JSON output is stable across multiple builds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = Path(tmpdir) / "allowlist1.json"
            path2 = Path(tmpdir) / "allowlist2.json"
            
            allowlist1 = build_allowlist(sample_replay_summary, 50, 0.2, 10.0, 7)
            allowlist2 = build_allowlist(sample_replay_summary, 50, 0.2, 10.0, 7)
            
            # Compare allowed groups (ignore timestamp)
            assert allowlist1["allowed_groups"] == allowlist2["allowed_groups"]
            assert allowlist1["total_allowed"] == allowlist2["total_allowed"]

    def test_sorted_output_order(self, sample_replay_summary):
        """Verify groups are sorted deterministically by key."""
        allowed = filter_groups(sample_replay_summary["groups"], 50, 0.2, 10.0, 7)
        
        # All groups in one pass (add more groups to sample for this test)
        # For now, just verify list is non-empty and sorted keys exist
        keys = [g.to_key() for g in allowed]
        assert len(keys) > 0
        # Verify keys are sorted
        assert keys == sorted(keys)


class TestGroupKeyConstruction:
    """Test group key format correctness."""

    def test_group_key_format(self):
        """Verify group key follows spec: symbol|timeframe|session|signal_type|direction."""
        entry = AllowlistEntry(
            symbol="EURUSD",
            timeframe="1h",
            session="london",
            signal_type="bearish_bos",
            direction="long",
        )
        
        key = entry.to_key()
        parts = key.split("|")
        
        assert len(parts) == 5
        assert parts[0] == "EURUSD"
        assert parts[1] == "1h"
        assert parts[2] == "london"
        assert parts[3] == "bearish_bos"
        assert parts[4] == "long"


class TestAllowlistMetadata:
    """Test allowlist metadata structure."""

    def test_metadata_fields_present(self, sample_replay_summary):
        """Verify all required metadata fields are present."""
        allowlist = build_allowlist(sample_replay_summary, 50, 0.2, 10.0, 7)
        
        required_keys = [
            "timestamp",
            "source_replay_summary",
            "thresholds",
            "total_allowed",
            "total_groups_evaluated",
            "allowed_groups",
        ]
        
        for key in required_keys:
            assert key in allowlist

    def test_thresholds_captured(self, sample_replay_summary):
        """Verify thresholds are recorded in output."""
        allowlist = build_allowlist(sample_replay_summary, 55, 0.25, 8.5, 6)
        
        assert allowlist["thresholds"]["min_samples"] == 55
        assert allowlist["thresholds"]["min_expectancy"] == 0.25
        assert allowlist["thresholds"]["max_drawdown_r"] == 8.5
        assert allowlist["thresholds"]["max_loss_streak"] == 6

    def test_counts_correct(self, sample_replay_summary):
        """Verify group counts are accurate."""
        allowlist = build_allowlist(sample_replay_summary, 50, 0.2, 10.0, 7)
        
        assert allowlist["total_groups_evaluated"] == 5
        assert allowlist["total_allowed"] == 1
        assert len(allowlist["allowed_groups"]) == allowlist["total_allowed"]


class TestFileLoading:
    """Test loading replay summary from file."""

    def test_load_from_file(self, sample_replay_summary):
        """Verify load_replay_summary reads JSON correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "replay_summary.json"
            with open(path, "w") as f:
                json.dump(sample_replay_summary, f)
            
            loaded = load_replay_summary(str(path))
            assert loaded["total_groups"] == 5
            assert len(loaded["groups"]) == 5

    def test_load_file_not_found(self):
        """Verify FileNotFoundError when file missing."""
        with pytest.raises(FileNotFoundError):
            load_replay_summary("/nonexistent/path/replay_summary.json")
