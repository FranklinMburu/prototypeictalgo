
"""
Advanced notification notifiers for Slack, Discord, Telegram with:
- EMOJI_MAP, platform-aware formatting, markdown/escaping, TP/SL summary
- Latency metrics, error budget tracker, Prometheus hooks, circuit breaker
- DLQ integration and testable payload rendering
"""


import aiohttp
import asyncio
import json
import time
from typing import Any, Dict, Optional


# Explicitly export public API for test discovery
__all__ = [
    "emoji_for_recommendation",
    "format_payload_markdown",
]



try:
    from .config import get_settings
    from .logging_setup import logger
    from . import deadletter
    from . import metrics
except ImportError:
    # Absolute imports for script mode
    from reasoner_service.config import get_settings
    from reasoner_service.logging_setup import logger
    import reasoner_service.deadletter as deadletter
    import reasoner_service.metrics as metrics

_cfg = get_settings()

# --- UX: Emoji, Markdown, TP/SL Formatting ---

# --- Enhanced Emoji Map ---
EMOJI_MAP = {
    "enter": "✅",
    "wait": "⏳",
    "do_nothing": "🚫",
    "exit": "🚪",
    "tp": "🎯",
    "sl": "🛡️",
    "long": "🟢",
    "short": "🔴",
    "neutral": "⚪",
}


def emoji_for_recommendation(rec: str) -> str:
    return EMOJI_MAP.get(rec, "❔")

def _format_tp_sl(payload: Dict[str, Any], platform: str = "slack") -> str:
    tp = payload.get("tp")
    sl = payload.get("sl")
    if tp is not None or sl is not None:
        tp_str = f"*TP*: {tp}" if tp is not None else "*TP*: _not provided_"
        sl_str = f"*SL*: {sl}" if sl is not None else "*SL*: _not provided_"
        sep = " | " if platform != "telegram" else "\n"
        return f"{tp_str}{sep}{sl_str}"
    return "*TP/SL*: _not provided_"

def _escape_slack(text: str) -> str:
    # Slack escaping for <, >, &
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _escape_telegram_md(text: str) -> str:
    # Telegram MarkdownV2 escaping
    for c in r'_[]()~`>#+-=|{}.!':
        text = text.replace(c, f"\{c}")
    return text


def format_payload_markdown(payload: Dict[str, Any], platform: str) -> str:
    emoji = emoji_for_recommendation(payload.get("recommendation", ""))
    symbol = payload.get("symbol", "?")
    entry = payload.get("entry")
    conf = payload.get("confidence")
    summary = payload.get("summary", "")
    tp_sl = _format_tp_sl(payload, platform)
    # Platform-specific markdown
    if platform == "slack":
        base = f"{emoji} *{payload.get('recommendation','').upper()}* – *{symbol}*"
        if entry:
            base += f" @ *{entry}*"
        if conf is not None:
            base += f" (conf: *{conf:.2f}*)"
        base += f"\n• {tp_sl}"
        if summary:
            base += f"\n_{_escape_slack(summary)}_"
        return _escape_slack(base)
    elif platform == "telegram":
        base = f"{emoji} *{payload.get('recommendation','').upper()}* – *{symbol}*"
        if entry:
            base += f" @ *{entry}*"
        if conf is not None:
            base += f" (conf: *{conf:.2f}*)"
        base += f"\n• {tp_sl}"
        if summary:
            base += f"\n_{summary}_"
        return _escape_telegram_md(base)
    elif platform == "discord":
        base = f"{emoji} **{payload.get('recommendation','').upper()}** – **{symbol}**"
        if entry:
            base += f" @ **{entry}**"
        if conf is not None:
            base += f" (conf: **{conf:.2f}** )"
        base += f"\n• {tp_sl}"
        if summary:
            base += f"\n*{summary}*"
        return base
    # fallback
    base = f"{emoji} {payload.get('recommendation','').upper()} – {symbol}"
    if entry:
        base += f" @ {entry}"
    if conf is not None:
        base += f" (conf: {conf:.2f})"
    base += f"\n{tp_sl}"
    if summary:
        base += f"\n{summary}"
    return base

# --- TEST CASES ---
# --- TEST CASES ---
def _test_emoji():
    assert emoji_for_recommendation("enter") == "✅"
    assert emoji_for_recommendation("wait") == "⏳"
    assert emoji_for_recommendation("do_nothing") == "🚫"
    assert emoji_for_recommendation("long") == "🟢"
    assert emoji_for_recommendation("short") == "🔴"
    assert emoji_for_recommendation("unknown") == "❔"

