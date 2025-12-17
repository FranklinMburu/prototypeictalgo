"""Tests for PolicyStore and policy gate integration."""

import asyncio
import pytest
from reasoner_service.orchestrator import DecisionOrchestrator, PolicyStore


@pytest.fixture
def non_permissive_orch(monkeypatch):
    """Create an orchestrator with ENABLE_PERMISSIVE_POLICY=False."""
    # Mock get_settings to return non-permissive config
    mock_cfg = type('obj', (object,), {
        'ENABLE_PERMISSIVE_POLICY': False,
        'DEDUP_WINDOW_SECONDS': 60,
        'QUIET_HOURS': None,
        'DEDUP_ENABLED': False,
        'REDIS_DEDUP_ENABLED': False,
        'REDIS_DLQ_ENABLED': False,
        'DLQ_POLL_INTERVAL_SECONDS': 5,
        'SLACK_WEBHOOK_URL': '',
        'DISCORD_WEBHOOK_URL': '',
        'TELEGRAM_TOKEN': '',
        'TELEGRAM_CHAT_ID': '',
    })()
    
    from reasoner_service import orchestrator as orch_module
    original_get_settings = orch_module.get_settings
    monkeypatch.setattr(orch_module, "get_settings", lambda: mock_cfg)
    
    orch = DecisionOrchestrator(":memory:")
    return orch


class TestPolicyStore:
    """Unit tests for PolicyStore interface and fallback behavior."""

    def test_policy_store_initialization(self):
        """PolicyStore should initialize with orchestrator reference."""
        orch = DecisionOrchestrator(":memory:")
        assert orch.policy_store is not None
        assert isinstance(orch.policy_store, PolicyStore)
        assert orch.policy_store.orch is orch

    @pytest.mark.asyncio
    async def test_get_policy_killzone_marker_fallback(self):
        """PolicyStore should fall back to killzone marker when no config."""
        orch = DecisionOrchestrator(":memory:")
        ps = orch.policy_store

        # Test with killzone marker active
        policy = await ps.get_policy("killzone", {"killzone": True})
        assert policy == {"active": True}

        # Test with killzone marker inactive
        policy = await ps.get_policy("killzone", {"killzone": False})
        assert policy == {"active": False}

        # Test with no killzone marker
        policy = await ps.get_policy("killzone", {})
        assert policy == {"active": False}

    @pytest.mark.asyncio
    async def test_get_policy_regime_marker_fallback(self):
        """PolicyStore should fall back to regime marker."""
        orch = DecisionOrchestrator(":memory:")
        ps = orch.policy_store

        # Test with regime marker
        policy = await ps.get_policy("regime", {"regime": "restricted"})
        assert policy == {"regime": "restricted"}

        # Test with no regime marker
        policy = await ps.get_policy("regime", {})
        assert policy == {"regime": None}

    @pytest.mark.asyncio
    async def test_get_policy_cooldown_marker_fallback(self):
        """PolicyStore should fall back to cooldown marker."""
        orch = DecisionOrchestrator(":memory:")
        ps = orch.policy_store

        # Test with cooldown marker
        policy = await ps.get_policy("cooldown", {"cooldown_until": 1700000000000})
        assert policy == {"cooldown_until": 1700000000000}

        # Test with no cooldown marker
        policy = await ps.get_policy("cooldown", {})
        assert policy == {"cooldown_until": 0}

    @pytest.mark.asyncio
    async def test_get_policy_exposure_marker_fallback(self):
        """PolicyStore should fall back to exposure/max_exposure markers."""
        orch = DecisionOrchestrator(":memory:")
        ps = orch.policy_store

        # Test with both markers
        policy = await ps.get_policy("exposure", {"exposure": 50.5, "max_exposure": 100.0})
        assert policy == {"exposure": 50.5, "max_exposure": 100.0}

        # Test with no markers
        policy = await ps.get_policy("exposure", {})
        assert policy == {"exposure": 0.0, "max_exposure": 0.0}

    @pytest.mark.asyncio
    async def test_get_policy_confidence_threshold_default(self):
        """PolicyStore should return default confidence threshold."""
        orch = DecisionOrchestrator(":memory:")
        ps = orch.policy_store

        policy = await ps.get_policy("confidence_threshold", {})
        assert policy == {"min_confidence": 0.5}

    @pytest.mark.asyncio
    async def test_get_policy_unknown_policy_returns_empty(self):
        """PolicyStore should return empty dict for unknown policy names."""
        orch = DecisionOrchestrator(":memory:")
        ps = orch.policy_store

        policy = await ps.get_policy("unknown_policy", {"data": "value"})
        assert policy == {}

    @pytest.mark.asyncio
    async def test_get_policy_orchestrator_config_precedence(self):
        """PolicyStore should use orchestrator._policy_config if present."""
        orch = DecisionOrchestrator(":memory:")
        ps = orch.policy_store

        # Set custom policy config on orchestrator
        orch._policy_config = {
            "killzone": {"active": True, "reason": "maintenance"},
            "exposure": {"exposure": 25.0, "max_exposure": 75.0},
        }

        # PolicyStore should use config instead of markers
        policy = await ps.get_policy("killzone", {"killzone": False})
        assert policy == {"active": True, "reason": "maintenance"}

        policy = await ps.get_policy("exposure", {"exposure": 50.0, "max_exposure": 100.0})
        assert policy == {"exposure": 25.0, "max_exposure": 75.0}


