
import logging
import asyncio
import httpx
from typing import Optional, Dict, Any, List

def escape_markdown_v2(text: str) -> str:
    """
    Escapes special characters for Telegram MarkdownV2.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, engine=None, logger: Optional[logging.Logger] = None):
        self.token = token
        self.chat_id = chat_id
        self.engine = engine
        self.logger = logger or logging.getLogger("telegram_notifier")

    async def notify(self, decision: Dict[str, Any], decision_id: Optional[Any] = None) -> Dict[str, Any]:
        """
        Sends a Telegram message using the Bot API. Handles MarkdownV2 escaping, retries, and logs errors.
        """
        bot_token = self.token
        chat_ids = [self.chat_id] if isinstance(self.chat_id, str) else list(self.chat_id)
        message = decision.get("summary") or str(decision)
        parse_mode = "MarkdownV2"
        max_retries = 3
        base_delay = 0.5
        timeout = 10.0
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        escaped_message = escape_markdown_v2(message)
        results = {}

        async with httpx.AsyncClient(timeout=timeout) as client:
            for chat_id in chat_ids:
                attempt = 0
                while attempt <= max_retries:
                    try:
                        resp = await client.post(
                            url,
                            data={
                                "chat_id": chat_id,
                                "text": escaped_message,
                                "parse_mode": parse_mode,
                                "disable_web_page_preview": True,
                            },
                        )
                        if resp.status_code == 429:
                            retry_after = resp.json().get("parameters", {}).get("retry_after", 1)
                            self.logger.warning(f"Telegram rate limit for chat_id={chat_id}, retrying in {retry_after}s")
                            await asyncio.sleep(retry_after)
                            attempt += 1
                            continue
                        resp.raise_for_status()
                        data = resp.json()
                        if data.get("ok"):
                            results[chat_id] = {"ok": True}
                        else:
                            error_msg = data.get("description", "Unknown error")
                            self.logger.error(f"Telegram send failed for chat_id={chat_id}: {error_msg}")
                            results[chat_id] = {"ok": False, "error": error_msg}
                        break
                    except (httpx.RequestError, httpx.HTTPStatusError) as e:
                        self.logger.error(f"Telegram send error for chat_id={chat_id}: {e}")
                        if attempt < max_retries:
                            delay = base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)
                            attempt += 1
                        else:
                            results[chat_id] = {"ok": False, "error": str(e)}
                            break
                    except Exception as e:
                        self.logger.exception(f"Unexpected error sending Telegram message to chat_id={chat_id}: {e}")
                        results[chat_id] = {"ok": False, "error": str(e)}
                        break
                else:
                    results[chat_id] = {"ok": False, "skipped": True, "error": "Max retries exceeded"}
        return results
