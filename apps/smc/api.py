from fastapi import APIRouter, Depends, HTTPException
from apps.smc.decision_engine import SMCDecisionEngine
from apps.smc.models import SMCDecision
from ict_trading_system.src.utils.logger import setup_logging
import logging
from pydantic import BaseModel
from typing import Any, Dict

setup_logging()
setup_logging()
router = APIRouter()
engine = SMCDecisionEngine()

class SMCRequest(BaseModel):
    context: Dict[str, Any]

@router.post("/smc/evaluate", response_model=SMCDecision)
async def evaluate_smc(request: SMCRequest):
    try:
        decision = await engine.evaluate(request.context)
        return decision
    except Exception as e:
        logging.error(f"SMC API evaluation failed: {e}")
        raise HTTPException(status_code=500, detail="SMC evaluation failed")
