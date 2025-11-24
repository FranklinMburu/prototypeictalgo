import asyncio
import time
import pytest
import sys
import os
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from reasoner_service.orchestrator import DecisionOrchestrator


class FakeRedis:
    def __init__(self):
        self._list = []
        self.rpush_calls = 0
        self.lpop_calls = 0

    async def rpush(self, key, value):
        self.rpush_calls += 1
        self._list.append(value)

    async def lpop(self, key):
        self.lpop_calls += 1
        if not self._list:
            return None
        return self._list.pop(0)

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_redis_dlq_success(monkeypatch):
    orch = DecisionOrchestrator(dsn=None)
    from reasoner_service.config import get_settings
    s = get_settings()
    s.REDIS_DLQ_ENABLED = True
    s.REDIS_URL = "redis://unused"
    s.REDIS_DLQ_KEY = "dlq:test"

    fake = FakeRedis()
    orch._redis = fake

    call_count = {"n": 0}

    async def fake_insert(session_arg, **kwargs):
        call_count["n"] += 1
        return "ok-id"

    monkeypatch.setattr("reasoner_service.orchestrator.insert_decision", fake_insert, raising=False)

    # push one entry into fake redis
    entry = {"decision": {"symbol": "BTCUSD", "confidence": 0.5}, "ts": int(time.time()*1000), "attempts": 0, "next_attempt_ts": 0}
    await fake.rpush(s.REDIS_DLQ_KEY, json.dumps(entry))

    # run a retry once, it should LPOP and succeed
    await orch._dlq_retry_once()

    # confirm lpop was called and insert called
    assert fake.lpop_calls >= 1
    assert call_count["n"] == 1
    # list should be empty
    assert fake._list == []


@pytest.mark.asyncio
async def test_redis_dlq_failure_pushback(monkeypatch):
    orch = DecisionOrchestrator(dsn=None)
    from reasoner_service.config import get_settings
    s = get_settings()
    s.REDIS_DLQ_ENABLED = True
    s.REDIS_URL = "redis://unused"
    s.REDIS_DLQ_KEY = "dlq:test"

    fake = FakeRedis()
    orch._redis = fake

    call_count = {"n": 0}

    async def failing_insert(session_arg, **kwargs):
        call_count["n"] += 1
        raise Exception("db still down")

    monkeypatch.setattr("reasoner_service.orchestrator.insert_decision", failing_insert, raising=False)

    entry = {"decision": {"symbol": "ETHUSD", "confidence": 0.2}, "ts": int(time.time()*1000), "attempts": 0, "next_attempt_ts": 0}
    await fake.rpush(s.REDIS_DLQ_KEY, json.dumps(entry))

    # run retry once: it will lpop, attempt insert, fail, then rpush back
    await orch._dlq_retry_once()

    assert fake.lpop_calls >= 1
    # pushback should have occurred
    assert fake.rpush_calls >= 1
    # list length should be 1

    assert len(fake._list) == 1
