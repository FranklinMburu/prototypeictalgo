
<!-- starting the server -->

fuser -k 8000/tcp || true
. .venv/bin/activate && uvicorn ict_trading_system.main:app --reload --host 0.0.0.0 --port 8000

<!-- sending a test payload to webhook receive -->

curl -X POST "http://localhost:8000/api/webhook/receive" -H "Content-Type: application/json" -H "X-WEBHOOK-SECRET: ${WEBHOOK_SECRET}" --data-binary @test_payload.json