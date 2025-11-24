import sys, os
import pytest
import asyncio

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils.redis_wrapper import redis_op
from reasoner_service.orchestrator import DecisionOrchestrator


class Flaky:
    def __init__(self, fail_first=1):
        self._fail_first = fail_first

    async def incr(self, key):
        if self._fail_first > 0:
            self._fail_first -= 1
            raise Exception('boom')
        return 1

    async def ping(self):
        # ping should succeed (simulate upstream recovery)
        if self._fail_first > 0:
            self._fail_first -= 1
            raise Exception('ping fail')
        return True


@pytest.mark.asyncio
async def test_redis_op_retries(monkeypatch):
    orch = DecisionOrchestrator()
    # monkeypatch aioredis.from_url to return Flaky instance
    class M:
        def __init__(self):
            self.instance = Flaky()

        def from_url(self, url):
            return self.instance

    monkeypatch.setitem(sys.modules, 'redis.asyncio', M())

    # call redis_op which should attempt, fail once, then reconnect and retry
    res = await redis_op(orch, lambda r, k: r.incr(k), 'k')
    assert res.get('ok') is True
    assert res.get('value') == 1
