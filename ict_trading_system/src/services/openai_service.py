
import openai
import logging
from config import settings
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
    return cached_gpt_analysis(prompt)
