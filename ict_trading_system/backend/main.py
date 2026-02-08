from ai_agent import analyze_trade_signal
from db import SessionLocal, Alert
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# --- Telegram notification logic (inlined for import safety) ---
import requests
import os
def send_telegram_message(message: str) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_ids = ["7389181251", "7713702036"]  # Add/remove chat IDs as needed
    if not bot_token or not chat_ids:
        logger.error("Telegram bot token or chat IDs not set in environment.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    success = True
    for chat_id in chat_ids:
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                logger.error(f"Telegram error for {chat_id}: {resp.status_code} {resp.text}")
                success = False
        except Exception as e:
            logger.error(f"Telegram send error for {chat_id}: {e}")
            success = False
    return success

app = FastAPI()

@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    try:
        data = await request.json()
        logger.debug("Received TradingView alert", extra={"data": data})
        # AI/Reasoning Agent analysis
        ai_result = analyze_trade_signal(data)

        # Log to database
        db = SessionLocal()
        alert = Alert(
            symbol=data.get('symbol'),
            tf=data.get('tf'),
            side=data.get('side'),
            score=data.get('score'),
            entry=data.get('entry'),
            sl=data.get('sl'),
            tp=data.get('tp'),
            session=data.get('session'),
            htf_mid=data.get('htf_mid'),
            regime=data.get('regime'),
            choch_up=data.get('choch_up'),
            choch_down=data.get('choch_down'),
            bos_up=data.get('bos_up'),
            bos_down=data.get('bos_down')
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        db.close()

        # Send Telegram notification with AI result
        msg = (
            f"*ICT Alert*\n"
            f"Symbol: {data.get('symbol')}\n"
            f"Side: {data.get('side')}\n"
            f"Entry: {data.get('entry')}\n"
            f"SL: {data.get('sl')}\n"
            f"TP: {data.get('tp')}\n"
            f"Score: {data.get('score')}\n"
            f"Session: {data.get('session')}\n"
            f"AI: {ai_result.get('score')}% - {ai_result.get('explanation')}"
        )
        tg_ok = send_telegram_message(msg)
        return JSONResponse(content={"status": "ok", "received": data, "telegram_sent": tg_ok, "db_id": alert.id, "ai": ai_result})
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid payload")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
