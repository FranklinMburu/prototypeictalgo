
import logging
from src.services.openai_service import analyze_signal
from src.services.telegram_service import send_telegram_alert, format_alert
from src.models.database import SessionLocal, Signal, Analysis
from sqlalchemy.exc import SQLAlchemyError
from config import settings
import asyncio

logger = logging.getLogger(__name__)

# Background task queue for signal processing
signal_queue = asyncio.Queue()

async def process_signal(signal_data: dict):
    await signal_queue.put(signal_data)

async def signal_worker():
    while True:
        signal_data = await signal_queue.get()
        async with SessionLocal() as session:
            try:
                # Save signal
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

                # AI analysis
                ai_result = analyze_signal(signal_data)
                db_analysis = Analysis(
                    signal_id=db_signal.id,
                    gpt_analysis=ai_result['content'],
                    confidence_score=ai_result.get('score', db_signal.confidence),
                    recommendation=ai_result.get('explanation', ''),
                )
                session.add(db_analysis)
                await session.commit()

                # Send Telegram alert
                alert_msg = format_alert(signal_data, ai_result)
                await send_telegram_alert(alert_msg)
            except SQLAlchemyError as e:
                logger.error(f"DB error: {e}")
                await session.rollback()
            except Exception as e:
                logger.error(f"Signal processing error: {e}")
        signal_queue.task_done()