class TestPolicyGateIntegration:
    """Integration tests for policy gates consulting PolicyStore."""

    @pytest.mark.asyncio
    async def test_pre_reasoning_policy_check_killzone_veto(self, non_permissive_orch):
        """Pre-reasoning hook should veto on killzone via PolicyStore."""
        orch = non_permissive_orch
        # Set up killzone policy config
        orch._policy_config = {"killzone": {"active": True}}

        decision = {"id": "test1", "symbol": "AAPL", "killzone": False}
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "veto"
        assert result["reason"] == "killzone"
        assert orch._policy_counters["veto"] == 1
        assert len(orch._policy_audit) == 1
        assert orch._policy_audit[0]["reason"] == "killzone"

    @pytest.mark.asyncio
    async def test_pre_reasoning_policy_check_regime_restricted(self, non_permissive_orch):
        """Pre-reasoning hook should veto on restricted regime."""
        orch = non_permissive_orch

        decision = {"id": "test2", "symbol": "AAPL", "regime": "restricted"}
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "veto"
        assert result["reason"] == "regime_restricted"
        assert orch._policy_counters["veto"] == 1

    @pytest.mark.asyncio
    async def test_pre_reasoning_policy_check_cooldown_defer(self, non_permissive_orch):
        """Pre-reasoning hook should defer on active cooldown."""
        orch = non_permissive_orch
        import time

        future_ms = int(time.time() * 1000) + 60000  # 60 seconds in future
        decision = {"id": "test3", "symbol": "AAPL", "cooldown_until": future_ms}
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "defer"
        assert result["reason"] == "cooldown"
        assert orch._policy_counters["defer"] == 1
        # Should append to DLQ
        assert len(orch._persist_dlq) == 1

    @pytest.mark.asyncio
    async def test_pre_reasoning_policy_check_exposure_veto(self, non_permissive_orch):
        """Pre-reasoning hook should veto on exposure exceeded."""
        orch = non_permissive_orch

        decision = {"id": "test4", "symbol": "AAPL", "exposure": 100.0, "max_exposure": 50.0}
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "veto"
        assert result["reason"] == "risk_limit_exceeded"
        assert orch._policy_counters["veto"] == 1
        assert len(orch._policy_audit) == 1
        entry = orch._policy_audit[0]
        assert entry["exposure"] == 100.0
        assert entry["max_exposure"] == 50.0

    @pytest.mark.asyncio
    async def test_pre_reasoning_policy_check_pass_on_clear(self, non_permissive_orch):
        """Pre-reasoning hook should pass when all checks clear."""
        orch = non_permissive_orch

        decision = {
            "id": "test5",
            "symbol": "AAPL",
            "killzone": False,
            "regime": "normal",
            "exposure": 50.0,
            "max_exposure": 100.0,
        }
        result = await orch.pre_reasoning_policy_check(decision)

        assert result["result"] == "pass"
        assert orch._policy_counters["pass"] == 1
        assert orch._policy_counters["veto"] == 0
        assert orch._policy_counters["defer"] == 0

    @pytest.mark.asyncio
    async def test_post_reasoning_policy_check_low_confidence_veto(self, non_permissive_orch):
        """Post-reasoning hook should veto on low confidence enter."""
        orch = non_permissive_orch

        reasoning = {"id": "test6", "recommendation": "enter", "confidence": 0.3}
        result = await orch.post_reasoning_policy_check(reasoning)

        assert result["result"] == "veto"
        assert result["reason"] == "low_confidence"
        assert orch._policy_counters["veto"] == 1

    @pytest.mark.asyncio
    async def test_post_reasoning_policy_check_high_confidence_pass(self, non_permissive_orch):
        """Post-reasoning hook should pass on high confidence enter."""
        orch = non_permissive_orch

        reasoning = {"id": "test7", "recommendation": "enter", "confidence": 0.8}
        result = await orch.post_reasoning_policy_check(reasoning)

        assert result["result"] == "pass"
        assert orch._policy_counters["pass"] == 1

    @pytest.mark.asyncio
    async def test_post_reasoning_policy_check_custom_confidence_threshold(self, non_permissive_orch):
        """Post-reasoning hook should respect custom confidence threshold."""
        orch = non_permissive_orch
        orch._policy_config = {"confidence_threshold": {"min_confidence": 0.8}}

        reasoning = {"id": "test8", "recommendation": "enter", "confidence": 0.7}
        result = await orch.post_reasoning_policy_check(reasoning)

        assert result["result"] == "veto"
        assert result["reason"] == "low_confidence"
        assert orch._policy_counters["veto"] == 1

    @pytest.mark.asyncio
    async def test_post_reasoning_policy_check_do_nothing_recommendation_passes(self, non_permissive_orch):
        """Post-reasoning hook should pass on do_nothing recommendation."""
        orch = non_permissive_orch

        reasoning = {"id": "test9", "recommendation": "do_nothing", "confidence": 0.1}
        result = await orch.post_reasoning_policy_check(reasoning)

        assert result["result"] == "pass"
        assert orch._policy_counters["pass"] == 1

    @pytest.mark.asyncio
    async def test_policy_counters_accumulate(self, non_permissive_orch):
        """Policy counters should accumulate across multiple checks."""
        orch = non_permissive_orch

        # First check: pass
        await orch.pre_reasoning_policy_check({"killzone": False})
        assert orch._policy_counters == {"pass": 1, "veto": 0, "defer": 0}

        # Second check: veto
        await orch.pre_reasoning_policy_check({"killzone": True})
        assert orch._policy_counters == {"pass": 1, "veto": 1, "defer": 0}

        # Third check: defer
        import time
        future_ms = int(time.time() * 1000) + 60000
        await orch.pre_reasoning_policy_check({"cooldown_until": future_ms})
        assert orch._policy_counters == {"pass": 1, "veto": 1, "defer": 1}

    @pytest.mark.asyncio
    async def test_policy_audit_trail(self, non_permissive_orch):
        """Policy audit trail should record all enforcement actions."""
        orch = non_permissive_orch

        # Veto action
        await orch.pre_reasoning_policy_check({"id": "dec1", "killzone": True})
        # Pass action
        await orch.pre_reasoning_policy_check({"id": "dec2", "killzone": False})

        assert len(orch._policy_audit) == 1
        audit_entry = orch._policy_audit[0]
        assert audit_entry["action"] == "veto"
        assert audit_entry["reason"] == "killzone"
        assert audit_entry["id"] == "dec1"
        assert "ts" in audit_entry

    @pytest.mark.asyncio
    async def test_permissive_mode_bypasses_all_checks(self):
        """When ENABLE_PERMISSIVE_POLICY=True, all checks should pass."""
        orch = DecisionOrchestrator(":memory:")

        # All conditions would normally fail
        decision = {
            "id": "test10",
            "killzone": True,
            "regime": "restricted",
            "exposure": 200.0,
            "max_exposure": 50.0,
        }

        # With permissive mode enabled (default), should still pass
        result = await orch.pre_reasoning_policy_check(decision)
        assert result["result"] == "pass"
        assert orch._policy_counters["veto"] == 0

        # Same for post-reasoning
        reasoning = {"id": "test10", "recommendation": "enter", "confidence": 0.1}
        result = await orch.post_reasoning_policy_check(reasoning)
        assert result["result"] == "pass"
        assert orch._policy_counters["veto"] == 0


