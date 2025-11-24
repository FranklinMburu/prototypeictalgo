"""
memory_service.py

Async Redis-backed memory layer for Smart Money trading alerts.

This single-file module includes:
 - normalized alert ingestion, atomic Lua-backed ring buffer writes with dedupe
 - Persistent Symbol Registry
 - Analytical Metrics Layer (trend acceleration, bias shift rate, volatility index)
 - Reasoner stub (consumes fused snapshot -> structured decision)
 - Validation hooks (schema checks + optional HMAC signature verification)
 - Structured logging & metrics (Redis counters + Python logging)
 - Simulation engine to replay alerts for stress testing
 - Timeframe Cohesion Index (TF cohesion measurement)
 - Safe distributed locking with token + Lua unlock
 - Performance and concurrency improvements as requested
"""
from __future__ import annotations
import asyncio
import json
import time
import math
import uuid
import hashlib
import hmac
import logging
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

import statistics

# --- LLM REASONER INTEGRATION ---
try:
    from reasoner_service.reasoner import reason_from_snapshot as llm_reason_from_snapshot
except ImportError:
    llm_reason_from_snapshot = None

try:
    import redis.asyncio as aioredis
    from redis.exceptions import NoScriptError
except Exception:
    aioredis = None
    NoScriptError = Exception

# --- CONFIG ------------------------------------------------------------------
TF_ORDER = ["D", "H4", "H1", "M15", "M5", "M3"]
WINDOW_CAPS = {"D": 8, "H4": 12, "H1": 24, "M15": 48, "M5": 80, "M3": 120}
WEIGHTS = {"D": 3.0, "H4": 2.0, "H1": 1.5, "M15": 1.0, "M5": 0.8, "M3": 0.6}

# TTLs (seconds)
RB_TTL = 3 * 24 * 3600
FUSE_TTL = 6 * 3600
BIAS_HIST_TTL = 30 * 24 * 3600
LOCK_TTL_MS = 1000
SYMBOL_REGISTRY_TTL = 7 * 24 * 3600  # considered active if seen within 7 days

# Metrics keys prefix
METRICS_PREFIX = "metrics"

# Logging
logger = logging.getLogger("memory_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(ch)

# --- INTERNAL CACHES / LITERALS ----------------------------------------------
_STORE_ALERT_SHA: Optional[str] = None  # cached SHA for the store_alert Lua script

# Lua script for atomic dedupe + lpush + ltrim + set head + expire
_STORE_ALERT_LUA = r"""
-- KEYS[1] = head_key
-- KEYS[2] = rb_key
-- ARGV[1] = new_ts
-- ARGV[2] = payload_json
-- ARGV[3] = cap
-- ARGV[4] = rb_ttl
-- ARGV[5] = head_ttl
local head = redis.call('get', KEYS[1])
if head and tonumber(head) >= tonumber(ARGV[1]) then
  return 0
end
redis.call('lpush', KEYS[2], ARGV[2])
redis.call('ltrim', KEYS[2], 0, tonumber(ARGV[3]) - 1)
redis.call('set', KEYS[1], ARGV[1])
redis.call('expire', KEYS[2], tonumber(ARGV[4]))
redis.call('expire', KEYS[1], tonumber(ARGV[5]))
return 1
"""

# Lua unlock script (deletes key only if token matches)
_UNLOCK_LUA = r"""
-- KEYS[1] = lock_key
-- ARGV[1] = token
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


from utils.redis_wrapper import redis_op


def _client_ctx_for(client):
    class Ctx:
        def __init__(self, cli):
            self._redis = cli
            self._redis_circuit_open_until = 0
        async def _ensure_redis(self):
            return

    return Ctx(client)


async def _call_redis(client, method: str, *args, **kwargs):
    """Call method on raw redis client via redis_op and return raw value."""
    ctx = _client_ctx_for(client)
    # op_fn will call getattr(r, method)(*args, **kwargs)
    resp = await redis_op(ctx, lambda r, *a, **kw: getattr(r, method)(*a, **kw), *args, **kwargs)
    return resp.get("value")


async def _run_pipeline(client, pipeline_fn):
    """Run a pipeline function against client.pipeline() inside redis_op. pipeline_fn is a sync callable that receives the pipeline and queues commands (must not call execute)."""
    ctx = _client_ctx_for(client)

    def op_fn(r):
        p = r.pipeline()
        pipeline_fn(p)
        return p.execute()

    resp = await redis_op(ctx, op_fn)
    return resp.get("value")

# --- HELPERS -----------------------------------------------------------------
def now_ms() -> int:
    return int(time.time() * 1000)


def _safe_get(d: dict, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


# --- VALIDATION HOOKS --------------------------------------------------------
def validate_payload_schema(payload: Dict[str, Any]) -> None:
    """Basic schema checks. Raises ValueError when invalid.

    Expected minimal keys: symbol, timeframe or tf, timestamp_ms or ts, candle.c OR close
    Keep this lightweight: detailed validation should be done upstream if needed.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    if not payload.get("symbol"):
        raise ValueError("missing required field: symbol")
    if not (payload.get("timeframe") or payload.get("tf")):
        raise ValueError("missing required field: timeframe/tf")
    if not (payload.get("timestamp_ms") or payload.get("ts")):
        raise ValueError("missing required field: timestamp_ms/ts")
    # accept candle.c OR top-level close fallback
    if _safe_get(payload, "candle", "c") is None and payload.get("close") is None:
        raise ValueError("missing required field: candle.c or close")


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """HMAC-SHA256 verification. Returns True if signature matches.

    signature: hex digest string from header
    secret: shared secret string
    """
    if not signature or not secret:
        return False
    mac = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)


