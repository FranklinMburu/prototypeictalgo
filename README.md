bash
bash
demo.py - example runner.
tests/ - pytest tests for schema, fallback, and repair.
bash
bash

# Reasoner Service

Turn fused market snapshots into validated trading decisions using an LLM with repair, deterministic fallback, async storage, and multi-channel notifications.

## Setup

1. Create a Python 3.11+ virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in your API keys, webhook URLs, and DB DSN
```

## Run demo

To build, persist, and notify a decision:

```bash
python demo.py --symbol XAUUSD --recommendation enter --bias bullish --confidence 0.82 --duration-ms 120 --summary "demo" --persist --dsn "sqlite+aiosqlite:///:memory:"
```

If you omit --slack, --discord, and --telegram flags, the demo will send to all channels by default. If you provide any specific channel flags, only those channels will be used.

## Run tests

Install dev requirements, then:

```bash
pytest -q
```

Tests mock network calls; no secrets required.

## Environment variables (see .env.example)

- `POSTGRES_URI` - async DSN for Postgres (production)
- `SLACK_WEBHOOK_URL`, `DISCORD_WEBHOOK_URL`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`
- `NOTIFY_LEVEL` - info|warn|all
- `MIN_WARN_CONFIDENCE` - default 0.7
- `REQUIRE_ALERT_ON_FALLBACK` - true|false
- `NOTIFIER_MAX_CONCURRENCY`, `NOTIFIER_HTTP_TIMEOUT`, `NOTIFIER_RETRIES`, `NOTIFIER_BACKOFF`
- `LOG_LEVEL`, `LOG_FILE`

## Features

- Async SQLAlchemy storage for Decision records and Notification logs
- Multi-channel notifiers (Slack, Discord, Telegram) with concurrency control and filtering
- CLI demo to build/persist a decision and send notifications
- Tests (pytest + pytest-asyncio) which do not make real network calls

## Security notes

- Never commit real tokens or webhook URLs.
- Protect access to logs and DB.
- For production, use secrets manager and proper IAM.
