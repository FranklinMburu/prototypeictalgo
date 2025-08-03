import time
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_webhook_performance():
    data = {"symbol": "EURUSD", "timeframe": "5M", "signal_type": "CHoCH", "confidence": 90, "price_data": {}}
    start = time.time()
    for _ in range(10):
        response = client.post("/api/webhook/receive?secret=test", json=data)
    elapsed = time.time() - start
    assert elapsed < 2, f"Webhook response time too slow: {elapsed}s"
