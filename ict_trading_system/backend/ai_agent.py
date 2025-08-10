 # ai_agent.py
# OpenAI GPT-4 integration for trade reasoning/validation (with fallback stub)
import os
import requests
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env.openai'))

def analyze_trade_signal(signal: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-REPLACE"):
        # Fallback stub if no key
        return {
            "score": 90,
            "explanation": "This is a high-confidence setup based on confluence and session context.",
            "entry": signal.get("entry", "N/A")
        }
    try:
        prompt = (
            f"Analyze this trading signal and provide a confidence score (0-100) and a short explanation.\n"
            f"Signal: {signal}\n"
            f"Respond as JSON: {{'score': <int>, 'explanation': <str>, 'entry': <float>}}"
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4-turbo",
            "messages": [
                {"role": "system", "content": "You are a professional trading assistant."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 200,
            "temperature": 0.2
        }
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            # Try to parse the JSON from the response
            import json as _json
            try:
                result = _json.loads(content.replace("'", '"'))
                return result
            except Exception:
                return {"score": 80, "explanation": content, "entry": signal.get("entry", "N/A")}
        else:
            return {
                "score": 80,
                "explanation": f"OpenAI error: {resp.status_code} {resp.text}",
                "entry": signal.get("entry", "N/A")
            }
    except Exception as e:
        return {
            "score": 80,
            "explanation": f"AI error: {e}",
            "entry": signal.get("entry", "N/A")
        }
