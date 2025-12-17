import asyncio
import types
import pytest

from reasoner_service.plan_executor import PlanExecutor, ExecutionContext


class FakeOrch:
    def __init__(self):
        self._notify_calls = []
        self._dlq_calls = []
        async def reasoner_call(prompt, signal, decision):
            return {"signal_ok": True}
        # expose as orch.reasoner.call
        self.reasoner = types.SimpleNamespace(call=reasoner_call)

    async def notify(self, channel, payload, ctx):
        self._notify_calls.append((channel, payload))
        return {"ok": True}

    async def publish_to_dlq(self, payload):
        self._dlq_calls.append(payload)


@pytest.mark.asyncio
async def test_basic_plan():
    orch = FakeOrch()
    pe = PlanExecutor(orch)
    plan = {
        "start": "s1",
        "steps": {
            "s1": {"type": "call_ai", "spec": {"prompt": "p1"}, "on_success": "s2", "on_failure": None},
            "s2": {"type": "eval", "spec": {"expr": "results['s1']['signal_ok'] == True"}, "on_success": "s3", "on_failure": None},
            "s3": {"type": "notify", "spec": {"channel": "telegram", "payload": "Signal OK: {results[s1][signal_ok]}"}, "on_success": None}
        }
    }
    ctx = ExecutionContext(orch=orch, signal={"symbol": "EURUSD"}, decision={}, corr_id="cid-1")
    res = await pe.run_plan(plan, ctx)
    assert "s1" in res
    assert "s2" in res
    assert "s3" in res
    # notify was called once
    assert len(orch._notify_calls) == 1
    ch, payload = orch._notify_calls[0]
    assert ch == "telegram"
    assert "Signal OK" in payload


@pytest.mark.asyncio
async def test_retry_on_failure():
    calls = {"count": 0}

    class RetryOrch:
        def __init__(self):
            async def reasoner_call(prompt, signal, decision):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise Exception("simulated transient")
                return {"signal_ok": True}
            self.reasoner = types.SimpleNamespace(call=reasoner_call)
            self._notify_calls = []
            async def notify(channel, payload, ctx):
                self._notify_calls.append((channel, payload))
            self.notify = notify

    orch = RetryOrch()
    pe = PlanExecutor(orch)
    plan = {
        "start": "s1",
        "steps": {
            "s1": {"type": "call_ai", "spec": {"prompt": "p1"}, "on_success": None, "on_failure": None, "retries": 2},
        }
    }
    ctx = ExecutionContext(orch=orch, signal={}, decision={}, corr_id="cid-2")
    res = await pe.run_plan(plan, ctx)
    assert calls["count"] == 2
    assert "s1" in res


@pytest.mark.asyncio
async def test_timeout_moves_to_on_failure():
    class SlowOrch:
        def __init__(self):
            async def reasoner_call(prompt, signal, decision):
                await asyncio.sleep(0.2)
                return {"ok": True}
            self.reasoner = types.SimpleNamespace(call=reasoner_call)
            self._notify_calls = []
            async def notify(channel, payload, ctx):
                self._notify_calls.append((channel, payload))
            self.notify = notify

    orch = SlowOrch()
    pe = PlanExecutor(orch)
    plan = {
        "start": "s1",
        "steps": {
            "s1": {"type": "call_ai", "spec": {"prompt": "p1"}, "on_success": None, "on_failure": "sfail", "timeout_s": 0.05},
            "sfail": {"type": "notify", "spec": {"channel": "telegram", "payload": "Failed"}, "on_success": None}
        }
    }
    ctx = ExecutionContext(orch=orch, signal={}, decision={}, corr_id="cid-3")
    res = await pe.run_plan(plan, ctx)
    # sfail should have been executed and present in results
    assert "sfail" in ctx.results