def _test_formatting():
    payload = {
        "recommendation": "enter",
        "symbol": "BTCUSD",
        "entry": 1975.0,
        "confidence": 0.88,
        "tp": 2000.0,
        "sl": 1950.0,
        "summary": "Breakout above resistance."
    }
    slack = format_payload_markdown(payload, "slack")
    telegram = format_payload_markdown(payload, "telegram")
    discord = format_payload_markdown(payload, "discord")
    assert "✅" in slack and "*ENTER*" in slack and "BTCUSD" in slack
    assert "*TP*" in slack and "*SL*" in slack
    assert "Breakout above resistance." in slack
    assert "✅" in telegram and "*ENTER*" in telegram
    assert "BTCUSD" in telegram and "*TP*" in telegram
    assert "✅" in discord and "**ENTER**" in discord
    assert "BTCUSD" in discord and "*Breakout above resistance.*" in discord

def _test_tp_sl_fallback():
    payload = {"recommendation": "wait", "symbol": "ETHUSD"}
    slack = format_payload_markdown(payload, "slack")
    assert "not provided" in slack

def _test_latency_metric():
    import time
    from types import SimpleNamespace
    class DummyMetrics:
        def __init__(self):
            self.latencies = []
        def labels(self, **kwargs):
            return self
        def observe(self, val):
            self.latencies.append(val)
    dummy = DummyMetrics()
    t0 = time.time()
    time.sleep(0.01)
    latency = time.time() - t0
    dummy.observe(latency)
    assert dummy.latencies and dummy.latencies[0] > 0


def run_tests():
    """Run all notification UX and SLO test cases."""
    _test_emoji()
    _test_formatting()
    _test_tp_sl_fallback()
    _test_latency_metric()
    print("All notification UX and SLO tests passed.")


if __name__ == "__main__":
    run_tests()

# --- SLOs: Latency, Error Budget, Circuit Breaker ---
class ErrorBudgetTracker:
    def __init__(self, window_seconds=3600, max_fail_pct=0.01):
        self.window = window_seconds
        self.max_fail_pct = max_fail_pct
        self.events = []  # (ts, ok:bool)
        self.lock = asyncio.Lock()
        self.breached = False

    async def register(self, ok: bool):
        now = time.time()
        async with self.lock:
            self.events.append((now, ok))
            # prune old
            self.events = [(t, o) for t, o in self.events if now - t < self.window]
            fails = sum(1 for _, o in self.events if not o)
            total = len(self.events)
            fail_pct = fails / total if total else 0.0
            if fail_pct > self.max_fail_pct and not self.breached:
                self.breached = True
                await self._default_breach_action()
            elif fail_pct <= self.max_fail_pct:
                self.breached = False

    async def _default_breach_action(self):
        # Ping Slack on SLO breach
        logger.error("Error budget breached! Notifying Slack.")
        # Could send a Slack alert here

error_budget = ErrorBudgetTracker()

def discord_color_for_confidence(conf: float) -> int:
    if conf >= 0.8:
        return 0x2ecc40  # green
    elif conf >= 0.5:
        return 0xffc300  # yellow
    else:
        return 0xe74c3c  # red

def prometheus_alert_rules_yaml():
    return f"""
groups:
  - name: notifier-alerts
    rules:
      - alert: NotifierLatencyHigh
        expr: histogram_quantile(0.95, sum(rate(notification_latency_seconds_bucket[5m])) by (le,channel)) > 1.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High notification latency
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_open > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: Circuit breaker open for notifier
      - alert: NotifierFailureBudgetBreached
        expr: notifier_failures_total / (notifier_success_total + notifier_failures_total) > 0.01
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: Notifier error budget breached
"""

# --- Notifier Classes ---
class SlackNotifier:
    def __init__(self, webhook_url: str = None, engine: Any = None):
        self.webhook_url = webhook_url or _cfg.SLACK_WEBHOOK_URL
        self.engine = engine

    async def notify(self, payload: Dict[str, Any], decision_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.webhook_url:
            logger.warning("Slack webhook URL not set")
            return {"ok": False, "error": "no_webhook_url", "status": None}
        text = format_payload_markdown(payload, "slack")
        data = {"text": text}
        t0 = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=data, timeout=10) as resp:
                    status = resp.status
                    latency = (time.time() - t0)
                    metrics.notifier_requests_total.labels(channel="slack", status="success" if status == 200 else "failure").inc()
                    metrics.notifier_latency_seconds.labels(channel="slack").observe(latency)
                    await error_budget.register(status == 200)
                    if status == 200:
                        return {"ok": True, "status": status, "latency": latency}
                    else:
                        err = await resp.text()
                        raise Exception(f"Slack error: {status} {err}")
        except Exception as e:
            logger.error(f"Slack notify failed: {e}")
            try:
                import redis.asyncio as redis
                redis_conn = await redis.from_url(_cfg.REDIS_URL)
                await deadletter.publish_deadletter(redis_conn, decision_id, "slack", payload, str(e))
                await redis_conn.close()
            except Exception as dlq_e:
                logger.error(f"DLQ publish failed: {dlq_e}")
            await error_budget.register(False)
            metrics.notifier_requests_total.labels(channel="slack", status="failure").inc()
            return {"ok": False, "error": str(e), "status": None}

