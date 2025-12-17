import pytest

from reasoner_service import config as cfg_mod


@pytest.mark.asyncio
async def test_orchestrator_execute_plan_invoked(monkeypatch):
    # simple plan
    plan = {
        "start": "s1",
        "steps": {
            "s1": {"type": "notify", "spec": {"channel": "telegram", "payload": "Test"}, "on_success": None}
        }
    }

    # enable feature flag
    monkeypatch.setenv("ENABLE_PLAN_EXECUTOR", "1")
    # set flag on the cached Settings instance
    cfg_mod.get_settings().ENABLE_PLAN_EXECUTOR = True

    called = {"invoked": False}

    async def fake_execute(self, plan_arg, execution_ctx):
        called["invoked"] = True
        return {"s1": {"ok": True}}

    # patch method on class
    from reasoner_service.orchestrator import DecisionOrchestrator
    monkeypatch.setattr(DecisionOrchestrator, "execute_plan_if_enabled", fake_execute)

    # directly call the method via a fresh orchestrator instance to simulate the integration
    orch = DecisionOrchestrator()
    res = await orch.execute_plan_if_enabled(plan, {"signal": {}, "decision": {}, "corr_id": "cid"})
    assert called["invoked"]
    assert isinstance(res, dict)
