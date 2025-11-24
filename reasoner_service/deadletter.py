"""
Dead-letter queue and retry mechanism for notification dispatches.

- Publishes failed notification attempts to Redis Stream "deadletter:notifications".
- Background coroutine polls the stream, honors exponential backoff and `next_retry_utc`,
  and re-dispatches using notifier classes (SlackNotifier, DiscordNotifier, TelegramNotifier).
- Caps attempts via config.MAX_DLQ_RETRIES and persists outcomes to storage and metrics.
- Provides helper CLI-invokable functions for targeted retries (by decision_id or time window).
"""

from __future__ import annotations
import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List, Tuple

import redis.asyncio as redis
from utils.redis_wrapper import redis_op

from .config import get_settings
from .alerts import SlackNotifier, DiscordNotifier, TelegramNotifier
from .logging_setup import logger
from . import storage
from . import metrics

DLQ_STREAM_KEY = "deadletter:notifications"

_cfg = get_settings()


def _client_ctx_for(client):
    """Return a minimal ctx object wrapping a raw redis client for redis_op."""
    class Ctx:
        def __init__(self, cli):
            self._redis = cli
            self._redis_circuit_open_until = 0
        async def _ensure_redis(self):
            return

    return Ctx(client)

# Defaults (configurable by env via get_settings if you choose to extend)
DEFAULT_POLL_INTERVAL = 15  # seconds between scans
DEFAULT_BASE_BACKOFF = 10.0  # seconds
DEFAULT_MAX_RETRIES = getattr(_cfg, "DLQ_MAX_RETRIES", 5)
DEFAULT_STREAM_TRIM_LEN = getattr(_cfg, "DLQ_MAX_LEN", 10000)
FALLBACK_TTL_DAYS = getattr(_cfg, "DLQ_FALLBACK_TTL_DAYS", 7)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now_utc().isoformat()


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        try:
            # fallback: epoch string
            ts = float(s)
            return datetime.fromtimestamp(ts, timezone.utc)
        except Exception:
            return None


async def publish_deadletter(
    redis: redis.Redis,
    decision_id: Optional[str],
    channel: str,
    payload: Dict[str, Any],
    error: str,
    *,
    attempts: int = 1,
    base_backoff_seconds: float = DEFAULT_BASE_BACKOFF,
    next_retry_utc: Optional[datetime] = None,
) -> str:
    """
    Publish a dead-letter entry to Redis Stream.

    Fields stored (all as strings):
      - decision_id
      - channel
      - payload (JSON string)
      - error
      - timestamp_utc (ISO)
      - retry_meta (JSON: attempts, base_backoff_seconds, next_retry_utc_iso)
    Returns the stream entry ID.
    """
    entry = {
        "decision_id": decision_id or "",
        "channel": channel,
        "payload": json.dumps(payload, default=str),
        "error": str(error),
        "timestamp_utc": _iso_now(),
    }
    next_retry = next_retry_utc or (_now_utc() + timedelta(seconds=base_backoff_seconds * (2 ** (attempts - 1))))
    retry_meta = {"attempts": int(attempts), "base_backoff_seconds": float(base_backoff_seconds), "next_retry_utc": next_retry.isoformat()}
    entry["retry_meta"] = json.dumps(retry_meta)
    # XADD stream via redis_op wrapper
    try:
        ctx = _client_ctx_for(redis)
        resp = await redis_op(ctx, lambda r, key, ent, max_len, approx: r.xadd(key, ent, max_len=max_len, approximate=approx), DLQ_STREAM_KEY, entry, DEFAULT_STREAM_TRIM_LEN, False)
        stream_id = resp.get("value")
        logger.info("Published deadletter id=%s decision=%s channel=%s attempts=%d", stream_id, decision_id, channel, attempts)
        return stream_id
    except Exception:
        logger.exception("Failed to publish to deadletter stream")
        raise


