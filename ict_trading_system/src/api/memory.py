from fastapi import APIRouter, Query
from ict_trading_system.src.utils.memory_agent import query_memory

router = APIRouter()

@router.get("/memory/search")
def search_memory(q: str = Query(..., description="Query text for semantic memory search"), n: int = 5):
    """Semantic search over trade/analysis memory."""
    results = query_memory(q, n_results=n)
    return {"results": results}
