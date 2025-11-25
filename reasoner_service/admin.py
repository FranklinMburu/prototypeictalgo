from fastapi import APIRouter, HTTPException, Header
from typing import Any, Dict, List
from .config import get_settings
from .orchestrator import DecisionOrchestrator
from utils.redis_wrapper import redis_op

router = APIRouter()
_cfg = get_settings()

# The orchestrator instance should be created by the application and passed in.
# For convenience in small deployments we allow creating a helper to bind an orchestrator.
_bound_orchestrator: DecisionOrchestrator = None


def bind_orchestrator(o: DecisionOrchestrator):
    global _bound_orchestrator
    _bound_orchestrator = o


@router.get("/dlq")
async def dlq_list(max_items: int = 100) -> Dict[str, Any]:
    if not _bound_orchestrator:
        raise HTTPException(status_code=500, detail="orchestrator not bound")
    orch = _bound_orchestrator
    items = []
    # If an orchestrator-provided redis client exists, prefer it (tests inject FakeRedis)
    if getattr(orch, "_redis", None) is not None:
        # use LRANGE to fetch items
        try:
            from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
            _raw_res = await redis_op(orch, lambda r, key, s, e: r.lrange(key, s, e), _cfg.REDIS_DLQ_KEY, 0, max_items - 1)
            raw = _raw_res.get("value") if isinstance(_raw_res, dict) else _raw_res
            for r in raw:
                try:
                    items.append(r if isinstance(r, dict) else r.decode() if isinstance(r, bytes) else r)
                except Exception:
                    items.append(str(r))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        async with orch._dlq_lock:
            items = list(orch._persist_dlq)[:max_items]
    return {"count": len(items), "items": items}


@router.post("/dlq/requeue")
async def dlq_requeue_all(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    if not _bound_orchestrator:
        raise HTTPException(status_code=500, detail="orchestrator not bound")
    # simple token check
    if _cfg.ADMIN_TOKEN:
        if not x_admin_token or x_admin_token != _cfg.ADMIN_TOKEN:
            raise HTTPException(status_code=401, detail="unauthorized")
    orch = _bound_orchestrator
    moved = 0
    if getattr(orch, "_redis", None) is not None:
        # nothing to do; entries remain in Redis
        return {"moved": 0}
    else:
        async with orch._dlq_lock:
            # simply re-append entries to the in-memory list front
            for e in list(orch._persist_dlq):
                orch._persist_dlq.append(e)
                moved += 1
    return {"moved": moved}


@router.post("/dlq/flush")
async def dlq_flush(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    if not _bound_orchestrator:
        raise HTTPException(status_code=500, detail="orchestrator not bound")
    # simple token check
    if _cfg.ADMIN_TOKEN:
        if not x_admin_token or x_admin_token != _cfg.ADMIN_TOKEN:
            raise HTTPException(status_code=401, detail="unauthorized")
    orch = _bound_orchestrator
    if getattr(orch, "_redis", None) is not None:
            try:
                from utils.redis_wrapper import RedisUnavailable, RedisOpFailed
                try:
                    await redis_op(orch, lambda r, key: r.delete(key), _cfg.REDIS_DLQ_KEY)
                    return {"deleted": True}
                except (RedisUnavailable, RedisOpFailed) as e:
                    raise HTTPException(status_code=500, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    else:
        async with orch._dlq_lock:
            orch._persist_dlq.clear()
        return {"deleted": True}
