import requests
from config import settings

def test_fastapi():
    try:
        r = requests.get(f"http://localhost:{settings.PORT}/health")
        print("FastAPI health:", r.json())
    except Exception as e:
        print("FastAPI health check failed:", e)

def test_telegram():
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
    try:
        r = requests.get(url)
        print("Telegram bot:", r.json())
    except Exception as e:
        print("Telegram test failed:", e)

def test_openai():
    try:
        import openai
        openai.api_key = settings.OPENAI_API_KEY
        openai.Model.list()
        print("OpenAI: OK")
    except Exception as e:
        print("OpenAI test failed:", e)

if __name__ == "__main__":
    test_fastapi()
    test_telegram()
    test_openai()
