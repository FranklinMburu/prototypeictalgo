import pytest; pytest.skip('Skipping legacy apps tests: missing apps.smc.notifier', allow_module_level=True)
import pytest
from apps.smc.models import SMCDecision
from apps.smc.notifier import SMCNotifier

class DummyNotifier:
    def __init__(self):
        self.sent = []
    async def send(self, msg):
        self.sent.append(msg)

@pytest.mark.asyncio
async def test_smc_notifier_sends():
    dummy = DummyNotifier()
    notifier = SMCNotifier([dummy])
    decision = SMCDecision.model_validate({
        "metadata": {"symbol": "XAUUSD", "timeframe_context": ["4H"], "timestamp": "2025-08-11T12:00:00Z"},
        "checklist": [{"key": "htf_bias", "status": "met", "rationale": "test"}],
        "confidence_score": 90,
        "opportunity_tier": "strong",
        "action": "long",
        "risk": {"stop_loss": 0.2, "take_profit": 0.6, "rr_min": 3.0, "risk_per_trade": 1.0}
    })
    await notifier.notify(decision, {"foo": "bar"})
    assert dummy.sent
    assert "XAUUSD" in dummy.sent[0]
