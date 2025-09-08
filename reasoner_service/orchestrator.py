from __future__ import annotations

import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, time as dt_time, timezone


from .config import get_settings, load_routing_rules, load_routing_overrides
from .storage import create_engine_from_env_or_dsn, init_models, insert_decision, compute_decision_hash
from .alerts import SlackNotifier, DiscordNotifier, TelegramNotifier
from .metrics import start_metrics_server_if_enabled, decisions_processed_total, deduplicated_decisions_total
from .logging_setup import logger

_cfg = get_settings()



class DecisionOrchestrator:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn
        self.engine = None
        self.notifiers = {}
        self._dedup = {}  # hash -> ts
        self._lock = asyncio.Lock()
        # routing caches
        self._routing_rules = load_routing_rules()
        self._routing_overrides = load_routing_overrides()

    async def setup(self):
        self.engine = create_engine_from_env_or_dsn(self.dsn)
        await init_models(self.engine)
        self.notifiers = {
            "slack": SlackNotifier(_cfg.SLACK_WEBHOOK_URL, engine=self.engine),
            "discord": DiscordNotifier(_cfg.DISCORD_WEBHOOK_URL, engine=self.engine),
            "telegram": TelegramNotifier(_cfg.TELEGRAM_TOKEN, _cfg.TELEGRAM_CHAT_ID, engine=self.engine),
        }
        start_metrics_server_if_enabled()

    def _is_quiet_hours(self, now: Optional[datetime] = None) -> bool:
        q = _cfg.QUIET_HOURS
        if not q:
            return False
        try:
            now = now or datetime.utcnow()
            parts = q.split("-")
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
                return t >= start_t or t <= end_t
        except Exception:
            return False

    def _normalize_decision(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        d = dict(decision)
        if d.get("symbol"):
            d["symbol"] = str(d["symbol"]).upper()
        else:
            d["symbol"] = "UNKNOWN"
        try:
            conf = float(d.get("confidence", 0.0))
        except Exception:
            conf = 0.0
        d["confidence"] = max(0.0, min(1.0, conf))
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
        d.setdefault("bias", "neutral")
        d.setdefault("recommendation", "do_nothing")
        d.setdefault("duration_ms", int(d.get("duration_ms", 0) or 0))
        d.setdefault("summary", str(d.get("summary", "")))
        d.setdefault("repair_used", bool(d.get("repair_used", False)))
        d.setdefault("fallback_used", bool(d.get("fallback_used", False)))
        # ensure tags list
        tags = d.get("tags") or []
        if isinstance(tags, str):
            # comma separated
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        d["tags"] = list(tags)
        return d
    def _in_override_window(self, override: Dict[str, Any], now_utc: Optional[datetime] = None) -> bool:
        now = now_utc or datetime.utcnow()
        try:
            start = override.get("start")
            end = override.get("end")
            if not start or not end:
                return False
            sh, sm = map(int, start.split(":"))
            eh, em = map(int, end.split(":"))
            start_t = dt_time(sh, sm)
            end_t = dt_time(eh, em)
            t = now.time()
            if start_t < end_t:
                return start_t <= t <= end_t
            else:
                return t >= start_t or t <= end_t
        except Exception:
            return False

    def _get_routing_for_decision(self, decision: Dict[str, Any]) -> List[str]:
        """Resolve routing channels for a decision using:
           1) time-based overrides for the symbol (UTC)
           2) exact symbol routing rules
           3) tag-based routing rules (key format tag1|tag2 matches if all tags present)
           4) wildcard symbol patterns ending with '*'
        """
        symbol = decision.get("symbol", "")
        tags = set(decision.get("tags", []) or [])

        # 1) overrides
        for ov in self._routing_overrides:
            if ov.get("symbol") == symbol:
                if self._in_override_window(ov):
                    chs = ov.get("channels") or []
                    if isinstance(chs, list) and chs:
                        return chs

        # 2) exact symbol
        rules = self._routing_rules or {}
        if symbol in rules:
            return rules[symbol]

        # 3) tag-based
        matched = []
        for key, chs in rules.items():
            if "|" in key:
                required = {p.strip() for p in key.split("|") if p.strip()}
                if required and required.issubset(tags):
                    matched.extend(chs)
        if matched:
            # return unique preserving order
            return list(dict.fromkeys(matched))

        # 4) wildcard symbol patterns
        for key, chs in rules.items():
            if key.endswith("*") and symbol.startswith(key[:-1]):
                return chs

        # default fallback: all channels
        return ["slack", "discord", "telegram"]

    async def process_decision(self, decision: Dict[str, Any], persist: bool = True, channels: Optional[List[str]] = None) -> Dict[str, Any]:
        d = self._normalize_decision(decision)
        symbol = d["symbol"]
        rec = d.get("recommendation")
        conf = float(d.get("confidence", 0.0))
        ts_ms = int(d.get("timestamp_ms", int(time.time() * 1000)))
        decision_hash = compute_decision_hash(symbol, rec, conf, ts_ms)
        now_ts = time.time()

        # dedup in-memory
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
                dec_id = await insert_decision(self.engine, symbol=symbol, decision_text=json.dumps(d), raw=d, bias=d.get("bias","neutral"), confidence=conf, recommendation=rec, repair_used=bool(d.get("repair_used")), fallback_used=bool(d.get("fallback_used")), duration_ms=int(d.get("duration_ms",0)), ts_ms=ts_ms)
                decisions_processed_total.labels(result="persisted").inc()
            except Exception as e:
                decisions_processed_total.labels(result="failed").inc()
                logger.exception("persist failure: %s", e)
                dec_id = None
        else:
            decisions_processed_total.labels(result="skipped_persist").inc()

        # channel selection
        if channels is None:
            routed = self._get_routing_for_decision(d)
        else:
            routed = channels

        # quiet hours check
        if self._is_quiet_hours() and not d.get("urgent", False):
            results = {ch: {"ok": False, "skipped": True, "reason": "quiet_hours"} for ch in routed}
            return {"id": dec_id, "skipped": skipped, "notify_results": results}

        # concurrent notify
        tasks = []
        for ch in routed:
            notifier = self.notifiers.get(ch)
            if not notifier:
                continue
            tasks.append(notifier.notify(d, decision_id=dec_id))
        notify_results = {}
        if tasks and not skipped:
            res_list = await asyncio.gather(*tasks, return_exceptions=False)
            for ch, r in zip(routed, res_list):
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

    async def close(self):
        if self.engine:
            await self.engine.dispose()
