
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
    # Redis DLQ settings
    REDIS_DLQ_ENABLED: bool = bool(int(os.getenv("REDIS_DLQ_ENABLED", "0")))
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_DLQ_KEY: str = os.getenv("REDIS_DLQ_KEY", "dlq:decisions")
    # control redis dlq polling and backoff defaults (can override DLQ_* values)
    DLQ_POLL_INTERVAL_SECONDS: float = float(os.getenv("DLQ_POLL_INTERVAL_SECONDS", "5"))
    DLQ_BASE_DELAY_SECONDS: float = float(os.getenv("DLQ_BASE_DELAY_SECONDS", "1"))
    DLQ_MAX_DELAY_SECONDS: float = float(os.getenv("DLQ_MAX_DELAY_SECONDS", "60"))
    DLQ_MAX_RETRIES: int = int(os.getenv("DLQ_MAX_RETRIES", "5"))
    # Redis dedup settings (SETNX with TTL)
    REDIS_DEDUP_ENABLED: bool = bool(int(os.getenv("REDIS_DEDUP_ENABLED", "0")))
    REDIS_DEDUP_PREFIX: str = os.getenv("REDIS_DEDUP_PREFIX", "dedup:")
    REDIS_DEDUP_TTL_SECONDS: int = int(os.getenv("REDIS_DEDUP_TTL_SECONDS", "60"))
    # Redis reconnect jitter and circuit-breaker
    REDIS_RECONNECT_MAX_ATTEMPTS: int = int(os.getenv("REDIS_RECONNECT_MAX_ATTEMPTS", "5"))
    REDIS_RECONNECT_BASE_DELAY: float = float(os.getenv("REDIS_RECONNECT_BASE_DELAY", "0.5"))
    REDIS_RECONNECT_MAX_DELAY: float = float(os.getenv("REDIS_RECONNECT_MAX_DELAY", "10"))
    REDIS_RECONNECT_JITTER_MS: int = int(os.getenv("REDIS_RECONNECT_JITTER_MS", "250"))
    REDIS_CIRCUIT_COOLDOWN_SECONDS: float = float(os.getenv("REDIS_CIRCUIT_COOLDOWN_SECONDS", "60"))
    # Admin API token for basic protection of requeue/flush endpoints
    ADMIN_TOKEN: str = os.getenv("REASONER_ADMIN_TOKEN", "")
    # Feature toggles for Plan Executor
    ENABLE_PLAN_EXECUTOR: bool = bool(int(os.getenv("ENABLE_PLAN_EXECUTOR", "0")))
    DEBUG_PLAN_EXECUTOR: bool = bool(int(os.getenv("DEBUG_PLAN_EXECUTOR", "0")))
    # Feature toggle for permissive policy mode (default: True)
    ENABLE_PERMISSIVE_POLICY: bool = bool(int(os.getenv("ENABLE_PERMISSIVE_POLICY", "1")))

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
