"""
Tests for AllowlistPolicyGate integration.

Verifies:
- Allowlist loader creates deterministic group keys
- Policy gate vetoes groups not in allowlist
- Policy gate allows groups in allowlist
- Fail-open behavior when file is missing
- Proper logging and audit trail
- Deterministic behavior (same input → same veto/pass)
"""

import json
import pytest
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

from reasoner_service.orchestrator import DecisionOrchestrator
from reasoner_service.allowlist_loader import AllowlistLoader


@pytest.fixture
def sample_allowlist_data():
    """Create sample allowlist JSON data."""
    return {
        "timestamp": "2026-02-13T00:00:00Z",
        "source_replay_summary": "2026-02-13T00:00:00Z",
        "thresholds": {
            "min_samples": 50,
            "min_expectancy": 0.2,
            "max_drawdown_r": 10.0,
            "max_loss_streak": 7,
        },
        "total_allowed": 2,
        "total_groups_evaluated": 9,
        "allowed_groups": [
            {
                "symbol": "EURUSD",
                "timeframe": "1h",
                "session": "london",
                "signal_type": "bearish_bos",
                "direction": "long",
            },
            {
                "symbol": "GBPUSD",
                "timeframe": "4h",
                "session": "newyork",
                "signal_type": "bullish_choch",
                "direction": "short",
            },
        ],
    }


@pytest.fixture
def allowlist_file(sample_allowlist_data):
    """Create temporary allowlist JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "allowlist.json"
        with open(path, "w") as f:
            json.dump(sample_allowlist_data, f)
        yield str(path)


@pytest.fixture
def orch_with_allowlist(allowlist_file):
    """Create orchestrator with allowlist enabled."""
    orch = DecisionOrchestrator()
    orch._constraints = {
        "allowlist": {"enabled": True, "path": allowlist_file}
    }
    return orch


def disable_permissive_policy():
    """Context manager to disable permissive policy for tests."""
    mock_cfg = MagicMock()
    mock_cfg.ENABLE_PERMISSIVE_POLICY = False
    return patch("reasoner_service.orchestrator.get_settings", return_value=mock_cfg)


class TestAllowlistLoaderBasic:
    """Test AllowlistLoader construction and key generation."""

    def test_make_key_from_components(self):
        """Verify group key construction from components."""
        key = AllowlistLoader._make_key(
            symbol="EURUSD",
            timeframe="1h",
            session="london",
            signal_type="bearish_bos",
            direction="long",
        )
        assert key == "EURUSD|1h|london|bearish_bos|long"

    def test_make_key_missing_field_returns_none(self):
        """Verify None returned when any field missing."""
        key = AllowlistLoader._make_key(
            symbol="EURUSD",
            timeframe="1h",
            session=None,  # Missing
            signal_type="bearish_bos",
            direction="long",
        )
        assert key is None

    def test_make_key_from_snapshot(self):
        """Verify convenience method makes key from snapshot."""
        snapshot = {
            "symbol": "GBPUSD",
            "timeframe": "4h",
            "session": "newyork",
            "signal_type": "bullish_choch",
            "direction": "short",
        }
        key = AllowlistLoader.make_key_from_snapshot(snapshot)
        assert key == "GBPUSD|4h|newyork|bullish_choch|short"

    def test_make_key_from_snapshot_missing_field(self):
        """Verify None when snapshot missing required field."""
        snapshot = {
            "symbol": "EURUSD",
            "timeframe": "1h",
            # Missing session
            "signal_type": "bearish_bos",
            "direction": "long",
        }
        key = AllowlistLoader.make_key_from_snapshot(snapshot)
        assert key is None


class TestAllowlistLoaderFileIO:
    """Test file loading and caching."""

    def test_load_valid_json(self, sample_allowlist_data):
        """Verify loader reads and caches valid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "allowlist.json"
            with open(path, "w") as f:
                json.dump(sample_allowlist_data, f)

            loader = AllowlistLoader()
            success = loader.load(str(path))
            assert success
            assert loader.is_enabled()

    def test_load_missing_file_returns_false(self):
        """Verify fail-open: returns False if file missing."""
        loader = AllowlistLoader()
        success = loader.load("/nonexistent/path/allowlist.json")
        assert not success
        assert not loader.is_enabled()

    def test_load_invalid_json(self):
        """Verify fail-open: returns False on invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "bad.json"
            with open(path, "w") as f:
                f.write("{invalid json}")

            loader = AllowlistLoader()
            success = loader.load(str(path))
            assert not success
            assert not loader.is_enabled()

    def test_cached_keys_deterministic(self, sample_allowlist_data):
        """Verify same file → same cached keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "allowlist.json"
            with open(path, "w") as f:
                json.dump(sample_allowlist_data, f)

            loader1 = AllowlistLoader(str(path))
            loader2 = AllowlistLoader(str(path))

            keys1 = loader1.get_allowed_keys()
            keys2 = loader2.get_allowed_keys()
            assert keys1 == keys2


