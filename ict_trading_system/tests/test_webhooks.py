import pytest
from fastapi.testclient import TestClient
from main import app
from config import settings

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_webhook_invalid_secret():
    response = client.post("/api/webhook/receive?secret=wrong", json={})
    assert response.status_code == 403

def test_webhook_low_confidence():
    data = {"symbol": "EURUSD", "timeframe": "5M", "signal_type": "CHoCH", "confidence": 50, "price_data": {}}
    response = client.post(f"/api/webhook/receive?secret={settings.WEBHOOK_SECRET}", json=data)
    assert response.status_code == 200
    assert response.json()["detail"] == "Low confidence, ignored."
