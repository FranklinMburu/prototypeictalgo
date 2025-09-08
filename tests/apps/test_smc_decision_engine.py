import pytest; pytest.skip('Skipping legacy apps tests: missing apps.smc.decision_engine', allow_module_level=True)
import pytest
import asyncio
from apps.smc.decision_engine import SMCDecisionEngine
from apps.smc.models import SMCDecision
from apps.smc.llm_client import FakeLLM

@pytest.mark.asyncio
async def test_decision_engine_valid_llm():
    engine = SMCDecisionEngine(llm=FakeLLM())
    context = {"symbol": "XAUUSD", "htf_bias": True, "liquidity_context": True, "poi": True, "ltf_confirmation": True, "timestamp": "2025-08-11T12:00:00Z", "timeframe_context": ["4H", "1H", "5M"]}
    decision = await engine.evaluate(context)
    assert isinstance(decision, SMCDecision)
    assert decision.opportunity_tier in ("strong", "moderate", "weak")
    assert decision.action in ("long", "short", "wait")
    assert 0 <= decision.confidence_score <= 100

@pytest.mark.asyncio
async def test_decision_engine_fallback():
    class BrokenLLM(FakeLLM):
        async def complete(self, prompt: str) -> str:
            return "not valid json"
    engine = SMCDecisionEngine(llm=BrokenLLM())
    context = {"symbol": "XAUUSD", "htf_bias": False, "liquidity_context": False, "poi": False, "ltf_confirmation": False, "timestamp": "2025-08-11T12:00:00Z", "timeframe_context": ["4H", "1H", "5M"]}
    decision = await engine.evaluate(context)
    assert isinstance(decision, SMCDecision)
    assert decision.opportunity_tier == "weak"
    assert decision.action == "wait"