class TestAllowlistLoaderQuery:
    """Test allowlist membership queries."""

    def test_is_allowed_returns_true(self, allowlist_file):
        """Verify is_allowed returns True for allowed key."""
        loader = AllowlistLoader(allowlist_file)
        key = "EURUSD|1h|london|bearish_bos|long"
        assert loader.is_allowed(key)

    def test_is_allowed_returns_false(self, allowlist_file):
        """Verify is_allowed returns False for non-allowed key."""
        loader = AllowlistLoader(allowlist_file)
        key = "XAUUSD|1h|london|bearish_bos|long"  # Not in allowlist
        assert not loader.is_allowed(key)

    def test_is_enabled_false_before_load(self):
        """Verify is_enabled returns False initially."""
        loader = AllowlistLoader()
        assert not loader.is_enabled()

    def test_is_enabled_true_after_load(self, allowlist_file):
        """Verify is_enabled returns True after successful load."""
        loader = AllowlistLoader(allowlist_file)
        assert loader.is_enabled()


class TestAllowlistPolicyGate:
    """Test integration with DecisionOrchestrator."""

    @pytest.mark.asyncio
    async def test_veto_not_in_allowlist(self, orch_with_allowlist):
        """Verify policy gate vetoes trades not in allowlist."""
        snapshot = {
            "id": "test-001",
            "symbol": "XAUUSD",  # Not in allowlist
            "timeframe": "1h",
            "session": "london",
            "signal_type": "bearish_bos",
            "direction": "long",
        }
        
        with disable_permissive_policy():
            result = await orch_with_allowlist.pre_reasoning_policy_check(snapshot)
            assert result["result"] == "veto"
            assert result["reason"] == "not_in_allowlist"
            assert orch_with_allowlist._policy_counters["veto"] == 1

    @pytest.mark.asyncio
    async def test_pass_in_allowlist(self, orch_with_allowlist):
        """Verify policy gate allows trades in allowlist."""
        snapshot = {
            "id": "test-002",
            "symbol": "EURUSD",  # In allowlist
            "timeframe": "1h",
            "session": "london",
            "signal_type": "bearish_bos",
            "direction": "long",
        }
        
        result = await orch_with_allowlist.pre_reasoning_policy_check(snapshot)
        assert result["result"] == "pass"
        assert orch_with_allowlist._policy_counters["veto"] == 0

    @pytest.mark.asyncio
    async def test_fail_open_no_file(self):
        """Verify policy gate does not veto if file missing (fail-open)."""
        orch = DecisionOrchestrator()
        orch._constraints = {
            "allowlist": {"enabled": True, "path": "/nonexistent/allowlist.json"}
        }
        
        snapshot = {
            "id": "test-003",
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "session": "london",
            "signal_type": "bearish_bos",
            "direction": "long",
        }
        
        result = await orch.pre_reasoning_policy_check(snapshot)
        # Fail-open: should pass even though file missing and group not checked
        assert result["result"] == "pass"
        assert orch._policy_counters["veto"] == 0

    @pytest.mark.asyncio
    async def test_disabled_gate_does_not_veto(self, allowlist_file):
        """Verify disabled gate does not veto even if group not allowed."""
        orch = DecisionOrchestrator()
        orch._constraints = {
            "allowlist": {"enabled": False, "path": allowlist_file}  # Disabled
        }
        
        snapshot = {
            "id": "test-004",
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "session": "london",
            "signal_type": "bearish_bos",
            "direction": "long",
        }
        
        result = await orch.pre_reasoning_policy_check(snapshot)
        assert result["result"] == "pass"
        assert orch._policy_counters["veto"] == 0

    @pytest.mark.asyncio
    async def test_missing_snapshot_field_does_not_crash(self, orch_with_allowlist):
        """Verify gate handles missing snapshot fields gracefully."""
        snapshot = {
            "id": "test-005",
            "symbol": "EURUSD",
            # Missing other fields
        }
        
        result = await orch_with_allowlist.pre_reasoning_policy_check(snapshot)
        # Should not crash, should pass (cannot determine group key)
        assert result["result"] == "pass"

    @pytest.mark.asyncio
    async def test_policy_audit_logged(self, orch_with_allowlist):
        """Verify veto is logged in audit trail."""
        snapshot = {
            "id": "test-006",
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "session": "london",
            "signal_type": "bearish_bos",
            "direction": "long",
        }
        
        with disable_permissive_policy():
            result = await orch_with_allowlist.pre_reasoning_policy_check(snapshot)
            assert result["result"] == "veto"
            
            # Verify audit entry
            audit_entries = [e for e in orch_with_allowlist._policy_audit if e.get("reason") == "not_in_allowlist"]
            assert len(audit_entries) >= 1
            assert audit_entries[0]["action"] == "veto"
            assert audit_entries[0]["id"] == "test-006"


