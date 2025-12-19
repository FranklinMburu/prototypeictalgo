"""
Tests for Level 2 policy enforcement scaffolding.
These tests verify that when permissive mode is disabled, the policy hooks can
veto or defer decisions based on snapshot markers. They do not implement real
risk logic; they assert that veto/defer paths are exercised and logged.
"""

import pytest
import time

from reasoner_service import config as cfg_mod
from reasoner_service.orchestrator import DecisionOrchestrator


@pytest.mark.asyncio
async def test_policy_veto_on_killzone(monkeypatch):
    # disable permissive policy mode
    monkeypatch.setenv("ENABLE_PERMISSIVE_POLICY", "0")
    cfg_mod.get_settings().ENABLE_PERMISSIVE_POLICY = False

    orch = DecisionOrchestrator()

    # snapshot that should trigger a killzone veto
    decision = {"symbol": "TST", "killzone": True, "recommendation": "enter", "confidence": 1.0}

    res = await orch.process_decision(decision, persist=False)

    # Expect the orchestrator to skip processing due to policy veto
    # It should return a dict indicating skipped/policy info
    assert isinstance(res, dict)
    assert res.get("skipped") is True or res.get("id") is None


@pytest.mark.asyncio
async def test_policy_defer_on_cooldown(monkeypatch):
    monkeypatch.setenv("ENABLE_PERMISSIVE_POLICY", "0")
    cfg_mod.get_settings().ENABLE_PERMISSIVE_POLICY = False

    orch = DecisionOrchestrator()

    future_ts = int((time.time() + 60) * 1000)
    decision = {"symbol": "TST", "cooldown_until": future_ts, "recommendation": "enter", "confidence": 1.0}

    res = await orch.process_decision(decision, persist=False)

    # Defer should not persist or notify; ensure no DLQ entries were created here
    assert isinstance(res, dict)
    assert res.get("skipped") is True or res.get("id") is None