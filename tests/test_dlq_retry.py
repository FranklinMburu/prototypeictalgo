import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch
import sys
import os

# ensure repo root is on sys.path for isolated test runs
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from reasoner_service.orchestrator import DecisionOrchestrator


@pytest.mark.asyncio
async def test_dlq_retry_success(monkeypatch):
    orch = DecisionOrchestrator(dsn=None)
    from reasoner_service.config import get_settings
    s = get_settings()
    s.DLQ_ENABLED = True
    s.DLQ_BASE_DELAY_SECONDS = 0.01
    s.DLQ_MAX_DELAY_SECONDS = 0.05
    s.DLQ_MAX_RETRIES = 3
    s.DLQ_POLL_INTERVAL_SECONDS = 0.01

    call_count = {"n": 0}

    async def fake_insert(session_arg, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise Exception("simulated db down")
        return 12345

    monkeypatch.setattr("reasoner_service.orchestrator.insert_decision", fake_insert, raising=False)

    decision = {"symbol": "BTCUSD", "confidence": 0.5, "timestamp_ms": int(time.time()*1000)}
    async with orch._dlq_lock:
        orch._persist_dlq.append({"decision": decision, "error": "init", "ts": int(time.time()*1000), "attempts": 0, "next_attempt_ts": 0.0})

    deadline = time.time() + 5.0
    while time.time() < deadline:
        await orch._dlq_retry_once()
        async with orch._dlq_lock:
            if not orch._persist_dlq:
                break
        await asyncio.sleep(0.01)

    async with orch._dlq_lock:
        assert orch._persist_dlq == []
    assert call_count["n"] >= 3


@pytest.mark.asyncio
async def test_dlq_retry_exhaust(monkeypatch):
    orch = DecisionOrchestrator(dsn=None)
    from reasoner_service.config import get_settings
    s = get_settings()
    s.DLQ_ENABLED = True
    s.DLQ_BASE_DELAY_SECONDS = 0.01
    s.DLQ_MAX_DELAY_SECONDS = 0.02
    s.DLQ_MAX_RETRIES = 2
    s.DLQ_POLL_INTERVAL_SECONDS = 0.01

    async def always_fail(session_arg, **kwargs):
        raise Exception("still down")

    monkeypatch.setattr("reasoner_service.orchestrator.insert_decision", always_fail, raising=False)

    decision = {"symbol": "ETHUSD", "confidence": 0.2, "timestamp_ms": int(time.time()*1000)}
    async with orch._dlq_lock:
        orch._persist_dlq.append({"decision": decision, "error": "init", "ts": int(time.time()*1000), "attempts": 0, "next_attempt_ts": 0.0})

    deadline = time.time() + 5.0
    while time.time() < deadline:
        await orch._dlq_retry_once()
        async with orch._dlq_lock:
            if not orch._persist_dlq:
                break
        await asyncio.sleep(0.01)

    async with orch._dlq_lock:
        assert orch._persist_dlq == []
