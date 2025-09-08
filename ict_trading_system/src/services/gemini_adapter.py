import requests
import logging
from ict_trading_system.config import settings
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GeminiAdapter:
    """
    Adapter for Google Gemini API (AI Studio key, free tier).
    Normalizes Gemini's response to OpenAI's /v1/chat/completions format.
    """
    def __init__(self):
        self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
        # Use the latest Gemini model endpoint as per quickstart
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. GeminiAdapter will not function.")

    def chat(self, prompt: str) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }
        data = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ]
        }
        try:
            resp = requests.post(self.api_url, headers=headers, json=data, timeout=10)
            resp.raise_for_status()
            gemini = resp.json()
            # Normalize Gemini response to OpenAI format
            content = gemini.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {
                "id": gemini.get("id", "gemini-mock-id"),
                "object": "chat.completion",
                "choices": [{
                    "message": {"role": "assistant", "content": content}
                }],
                "provider": "gemini"
            }
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return {
                "id": "gemini-error",
                "object": "chat.completion",
                "choices": [{
                    "message": {"role": "assistant", "content": "Gemini API error or unavailable."}
                }],
                "provider": "gemini"
            }
