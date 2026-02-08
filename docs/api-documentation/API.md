# API Documentation

## Health Check
- **GET** `/health`
  - Returns: `{ "status": "ok" }`

## Webhook Endpoint
- **POST** `/api/webhook/receive?secret=...`
  - Body: JSON signal payload (see below)
  - Returns: `{ "status": "received" }` or error
  - Security: Requires correct `secret` query param
  - Example payload:
    ```json
    {
      "symbol": "EURUSD",
      "timeframe": "5M",
      "signal_type": "CHoCH",
      "confidence": 90,
      "price_data": {"open":1.1,"high":1.2,"low":1.0,"close":1.15},
      "sl": 1.09,
      "tp": 1.13
    }
    ```

## Telegram Bot Endpoint
- **POST** `/api/telegram/command`
  - Body: `{ "command": "/status" | "/stats" | "/settings" }`
  - Returns: status, stats, or settings JSON

---

# Database Schema

## signals
- id: int (PK)
- symbol: str
- timeframe: str
- signal_type: str
- confidence: int
- raw_data: text
- timestamp: datetime

## analysis
- id: int (PK)
- signal_id: int (FK)
- gpt_analysis: text
- confidence_score: int
- recommendation: text
- timestamp: datetime

## trades
- id: int (PK)
- signal_id: int (FK)
- entry_price: float
- sl: float
- tp: float
- outcome: str
- pnl: float
- notes: text
- timestamp: datetime

## settings
- id: int (PK)
- key: str
- value: str
- description: text
- timestamp: datetime

---

# Troubleshooting
- Check `logs/app.log` for errors
- Use `/health` endpoint to verify server status
- Ensure all environment variables are set in `.env`
- For database issues, run Alembic migrations: `alembic upgrade head`

# Upgrade & Maintenance
- Update dependencies: `pip install -r requirements.txt`
- Run new Alembic migrations after model changes
- Backup `trading_system.db` regularly
- Rotate logs in `logs/` as needed

---

# OpenAPI/Swagger
- Visit `/docs` or `/redoc` when server is running for interactive API docs
