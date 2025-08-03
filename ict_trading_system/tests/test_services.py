import pytest
from src.services.openai_service import analyze_signal
from src.services.telegram_service import format_alert

def test_openai_prompt():
    signal = {"symbol": "EURUSD", "timeframe": "5M", "signal_type": "CHoCH", "confidence": 90, "price_data": {}}
    result = analyze_signal(signal)
    assert "content" in result

def test_telegram_format():
    signal = {"symbol": "EURUSD", "timeframe": "5M", "signal_type": "CHoCH", "confidence": 90, "sl": 1.0830, "tp": 1.0890, "session": "london"}
    ai = {"score": 87, "explanation": "Clean structure break with liquidity", "entry": "1.0850"}
    msg = format_alert(signal, ai)
    assert "HIGH CONFIDENCE SETUP" in msg
