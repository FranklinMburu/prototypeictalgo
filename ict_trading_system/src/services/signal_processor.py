

import logging
from ict_trading_system.src.services.openai_service import analyze_signal
from ict_trading_system.src.services.telegram_service import send_telegram_alert, format_alert
from ict_trading_system.src.models.database import SessionLocal, Signal, Analysis
from sqlalchemy.exc import SQLAlchemyError
from ict_trading_system.config import settings
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
    # Accept ts as int (unix ms) or ISO8601 string
    if isinstance(ts, str):
        try:
            # Remove 'Z' if present
            if ts.endswith('Z'):
                ts = ts[:-1]
            dt = datetime.fromisoformat(ts)
        except Exception:
            # fallback: try parsing as float seconds
            try:
                dt = datetime.utcfromtimestamp(float(ts))
            except Exception:
                return False
    else:
        # Assume ms timestamp
        dt = datetime.utcfromtimestamp(ts // 1000)
    hour = dt.hour
    if "london" in session and 7 <= hour < 10:
        return True
    if "ny" in session and 12 <= hour < 15:
        return True
    return False

def passes_confluence(signal_data: dict, min_confluences: int = 2) -> bool:
    # Count confluences (list of strings)
    conf = signal_data.get('confluences', [])
    return len(conf) >= min_confluences

def score_signal(signal_data: dict) -> int:
    # Score based on confluences (list), session, and signal type
    base = 60
    conf = signal_data.get('confluences', [])
    n_conf = len(conf)
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
                # Handle both legacy and repaired JSON formats
                gpt_analysis = ai_result['content'] if 'content' in ai_result else str(ai_result)

                db_analysis = Analysis(
                    signal_id=db_signal.id,
                    gpt_analysis=gpt_analysis,
                    confidence_score=ai_result.get('score', db_signal.confidence),
                    recommendation=ai_result.get('explanation', ''),
                )
                session.add(db_analysis)
                await session.commit()

                # --- Store embedding in memory agent ---
                try:
                    from ict_trading_system.src.utils.memory_agent import add_to_memory
                    memory_id = f"analysis-{db_analysis.id}"
                    memory_text = gpt_analysis
                    memory_meta = {
                        "symbol": signal_data.get("symbol"),
                        "timeframe": signal_data.get("timeframe"),
                        "signal_type": signal_data.get("signal_type"),
                        "confidence": signal_data.get("confidence"),
                        "timestamp": str(signal_data.get("timestamp")),
                        "analysis_id": db_analysis.id,
                        "signal_id": db_signal.id
                    }
                    add_to_memory(memory_id, memory_text, memory_meta)
                except Exception as e:
                    logger.error(f"Memory agent error: {e}")

                # --- Send Telegram alert ---
                alert_msg = format_alert(signal_data, ai_result)
                await send_telegram_alert(alert_msg)
            except SQLAlchemyError as e:
                logger.error(f"DB error: {e}")
                await session.rollback()
            except Exception as e:
                logger.error(f"Signal processing error: {e}")
        signal_queue.task_done()
