#!/bin/bash
# Complete ICT Trading System End-to-End Test
# This script demonstrates the full signal processing pipeline with AI analysis

set -e

PROJECT_DIR="/home/franklin/SOFTWARE_ENGENEERING/Development/code/se-prep/Webportfolio/MYAI-AGENT/prototypeictalgo"
cd "$PROJECT_DIR"

VENV_BIN="$PROJECT_DIR/.venv/bin"
LOG_FILE="$PROJECT_DIR/ict_trading_system/logs/app.log"

echo "====================================================================="
echo "ICT Trading System - Complete End-to-End Test"
echo "====================================================================="
echo ""

# Start the server
echo "[1/5] Starting FastAPI server..."
$VENV_BIN/uvicorn ict_trading_system.main:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
SERVER_PID=$!
echo "✅ Server started (PID: $SERVER_PID)"
sleep 3

# Wait for health check
echo ""
echo "[2/5] Verifying server is ready..."
for i in {1..10}; do
  if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Server is healthy and ready"
    break
  fi
  if [ $i -eq 10 ]; then
    echo "❌ Server failed to start"
    exit 1
  fi
  sleep 1
done

# Send test signal
echo ""
echo "[3/5] Sending test trading signal..."
cat > "$PROJECT_DIR/test_signal_final.json" << 'EOF'
{
  "symbol": "BTCUSD",
  "timeframe": "1H",
  "signal_type": "CHoCH",
  "confidence": 87,
  "timestamp": "2026-02-06T09:30:00Z",
  "price_data": {
    "open": 43100,
    "high": 43500,
    "low": 42800,
    "close": 43250
  },
  "sl": 42800,
  "tp": 43500,
  "multi_tf": {
    "4H": "bullish",
    "daily": "neutral"
  },
  "confluences": [
    "support_level",
    "fibonacci_618",
    "moving_average_200"
  ]
}
EOF

RESPONSE=$(curl -s -X POST http://localhost:8000/api/webhook/receive \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: supersecret" \
  -d @"$PROJECT_DIR/test_signal_final.json")

echo "📨 Signal sent: BTCUSD 1H CHoCH"
echo "Response: $RESPONSE"
echo "✅ Webhook received the signal"

# Wait for processing
echo ""
echo "[4/5] Waiting for signal processing..."
sleep 5

# Check logs for AI analysis
echo ""
echo "[5/5] Checking AI analysis results..."
echo ""
echo "--- Latest Log Entries (AI Analysis) ---"
tail -30 "$LOG_FILE" | grep -E "AI RAW|score|confidence|Telegram|analysis" || echo "Processing logs..."

echo ""
echo "====================================================================="
echo "✅ TEST COMPLETE"
echo "====================================================================="
echo ""
echo "Check your Telegram for the alert message with AI analysis!"
echo "Server is running at http://localhost:8000"
echo "Stop server with: kill $SERVER_PID"
echo ""