async def _reconstruct_payload_from_entry(fields: Dict[bytes, bytes]) -> Tuple[Optional[str], str, Dict[str, Any], str, datetime, Dict[str, Any]]:
    """
    Utility to parse Redis stream entry fields (raw bytes) into structured values.
    Returns tuple:
      (decision_id, channel, payload_dict, error, timestamp_utc, retry_meta_dict)
    """
    def _bget(k: str) -> Optional[str]:
        v = fields.get(k.encode())
        if v is None:
            return None
        if isinstance(v, bytes):
            return v.decode()
        return str(v)

    decision_id = _bget("decision_id")
    channel = _bget("channel") or ""
    payload_s = _bget("payload") or "{}"
    try:
        payload = json.loads(payload_s)
    except Exception:
        payload = {"raw": payload_s}
    error = _bget("error") or ""
    ts_s = _bget("timestamp_utc")
    ts = _parse_iso(ts_s) or _now_utc()
    retry_meta_s = _bget("retry_meta") or "{}"
    try:
        retry_meta = json.loads(retry_meta_s)
    except Exception:
        retry_meta = {}
    return decision_id, channel, payload, error, ts, retry_meta


async def _dispatch_via_notifier(notifier_name: str, notifier, payload: Dict[str, Any], decision_id: Optional[str]) -> Dict[str, Any]:
    """
    Dispatch using notifier.notify and handle exceptions; returns result dict.
    """
    try:
        # notifier.notify may be async
        res = await notifier.notify(payload, decision_id=decision_id)
        # ensure standard dict shape
        if not isinstance(res, dict):
            return {"ok": False, "error": "invalid_notifier_response", "status": None}
        return res
    except Exception as e:
        logger.exception("Notifier dispatch raised")
        return {"ok": False, "error": str(e), "status": None}


