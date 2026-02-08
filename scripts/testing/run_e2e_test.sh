#!/bin/bash
# Full E2E performance test with real Gemini API key

if [ -z "$GEMINI_API_KEY" ]; then
  echo "ERROR: GEMINI_API_KEY environment variable not set"
  exit 1
fi

cd /home/franklin/SOFTWARE_ENGENEERING/Development/code/se-prep/Webportfolio/MYAI-AGENT/prototypeictalgo

echo "=========================================="
echo "ICT TRADING SYSTEM - E2E PERFORMANCE TEST"
echo "=========================================="
echo ""

# Kill any running servers
pkill -f uvicorn || true
sleep 1

# Start server with real Gemini key
echo "[1] Starting server with REAL Gemini API key..."
REASONER_PROVIDER=gemini \
EMBEDDING_PROVIDER=gemini \
GEMINI_API_KEY="$GEMINI_API_KEY" \
/home/franklin/SOFTWARE_ENGENEERING/Development/code/se-prep/Webportfolio/MYAI-AGENT/prototypeictalgo/.venv/bin/uvicorn ict_trading_system.main:app --host 0.0.0.0 --port 8000 --reload 2>&1 &

SERVER_PID=$!
sleep 3

# Send realistic trading signal
echo ""
echo "[2] Sending realistic EURUSD 4H BOS signal..."
WEBHOOK_RESPONSE=$(curl -s -X POST http://localhost:8000/api/webhook/receive \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: supersecret" \
  -d @test_signal_realistic.json)

echo "Webhook Response: $WEBHOOK_RESPONSE"
sleep 4

# Collect logs
echo ""
echo "[3] AI Analysis Results:"
echo "=========================================="
tail -n 150 ict_trading_system/logs/app.log | grep -A 10 "AI RAW RESPONSE\|AI JSON REPAIR\|Telegram alert" | head -40

echo ""
echo "[4] Full Processing Flow:"
echo "=========================================="
tail -n 200 ict_trading_system/logs/app.log | grep "REASONER FACTORY\|Gemini API\|KILLZONE\|Telegram alert sent" | tail -15

echo ""
echo "=========================================="
echo "Test Complete. Check logs for full details."
echo "Log file: $(pwd)/ict_trading_system/logs/app.log"
echo "=========================================="

# Cleanup
kill $SERVER_PID 2>/dev/null || true
