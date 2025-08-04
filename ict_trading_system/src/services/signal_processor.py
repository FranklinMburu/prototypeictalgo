

import logging
from src.services.openai_service import analyze_signal
from src.services.telegram_service import send_telegram_alert, format_alert
from src.models.database import SessionLocal, Signal, Analysis
from sqlalchemy.exc import SQLAlchemyError
from config import settings
import asyncio

from datetime import datetime, timezone
from typing import Tuple

logger = logging.getLogger(__name__)

# Background task queue for signal processing
signal_queue = asyncio.Queue()

REQUIRED_FIELDS = [
    'symbol', 'timeframe', 'signal_type', 'confidence', 'timestamp',
    'price_data', 'sl', 'tp', 'multi_tf', 'confluences'
]

def validate_signal(signal_data: dict) -> Tuple[bool, str]:
    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in signal_data:
            return False, f"Missing required field: {field}"
    # Validate price_data
    for k in ['open', 'high', 'low', 'close']:
        if k not in signal_data['price_data']:
            return False, f"Missing price_data field: {k}"
    # Validate confidence
    try:
        conf = int(signal_data['confidence'])
        if not (0 <= conf <= 100):
            return False, "Confidence out of range"
    except Exception:
        return False, "Invalid confidence value"
    return True, ""

def is_in_killzone(ts: int, session: str = "london,ny") -> bool:
    # Example: London 07:00-10:00 UTC, NY 12:00-15:00 UTC
    dt = datetime.utcfromtimestamp(ts // 1000)
    hour = dt.hour
    if "london" in session and 7 <= hour < 10:
        return True
    if "ny" in session and 12 <= hour < 15:
        return True
    return False

def passes_confluence(signal_data: dict, min_confluences: int = 2) -> bool:
    # Count True confluences
    conf = signal_data.get('confluences', {})
    return sum(1 for v in conf.values() if v == True or v == 1) >= min_confluences

def score_signal(signal_data: dict) -> int:
    # Score based on confluences, session, and signal type
    base = 60
    conf = signal_data.get('confluences', {})
    n_conf = sum(1 for v in conf.values() if v == True or v == 1)
    session_bonus = 10 if is_in_killzone(signal_data['timestamp']) else 0
    type_bonus = 10 if signal_data['signal_type'] in ["CHoCH", "BoS"] else 0
    return min(100, base + n_conf * 10 + session_bonus + type_bonus)

async def process_signal(signal_data: dict):
    await signal_queue.put(signal_data)

async def signal_worker():
    while True:
        signal_data = await signal_queue.get()
        async with SessionLocal() as session:
            try:
                # --- Robust Validation ---
                valid, err = validate_signal(signal_data)
                if not valid:
                    logger.error(f"Invalid signal: {err} | Data: {signal_data}")
                    signal_queue.task_done()
                    continue

                # --- Confluence & Session Checks ---
                if not passes_confluence(signal_data, min_confluences=2):
                    logger.info(f"Signal dropped: insufficient confluences | Data: {signal_data}")
                    signal_queue.task_done()
                    continue
                if not is_in_killzone(signal_data['timestamp']):
                    logger.info(f"Signal dropped: not in killzone | Data: {signal_data}")
                    signal_queue.task_done()
                    continue

                # --- Confidence Scoring ---
                signal_data['confidence'] = score_signal(signal_data)
                if signal_data['confidence'] < 75:
                    logger.info(f"Signal dropped: low confidence | Data: {signal_data}")
                    signal_queue.task_done()
                    continue

                # --- Save signal ---
                db_signal = Signal(
                    symbol=signal_data['symbol'],
                    timeframe=signal_data['timeframe'],
                    signal_type=signal_data['signal_type'],
                    confidence=signal_data['confidence'],
                    raw_data=str(signal_data),
                )
                session.add(db_signal)
                await session.commit()
                await session.refresh(db_signal)

                # --- AI analysis ---
                ai_result = analyze_signal(signal_data)
                db_analysis = Analysis(
                    signal_id=db_signal.id,
                    gpt_analysis=ai_result['content'],
                    confidence_score=ai_result.get('score', db_signal.confidence),
                    recommendation=ai_result.get('explanation', ''),
                )
                session.add(db_analysis)
                await session.commit()

                # --- Send Telegram alert ---
                alert_msg = format_alert(signal_data, ai_result)
                await send_telegram_alert(alert_msg)
            except SQLAlchemyError as e:
                logger.error(f"DB error: {e}")
                await session.rollback()
            except Exception as e:
                logger.error(f"Signal processing error: {e}")
        signal_queue.task_done()
