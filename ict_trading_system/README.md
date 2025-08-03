# ICT Trading System

## Quick Start Guide

1. **Clone the repository**
2. **Install Python 3.9+ and dependencies**
3. **Copy `.env.example` to `.env` and fill in your keys**
4. **Run database setup:**
   ```bash
   python scripts/setup_database.py
   ```
5. **Start the FastAPI server:**
   ```bash
   uvicorn main:app --reload
   ```
6. **Set up TradingView Pine Script (see `pine_script/installation_guide.md`)
7. **Configure your Telegram bot**
8. **Test connections:**
   ```bash
   python scripts/test_connections.py
   ```

---

## Prerequisites and Installation
- Python 3.9+
- TradingView account
- OpenAI API key
- Telegram bot token

## TradingView Pine Script Setup
See `pine_script/installation_guide.md` for step-by-step instructions.

## API Key Configuration
- Copy `.env.example` to `.env` and fill in all required fields.

## Telegram Bot Setup
- Create a bot with @BotFather
- Add your bot token and chat ID to `.env`

## Running the Application
- Use `uvicorn main:app --reload` for development
- For production, use a process manager (e.g., systemd, pm2)

## Testing Instructions
- Run all tests with `pytest`

## Troubleshooting Guide
- Check `logs/` for errors
- Ensure all environment variables are set
- Use `/health` endpoint for health checks

## Performance Monitoring
- Logs are rotated and stored in `logs/`
- Use `/health` endpoint for uptime

## Upgrade and Maintenance
- Use Alembic for database migrations
- Backup `trading_system.db` regularly

---

## Code Documentation
- All modules and functions are documented with docstrings and type hints
- See `src/` for API and service documentation


## API Endpoints & Docs
- `/api/webhook` - TradingView webhook
- `/api/telegram` - Telegram bot commands
- `/health` - Health check
- [Full API & Schema Docs](docs/API.md)
- [Swagger/OpenAPI UI](http://localhost:8000/docs) (when running)

## Troubleshooting & Maintenance
- See [docs/API.md](docs/API.md#troubleshooting) for troubleshooting
- See [docs/API.md](docs/API.md#upgrade--maintenance) for upgrade/maintenance

---

## License
MIT