class TestPolicyStoreWithMockedBackend:
    """Tests that simulate a custom PolicyStore backend."""

    @pytest.mark.asyncio
    async def test_custom_policy_backend_injection(self, non_permissive_orch):
        """Tests should be able to inject custom policy backends."""
        orch = non_permissive_orch

        # Create a custom policy store that always vetoes
        class VetoingPolicyStore(PolicyStore):
            async def get_policy(self, policy_name: str, context: dict) -> dict:
                if policy_name == "killzone":
                    return {"active": True}  # Always active
                return await super().get_policy(policy_name, context)

        orch.policy_store = VetoingPolicyStore(orch, backends=[])

        # Now pre-reasoning should veto
        result = await orch.pre_reasoning_policy_check({})
        assert result["result"] == "veto"
        assert result["reason"] == "killzone"

    @pytest.mark.asyncio
    async def test_permissive_policy_store_injection(self):
        """Tests should be able to inject a permissive policy backend."""
        orch = DecisionOrchestrator(":memory:")

        # Create a permissive policy store that always passes
        class PermissivePolicyStore(PolicyStore):
            async def get_policy(self, policy_name: str, context: dict) -> dict:
                # Return safe defaults for all policies
                if policy_name == "killzone":
                    return {"active": False}
                if policy_name == "regime":
                    return {"regime": "normal"}
                if policy_name == "cooldown":
                    return {"cooldown_until": 0}
                if policy_name == "exposure":
                    return {"exposure": 0.0, "max_exposure": float("inf")}
                return await super().get_policy(policy_name, context)

        orch.policy_store = PermissivePolicyStore(orch)

        # Even with dangerous markers, should pass
        decision = {
            "killzone": True,
            "regime": "restricted",
            "exposure": 1000.0,
            "max_exposure": 1.0,
        }
        result = await orch.pre_reasoning_policy_check(decision)
        assert result["result"] == "pass"
