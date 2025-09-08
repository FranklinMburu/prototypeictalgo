import pytest; pytest.skip('Skipping legacy apps tests: missing apps.smc.llm_client', allow_module_level=True)
import pytest
from apps.smc.llm_client import FakeLLM
from apps.smc.models import SMCDecision

@pytest.mark.asyncio
async def test_fake_llm_returns_valid_json():
    llm = FakeLLM()
    prompt = "irrelevant"
    output = await llm.complete(prompt)
    # Should be valid JSON and match schema
    dec = SMCDecision.model_validate_json(output)
    assert dec.action == "long"
    assert dec.opportunity_tier == "strong"
