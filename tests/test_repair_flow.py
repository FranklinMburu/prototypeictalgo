"""Test the repair flow by simulating a malformed LLM output corrected by repair."""

import pytest
import asyncio
import json
from reasoner_service.reasoner import reason_from_snapshot
from reasoner_service.llm_client import LLMClient
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_repair_flow(monkeypatch):
    snap = {"symbol": "X1", "snapshot_ts": 3, "alignment_score": 0.8, "cohesion": 0.7, "tfs": [{"tf":"D","bias_local":"bullish"}], "analytics": {"volatility_index": 0.2}}
    # Simulate LLM returning invalid JSON first, then repair returns valid JSON
    bad_output = "This is not JSON"
    valid_decision = {
        "symbol": "X1", "snapshot_ts_ms": 3, "bias": "bullish", "confidence": 0.85,
        "recommendation": "enter",
        "triggers": {"entry_condition": "x", "take_profits": [1.0], "stop_loss": 0.5},
        "drivers": ["d1"], "caveats": [], "summary": "ok", "versions": {"reasoner_version": "v1.0.0", "strategy_version": "sma_bias_v0"}
    }
    class DummyLLM:
        async def complete(self, _):
            return bad_output
        async def repair(self, _):
            return json.dumps(valid_decision)
    llm = DummyLLM()
    decision = await reason_from_snapshot(snap, llm=llm)
    assert decision["symbol"] == "X1"
    assert decision["recommendation"] == "enter"
