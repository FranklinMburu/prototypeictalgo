import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from reasoner_service.orchestrator import DecisionOrchestrator


@pytest.mark.asyncio
async def test_insert_decision_sessionmaker_used():
    orch = DecisionOrchestrator()
    # simulate setup creating a sessionmaker
    fake_sessionmaker = AsyncMock()
    orch._sessionmaker = fake_sessionmaker
    # Mock insert_decision to capture the session arg
    with patch("reasoner_service.orchestrator.insert_decision", new=AsyncMock(return_value="dec123")) as mock_insert:
        res = await orch.process_decision({"symbol": "TST", "recommendation": "enter", "confidence": 0.9, "timestamp_ms": 1})
        # insert_decision should be called with sessionmaker
        assert mock_insert.await_count == 1


@pytest.mark.asyncio
async def test_persistence_dlq_on_failure():
    orch = DecisionOrchestrator()
    orch._sessionmaker = None
    # Patch insert_decision to raise
    async def fail_insert(*args, **kwargs):
        raise Exception("db down")
    with patch("reasoner_service.orchestrator.insert_decision", new=fail_insert):
        res = await orch.process_decision({"symbol": "TST", "recommendation": "enter", "confidence": 0.9, "timestamp_ms": 1})
        # After failure, in-memory DLQ should have one entry
        assert len(orch._persist_dlq) >= 1
