
import openai
import logging
from ict_trading_system.config import settings
from functools import lru_cache
from typing import Dict, Any
import time
import threading

logger = logging.getLogger(__name__)

# Token usage tracking
total_tokens_used = 0
token_lock = threading.Lock()

# Simple rate limiting (max 60 requests per minute)
rate_limit = 60
rate_window = 60  # seconds
request_times = []

def rate_limited():
    now = time.time()
    # Remove requests outside the window
    while request_times and now - request_times[0] > rate_window:
        request_times.pop(0)
    if len(request_times) >= rate_limit:
        return True
    request_times.append(now)
    return False

@lru_cache(maxsize=256)
def cached_gpt_analysis(prompt: str) -> Dict[str, Any]:
    global total_tokens_used
    # Mock response if OPENAI_API_KEY is set to 'mock'
    if getattr(settings, 'OPENAI_API_KEY', None) == "mock":
        logger.info("Using mock OpenAI response.")
        return {
            "content": "{\"score\": 88, \"risk\": \"medium\", \"entry\": \"Buy above 43200\", \"exit\": \"Take profit at 43500, stop loss at 42800\", \"explanation\": \"This is a mock AI analysis.\"}",
            "usage": 0
        }
    if rate_limited():
        logger.warning("OpenAI rate limit reached. Try again later.")
        return {"content": "Rate limit reached. Try again later.", "usage": 0}
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You are a professional trading analyst."},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=512
        )
        usage = response.usage.total_tokens if hasattr(response, 'usage') else 0
        with token_lock:
            total_tokens_used += usage
        content = response.choices[0].message.content
        return {"content": content, "usage": usage}
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return {"content": "AI analysis unavailable.", "usage": 0}

def get_total_tokens_used() -> int:
    with token_lock:
        return total_tokens_used

def analyze_signal(signal_data: dict) -> Dict[str, Any]:
    prompt = f"""
    Evaluate the following trading setup:
    Symbol: {signal_data['symbol']}
    Timeframe: {signal_data['timeframe']}
    Signal Type: {signal_data['signal_type']}
    Confidence: {signal_data['confidence']}
    Price Data: {signal_data['price_data']}

    1. Score setup quality (1-100)
    2. Risk assessment
    3. Entry/exit recommendations
    4. Plain English explanation
    Respond in JSON: {{'score': int, 'risk': str, 'entry': str, 'exit': str, 'explanation': str}}
    """
    from ict_trading_system.src.services.reasoner_factory import ReasonerFactory
    reasoner = ReasonerFactory.create()
    response = reasoner.chat(prompt)
    # Normalize response to expected dict
    if isinstance(response, dict):
        # GeminiAdapter returns dict
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    else:
        # OpenAIAdapter returns ReasonerResponse
        content = getattr(response, "text", "")
    import json
    import re
    logger = logging.getLogger(__name__)
    logger.info(f"[AI RAW RESPONSE] {content}")
    try:
        parsed = json.loads(content)
        return parsed
    except Exception:
        # Try to extract JSON substring using regex
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group(0)
            try:
                parsed = json.loads(json_str)
                logger.info("[AI JSON REPAIR] Successfully extracted JSON from response.")
                return parsed
            except Exception as e2:
                logger.warning(f"[AI JSON REPAIR] Failed to parse extracted JSON: {e2}")
        logger.warning("[AI JSON REPAIR] Could not extract valid JSON from response.")
        return {"content": content, "score": 0, "risk": "unknown", "entry": "N/A", "exit": "N/A", "explanation": content}
