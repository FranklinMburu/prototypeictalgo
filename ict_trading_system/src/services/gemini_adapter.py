import requests
import logging
import time
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
        # Use the required Gemini model endpoint (gemini-2.5-flash) and pass API key as query param
        # Per project constraints: use exactly gemini-2.5-flash
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}" if self.api_key else None
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not set. GeminiAdapter will not function.")

    def chat(self, prompt: str) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
        }
        data = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ]
        }
        
        # Retry logic with exponential backoff for rate limiting
        max_retries = 3
        base_delay = 1  # Start with 1 second
        
        for attempt in range(max_retries):
            try:
                resp = requests.post(self.api_url, headers=headers, json=data, timeout=15)
                
                # Handle 429 rate limit with exponential backoff
                if resp.status_code == 429:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                        logger.warning(f"Gemini API rate limited. Retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Gemini API rate limited after {max_retries} retries")
                
                # Log and surface non-200 bodies for troubleshooting
                if resp.status_code != 200:
                    body = resp.text
                    logger.error(f"Gemini non-200 response: status={resp.status_code} body={body}")
                    resp.raise_for_status()

                gemini = resp.json()
                # Robustly extract text from candidates[0].content.parts[0].text
                content = ""
                try:
                    candidates = gemini.get("candidates", [])
                    if candidates and isinstance(candidates, list):
                        first = candidates[0]
                        content_obj = first.get("content", {})
                        parts = content_obj.get("parts", []) if isinstance(content_obj, dict) else []
                        if parts and isinstance(parts, list):
                            content = parts[0].get("text", "") or ""
                except Exception as ex:
                    logger.warning(f"Failed to extract Gemini text: {ex} | full_response={gemini}")
                return {
                    "id": gemini.get("id", "gemini-mock-id"),
                    "object": "chat.completion",
                    "choices": [{
                        "message": {"role": "assistant", "content": content}
                    }],
                    "provider": "gemini"
                }
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Gemini API timeout. Retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Gemini API timeout after {max_retries} retries")
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                break
        
        # Return error response if all retries failed
        return {
            "id": "gemini-error",
            "object": "chat.completion",
            "choices": [{
                "message": {"role": "assistant", "content": "Gemini API error or unavailable."}
            }],
            "provider": "gemini"
        }
