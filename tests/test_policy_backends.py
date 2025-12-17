"""Tests for PolicyBackend implementations."""

import pytest
import json
from reasoner_service.policy_backends import (
    PolicyBackend,
    DefaultPolicyBackend,
    OrchestratorConfigBackend,
    ChainedPolicyBackend,
    RedisPolicyBackend,
)
from reasoner_service.orchestrator import DecisionOrchestrator


class TestDefaultPolicyBackend:
    """Tests for DefaultPolicyBackend (marker fallback)."""

    @pytest.mark.asyncio
    async def test_default_backend_killzone(self):
        """DefaultPolicyBackend should read killzone marker."""
        backend = DefaultPolicyBackend()

        policy = await backend.get_policy("killzone", {"killzone": True})
        assert policy == {"active": True}

        policy = await backend.get_policy("killzone", {})
        assert policy == {"active": False}

    @pytest.mark.asyncio
    async def test_default_backend_all_policies(self):
        """DefaultPolicyBackend should support all standard policy names."""
        backend = DefaultPolicyBackend()

        context = {
            "killzone": True,
            "regime": "restricted",
            "cooldown_until": 1700000000000,
            "exposure": 50.0,
            "max_exposure": 100.0,
        }

        assert await backend.get_policy("killzone", context) == {"active": True}
        assert await backend.get_policy("regime", context) == {"regime": "restricted"}
        assert await backend.get_policy("cooldown", context) == {
            "cooldown_until": 1700000000000
        }
        assert await backend.get_policy("exposure", context) == {
            "exposure": 50.0,
            "max_exposure": 100.0,
        }
        assert await backend.get_policy("confidence_threshold", context) == {
            "min_confidence": 0.5
        }


class TestOrchestratorConfigBackend:
    """Tests for OrchestratorConfigBackend."""

    @pytest.mark.asyncio
    async def test_orchestrator_config_backend_reads_config(self):
        """OrchestratorConfigBackend should read from _policy_config."""
        orch = DecisionOrchestrator(":memory:")
        orch._policy_config = {
            "killzone": {"active": True, "reason": "maintenance"},
            "exposure": {"exposure": 10.0, "max_exposure": 50.0},
        }
        backend = OrchestratorConfigBackend(orch)

        policy = await backend.get_policy("killzone", {})
        assert policy == {"active": True, "reason": "maintenance"}

        policy = await backend.get_policy("exposure", {})
        assert policy == {"exposure": 10.0, "max_exposure": 50.0}

    @pytest.mark.asyncio
    async def test_orchestrator_config_backend_empty_when_no_config(self):
        """OrchestratorConfigBackend should return empty dict when no config."""
        orch = DecisionOrchestrator(":memory:")
        backend = OrchestratorConfigBackend(orch)

        policy = await backend.get_policy("killzone", {})
        assert policy == {}

    @pytest.mark.asyncio
    async def test_orchestrator_config_backend_partial_config(self):
        """OrchestratorConfigBackend should work with partial config."""
        orch = DecisionOrchestrator(":memory:")
        orch._policy_config = {"killzone": {"active": False}}
        backend = OrchestratorConfigBackend(orch)

        # Config has killzone
        policy = await backend.get_policy("killzone", {})
        assert policy == {"active": False}

        # Config doesn't have exposure
        policy = await backend.get_policy("exposure", {})
        assert policy == {}


class TestChainedPolicyBackend:
    """Tests for ChainedPolicyBackend (fallback chain)."""

    @pytest.mark.asyncio
    async def test_chained_backend_tries_first_then_fallback(self):
        """ChainedPolicyBackend should use first non-empty result."""
        orch = DecisionOrchestrator(":memory:")
        orch._policy_config = {"killzone": {"active": True}}

        # Chain: config backend first, then default
        backend = ChainedPolicyBackend(
            OrchestratorConfigBackend(orch),
            DefaultPolicyBackend(),
        )

        # Should get from config backend
        policy = await backend.get_policy("killzone", {"killzone": False})
        assert policy == {"active": True}

        # Should fall back to default when config doesn't have it
        policy = await backend.get_policy("regime", {"regime": "restricted"})
        assert policy == {"regime": "restricted"}

    @pytest.mark.asyncio
    async def test_chained_backend_empty_on_complete_miss(self):
        """ChainedPolicyBackend should return empty when all backends miss."""

        class EmptyBackend(PolicyBackend):
            async def get_policy(self, policy_name: str, context: dict) -> dict:
                return {}

        backend = ChainedPolicyBackend(EmptyBackend(), EmptyBackend())

        policy = await backend.get_policy("unknown", {})
        assert policy == {}

    @pytest.mark.asyncio
    async def test_chained_backend_skips_exceptions(self):
        """ChainedPolicyBackend should skip backends that raise exceptions."""

        class FailingBackend(PolicyBackend):
            async def get_policy(self, policy_name: str, context: dict) -> dict:
                raise RuntimeError("Connection failed")

        class WorkingBackend(PolicyBackend):
            async def get_policy(self, policy_name: str, context: dict) -> dict:
                return {"result": "ok"}

        backend = ChainedPolicyBackend(FailingBackend(), WorkingBackend())

        # Should skip failing backend and use working one
        policy = await backend.get_policy("test", {})
        assert policy == {"result": "ok"}


