import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from config import settings
from src.utils.logger import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)


app = FastAPI(title="ICT Smart Money Trading Alert System", version="1.0.0")

# Graceful startup/shutdown and config validation

@app.on_event("startup")
async def startup_event():
    # Validate config
    required = [settings.OPENAI_API_KEY, settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID, settings.WEBHOOK_SECRET, settings.DATABASE_URL]
    if any([not v or v == "" for v in required]):
        logger.critical("Missing required environment variables. Check your .env file.")
        raise RuntimeError("Missing required environment variables. Application will not start.")
    logger.info("Startup validation complete. All required environment variables are set.")
    # Start background signal worker
    from src.services.signal_processor import signal_worker
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(signal_worker())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown: cleaning up resources.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# Import and include routers
from src.api.webhooks import router as webhook_router
from src.api.telegram_bot import router as telegram_router

app.include_router(webhook_router, prefix="/api/webhook", tags=["webhook"])
app.include_router(telegram_router, prefix="/api/telegram", tags=["telegram"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
