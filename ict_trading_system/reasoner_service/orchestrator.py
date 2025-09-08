"""
NOTE: This file is part of a package and must not be run directly.
Imports use relative paths and require the module to be run as part of the package.
To use this code, always run from the project root with:
    python -m ict_trading_system.reasoner_service.orchestrator
or import DecisionOrchestrator from another module.
"""

if __name__ == "__main__":
    raise RuntimeError(
        "This file is part of a package and cannot be run directly. "
        "Use: python -m ict_trading_system.reasoner_service.orchestrator from the project root."
    )

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, time as dt_time, timezone


from .config import get_settings
from .storage import (
    create_engine_from_env_or_dsn,
    init_models,
    insert_decision,
    compute_decision_hash,
)
from .alerts import SlackNotifier, DiscordNotifier, TelegramNotifier, route_channels_for_symbol
from .metrics import start_metrics_server_if_enabled, decisions_processed_total, deduplicated_decisions_total
from .logging_setup import logger

_cfg = get_settings()


class DecisionOrchestrator:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn
        self.engine = None
        self.notifiers: Dict[str, Any] = {}
        self._dedup: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def setup(self) -> None:
        self.engine = create_engine_from_env_or_dsn(self.dsn)
        await init_models(self.engine)
        self.notifiers = {}
        # Robust notifier setup with error logging
        try:
            self.notifiers["slack"] = SlackNotifier(_cfg.SLACK_WEBHOOK_URL, engine=self.engine)
        except Exception as e:
            logger.error(f"Failed to initialize SlackNotifier: {e}")
        try:
            self.notifiers["discord"] = DiscordNotifier(_cfg.DISCORD_WEBHOOK_URL, engine=self.engine)
        except Exception as e:
            logger.error(f"Failed to initialize DiscordNotifier: {e}")
        try:
            self.notifiers["telegram"] = TelegramNotifier(_cfg.TELEGRAM_BOT_TOKEN, _cfg.TELEGRAM_CHAT_ID, engine=self.engine)
        except Exception as e:
            logger.error(f"Failed to initialize TelegramNotifier: {e}")
        start_metrics_server_if_enabled()
        logger.info("Orchestrator setup complete")

    def _is_quiet_hours(self, now: Optional[datetime] = None) -> bool:
        """Return True if current time is within configured quiet hours window (UTC)."""
        q = _cfg.QUIET_HOURS
        if not q:
            return False
        try:
            now = now or datetime.now(timezone.utc)
            parts = q.split("-")
            if len(parts) != 2:
                return False
            start = parts[0].strip()
            end = parts[1].strip()
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            t = now.time()
            start_t = dt_time(sh, sm)
            end_t = dt_time(eh, em)
            if start_t < end_t:
                return start_t <= t <= end_t
            else:
                # window crosses midnight
                return t >= start_t or t <= end_t
        except Exception:
            return False

    def _normalize_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize decision for persistence and notifications."""
        d = dict(decision)
        # symbol uppercase
        d["symbol"] = str(d.get("symbol", "UNKNOWN")).upper()
        # confidence normalization: support 0-100 or 0.0-1.0
        try:
            conf = float(d.get("confidence", 0.0))
        except Exception:
            conf = 0.0
        # If confidence > 1.0, assume it's 0-100 and normalize
        if conf > 1.0:
            conf = conf / 100.0
        d["confidence"] = max(0.0, min(1.0, conf))
        # timestamps (ISO + ms)
        ts = d.get("timestamp") or d.get("timestamp_iso")
        if not ts:
            now = datetime.now(timezone.utc)
            d["timestamp"] = now.isoformat()
            d["timestamp_ms"] = int(now.timestamp() * 1000)
        else:
            try:
                parsed = datetime.fromisoformat(ts) if isinstance(ts, str) else None
                if parsed is None:
                    parsed = datetime.now(timezone.utc)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                d["timestamp"] = parsed.isoformat()
                d["timestamp_ms"] = int(parsed.timestamp() * 1000)
            except Exception:
                now = datetime.now(timezone.utc)
                d["timestamp"] = now.isoformat()
                d["timestamp_ms"] = int(now.timestamp() * 1000)
        # defaults
        d.setdefault("bias", "neutral")
        d.setdefault("recommendation", "do_nothing")
        d.setdefault("duration_ms", int(d.get("duration_ms", 0) or 0))
        d.setdefault("summary", str(d.get("summary", "")))
        d.setdefault("repair_used", bool(d.get("repair_used", False)))
        d.setdefault("fallback_used", bool(d.get("fallback_used", False)))
        return d

    async def process_decision(
        self,
        decision: Dict[str, Any],
        persist: bool = True,
        channels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Normalize, dedup, persist, notify concurrently, return summary."""
        d = self._normalize_decision(decision)
        symbol = d["symbol"]
        rec = d.get("recommendation")
        conf = float(d.get("confidence", 0.0))
        ts_ms = int(d.get("timestamp_ms", int(time.time() * 1000)))
        decision_hash = compute_decision_hash(symbol, rec, conf, ts_ms)
        now_ts = time.time()

        # dedup (in-memory)
        skipped = False
        if _cfg.DEDUP_ENABLED:
            async with self._lock:
                last = self._dedup.get(decision_hash)
                if last and (now_ts - last) < _cfg.DEDUP_WINDOW_SECONDS:
                    deduplicated_decisions_total.inc()
                    skipped = True
                else:
                    self._dedup[decision_hash] = now_ts

        # persist
        dec_id = None
        if persist:
            try:
                dec_id = await insert_decision(
                    self.engine,
                    symbol=symbol,
                    decision_text=json.dumps(d, ensure_ascii=False),
                    raw=d,
                    bias=d.get("bias", "neutral"),
                    confidence=conf,
                    recommendation=rec,
                    repair_used=bool(d.get("repair_used")),
                    fallback_used=bool(d.get("fallback_used")),
                    duration_ms=int(d.get("duration_ms", 0)),
                    ts_ms=ts_ms,
                )
                decisions_processed_total.labels(result="persisted").inc()
            except Exception as e:
                decisions_processed_total.labels(result="failed").inc()
                logger.exception("persist failure: %s", e)
                dec_id = None
        else:
            decisions_processed_total.labels(result="skipped_persist").inc()

        # routing
        routed = channels if channels is not None else route_channels_for_symbol(symbol)
        if not routed:
            routed = ["slack", "discord", "telegram"]

        # quiet hours
        if self._is_quiet_hours() and not d.get("urgent", False):
            logger.info(f"Notification skipped due to quiet hours for symbol {symbol} (channels: {routed})")
            results = {ch: {"ok": False, "skipped": True, "reason": "quiet_hours"} for ch in routed}
            return {"id": dec_id, "skipped": skipped, "notify_results": results}

        # notify
        notify_results: Dict[str, Any] = {}
        if not skipped and routed:
            tasks = []
            for ch in routed:
                notifier = self.notifiers.get(ch)
                if not notifier:
                    notify_results[ch] = {"ok": False, "skipped": True, "reason": "unconfigured"}
                    continue
                tasks.append(notifier.notify(d, decision_id=dec_id))
            if tasks:
                res_list = await asyncio.gather(*tasks, return_exceptions=False)
                for ch, r in zip([c for c in routed if c in self.notifiers], res_list):
                    notify_results[ch] = r
        else:
            for ch in routed:
                notify_results[ch] = {"ok": False, "skipped": True}

        return {"id": dec_id, "skipped": skipped, "notify_results": notify_results}

    async def run_from_queue(self, queue: asyncio.Queue, stop_event: Optional[asyncio.Event] = None) -> None:
        while True:
            if stop_event and stop_event.is_set():
                break
            try:
                decision = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                await self.process_decision(decision)
            except Exception:
                logger.exception("error processing decision")
            finally:
                try:
                    queue.task_done()
                except Exception:
                    pass

    async def close(self) -> None:
        if self.engine:
            await self.engine.dispose()
            self.engine = None
