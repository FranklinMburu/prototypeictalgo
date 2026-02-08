import requests
import sys
import os
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import settings

logger = logging.getLogger(__name__)

def test_fastapi():
    try:
        r = requests.get(f"http://localhost:{settings.PORT}/health")
        logger.info(f"FastAPI health: {r.json()}")
    except Exception as e:
        logger.error(f"FastAPI health check failed: {e}")

def test_telegram():
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
    try:
        r = requests.get(url)
        logger.info(f"Telegram bot: {r.json()}")
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")

def test_openai():
    try:
        import openai
        openai.api_key = settings.OPENAI_API_KEY
        openai.Model.list()
        logger.info("OpenAI: OK")
    except Exception as e:
        logger.error(f"OpenAI test failed: {e}")

if __name__ == "__main__":
    test_fastapi()
    test_telegram()
    test_openai()
