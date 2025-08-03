import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings

client = TestClient(app)

def test_full_signal_flow(monkeypatch):
    # Mock OpenAI and Telegram
    monkeypatch.setattr("src.services.openai_service.analyze_signal", lambda x: {"content": "AI OK", "score": 90, "explanation": "Good", "entry": "1.1000"})
    monkeypatch.setattr("src.services.telegram_service.send_telegram_alert", lambda msg, **kwargs: True)
    data = {
        "symbol": "EURUSD",
        "timeframe": "5M",
        "signal_type": "CHoCH",
        "confidence": 90,
        "price_data": {"open":1.1,"high":1.2,"low":1.0,"close":1.15},
        "sl": 1.09,
        "tp": 1.13
    }
    response = client.post(f"/api/webhook/receive?secret={settings.WEBHOOK_SECRET}", json=data)
    assert response.status_code == 200
    assert response.json()["status"] == "received"

def test_telegram_command_status():
    response = client.post("/api/telegram/command", json={"command": "/status"})
    assert response.status_code == 200
    assert response.json()["status"] == "Bot is running and ready."
