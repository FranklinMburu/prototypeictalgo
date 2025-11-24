from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any, Callable, Awaitable

# avoid importing reasoner_service at module import time; defer into function to
# keep test imports lightweight and allow tests to monkeypatch sys.modules

logger = logging.getLogger(__name__)


class RedisUnavailable(Exception):
    pass


class RedisOpFailed(Exception):
    pass


async def redis_op(ctx, op_fn: Callable[..., Awaitable[Any]], *op_args, retries: int = 1, **op_kwargs) -> Any:
    """Execute a redis operation with a single reconnect+retry.

    ctx: orchestrator instance (so we can call ctx._ensure_redis)
    op_fn: async callable that accepts a redis client and performs the op. Any
        additional positional/keyword args passed to redis_op will be forwarded
        to op_fn after the redis client.
    retries: number of retries after reconnect (default 1)

    Raises:
      RedisUnavailable if redis is not available after ensure step.
      RedisOpFailed if operation fails after retries.
    """
    # import get_settings and metrics lazily to avoid import-time failures in tests
    try:
        from reasoner_service.config import get_settings
        from reasoner_service.metrics import (
            redis_op_errors_total,
            redis_op_retries_total,
            redis_circuit_opened_total,
            redis_reconnect_attempts,
        )
    except Exception:
        # create lightweight fallbacks
        def get_settings():
            class _S:
                REDIS_RECONNECT_JITTER_MS = 100
            return _S()
        class _FakeMetric:
            def inc(self, *a, **k):
                return
        redis_op_errors_total = _FakeMetric()
        redis_op_retries_total = _FakeMetric()
        redis_circuit_opened_total = _FakeMetric()
        redis_reconnect_attempts = _FakeMetric()
    cfg = get_settings()

    # dynamic import so tests can monkeypatch redis.asyncio
    try:
        import importlib

        aioredis_mod = importlib.import_module("redis.asyncio")
    except Exception:
        aioredis_mod = None

    # circuit-check: if circuit is open, raise RedisUnavailable
    now = time_monotonic = None
    try:
        now = asyncio.get_event_loop().time()
    except Exception:
        now = None
    if getattr(ctx, "_redis_circuit_open_until", 0) and ctx._redis_circuit_open_until > 0:
        try:
            redis_circuit_opened_total.inc()
        except Exception:
            pass
        logger.warning("redis circuit open, skipping redis op")
        raise RedisUnavailable("redis circuit open")

    # increment call metric
    try:
        from reasoner_service.metrics import redis_op_calls_total
        redis_op_calls_total.inc()
    except Exception:
        pass

    # ensure connection if needed
    if ctx._redis is None:
        await ctx._ensure_redis()
        if ctx._redis is None:
            raise RedisUnavailable("no redis available after ensure")

    # attempt op with a single reconnect+retry
    attempt = 0
    last_exc = None
    while attempt <= retries:
        attempt += 1
        try:
            res = op_fn(ctx._redis, *op_args, **op_kwargs)
            if asyncio.iscoroutine(res):
                res = await res
            return {"ok": True, "value": res}
        except Exception as e:
            last_exc = e
            try:
                redis_op_errors_total.inc()
            except Exception:
                pass
            logger.exception("redis op failed on attempt %d: %s", attempt, e)
            if attempt > retries:
                break
            try:
                redis_op_retries_total.inc()
            except Exception:
                pass
            # try reconnect
            try:
                await ctx._ensure_redis()
            except Exception:
                pass
            # if still no client, raise unavailable
            if ctx._redis is None:
                raise RedisUnavailable("redis unavailable after reconnect")
            # small jitter before retry
            await asyncio.sleep(random.uniform(0, cfg.REDIS_RECONNECT_JITTER_MS) / 1000.0)

    # final failure
    raise RedisOpFailed(str(last_exc))
