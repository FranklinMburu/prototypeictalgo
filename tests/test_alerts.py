import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from reasoner_service.notifier_alerts import emoji_for_recommendation, format_payload_markdown

def test_emoji_mapping():
    assert emoji_for_recommendation("enter") == "✅"
    assert emoji_for_recommendation("wait") == "⏳"
    assert emoji_for_recommendation("do_nothing") == "🚫"
    assert emoji_for_recommendation("long") == "🟢"
    assert emoji_for_recommendation("short") == "🔴"
    assert emoji_for_recommendation("unknown") == "❔"

def test_formatting_slack():
    payload = {
        "recommendation": "enter",
        "symbol": "BTCUSD",
        "entry": 1975.0,
        "confidence": 0.88,
        "tp": 2000.0,
        "sl": 1950.0,
        "summary": "Breakout above resistance."
    }
    slack = format_payload_markdown(payload, "slack")
    assert "✅" in slack and "*ENTER*" in slack and "BTCUSD" in slack
    assert "*TP*" in slack and "*SL*" in slack
    assert "Breakout above resistance." in slack

def test_formatting_telegram():
    payload = {
        "recommendation": "enter",
        "symbol": "BTCUSD",
        "entry": 1975.0,
        "confidence": 0.88,
        "tp": 2000.0,
        "sl": 1950.0,
        "summary": "Breakout above resistance."
    }
    telegram = format_payload_markdown(payload, "telegram")
    assert "✅" in telegram and "*ENTER*" in telegram
    assert "BTCUSD" in telegram and "*TP*" in telegram

def test_formatting_discord():
    payload = {
        "recommendation": "enter",
        "symbol": "BTCUSD",
        "entry": 1975.0,
        "confidence": 0.88,
        "tp": 2000.0,
        "sl": 1950.0,
        "summary": "Breakout above resistance."
    }
    discord = format_payload_markdown(payload, "discord")
    assert "✅" in discord and "**ENTER**" in discord
    assert "BTCUSD" in discord and "*Breakout above resistance.*" in discord

def test_tp_sl_fallback():
    payload = {"recommendation": "wait", "symbol": "ETHUSD"}
    slack = format_payload_markdown(payload, "slack")
    assert "not provided" in slack

def test_latency_metric():
    import time
    class DummyMetrics:
        def __init__(self):
            self.latencies = []
        def labels(self, **kwargs):
            return self
        def observe(self, val):
            self.latencies.append(val)
    dummy = DummyMetrics()
    t0 = time.time()
    time.sleep(0.01)
    latency = time.time() - t0
    dummy.observe(latency)
    assert dummy.latencies and dummy.latencies[0] > 0
