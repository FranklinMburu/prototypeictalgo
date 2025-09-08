"""Tests fallback path when LLM not available or returns invalid."""

import pytest
import asyncio
from reasoner_service.reasoner import reason_from_snapshot
from reasoner_service.llm_client import LLMClient
from unittest.mock import patch

@pytest.mark.asyncio
async def test_reasoner_uses_fallback_on_llm_error(monkeypatch):
    # Prepare snapshot missing price etc.
    snap = {"symbol": "TEST", "snapshot_ts": 1, "alignment_score": 0.4, "cohesion": 0.4, "tfs": [] , "analytics": {"volatility_index": 0.2}}
    # Force LLMClient.complete to raise
    class DummyLLM:
        async def complete(self, _):
            raise RuntimeError("LLM down")
    llm = DummyLLM()
    decision = await reason_from_snapshot(snap, llm=llm)
    assert decision["recommendation"] in {"do_nothing", "wait_for_breakout", "enter"}
    assert "summary" in decision

@pytest.mark.asyncio
async def test_reasoner_fallback_valid_schema(monkeypatch):
    snap = {"symbol": "TWO", "snapshot_ts": 2, "alignment_score": 0.9, "cohesion": 0.8, "tfs": [{"tf":"D","bias_local":"bullish"}], "analytics": {"volatility_index": 0.1}}
    class DummyLLM:
        async def complete(self, _):
            raise RuntimeError("LLM down")
    llm = DummyLLM()
    decision = await reason_from_snapshot(snap, llm=llm)
    # ensure decision valid and includes required keys
    assert decision["symbol"] == "TWO"
    assert "confidence" in decision
