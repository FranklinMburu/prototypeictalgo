import asyncio
import time
import pytest
import sys, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from reasoner_service.orchestrator import DecisionOrchestrator


class FlakyRedis:
    def __init__(self, fail_times=2):
        self._fail = fail_times
        self.created = False

    def ping_calls(self):
        return getattr(self, '_pings', 0)

    async def ping(self):
        self._pings = getattr(self, '_pings', 0) + 1
        if self._fail > 0:
            self._fail -= 1
            raise Exception('ping fail')
        return True

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_ensure_redis_retries_then_succeeds(monkeypatch):
    orch = DecisionOrchestrator()
    # monkeypatch aioredis.from_url to return a FlakyRedis instance
    class FakeAR:
        def __init__(self, fail_times):
            # return the same underlying instance so failures count down across attempts
            self.instance = FlakyRedis(fail_times=fail_times)

        def from_url(self, url):
            return self.instance

    fake_mod = FakeAR(fail_times=2)
    monkeypatch.setitem(sys.modules, 'redis.asyncio', fake_mod)

    # call ensure_redis: it should try, fail twice, then succeed
    await orch._ensure_redis(max_attempts=5, base_delay=0.01)
    # if _redis is set, the ping eventually succeeded
    assert orch._redis is not None


@pytest.mark.asyncio
async def test_ensure_redis_opens_circuit_on_exhaust(monkeypatch):
    orch = DecisionOrchestrator()
    # always failing redis
    class FakeAR2:
        def from_url(self, url):
            class Bad:
                async def ping(self):
                    raise Exception('down')
                async def close(self):
                    pass
            return Bad()

    monkeypatch.setitem(sys.modules, 'redis.asyncio', FakeAR2())
    # short cooldown
    orch._redis_circuit_open_until = 0
    await orch._ensure_redis(max_attempts=2, base_delay=0.01)
    # after exhausting attempts, _redis should be None and circuit_open_until set > now
    assert orch._redis is None
    assert orch._redis_circuit_open_until > time.time()
