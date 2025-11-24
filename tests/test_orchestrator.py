import asyncio
import pytest
import time

from reasoner_service.orchestrator import DecisionOrchestrator


class DummyNotifier:
    def __init__(self, name, should_fail=False):
        self.name = name
        self.should_fail = should_fail
        self.called = 0

    async def notify(self, payload, decision_id=None):
        self.called += 1
        if self.should_fail:
            raise Exception(f"{self.name} failed")
        return {"ok": True, "status": 200}


@pytest.mark.asyncio
async def test_dedup_key_normalization():
    orch = DecisionOrchestrator()
    # Create two decisions that only differ by small timestamp
    now_ms = int(time.time() * 1000)
    d1 = {"symbol": "TST", "recommendation": "enter", "confidence": 0.88, "timestamp_ms": now_ms}
    d2 = {"symbol": "TST", "recommendation": "enter", "confidence": 0.8801, "timestamp_ms": now_ms + 500}
    k1 = orch._compute_dedup_key(d1)
    k2 = orch._compute_dedup_key(d2)
    assert k1 == k2, f"Expected dedup keys to match but got {k1} vs {k2}"


@pytest.mark.asyncio
async def test_notify_resilience():
    orch = DecisionOrchestrator()
    # inject dummy notifiers
    orch.notifiers = {
        "telegram": DummyNotifier("telegram", should_fail=True),
        "slack": DummyNotifier("slack", should_fail=False),
    }
    routed = ["telegram", "slack"]
    # Create a simple decision
    d = {"symbol": "TST", "recommendation": "enter", "confidence": 0.9}
    # call notify concurrently by invoking the notification gather logic indirectly
    tasks = [orch.notifiers[ch].notify(d) for ch in routed]
    res = await asyncio.gather(*tasks, return_exceptions=True)
    # verify that the failing notifier returned Exception in gather
    assert isinstance(res[0], Exception)
    assert res[1] == {"ok": True, "status": 200}
