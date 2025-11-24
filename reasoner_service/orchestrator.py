from __future__ import annotations

import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, time as dt_time, timezone


from .config import get_settings
try:
    import redis.asyncio as aioredis
except Exception:
    aioredis = None
from .storage import create_engine_from_env_or_dsn, create_engine_and_sessionmaker, init_models, insert_decision, compute_decision_hash
from .alerts import SlackNotifier, DiscordNotifier, TelegramNotifier
from .metrics import start_metrics_server_if_enabled, decisions_processed_total, deduplicated_decisions_total, dlq_retries_total, dlq_size, redis_reconnect_attempts
from .logging_setup import logger
from utils.redis_wrapper import redis_op

_cfg = get_settings()



class DecisionOrchestrator:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn
        self.engine = None
        self._sessionmaker = None
        self.notifiers = {}
        self._dedup = {}  # hash -> ts
        self._lock = asyncio.Lock()
        # lock protecting the in-memory DLQ
        self._dlq_lock = asyncio.Lock()
        # in-memory DLQ for failed persistence attempts (non-blocking fallback)
        # each entry: {decision, error, ts, attempts:int, next_attempt_ts:float}
        self._persist_dlq = []
        # redis client will be set in setup() if enabled
        self._redis = None
        # background task for retrying DLQ entries
        self._dlq_task = None
        # simple circuit-breaker state for redis reconnects
        self._redis_failure_count = 0
        self._redis_circuit_open_until = 0.0
        # routing caches (safe defaults if not provided via config helpers)
        try:
            # some repos provide helper loaders; try importing dynamically
            from .config import load_routing_rules as _lr, load_routing_overrides as _lo
            self._routing_rules = _lr()
            self._routing_overrides = _lo()
        except Exception:
            self._routing_rules = {}
            self._routing_overrides = []

    # --- Safety helper: normalized dedup key ---
    def _compute_dedup_key(self, decision: Dict[str, Any]) -> str:
        """
        Compute a stable deduplication key that is resilient to small timestamp or floating
        point differences. Rules (in order):
        1. If `idempotency_key` present, use it directly.
        2. If `signal_id` present, use it directly.
        3. Otherwise, normalize by symbol, recommendation, rounded confidence, and
           a timestamp bucket derived from DEDUP_WINDOW_SECONDS.

        Safety: this intentionally avoids including raw `timestamp_ms` or raw floats
        so that near-duplicate signals within the dedup window produce the same key.
        """
        # 1) idempotency
        idem = decision.get("idempotency_key") or decision.get("idempotency") or decision.get("idempotencyKey")
        if idem:
            return f"idem:{str(idem)}"
        # 2) signal id
        sig = decision.get("signal_id") or decision.get("signalId")
        if sig:
            return f"sig:{str(sig)}"
        # 3) normalized bucket
        symbol = str(decision.get("symbol", "UNKNOWN")).upper()
        rec = str(decision.get("recommendation", "")).lower()
        try:
            conf = int(round(float(decision.get("confidence", 0.0)) * 100))
        except Exception:
            conf = 0
        ts_ms = int(decision.get("timestamp_ms", int(time.time() * 1000)))
        bucket_s = max(1, int(get_settings().DEDUP_WINDOW_SECONDS))
        ts_bucket = int((ts_ms // 1000) // bucket_s)
        return f"norm:{symbol}:{rec}:{conf}:{ts_bucket}"

    async def setup(self):
        # Create async engine and sessionmaker pair. Use sessionmaker for persistence calls.
        try:
            engine, sessionmaker = await create_engine_and_sessionmaker(self.dsn)
            self.engine = engine
            self._sessionmaker = sessionmaker
            await init_models(self.engine)
        except Exception:
            # Fallback to older helper (engine-only). This keeps changes additive and safe.
            self.engine = create_engine_from_env_or_dsn(self.dsn)
            await init_models(self.engine)
        self.notifiers = {
            "slack": SlackNotifier(_cfg.SLACK_WEBHOOK_URL, engine=self.engine),
            "discord": DiscordNotifier(_cfg.DISCORD_WEBHOOK_URL, engine=self.engine),
            "telegram": TelegramNotifier(_cfg.TELEGRAM_TOKEN, _cfg.TELEGRAM_CHAT_ID, engine=self.engine),
        }
        start_metrics_server_if_enabled()
        # setup optional Redis DLQ with backoff
        try:
            if _cfg.REDIS_DLQ_ENABLED and aioredis is not None:
                await self._ensure_redis()
        except Exception:
            logger.exception("error while configuring Redis DLQ")

        # start DLQ retry loop if enabled (either redis or in-memory)
        try:
            if _cfg.DLQ_POLL_INTERVAL_SECONDS and (_cfg.REDIS_DLQ_ENABLED and self._redis is not None or _cfg.DLQ_POLL_INTERVAL_SECONDS):
                # run background retry loop
                self._dlq_task = asyncio.create_task(self._dlq_retry_loop())
        except Exception:
            logger.exception("failed to start DLQ retry task")

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
        # Use normalized dedup key which avoids raw timestamp/float sensitivity
        decision_hash = self._compute_dedup_key(d)
        now_ts = time.time()

        # dedup in-memory
        skipped = False
        if _cfg.DEDUP_ENABLED:
            # try optional Redis-based dedup first (SETNX + EXPIRE)
            if _cfg.REDIS_DEDUP_ENABLED and getattr(self, "_redis", None) is not None:
                try:
                    key = f"{_cfg.REDIS_DEDUP_PREFIX}{decision_hash}"
                    # SETNX equivalent: set with nx=True and expire
                    try:
                        from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
                        _rres = await redis_op(self, lambda r, k, v, ex, nx: r.set(k, v, ex=ex, nx=nx), key, "1", ex=int(_cfg.REDIS_DEDUP_TTL_SECONDS), nx=True)
                        # redis_op returns a dict {ok: True, value: <raw>} for success
                        r = _rres.get("value") if isinstance(_rres, dict) else _rres
                        # many redis clients return True/False for set nx; treat falsy as already present
                        if not r:
                            deduplicated_decisions_total.inc()
                            skipped = True
                    except (RedisUnavailable, RedisOpFailed):
                        # fallback to in-memory dedup if redis op fails
                        pass
                    except Exception:
                        # any other redis error -> fallback to in-memory
                        pass
                    else:
                        # marked in redis; continue processing
                        pass
                except Exception:
                    # fallback to in-memory dedup on redis error
                    pass

        # persist
        dec_id = None
        if persist:
            try:
                # Prefer sessionmaker-based persistence (sessionmaker is created in setup)
                session_arg = self._sessionmaker if self._sessionmaker is not None else self.engine
                dec_id = await insert_decision(session_arg, symbol=symbol, decision_text=json.dumps(d), raw=d, bias=d.get("bias","neutral"), confidence=conf, recommendation=rec, repair_used=bool(d.get("repair_used")), fallback_used=bool(d.get("fallback_used")), duration_ms=int(d.get("duration_ms",0)), ts_ms=ts_ms)
                decisions_processed_total.labels(result="persisted").inc()
            except Exception as e:
                decisions_processed_total.labels(result="failed").inc()
                logger.exception("persist failure: %s", e)
                # Non-blocking fallback: enqueue decision to in-memory DLQ for later retry
                try:
                    # annotate DLQ entry with attempts and schedule for immediate retry
                    entry = {"decision": d, "error": str(e), "ts": int(time.time() * 1000), "attempts": 0, "next_attempt_ts": 0.0}
                    if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                        # push JSON serialized entry to Redis list (RPUSH)
                        try:
                            from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
                            await redis_op(self, lambda r, key, v: r.rpush(key, v), _cfg.REDIS_DLQ_KEY, json.dumps(entry))
                            # update dlq size metric if available
                            try:
                                llen = await redis_op(self, lambda r, key: r.llen(key), _cfg.REDIS_DLQ_KEY)
                                try:
                                    dlq_size.set(llen)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                            logger.warning("Decision persisted to Redis DLQ (will retry later)")
                        except (RedisUnavailable, RedisOpFailed) as re:
                            logger.exception("failed to push to redis DLQ, falling back to in-memory: %s", re)
                            async with self._dlq_lock:
                                self._persist_dlq.append(entry)
                    else:
                        async with self._dlq_lock:
                            self._persist_dlq.append(entry)
                            logger.warning("Decision persisted to in-memory DLQ (will retry later)")
                            try:
                                dlq_size.set(len(self._persist_dlq))
                            except Exception:
                                pass
                except Exception as dlq_e:
                    logger.error("Failed to enqueue to in-memory DLQ: %s", dlq_e)
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
            # Use return_exceptions=True so one notifier failure doesn't cancel others
            res_list = await asyncio.gather(*tasks, return_exceptions=True)
            for ch, r in zip(routed, res_list):
                if isinstance(r, Exception):
                    # Normalize exception into a notifier result dict, preserve exception text
                    logger.error(f"Notifier {ch} raised: {r}")
                    notify_results[ch] = {"ok": False, "error": str(r)}
                else:
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
        # stop DLQ retry task
        if self._dlq_task:
                try:
                    self._dlq_task.cancel()
                    await self._dlq_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("error stopping DLQ task")
        # close redis client if present
        if self._redis:
            try:
                # use wrapper to close gracefully
                try:
                    await redis_op(self, lambda r: r.close())
                except Exception:
                    # close is best-effort; swallow errors but log below
                    pass
            except Exception:
                logger.exception("error closing redis client")
        if self.engine:
            await self.engine.dispose()

    async def _dlq_retry_loop(self) -> None:
        """Background loop that periodically attempts to re-persist DLQ entries.

        This loop is intentionally additive and non-blocking when DLQ is empty.
        """
        poll_interval = max(0.5, float(get_settings().DLQ_POLL_INTERVAL_SECONDS or 5))
        while True:
            try:
                await self._dlq_retry_once()
            except Exception:
                logger.exception("error during DLQ retry iteration")
            try:
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break

    async def _ensure_redis(self, max_attempts: Optional[int] = None, base_delay: Optional[float] = None):
        """Ensure self._redis is connected, with exponential backoff on failures.

        This sets `self._redis` to an aioredis client or None on persistent failure.
        """
        # Attempt to import redis.asyncio dynamically so tests can monkeypatch sys.modules
        try:
            import importlib

            local_aioredis = importlib.import_module("redis.asyncio")
        except Exception:
            # fallback to module-level aioredis captured at import time
            local_aioredis = aioredis
        if local_aioredis is None:
            self._redis = None
            return

        # load defaults from config when not provided
        cfg = get_settings()
        max_attempts = int(max_attempts or cfg.REDIS_RECONNECT_MAX_ATTEMPTS)
        base_delay = float(base_delay or cfg.REDIS_RECONNECT_BASE_DELAY)
        max_delay = float(cfg.REDIS_RECONNECT_MAX_DELAY)
        jitter_ms = int(cfg.REDIS_RECONNECT_JITTER_MS)
        cooldown = float(cfg.REDIS_CIRCUIT_COOLDOWN_SECONDS)

        now = time.time()
        if self._redis_circuit_open_until and now < self._redis_circuit_open_until:
            logger.warning("redis circuit open until %s, skipping reconnect attempts", self._redis_circuit_open_until)
            self._redis = None
            return

        attempts = 0
        while attempts < max_attempts:
            try:
                self._redis = local_aioredis.from_url(_cfg.REDIS_URL)
                # test connection with ping
                try:
                    pong = await self._redis.ping()
                    if pong:
                        # reset failure counter on success
                        self._redis_failure_count = 0
                        self._redis_circuit_open_until = 0.0
                        return
                except Exception:
                    # ping failed, close and retry
                    try:
                        await self._redis.close()
                    except Exception:
                        pass
                    self._redis = None
                    raise
            except Exception:
                attempts += 1
                self._redis_failure_count += 1
                try:
                    redis_reconnect_attempts.inc()
                except Exception:
                    pass
                # exponential backoff + jitter
                delay = min(max_delay, base_delay * (2 ** (attempts - 1)))
                # jitter
                jitter = (jitter_ms / 1000.0) * (0.5 - (time.time() % 1))
                delay = max(0.0, delay + jitter)
                logger.warning("redis connect attempt %d failed, retrying in %.1fs (jitter %.3f)", attempts, delay, jitter)
                await asyncio.sleep(delay)

        # if we exhausted attempts, open circuit for cooldown
        self._redis = None
        self._redis_circuit_open_until = time.time() + cooldown
        logger.error("could not establish redis connection for DLQ after %d attempts, circuit open for %.1fs", max_attempts, cooldown)

    async def _dlq_retry_once(self) -> None:
        """Process the in-memory DLQ once: try eligible entries whose next_attempt_ts <= now.

        Uses exponential backoff and removes successful entries. Entries exceeding
        max attempts will be logged and dropped.
        """
        now = time.time()
        base_delay = float(get_settings().DLQ_BASE_DELAY_SECONDS or 1.0)
        max_delay = float(get_settings().DLQ_MAX_DELAY_SECONDS or 60.0)
        max_retries = int(get_settings().DLQ_MAX_RETRIES or 5)

        entries = []
        # If redis DLQ enabled, pop one entry atomically (using LPOP) and process
        if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                try:
                    from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
                    # use LPOP to get oldest entry
                    _raw_res = await redis_op(self, lambda r, key: r.lpop(key), _cfg.REDIS_DLQ_KEY)
                    raw = _raw_res.get("value") if isinstance(_raw_res, dict) else _raw_res
                    if raw is None:
                        return
                    try:
                        entry = json.loads(raw)
                    except Exception:
                        logger.exception("invalid DLQ entry in redis, skipping")
                        return
                    entries = [entry]
                except (RedisUnavailable, RedisOpFailed):
                    logger.exception("error reading from redis DLQ, falling back to in-memory for this iteration")
                    async with self._dlq_lock:
                        entries = list(self._persist_dlq)
        else:
            # copy indices to avoid mutation during iteration
            async with self._dlq_lock:
                entries = list(self._persist_dlq)

        if not entries:
            return

        for idx, entry in enumerate(entries):
            try:
                attempts = int(entry.get("attempts", 0))
                next_ts = float(entry.get("next_attempt_ts", 0.0) or 0.0)
                if next_ts > now:
                    continue

                decision = entry.get("decision")
                # choose session arg like primary flow
                session_arg = self._sessionmaker if self._sessionmaker is not None else self.engine
                try:
                    dec_id = await insert_decision(session_arg, symbol=decision.get("symbol"), decision_text=json.dumps(decision), raw=decision, bias=decision.get("bias","neutral"), confidence=float(decision.get("confidence",0.0)), recommendation=decision.get("recommendation"), repair_used=bool(decision.get("repair_used")), fallback_used=bool(decision.get("fallback_used")), duration_ms=int(decision.get("duration_ms",0)), ts_ms=int(decision.get("timestamp_ms", int(time.time()*1000))))
                    logger.info("DLQ retry success for symbol=%s attempts=%d dec_id=%s", decision.get("symbol"), attempts, dec_id)
                    # if using redis we already popped the entry; nothing else to do
                    if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                        # success: already removed via LPOP
                        pass
                    else:
                        # remove entry from in-memory list
                        async with self._dlq_lock:
                            try:
                                self._persist_dlq.remove(entry)
                            except ValueError:
                                pass
                    continue
                except Exception as e:
                    attempts += 1
                    # compute next attempt ts with exponential backoff
                    delay = min(max_delay, base_delay * (2 ** (attempts - 1)))
                    next_attempt = now + delay
                    entry["attempts"] = attempts
                    entry["error"] = str(e)
                    entry["next_attempt_ts"] = next_attempt
                    if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                        # push back to redis with updated metadata (RPUSH)
                        try:
                            await redis_op(self, lambda r, key, v: r.rpush(key, v), _cfg.REDIS_DLQ_KEY, json.dumps(entry))
                        except Exception:
                            logger.exception("failed to push failed entry back to redis DLQ")
                    else:
                        async with self._dlq_lock:
                            # update stored entry (if still present)
                            for i, stored in enumerate(self._persist_dlq):
                                if stored is entry or stored.get("ts") == entry.get("ts"):
                                    self._persist_dlq[i] = entry
                                    break
                        try:
                            dlq_retries_total.inc()
                        except Exception:
                            pass
                    if attempts >= max_retries:
                        logger.error("DLQ entry exceeded max retries and will be dropped symbol=%s attempts=%d error=%s", decision.get("symbol"), attempts, str(e))
                        if _cfg.REDIS_DLQ_ENABLED and self._redis is not None:
                            # entry already popped; nothing to remove
                            pass
                        else:
                            async with self._dlq_lock:
                                try:
                                    self._persist_dlq.remove(entry)
                                except ValueError:
                                    pass
                    else:
                        logger.warning("DLQ retry failed for symbol=%s attempts=%d next_attempt_in=%.1fs error=%s", decision.get("symbol"), attempts, delay, str(e))
            except Exception:
                logger.exception("unexpected error processing DLQ entry")
                
                
                
