#!/usr/bin/env python3
"""Simple CLI to inspect Redis DLQ key."""
import asyncio
import os
import sys
import json

from reasoner_service.config import get_settings
try:
    import redis.asyncio as aioredis
except Exception:
    aioredis = None

async def main():
    cfg = get_settings()
    if not cfg.REDIS_DLQ_ENABLED:
        print("Redis DLQ not enabled in config")
        return
    if aioredis is None:
        print("redis.asyncio not installed")
        return
    # create client (support both sync-from_url and awaitable factory)
    try:
        r = await aioredis.from_url(cfg.REDIS_URL)
    except TypeError:
        r = aioredis.from_url(cfg.REDIS_URL)
    vals = await r.lrange(cfg.REDIS_DLQ_KEY, 0, -1)
    for i, v in enumerate(vals):
        try:
            print(i, json.loads(v))
        except Exception:
            print(i, v)
    await r.close()

if __name__ == '__main__':
    asyncio.run(main())
