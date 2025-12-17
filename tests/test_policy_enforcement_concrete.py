"""
Unit tests for concrete policy enforcement sources.
These tests exercise concrete veto/defer logic and the side-effects (audit counters, DLQ append).
"""

import pytest
import time

from reasoner_service import config as cfg_mod
from reasoner_service.orchestrator import DecisionOrchestrator


@pytest.mark.asyncio
async def test_concrete_killzone_veto_and_audit(monkeypatch):
    monkeypatch.setenv("ENABLE_PERMISSIVE_POLICY", "0")
    cfg_mod.get_settings().ENABLE_PERMISSIVE_POLICY = False

    orch = DecisionOrchestrator()

    snapshot = {"symbol": "TST", "killzone": True, "id": "snap1"}
    res = await orch.pre_reasoning_policy_check(snapshot)
    assert res.get("result") == "veto"
    assert res.get("reason") == "killzone"
    assert hasattr(orch, "_policy_counters") and orch._policy_counters["veto"] >= 1
    assert hasattr(orch, "_policy_audit") and any(a.get("reason") == "killzone" for a in orch._policy_audit)


@pytest.mark.asyncio
async def test_concrete_cooldown_defer_appends_dlq(monkeypatch):
    monkeypatch.setenv("ENABLE_PERMISSIVE_POLICY", "0")
    cfg_mod.get_settings().ENABLE_PERMISSIVE_POLICY = False

    orch = DecisionOrchestrator()

    future_ts = int((time.time() + 30) * 1000)
    snapshot = {"symbol": "TST", "cooldown_until": future_ts, "id": "snap2"}
    res = await orch.pre_reasoning_policy_check(snapshot)
    assert res.get("result") == "defer"
    assert res.get("reason") == "cooldown"
    # ensure DLQ entry was appended
    assert hasattr(orch, "_persist_dlq") and any(e.get("decision", {}).get("id") == "snap2" for e in orch._persist_dlq)
    assert hasattr(orch, "_policy_counters") and orch._policy_counters["defer"] >= 1