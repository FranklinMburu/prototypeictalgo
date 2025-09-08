
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from ict_trading_system.config import settings
import logging
from ict_trading_system.src.services.telegram_service import get_bot_status, get_bot_stats, get_bot_settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/command")
async def telegram_command(request: Request):
    data = await request.json()
    command = data.get("command", "")
    if command == "/status":
        return {"status": get_bot_status()}
    elif command == "/stats":
        return {"stats": get_bot_stats()}
    elif command == "/settings":
        return {"settings": get_bot_settings()}
    else:
        return JSONResponse(status_code=400, content={"detail": "Unknown command"})
