"""
Test that the policy gate hooks are invoked during the orchestrator's decision cycle.

This test verifies the scaffolding points exist and are called. It intentionally
does not assert any policy outcomes or change orchestration behavior.
"""

import pytest

from reasoner_service.orchestrator import DecisionOrchestrator


@pytest.mark.asyncio
async def test_policy_gates_called_during_process(monkeypatch):
    orch = DecisionOrchestrator()

    called = []

    def pre(snapshot, state=None, ctx=None):
        called.append(("pre", snapshot.get("symbol")))
        return {"result": "pass"}

    def post(output, state=None, ctx=None):
        called.append(("post", output.get("symbol")))
        return {"result": "pass"}

    # attach hooks
    orch.pre_reasoning_policy_check = pre
    orch.post_reasoning_policy_check = post

    # run a short decision through the orchestrator (no persistence)
    decision = {"symbol": "TST", "recommendation": "enter", "confidence": 0.9}
    res = await orch.process_decision(decision, persist=False)

    # hooks should have been called in order
    assert any(c[0] == "pre" for c in called), "pre hook was not called"
    assert any(c[0] == "post" for c in called), "post hook was not called"

    # Ensure no behavior change: the result still contains notify_results
    assert isinstance(res, dict)
    assert "notify_results" in res
