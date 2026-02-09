"""
Helper to load a JSON snapshot of aggregated performance metrics.
Returns a mapping of (symbol, model, session) -> metrics dict.
"""
import json
import logging
from typing import Any, Dict, Tuple


logger = logging.getLogger(__name__)


def load_metrics_snapshot(path: str) -> Dict[Tuple[str, str, str], Dict[str, Any]]:
    snapshot: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for k, v in raw.items():
            try:
                if isinstance(k, str) and k.startswith("["):
                    key_tuple = tuple(json.loads(k))
                else:
                    parts = [p.strip() for p in k.split(",")]
                    key_tuple = (parts[0], parts[1], parts[2])
                snapshot[key_tuple] = v
            except Exception as e:
                logger.warning("Skipping invalid metrics key %s: %s", k, e)
    except Exception as e:
        logger.error("Failed to load metrics snapshot: %s", e, exc_info=True)
    return snapshot
