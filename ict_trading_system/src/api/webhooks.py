
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from ict_trading_system.src.services.signal_processor import process_signal
from ict_trading_system.config import settings
from ict_trading_system.src.utils.helpers import sanitize_payload
import logging

router = APIRouter()
logger = logging.getLogger()  # Use root logger to ensure propagation and handler coverage

@router.post("/receive")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    logger.info(f"Received webhook POST from {request.client.host}:{request.client.port}")
    # Accept secret from header (preferred) or query param (fallback)
    secret = request.headers.get("x-webhook-secret")
    if not secret:
        secret = request.query_params.get("secret")
    if secret != settings.WEBHOOK_SECRET:
        logger.warning(f"Invalid webhook secret: received '{secret}'")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    try:
        data = await request.json()
        logger.info(f"Webhook payload: {data}")
        data = sanitize_payload(data)
        if data.get('confidence', 0) < settings.MIN_CONFIDENCE_SCORE:
            logger.info(f"Payload ignored due to low confidence: {data.get('confidence', 0)}")
            return JSONResponse(status_code=200, content={"detail": "Low confidence, ignored."})
        # Explicit SQL injection prevention: only allow expected fields
        allowed_fields = {"symbol", "timeframe", "signal_type", "confidence", "raw_data", "timestamp", "price_data", "sl", "tp", "multi_tf", "confluences"}
        for k in data.keys():
            if k not in allowed_fields:
                logger.warning(f"Unexpected field in webhook: {k}. Payload: {data}")
                raise HTTPException(status_code=400, detail=f"Invalid field in payload: {k}")
        background_tasks.add_task(process_signal, data)
        logger.info(f"Webhook accepted and passed to background task: {data}")
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        try:
            data = await request.json()
            logger.error(f"Payload on error: {data}")
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="Invalid payload")
