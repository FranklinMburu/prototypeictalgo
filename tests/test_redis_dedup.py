import asyncio
import time
import pytest
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from reasoner_service.orchestrator import DecisionOrchestrator


class FakeRedisDedup:
    def __init__(self):
        self._set = {}

    async def set(self, key, val, ex=None, nx=False):
        # nx semantics
        if nx:
            if key in self._set:
                return False
            self._set[key] = True
            return True
        self._set[key] = True
        return True

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_redis_dedup_skips(monkeypatch):
    orch = DecisionOrchestrator(dsn=None)
    from reasoner_service.config import get_settings
    s = get_settings()
    s.REDIS_DEDUP_ENABLED = True
    s.REDIS_DEDUP_PREFIX = "dedup:"
    s.REDIS_DEDUP_TTL_SECONDS = 10

    fake = FakeRedisDedup()
    orch._redis = fake

    # two identical decisions should lead to second being deduped
    d = {"symbol": "BTCUSD", "confidence": 0.5}
    res1 = orch._normalize_decision(d)
    # compute dedup key using internal helper (sanity)
    _ = orch._compute_dedup_key(res1)

    # first set should succeed (returns True), not skipped
    from reasoner_service.config import get_settings as gs
    # call process_decision twice
    out1 = await orch.process_decision(d, persist=False)
    out2 = await orch.process_decision(d, persist=False)

    assert out1["skipped"] is False
    assert out2["skipped"] is True
 
