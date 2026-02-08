import asyncio
import logging
from memory_service import init_redis, on_new_alert, inspect_snapshot

logger = logging.getLogger(__name__)

async def main():
    redis = await init_redis()
    # Example alert payload
    alert = {
        "symbol": "BTCUSD",
        "tf": "H1",
        "timestamp_ms": 1723296000000,
        "close": 42000.0,
        "bias_local": "bullish",
        "regime": "trend",
        "structure": {
            "bos": {"direction": "bullish"},
            "sweep": {"side": "none"},
            "order_blocks": [],
            "imbalance": []
        }
    }
    snap = await on_new_alert(redis, alert)
    logger.info(f"Fused snapshot: {snap}")
    # Inspect snapshot
    snap2 = await inspect_snapshot(redis, "BTCUSD")
    logger.info(f"Inspect snapshot: {snap2}")

if __name__ == "__main__":
    asyncio.run(main())
