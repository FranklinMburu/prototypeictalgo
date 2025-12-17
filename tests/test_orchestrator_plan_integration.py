"""
Integration tests verifying PlanExecutor is invoked by DecisionOrchestrator.run_from_queue
when a queued item contains a `plan` entry. Tests are minimal and non-invasive.
"""

import asyncio
import pytest

from reasoner_service.orchestrator import DecisionOrchestrator


@pytest.mark.asyncio
async def test_run_from_queue_invokes_planexecutor(monkeypatch):
    orch = DecisionOrchestrator()

    called = {"pe": False, "processed_decision": None}

    async def fake_execute_plan(plan, ctx):
        called["pe"] = True
        return {"ok": True, "executed": True}

    async def fake_process(decision, persist=True, channels=None):
        # capture the decision that reaches process_decision
        called["processed_decision"] = dict(decision)
        return {"id": None, "skipped": False, "notify_results": {}}

    # attach fakes
    orch.execute_plan_if_enabled = fake_execute_plan
    orch.process_decision = fake_process

    q = asyncio.Queue()
    stop = asyncio.Event()

    item = {"plan": {"name": "demo"}, "execution_ctx": {"signal": {}, "decision": {}, "corr_id": "c1"}, "symbol": "TST"}
    await q.put(item)

    # run orchestrator loop in background
    task = asyncio.create_task(orch.run_from_queue(q, stop))

    # wait for the item to be processed
    await q.join()
    # stop the run loop
    stop.set()
    await task

    assert called["pe"] is True
    assert called["processed_decision"] is not None
    # The processed decision should have the plan result attached by the orchestrator
    assert "_plan_result" in called["processed_decision"]
    assert called["processed_decision"]["_plan_result"].get("ok") is True


@pytest.mark.asyncio
async def test_run_from_queue_planexecutor_error_triggers_dlq_and_notify(monkeypatch):
    orch = DecisionOrchestrator()

    # make execute raise
    async def raise_execute(plan, ctx):
        raise RuntimeError("plan failed")

    published = []
    notified = []

    async def fake_publish(payload):
        published.append(payload)
        return True

    async def fake_notify(channel, payload, ctx=None):
        notified.append((channel, payload))
        return {"ok": False}

    async def fake_process(decision, persist=True, channels=None):
        return {"id": None, "skipped": False, "notify_results": {}}

    orch.execute_plan_if_enabled = raise_execute
    orch.publish_to_dlq = fake_publish
    orch.notify = fake_notify
    orch.process_decision = fake_process

    q = asyncio.Queue()
    stop = asyncio.Event()

    item = {"plan": {"name": "demo"}, "execution_ctx": {"signal": {}, "decision": {}, "corr_id": "c1"}, "symbol": "TST"}
    await q.put(item)

    task = asyncio.create_task(orch.run_from_queue(q, stop))
    await q.join()
    stop.set()
    await task

    # publish_to_dlq should have been called
    assert len(published) >= 1
    # notify should have been called (best-effort)
    assert any(n[0] == "slack" for n in notified)
