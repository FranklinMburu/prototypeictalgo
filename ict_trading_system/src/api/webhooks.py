
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from src.services.signal_processor import process_signal
from config import settings
from src.utils.helpers import sanitize_payload
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/receive")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    secret = request.query_params.get("secret")
    if secret != settings.WEBHOOK_SECRET:
        logger.warning("Invalid webhook secret.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        data = await request.json()
        data = sanitize_payload(data)
        if data.get('confidence', 0) < settings.MIN_CONFIDENCE_SCORE:
            return JSONResponse(status_code=200, content={"detail": "Low confidence, ignored."})
        # Explicit SQL injection prevention: only allow expected fields
        allowed_fields = {"symbol", "timeframe", "signal_type", "confidence", "raw_data", "timestamp", "price_data", "sl", "tp"}
        for k in data.keys():
            if k not in allowed_fields:
                logger.warning(f"Unexpected field in webhook: {k}")
                raise HTTPException(status_code=400, detail="Invalid field in payload")
        background_tasks.add_task(process_signal, data)
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
