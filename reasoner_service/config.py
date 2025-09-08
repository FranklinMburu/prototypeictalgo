
import os
from functools import lru_cache

class Settings:
    SLACK_WEBHOOK_URL: str = os.getenv("SLACK_WEBHOOK_URL", "")
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    DEDUP_ENABLED: bool = bool(int(os.getenv("DEDUP_ENABLED", "1")))
    DEDUP_WINDOW_SECONDS: int = int(os.getenv("DEDUP_WINDOW_SECONDS", "60"))
    QUIET_HOURS: str = os.getenv("QUIET_HOURS", "")

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