class TestAllowlistDeterminism:
    """Test deterministic behavior."""

    @pytest.mark.asyncio
    async def test_deterministic_veto(self, orch_with_allowlist):
        """Verify same snapshot → same veto result."""
        snapshot = {
            "id": "test-007",
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "session": "london",
            "signal_type": "bearish_bos",
            "direction": "long",
        }
        
        with disable_permissive_policy():
            result1 = await orch_with_allowlist.pre_reasoning_policy_check(snapshot)
            result2 = await orch_with_allowlist.pre_reasoning_policy_check(snapshot)
            
            assert result1 == result2
            assert result1["result"] == "veto"

    @pytest.mark.asyncio
    async def test_deterministic_pass(self, orch_with_allowlist):
        """Verify same snapshot → same pass result."""
        snapshot = {
            "id": "test-008",
            "symbol": "EURUSD",
            "timeframe": "1h",
            "session": "london",
            "signal_type": "bearish_bos",
            "direction": "long",
        }
        
        result1 = await orch_with_allowlist.pre_reasoning_policy_check(snapshot)
        result2 = await orch_with_allowlist.pre_reasoning_policy_check(snapshot)
        
        assert result1 == result2
        assert result1["result"] == "pass"


class TestAllowlistMetadata:
    """Test allowlist metadata access."""

    def test_get_thresholds(self, allowlist_file):
        """Verify thresholds are accessible."""
        loader = AllowlistLoader(allowlist_file)
        thresholds = loader.get_thresholds()
        
        assert thresholds["min_samples"] == 50
        assert thresholds["min_expectancy"] == 0.2
        assert thresholds["max_drawdown_r"] == 10.0
        assert thresholds["max_loss_streak"] == 7

    def test_get_metadata(self, allowlist_file):
        """Verify metadata is accessible."""
        loader = AllowlistLoader(allowlist_file)
        metadata = loader.get_metadata()
        
        assert metadata["total_allowed"] == 2
        assert metadata["total_groups_evaluated"] == 9

    def test_get_allowed_keys_returns_copy(self, allowlist_file):
        """Verify get_allowed_keys returns frozen copy."""
        loader = AllowlistLoader(allowlist_file)
        keys1 = loader.get_allowed_keys()
        keys2 = loader.get_allowed_keys()
        
        # Should be equal but separate frozensets
        assert keys1 == keys2
        assert isinstance(keys1, frozenset)