class TestRedisBackend:
    """Tests for RedisPolicyBackend."""

    @pytest.mark.asyncio
    async def test_redis_backend_initialization(self):
        """RedisPolicyBackend should initialize without errors."""
        backend = RedisPolicyBackend("redis://localhost:6379")
        assert backend.redis_url == "redis://localhost:6379"
        assert backend.key_prefix == "policy:"
        assert backend.ttl == 300

    @pytest.mark.asyncio
    async def test_redis_backend_custom_settings(self):
        """RedisPolicyBackend should accept custom settings."""
        backend = RedisPolicyBackend(
            "redis://localhost:6380", key_prefix="custom:", ttl=600
        )
        assert backend.redis_url == "redis://localhost:6380"
        assert backend.key_prefix == "custom:"
        assert backend.ttl == 600

    @pytest.mark.asyncio
    async def test_redis_backend_graceful_failure(self):
        """RedisPolicyBackend should gracefully handle connection failures."""
        # Intentionally use invalid Redis URL
        backend = RedisPolicyBackend("redis://invalid-host:9999")

        # Should return empty dict rather than raise
        policy = await backend.get_policy("test", {})
        assert policy == {}


class TestPolicyStoreWithBackends:
    """Tests for PolicyStore using pluggable backends."""

    def test_policy_store_default_backends(self):
        """PolicyStore should initialize with default backends."""
        orch = DecisionOrchestrator(":memory:")
        ps = orch.policy_store

        assert len(ps.backends) == 2
        # First should be OrchestratorConfigBackend, second DefaultPolicyBackend
        assert ps.backends[0].__class__.__name__ == "OrchestratorConfigBackend"
        assert ps.backends[1].__class__.__name__ == "DefaultPolicyBackend"

    def test_policy_store_custom_backends(self):
        """PolicyStore should accept custom backends."""

        class CustomBackend(PolicyBackend):
            async def get_policy(self, policy_name: str, context: dict) -> dict:
                return {"custom": True}

        orch = DecisionOrchestrator(":memory:")
        custom = CustomBackend()
        ps = PolicyStore(orch, backends=[custom])

        assert len(ps.backends) == 1
        assert ps.backends[0] is custom

    @pytest.mark.asyncio
    async def test_policy_store_orchestrator_config_takes_precedence(self):
        """PolicyStore should prefer orchestrator config over markers."""
        orch = DecisionOrchestrator(":memory:")
        orch._policy_config = {"killzone": {"active": True}}

        context = {"killzone": False}
        policy = await orch.policy_store.get_policy("killzone", context)

        # Should get config value, not marker
        assert policy == {"active": True}

    @pytest.mark.asyncio
    async def test_policy_store_marker_fallback_when_no_config(self):
        """PolicyStore should fall back to markers when no config."""
        orch = DecisionOrchestrator(":memory:")
        # No _policy_config set

        context = {"regime": "restricted"}
        policy = await orch.policy_store.get_policy("regime", context)

        # Should get marker value
        assert policy == {"regime": "restricted"}

    @pytest.mark.asyncio
    async def test_policy_store_chained_resolution(self):
        """PolicyStore should resolve policies through backend chain."""

        class FirstBackend(PolicyBackend):
            async def get_policy(self, policy_name: str, context: dict) -> dict:
                if policy_name == "killzone":
                    return {"active": True}
                return {}

        class SecondBackend(PolicyBackend):
            async def get_policy(self, policy_name: str, context: dict) -> dict:
                if policy_name == "regime":
                    return {"regime": "restricted"}
                return {}

        orch = DecisionOrchestrator(":memory:")
        ps = PolicyStore(orch, backends=[FirstBackend(), SecondBackend()])

        # Should get from first backend
        policy = await ps.get_policy("killzone", {})
        assert policy == {"active": True}

        # Should get from second backend
        policy = await ps.get_policy("regime", {})
        assert policy == {"regime": "restricted"}

        # Should get empty for unknown
        policy = await ps.get_policy("unknown", {})
        assert policy == {}