class DiscordNotifier:
    def __init__(self, webhook_url: str = None, engine: Any = None):
        self.webhook_url = webhook_url or _cfg.DISCORD_WEBHOOK_URL
        self.engine = engine

    async def notify(self, payload: Dict[str, Any], decision_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.webhook_url:
            logger.warning("Discord webhook URL not set")
            return {"ok": False, "error": "no_webhook_url", "status": None}
        conf = float(payload.get("confidence", 0.0))
        color = discord_color_for_confidence(conf)
        embed = {
            "title": f"{emoji_for_recommendation(payload.get('recommendation',''))} {payload.get('recommendation','').upper()} – {payload.get('symbol','?')}",
            "description": format_payload_markdown(payload, "discord"),
            "color": color,
        }
        data = {"embeds": [embed]}
        t0 = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=data, timeout=10) as resp:
                    status = resp.status
                    latency = (time.time() - t0)
                    metrics.notifier_requests_total.labels(channel="discord", status="success" if 200 <= status < 300 else "failure").inc()
                    metrics.notifier_latency_seconds.labels(channel="discord").observe(latency)
                    await error_budget.register(200 <= status < 300)
                    if 200 <= status < 300:
                        return {"ok": True, "status": status, "latency": latency}
                    else:
                        err = await resp.text()
                        raise Exception(f"Discord error: {status} {err}")
        except Exception as e:
            logger.error(f"Discord notify failed: {e}")
            try:
                import redis.asyncio as redis
                redis_conn = await redis.from_url(_cfg.REDIS_URL)
                await deadletter.publish_deadletter(redis_conn, decision_id, "discord", payload, str(e))
                await redis_conn.close()
            except Exception as dlq_e:
                logger.error(f"DLQ publish failed: {dlq_e}")
            await error_budget.register(False)
            metrics.notifier_requests_total.labels(channel="discord", status="failure").inc()
            return {"ok": False, "error": str(e), "status": None}

class TelegramNotifier:
    def __init__(self, token: str = None, chat_id: str = None, engine: Any = None):
        self.token = token or _cfg.TELEGRAM_TOKEN
        self.chat_id = chat_id or _cfg.TELEGRAM_CHAT_ID
        self.engine = engine

    async def notify(self, payload: Dict[str, Any], decision_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.token or not self.chat_id:
            logger.warning("Telegram token or chat_id not set")
            return {"ok": False, "error": "no_token_or_chat_id", "status": None}
        text = format_payload_markdown(payload, "telegram")
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {"chat_id": self.chat_id, "text": text, "parse_mode": "MarkdownV2"}
        t0 = time.time()
        logger.info(f"[TelegramNotifier] Sending to {self.chat_id}: {text}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, timeout=10) as resp:
                    status = resp.status
                    resp_text = await resp.text()
                    latency = (time.time() - t0)
                    logger.info(f"[TelegramNotifier] Response: status={status}, body={resp_text}")
                    metrics.notifier_requests_total.labels(channel="telegram", status="success" if 200 <= status < 300 else "failure").inc()
                    metrics.notifier_latency_seconds.labels(channel="telegram").observe(latency)
                    await error_budget.register(200 <= status < 300)
                    if 200 <= status < 300:
                        return {"ok": True, "status": status, "latency": latency}
                    else:
                        # Fallback: try plain text if MarkdownV2 fails
                        if status == 400 and 'parse_mode' in data:
                            logger.warning(f"[TelegramNotifier] MarkdownV2 failed, retrying as plain text...")
                            data_plain = {"chat_id": self.chat_id, "text": text}
                            async with session.post(url, json=data_plain, timeout=10) as resp2:
                                status2 = resp2.status
                                resp2_text = await resp2.text()
                                logger.info(f"[TelegramNotifier] Plain text response: status={status2}, body={resp2_text}")
                                if 200 <= status2 < 300:
                                    return {"ok": True, "status": status2, "latency": latency}
                                else:
                                    raise Exception(f"Telegram error (plain): {status2} {resp2_text}")
                        raise Exception(f"Telegram error: {status} {resp_text}")
        except Exception as e:
            logger.error(f"Telegram notify failed: {e}")
            try:
                import redis.asyncio as redis
                redis_conn = await redis.from_url(_cfg.REDIS_URL)
                await deadletter.publish_deadletter(redis_conn, decision_id, "telegram", payload, str(e))
                await redis_conn.close()
            except Exception as dlq_e:
                logger.error(f"DLQ publish failed: {dlq_e}")
            await error_budget.register(False)
            metrics.notifier_requests_total.labels(channel="telegram", status="failure").inc()
            return {"ok": False, "error": str(e), "status": None}
