import requests
import os

def send_telegram_message(message: str) -> bool:
    """
    Sends a message to a Telegram chat using a bot token and chat ID from environment variables.
    Returns True if successful, False otherwise.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("Telegram bot token or chat ID not set in environment.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            print(f"Telegram error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False

import logging
import asyncio
import requests
from ict_trading_system.config import settings
from typing import Dict, Any
import time

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"

async def send_telegram_alert(message: str, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
    chat_ids = str(settings.TELEGRAM_CHAT_ID).split(",")
    all_success = True
    for chat_id in chat_ids:
        chat_id = chat_id.strip().split()[0]  # Remove comments and whitespace
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        logger.info(f"[TELEGRAM DEBUG] Bot token: {settings.TELEGRAM_BOT_TOKEN}")
        logger.info(f"[TELEGRAM DEBUG] Chat ID: {chat_id} (type: {type(chat_id)})")
        logger.info(f"[TELEGRAM DEBUG] Message: {message}")
        sent = False
        for attempt in range(1, max_retries + 1):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: requests.post(TELEGRAM_API_URL, json=data, timeout=10))
                if response.status_code == 200:
                    logger.info(f"Telegram alert sent to {chat_id} (attempt {attempt}).")
                    sent = True
                    break
                else:
                    logger.error(f"Telegram error for {chat_id} (attempt {attempt}): {response.text}")
            except Exception as e:
                logger.error(f"Telegram send error for {chat_id} (attempt {attempt}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
        if not sent:
            all_success = False
    return all_success

def format_alert(signal: Dict[str, Any], ai_analysis: Dict[str, Any]) -> str:
    conf = ai_analysis.get('score', signal.get('confidence', 0))
    reason = ai_analysis.get('explanation', 'AI analysis unavailable.')
    entry = ai_analysis.get('entry', 'N/A')
    sl = signal.get('sl', 'N/A')
    tp = signal.get('tp', 'N/A')
    session = signal.get('session', 'Unknown')
    return (
        f"🟢 <b>HIGH CONFIDENCE SETUP</b>\n"
        f"📊 <b>{signal['symbol']} | {signal['timeframe']} {signal['signal_type']}</b>\n"
        f"🎯 Entry: <b>{entry}</b> | SL: <b>{sl}</b> | TP: <b>{tp}</b>\n"
        f"🧠 AI: <b>{conf}% confidence</b> - {reason}\n"
        f"⏰ {session.title()} Killzone Active"
    )

def get_bot_status() -> str:
    return "Bot is running and ready."

def get_bot_stats() -> Dict[str, Any]:
    # Example: return dummy stats, replace with real stats as needed
    return {
        "alerts_sent": 0,  # Replace with real count
        "last_alert_time": "N/A"
    }

def get_bot_settings() -> Dict[str, Any]:
    return {
        "min_confidence_score": settings.MIN_CONFIDENCE_SCORE,
        "max_daily_signals": settings.MAX_DAILY_SIGNALS,
        "active_sessions": settings.ACTIVE_SESSIONS
    }