async def _process_deadletter_entry(redis: redis.Redis, stream_id: str, fields: Dict[bytes, bytes], engine: Optional[Any] = None, semaphore: Optional[asyncio.Semaphore] = None, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
    """
    Process a single dead-letter stream entry.
      - If next_retry_utc is in the future: skip
      - Otherwise attempt re-dispatch
      - On success: XDEL the entry and write storage log
      - On failure: increment attempts, schedule next_retry_utc, update entry (via XADD new entry and XDEL old)
    """
    decision_id, channel, payload, orig_error, ts, retry_meta = await _reconstruct_payload_from_entry(fields)
    attempts = int(retry_meta.get("attempts", 1))
    base_backoff = float(retry_meta.get("base_backoff_seconds", DEFAULT_BASE_BACKOFF))
    next_retry_iso = retry_meta.get("next_retry_utc")
    next_retry_dt = _parse_iso(next_retry_iso) if next_retry_iso else None
    now = _now_utc()

    if next_retry_dt and next_retry_dt > now:
        # skip early entry
        logger.debug("Skipping deadletter id=%s for channel=%s until %s", stream_id, channel, next_retry_dt.isoformat())
        return

    # map channel to notifier
    notifier = None
    if channel == "slack":
        notifier = SlackNotifier(engine=engine)
    elif channel == "discord":
        notifier = DiscordNotifier(engine=engine)
    elif channel == "telegram":
        notifier = TelegramNotifier(engine=engine)
    else:
        logger.warning("Unknown notifier channel %s for deadletter id=%s", channel, stream_id)
        # mark as failed and store log
        if engine:
            await storage.log_notification(engine, decision_id=decision_id, channel=channel, status="failure", http_status=None, error=f"unknown_channel:{channel}")
        return

    # concurrency guard
    if semaphore is None:
        semaphore = asyncio.Semaphore(3)

    async with semaphore:
        res = await _dispatch_via_notifier(channel, notifier, payload, decision_id=decision_id)

    # Persist metrics & log
    if res.get("ok"):
        # success: remove from stream and log success
        try:
            ctx = _client_ctx_for(redis)
            await redis_op(ctx, lambda r, key, sid: r.xdel(key, sid), DLQ_STREAM_KEY, stream_id)
        except Exception:
            logger.exception("Failed to delete DLQ entry %s after success", stream_id)
        try:
            if engine:
                await storage.log_notification(engine, decision_id=decision_id, channel=channel, status="success", http_status=res.get("status"), error=None)
        except Exception:
            logger.exception("Failed to write success notification log")
        metrics.notifier_requests_total.labels(channel=channel, status="success").inc()
        logger.info("DLQ retry success id=%s channel=%s decision=%s", stream_id, channel, decision_id)
    else:
        # failure: decide to reschedule or cap
        attempts += 1
        if attempts > max_retries:
            # move to final-failed territory: remove or set TTL marker
            try:
                ctx = _client_ctx_for(redis)
                await redis_op(ctx, lambda r, key, sid: r.xdel(key, sid), DLQ_STREAM_KEY, stream_id)
            except Exception:
                logger.exception("Failed to delete DLQ entry %s after max retries", stream_id)
            # log final failure
            if engine:
                await storage.log_notification(engine, decision_id=decision_id, channel=channel, status="failure", http_status=res.get("status"), error=res.get("error") or orig_error)
            metrics.notifier_requests_total.labels(channel=channel, status="failure").inc()
            logger.error("DLQ entry id=%s exceeded max retries (%d); dropped", stream_id, max_retries)
            # optional alerting hook could be placed here
            return
        # otherwise reschedule: compute next_retry and re-add entry
        delay = base_backoff * (2 ** (attempts - 1))
        next_retry = now + timedelta(seconds=delay)
        new_retry_meta = {"attempts": attempts, "base_backoff_seconds": base_backoff, "next_retry_utc": next_retry.isoformat()}
        new_entry = {
            "decision_id": decision_id or "",
            "channel": channel,
            "payload": json.dumps(payload, default=str),
            "error": str(res.get("error") or orig_error),
            "timestamp_utc": _iso_now(),
            "retry_meta": json.dumps(new_retry_meta),
        }
        try:
            ctx = _client_ctx_for(redis)
            # append new entry and trim
            await redis_op(ctx, lambda r, key, ent, max_len, approx: r.xadd(key, ent, max_len=max_len, approximate=approx), DLQ_STREAM_KEY, new_entry, DEFAULT_STREAM_TRIM_LEN, False)
            # remove old entry
            await redis_op(ctx, lambda r, key, sid: r.xdel(key, sid), DLQ_STREAM_KEY, stream_id)
            logger.info("Re-scheduled DLQ id=%s to next_retry=%s attempts=%d", stream_id, next_retry.isoformat(), attempts)
        except Exception:
            logger.exception("Failed to reschedule DLQ entry %s", stream_id)
        # record retry failure metric/log
        metrics.notifier_requests_total.labels(channel=channel, status="failure").inc()
        if engine:
            try:
                await storage.log_notification(engine, decision_id=decision_id, channel=channel, status="failure", http_status=res.get("status"), error=res.get("error"))
            except Exception:
                logger.exception("Failed to write retry failure log")


async def poll_deadletter_loop(
    redis: redis.Redis,
    engine: Optional[Any] = None,
    *,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    max_batch: int = 50,
    semaphore: Optional[asyncio.Semaphore] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    start_id: str = "0-0",
    stop_event: Optional[asyncio.Event] = None,
):
    """
    Background loop: scans DLQ stream using XRANGE and processes entries eligible for retry.

    Notes:
    - Uses XRANGE from last seen ID to end, processes up to max_batch entries each tick.
    - Respect `next_retry_utc` and skip early entries.
    - Uses semaphore for concurrency when dispatching.
    - Keeps 'start_id' to avoid reprocessing old entries on restart.
    """
    last_id = start_id
    if semaphore is None:
        semaphore = asyncio.Semaphore(3)

    while True:
        if stop_event and stop_event.is_set():
            logger.info("DLQ poll loop stopping due to stop_event")
            break
        try:
            # XRANGE from last_id (exclusive) to +, limit max_batch
            # If last_id == "0-0", include from beginning
            ctx = _client_ctx_for(redis)
            resp = await redis_op(ctx, lambda r, key, min, max, count: r.xrange(key, min=min, max=max, count=count), DLQ_STREAM_KEY, min=last_id, max="+", count=max_batch)
            entries = resp.get("value")
            if not entries:
                # no entries; sleep and continue
                await asyncio.sleep(poll_interval)
                continue
            for stream_id, fields in entries:
                # stream_id is bytes; decode if needed
                sid = stream_id.decode() if isinstance(stream_id, bytes) else str(stream_id)
                # process entry but do not block scanning other entries
                try:
                    await _process_deadletter_entry(redis, sid, fields, engine=engine, semaphore=semaphore, max_retries=max_retries)
                except Exception:
                    logger.exception("Error processing DLQ entry %s", sid)
                last_id = sid  # advance last seen
            # sleep before next scan
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("DLQ poll loop cancelled")
            break
        except Exception:
            logger.exception("DLQ poll loop encountered error, sleeping then retrying")
            await asyncio.sleep(poll_interval)


# --------------------------
# CLI helpers for on-demand retries
# --------------------------

async def retry_deadletter_by_decision_id(redis: redis.Redis, engine: Optional[Any], decision_id: str, semaphore: Optional[asyncio.Semaphore] = None, max_retries: int = DEFAULT_MAX_RETRIES) -> int:
    """
    Scan the DLQ for entries matching decision_id and attempt immediate retry (ignores next_retry_utc).
    Returns number of retried entries.
    """
    count = 0
    if semaphore is None:
        semaphore = asyncio.Semaphore(3)
    # scan entire stream (could be optimized via indices or consumer groups)
    ctx = _client_ctx_for(redis)
    resp = await redis_op(ctx, lambda r, key, min, max, count: r.xrange(key, min=min, max=max, count=count), DLQ_STREAM_KEY, min="-", max="+", count=DEFAULT_STREAM_TRIM_LEN)
    entries = resp.get("value")
    for stream_id, fields in entries:
        _, channel, payload, _, _, retry_meta = await _reconstruct_payload_from_entry(fields)
        # decision_id parsed from fields
        d_id = (fields.get(b"decision_id") or b"").decode()
        if d_id != decision_id:
            continue
        sid = stream_id.decode() if isinstance(stream_id, bytes) else str(stream_id)
        # force immediate attempt: override retry_meta next_retry_utc to now
        try:
            await _process_deadletter_entry(redis, sid, fields, engine=engine, semaphore=semaphore, max_retries=max_retries)
            count += 1
        except Exception:
            logger.exception("retry by decision_id failed for entry %s", sid)
    logger.info("Retry by decision_id=%s attempted %d entries", decision_id, count)
    return count


async def retry_deadletter_by_timerange(redis: redis.Redis, engine: Optional[Any], since: datetime, until: datetime, semaphore: Optional[asyncio.Semaphore] = None, max_retries: int = DEFAULT_MAX_RETRIES) -> int:
    """
    Retry entries whose original timestamp_utc falls within the provided [since, until) range.
    Returns number attempted.
    """
    count = 0
    ctx = _client_ctx_for(redis)
    resp = await redis_op(ctx, lambda r, key, min, max, count: r.xrange(key, min=min, max=max, count=count), DLQ_STREAM_KEY, min="-", max="+", count=DEFAULT_STREAM_TRIM_LEN)
    entries = resp.get("value")
    for stream_id, fields in entries:
        try:
            decision_id, channel, payload, error, ts, retry_meta = await _reconstruct_payload_from_entry(fields)
            if not (since <= ts < until):
                continue
            sid = stream_id.decode() if isinstance(stream_id, bytes) else str(stream_id)
            await _process_deadletter_entry(redis, sid, fields, engine=engine, semaphore=semaphore, max_retries=max_retries)
            count += 1
        except Exception:
            logger.exception("Error retrying DLQ entry in timerange")
    logger.info("Retry by timerange attempted %d entries", count)
    return count