# --- NORMALIZATION -----------------------------------------------------------
def normalize_alert(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize incoming alert payload into the compact alert we store in Redis.

    - Keeps schema small and consistent across producers
    """
    s = payload.get("structure", {}) or {}
    tf = payload.get("timeframe") or payload.get("tf") or "M5"
    ts = int(payload.get("timestamp_ms") or payload.get("ts") or now_ms())
    # fallback: candle.c or top-level close
    close = _safe_get(payload, "candle", "c", default=None)
    if close is None:
        close = payload.get("close", 0.0)
    close = float(close)

    return {
        "symbol": payload.get("symbol"),
        "tf": tf,
        "ts": ts,
        "close": close,
        "bias_local": payload.get("bias_local", "neutral"),
        "regime": payload.get("regime", "unknown"),
        "structure": {
            "bos": _safe_get(s, "bos", "direction", default="none"),
            "sweep": _safe_get(s, "sweep", "side", default="none"),
            "ob_count": len(s.get("order_blocks", [])) if isinstance(s.get("order_blocks"), list) else 0,
            "imbalance_count": len(s.get("imbalance", [])) if isinstance(s.get("imbalance"), list) else 0,
        },
    }


# --- SYMBOL REGISTRY --------------------------------------------------------
async def register_symbol(redis: Any, symbol: str) -> None:
    """Mark symbol as recently-seen and add to registry set.

    Stores a hash with last_seen timestamp for quick inspection.
    """
    key_set = "symbols:active"
    key_meta = f"symbol:meta:{symbol}"
    ts = now_ms()
    # Wrap pipeline execution in redis_op
    ctx = type("C", (), {"_redis": redis, "_redis_circuit_open_until": 0, "_ensure_redis": (lambda self: None)})
    await redis_op(ctx, lambda r, ks, sym, km, lst: (lambda p: (p.sadd(ks, sym), p.hset(km, mapping={"last_seen": str(ts)}), p.expire(km, lst), p.execute()))(r.pipeline()), key_set, symbol, key_meta, SYMBOL_REGISTRY_TTL)
    logger.debug("registered symbol %s", symbol)


async def get_active_symbols(redis: Any) -> List[str]:
    """Return list of currently active symbols (members of symbols:active).

    Note: this set can accumulate old symbols; callers may cross-check last_seen.
    """
    key_set = "symbols:active"
    ctx = type("C", (), {"_redis": redis, "_redis_circuit_open_until": 0, "_ensure_redis": (lambda self: None)})
    resp = await redis_op(ctx, lambda r, key: r.smembers(key), key_set)
    items = resp.get("value")
    return [i.decode() if isinstance(i, bytes) else i for i in items]


async def prune_symbol_registry(redis: Any, max_age_ms: int) -> int:
    """Prune registry entries last_seen older than max_age_ms. Returns number removed.

    Useful for periodic background cleanup.
    """
    now = now_ms()
    removed = 0
    members = await get_active_symbols(redis)
    for sym in members:
        meta_raw = await _call_redis(redis, "hget", f"symbol:meta:{sym}", "last_seen")
        if not meta_raw:
            await _call_redis(redis, "srem", "symbols:active", sym)
            removed += 1
            continue
        try:
            ts = int(meta_raw)
            if now - ts > max_age_ms:
                await _call_redis(redis, "srem", "symbols:active", sym)
                removed += 1
        except Exception:
            await _call_redis(redis, "srem", "symbols:active", sym)
            removed += 1
    logger.info("pruned %d symbols from registry", removed)
    return removed


# --- LUA SCRIPT LOADER ------------------------------------------------------
async def _get_store_alert_sha(redis: Any) -> str:
    """Load and cache the Lua script that atomically writes the ring buffer and head."""
    global _STORE_ALERT_SHA
    if _STORE_ALERT_SHA:
        return _STORE_ALERT_SHA
    try:
        sha = await _call_redis(redis, "script_load", _STORE_ALERT_LUA)
        _STORE_ALERT_SHA = sha
        return sha
    except Exception:
        # fallback: try to load by script_load again (best-effort)
        try:
            sha = await _call_redis(redis, "script_load", _STORE_ALERT_LUA)
            _STORE_ALERT_SHA = sha
            return sha
        except Exception:
            raise


# --- SAFE LOCK HELPERS ------------------------------------------------------
async def _acquire_lock(redis: Any, key: str, ttl_ms: int) -> Optional[str]:
    """Acquire a lock with a random token. Returns token or None."""
    token = uuid.uuid4().hex
    try:
        # SET key token NX PX ttl_ms
        ctx = type("C", (), {"_redis": redis, "_redis_circuit_open_until": 0, "_ensure_redis": (lambda self: None)})
        resp = await redis_op(ctx, lambda r, k, tok, nx, px: r.set(k, tok, nx=nx, px=px), key, token, True, ttl_ms)
        ok = resp.get("value")
        if ok:
            return token
        return None
    except Exception:
        return None


async def _release_lock(redis: Any, key: str, token: str) -> bool:
    """Release lock only if token matches (atomic). Returns True if released."""
    try:
        res = await _call_redis(redis, "eval", _UNLOCK_LUA, 1, key, token)
        return bool(res)
    except Exception:
        logger.exception("failed to release lock %s, falling back to safer path", key)
        # try fallback via eval through redis client wrapper
    try:
        resp = await _call_redis(redis, "eval", _UNLOCK_LUA, 1, key, token)
        return bool(resp)
    except NoScriptError:
        # script not loaded/executed; fallback to simple get+del (best-effort)
        try:
            cur = await _call_redis(redis, "get", key)
            if cur and (isinstance(cur, bytes) and cur.decode() == token or cur == token):
                await _call_redis(redis, "delete", key)
                return True
            return False
        except Exception:
            return False
    except Exception:
        return False
async def store_alert(redis: Any, alert: Dict[str, Any], cap: Optional[int] = None) -> bool:
    """Atomically store normalized alert into ring buffer using Lua script. Returns True if stored (not duplicate)."""
    symbol = alert.get("symbol")
    tf = alert.get("tf")
    if not symbol or not tf:
        return False
    key_head = f"head:{symbol}:{tf}"
    key_rb = f"rb:{symbol}:{tf}"
    cap = cap or WINDOW_CAPS.get(tf, 50)
    args = [str(alert.get("ts")), json.dumps(alert), str(cap), str(RB_TTL), str(RB_TTL)]
    try:
        sha = await _get_store_alert_sha(redis)
        try:
            res = await _call_redis(redis, "evalsha", sha, 2, key_head, key_rb, *args)
        except NoScriptError:
            # script not found server-side, reload and retry
            sha = await _get_store_alert_sha(redis)
            res = await _call_redis(redis, "evalsha", sha, 2, key_head, key_rb, *args)
        return int(res) == 1
    except Exception:
        logger.exception("store_alert failed for %s %s", alert.get("symbol"), alert.get("tf"))
        return False


async def fetch_window(redis: Any, symbol: str, tf: str, n: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch up to `n` normalized alerts from the ring buffer (newest first).

    Returns deduplicated list ordered newest->oldest.
    """
    key_rb = f"rb:{symbol}:{tf}"
    cap = n or WINDOW_CAPS.get(tf, 50)
    items = await _call_redis(redis, "lrange", key_rb, 0, cap - 1)
    alerts: List[Dict[str, Any]] = []
    for raw in items:
        try:
            if isinstance(raw, bytes):
                s = raw.decode()
            else:
                s = str(raw)
            alerts.append(json.loads(s))
        except Exception:
            continue
    seen = set()
    dedup = []
    for a in alerts:
        t = a.get("ts")
        if t in seen:
            continue
        seen.add(t)
        dedup.append(a)
    return dedup


# --- SUMMARIZATION, ALIGNMENT -----------------------------------------------
def majority(items: List[str]) -> str:
    if not items:
        return "neutral"
    c = Counter(items)
    top = c.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return items[0]
    return top[0][0]


def summarize_tf(alerts: List[Dict[str, Any]], tf: str) -> Optional[Dict[str, Any]]:
    if not alerts:
        return None
    latest = alerts[0]
    bos_seq = [a.get("structure", {}).get("bos", "none") for a in alerts[:3]]
    bos = bos_seq[0] if bos_seq else "none"
    if any((b != bos and b != "none") for b in bos_seq[1:]):
        bos = "none"
    bias = majority([a.get("bias_local", "neutral") for a in alerts[:5]])
    sweeps = sum(1 for a in alerts if a.get("structure", {}).get("sweep", "none") != "none")
    sweep_rate = sweeps / max(1, len(alerts))
    ranges: List[float] = []
    for i in range(min(20, max(0, len(alerts) - 1))):
        try:
            ranges.append(abs(alerts[i]["close"] - alerts[i + 1]["close"]))
        except Exception:
            continue
    range_avg = sum(ranges) / len(ranges) if ranges else 0.0
    range_p95 = 0.0
    if ranges and len(ranges) >= 2:
        sr = sorted(ranges)
        idx = max(0, min(len(sr) - 1, int(0.95 * len(sr)) - 1))
        range_p95 = sr[idx]
    else:
        range_p95 = range_avg

    return {
        "tf": tf,
        "last_ts": latest.get("ts"),
        "last_close": latest.get("close"),
        "bias_local": bias,
        "bos": bos,
        "sweep": latest.get("structure", {}).get("sweep", "none"),
        "ob_count": latest.get("structure", {}).get("ob_count", 0),
        "imbalance_count": latest.get("structure", {}).get("imbalance_count", 0),
        "regime": latest.get("regime", "unknown"),
        "window_stats": {
            "range_avg": round(range_avg, 6),
            "range_p95": round(range_p95, 6),
            "sweep_rate": round(sweep_rate, 4),
        },
    }


def align_score(tf_summaries: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
    if not tf_summaries:
        return 0.0, []
    sign = {"bullish": 1, "bearish": -1, "neutral": 0}
    score_num = 0.0
    score_den = 0.0
    conflicts: List[str] = []
    by_tf = {s["tf"]: s for s in tf_summaries}
    ordered = [by_tf[t] for t in TF_ORDER if t in by_tf]
    for s in ordered:
        w = WEIGHTS.get(s["tf"], 1.0)
        score_den += w
        score_num += w * sign.get(s.get("bias_local", "neutral"), 0)
    base = abs(score_num) / score_den if score_den else 0.0
    for i in range(len(ordered) - 1):
        a = ordered[i].get("bias_local")
        b = ordered[i + 1].get("bias_local")
        if (a == "bullish" and b == "bearish") or (a == "bearish" and b == "bullish"):
            conflicts.append(f"{ordered[i]['tf']}={a} vs {ordered[i+1]['tf']}={b}")
    penalty = 0.1 * len(conflicts)
    score = max(0.0, round(base - penalty, 4))
    return score, conflicts


# --- METRICS HELPER ---------------------------------------------------------
async def record_metric(redis: Any, name: str, value: float = 1.0, ttl: int = 7 * 24 * 3600) -> None:
    """Increment numeric metric. Chooses integer or float increment accordingly.

    Keys are: metrics:{name}
    """
    key = f"{METRICS_PREFIX}:{name}"
    try:
        # prefer integer increments if value is an integer
        if float(value).is_integer():
            await _call_redis(redis, "incrby", key, int(value))
        else:
            # incrbyfloat is supported by aioredis
            await _call_redis(redis, "incrbyfloat", key, float(value))
        await _call_redis(redis, "expire", key, ttl)
    except Exception:
        logger.exception("failed to record metric %s", name)


# --- FUSION ------------------------------------------------------------------
async def _compute_volatility_index_from_alerts(alerts_by_tf: Dict[str, List[Dict[str, Any]]]) -> float:
    """Compute volatility index from already-fetched alerts to avoid extra I/O."""
    vals = []
    for tf, alerts in alerts_by_tf.items():
        if not alerts:
            continue
        ranges = []
        for i in range(min(19, len(alerts) - 1)):
            try:
                ranges.append(abs(alerts[i]["close"] - alerts[i + 1]["close"]))
            except Exception:
                continue
        if not ranges:
            continue
        p95 = sorted(ranges)[max(0, int(0.95 * len(ranges)) - 1)] if len(ranges) >= 2 else statistics.mean(ranges)
        vals.append((tf, p95))
    if not vals:
        return 0.0
    weighted = 0.0
    weight_sum = 0.0
    for tf, v in vals:
        w = WEIGHTS.get(tf, 1.0)
        weighted += w * v
        weight_sum += w
    raw = weighted / weight_sum if weight_sum else 0.0
    norm = math.tanh(raw / 10.0)
    return float(round(norm, 4))


def compute_timeframe_cohesion(tf_summaries: List[Dict[str, Any]]) -> float:
    """Measure how synchronized the timeframes are.

    TCI approaches 1 when all TFs share the same bias, drops toward 0 when mixed.
    Uses WEIGHTS to emphasize higher TFs.
    """
    if not tf_summaries:
        return 0.0
    sign = {"bullish": 1, "bearish": -1, "neutral": 0}
    weighted = 0.0
    weight_sum = 0.0
    signs = []
    for s in tf_summaries:
        b = s.get("bias_local", "neutral")
        w = WEIGHTS.get(s.get("tf"), 1.0)
        val = sign.get(b, 0)
        weighted += w * val
        weight_sum += w
        signs.append(val)
    if weight_sum == 0:
        return 0.0
    if len(signs) <= 1:
        return 1.0
    var = statistics.pvariance(signs)
    cohesion = max(0.0, 1.0 - var)
    return round(cohesion, 4)


def _compute_trend_acceleration_from_alerts(alerts: List[Dict[str, Any]], lookback: int = 10) -> float:
    """Compute trend acceleration from a list of alerts (oldest->newest expected)."""
    if not alerts or len(alerts) < 3:
        return 0.0
    closes = [a["close"] for a in list(reversed(alerts))[:lookback]]  # oldest -> newest
    if len(closes) < 3:
        return 0.0
    d1 = [closes[i + 1] - closes[i] for i in range(len(closes) - 1)]
    d2 = [d1[i + 1] - d1[i] for i in range(len(d1) - 1)]
    try:
        mean_price = statistics.mean(closes)
        acc = statistics.mean(d2) / (mean_price if mean_price else 1.0)
    except Exception:
        acc = 0.0
    return float(acc)


async def fuse(redis: Any, symbol: str) -> Optional[Dict[str, Any]]:
    """Build and cache fused snapshot for `symbol`.

    Improvements:
     - safe token lock + Lua unlock
     - fetch each TF window once and reuse for metrics
     - batch metric updates (pipeline)
     - attach cohesion and analytics as requested
    """
    lock_key = f"lock:fuse:{symbol}"
    t0 = time.time()
    token = await _acquire_lock(redis, lock_key, LOCK_TTL_MS)
    if not token:
        raw = await _call_redis(redis, "get", f"fuse:{symbol}")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    try:
        alerts_by_tf: Dict[str, List[Dict[str, Any]]] = {}
        summaries: List[Dict[str, Any]] = []
        last_ts = 0

        # Fetch each TF once
        for tf in TF_ORDER:
            alerts = await fetch_window(redis, symbol, tf)
            alerts_by_tf[tf] = alerts
            s = summarize_tf(alerts, tf) if alerts else None
            if s:
                summaries.append(s)
                if s.get("last_ts"):
                    last_ts = max(last_ts, int(s.get("last_ts", 0)))

        if not summaries:
            return None

        score, conflicts = align_score(summaries)
        cohesion = compute_timeframe_cohesion(summaries)
        # analytics computed from already-fetched alerts to avoid double I/O
        vol_index = await _compute_volatility_index_from_alerts(alerts_by_tf)
        # accel_M5: try compute from fetched M5 alerts; fallback to helper that will fetch if needed
        accel_m5 = _compute_trend_acceleration_from_alerts(alerts_by_tf.get("M5", []), lookback=20)

        snapshot = {
            "symbol": symbol,
            "snapshot_ts": last_ts or now_ms(),
            "order": TF_ORDER,
            "tfs": summaries,
            "alignment_score": score,
            "conflicts": conflicts,
            "cohesion": cohesion,
            "analytics": {
                "volatility_index": vol_index,
                "accel_M5": accel_m5,
            },
            "versions": {"memory": "m_1.1.1", "schema": "mem_2025_08_10"},
        }

        # cache snapshot
        await _call_redis(redis, "set", f"fuse:{symbol}", json.dumps(snapshot), ex=FUSE_TTL)

        # metrics: batch updates
        latency_ms = int((time.time() - t0) * 1000)
        snapshot_age = now_ms() - snapshot["snapshot_ts"]

        def _queue_metrics(p):
            p.incrby(f"{METRICS_PREFIX}:fuse_count", 1)
            p.expire(f"{METRICS_PREFIX}:fuse_count", 7 * 24 * 3600)
            p.incrby(f"{METRICS_PREFIX}:fuse_latency_count:{symbol}", 1)
            p.expire(f"{METRICS_PREFIX}:fuse_latency_count:{symbol}", 7 * 24 * 3600)
            p.incrby(f"{METRICS_PREFIX}:fuse_latency_sum_ms:{symbol}", latency_ms)
            p.expire(f"{METRICS_PREFIX}:fuse_latency_sum_ms:{symbol}", 7 * 24 * 3600)
            p.set(f"{METRICS_PREFIX}:snapshot_age_ms:{symbol}", str(snapshot_age))
            p.expire(f"{METRICS_PREFIX}:snapshot_age_ms:{symbol}", 24 * 3600)
            for tf, alerts in alerts_by_tf.items():
                llen = len(alerts)
                cap = float(WINDOW_CAPS.get(tf, 50))
                ratio = float(llen) / cap if cap else 0.0
                p.incrbyfloat(f"{METRICS_PREFIX}:rb_fill_ratio:{symbol}:{tf}", ratio)
                p.expire(f"{METRICS_PREFIX}:rb_fill_ratio:{symbol}:{tf}", 7 * 24 * 3600)

        try:
            await _run_pipeline(redis, _queue_metrics)
        except Exception:
            logger.exception("failed to execute metrics pipeline in fuse for %s", symbol)

        return snapshot
    finally:
        # release lock safely using token-based Lua
        try:
            await _release_lock(redis, lock_key, token)
        except Exception:
            logger.exception("failed releasing lock for %s", symbol)


# --- BIAS HISTORY & ON_NEW_ALERT ---------------------------------------------
async def on_new_alert(redis: Any, raw_payload: Dict[str, Any], record_metrics: bool = True) -> Optional[Dict[str, Any]]:
    """Process a new raw alert payload.

    Steps:
      - optional validation
      - normalize
      - atomic store in ring buffer
      - register symbol
      - fuse snapshot
      - append bias history
      - record light metrics (batched when possible)
    """
    # validation
    try:
        validate_payload_schema(raw_payload)
    except ValueError as e:
        logger.warning("payload validation failed: %s", e)
        raise

    alert = normalize_alert(raw_payload)
    if not alert.get("symbol"):
        raise ValueError("payload missing symbol")

    # persist (atomic via Lua)
    stored = await store_alert(redis, alert)
    if not stored:
        if record_metrics:
            await record_metric(redis, "alerts.duplicate", 1)
            # per-symbol duplicate count
            await record_metric(redis, f"alerts.duplicate:{alert['symbol']}", 1)
        return None

    # registry
    await register_symbol(redis, alert["symbol"])

    # metrics (batched-ish)
    if record_metrics:
        # increment total ingested, per-symbol, and per-symbol velocity
        await record_metric(redis, "alerts.ingested", 1)
        await record_metric(redis, f"alerts.symbol:{alert['symbol']}", 1)
        await record_metric(redis, f"alerts.per_symbol:{alert['symbol']}", 1)

    # fuse snapshot
    snap = await fuse(redis, alert["symbol"])

    # bias history
    if snap:
        last = next((t for t in reversed(snap["tfs"]) if t), None)
        if last is None:
            last = snap["tfs"][-1]
        entry = {"ts": snap["snapshot_ts"], "bias": last.get("bias_local"), "score": snap.get("alignment_score")}
        try:
            await _run_pipeline(redis, lambda p: (p.lpush(f"bias_hist:{alert['symbol']}", json.dumps(entry)), p.ltrim(f"bias_hist:{alert['symbol']}", 0, 99), p.expire(f"bias_hist:{alert['symbol']}", BIAS_HIST_TTL)))
        except Exception:
            logger.exception("failed to update bias history for %s", alert["symbol"])
    return snap


# --- ANALYTICAL METRICS LAYER (backwards-compatible wrappers) -----------------
async def compute_trend_acceleration(redis: Any, symbol: str, tf: str, lookback: int = 10) -> float:
    """Public wrapper: compute trend acceleration by fetching alerts if needed."""
    alerts = await fetch_window(redis, symbol, tf, n=lookback)
    # adapt to _compute_trend_acceleration_from_alerts
    return _compute_trend_acceleration_from_alerts(alerts, lookback=lookback)


async def compute_bias_shift_rate(redis: Any, symbol: str, lookback: int = 50) -> float:
    """Compute rate of bias changes (shifts per lookback window) using bias_hist.

    Returns value in [0,1] representing fraction of entries that represent a bias change.
    """
    raw = await _call_redis(redis, "lrange", f"bias_hist:{symbol}", 0, lookback - 1)
    if not raw:
        return 0.0
    biases = []
    for r in raw:
        try:
            if isinstance(r, bytes):
                j = json.loads(r.decode())
            else:
                j = json.loads(r)
            biases.append(j.get("bias"))
        except Exception:
            continue
    if len(biases) < 2:
        return 0.0
    changes = sum(1 for i in range(len(biases) - 1) if biases[i] != biases[i + 1])
    return changes / max(1, len(biases) - 1)


async def compute_volatility_index(redis: Any, symbol: str) -> float:
    """Public wrapper: compute vol index by fetching alerts for TFs."""
    alerts_by_tf: Dict[str, List[Dict[str, Any]]] = {}
    for tf in TF_ORDER:
        alerts_by_tf[tf] = await fetch_window(redis, symbol, tf, n=20)
    return await _compute_volatility_index_from_alerts(alerts_by_tf)



# --- LLM-POWERED REASONER (replaces stub) ---
async def reason_from_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-powered reasoner: calls LLM, validates, repairs, falls back if needed."""
    if llm_reason_from_snapshot is None:
        raise ImportError("reasoner_service not found. Please ensure the reasoner_service package is installed and available.")
    return await llm_reason_from_snapshot(snapshot)


async def reason_from_symbol(redis: Any, symbol: str) -> Optional[Dict[str, Any]]:
    """Helper: fetch fused snapshot and run reasoner stub.

    Returns decision or None if no snapshot.
    """
    raw = await _call_redis(redis, "get", f"fuse:{symbol}")
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    snap = json.loads(raw)
    dec = await reason_from_snapshot(snap)
    # record decision metric
    await record_metric(redis, f"decisions:{symbol}", 1)
    return dec


# --- SIMULATION ENGINE ------------------------------------------------------
async def replay_alerts(redis: Any, alerts: List[Dict[str, Any]], speed: float = 0.0) -> List[Optional[Dict[str, Any]]]:
    """Replay a list of raw alert payloads through on_new_alert.

    - speed: seconds to await between alerts. 0 means as fast as possible.
    Returns list of fused snapshots produced (may contain None for duplicates).
    """
    results: List[Optional[Dict[str, Any]]] = []
    for a in alerts:
        try:
            snap = await on_new_alert(redis, a, record_metrics=False)
            results.append(snap)
            if speed and speed > 0:
                await asyncio.sleep(speed)
        except Exception as e:
            logger.exception("error replaying alert: %s", e)
            results.append(None)
    return results


async def load_alerts_from_file(path: str) -> List[Dict[str, Any]]:
    """Load a JSON file containing a list of alert objects.

    Lightweight helper for ad-hoc simulation.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array of alerts")
    return data


# --- UTILITIES / CLI ---------------------------------------------------------
async def init_redis(url: str = "redis://localhost/0") -> Any:
    return aioredis.from_url(url, decode_responses=False) if aioredis is not None else None


async def inspect_snapshot(redis: Any, symbol: str) -> Optional[Dict[str, Any]]:
    raw = await _call_redis(redis, "get", f"fuse:{symbol}")
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)
