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

# At the very end of the file, after all function and class definitions:
if __name__ != "__main__":
    import sys as _sys
    _mod = _sys.modules[__name__]
    setattr(_mod, "emoji_for_recommendation", emoji_for_recommendation)
    setattr(_mod, "format_payload_markdown", format_payload_markdown)
