

import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from config import settings
from src.utils.logger import setup_logging
import logging

# --- Global Rate Limiting ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# --- Sentry Integration ---
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

# Initialize Sentry if DSN is provided
if getattr(settings, "SENTRY_DSN", None):
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.5,  # Adjust as needed
        environment=getattr(settings, "ENV", "production"),
    )

setup_logging()
logger = logging.getLogger(__name__)



app = FastAPI(title="ICT Smart Money Trading Alert System", version="1.0.0")

# Set up global rate limiter (e.g., 100 requests/minute per IP)
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
@limiter.limit("10/second")  # Health endpoint: burst allowed
async def health_check(request: Request):
    return {"status": "ok"}


# Sentry will auto-capture unhandled exceptions, but keep logging for local dev
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Import and include routers
from src.api.webhooks import router as webhook_router
from src.api.telegram_bot import router as telegram_router
from src.api.users import router as users_router

app.include_router(webhook_router, prefix="/api/webhook", tags=["webhook"])
app.include_router(telegram_router, prefix="/api/telegram", tags=["telegram"])
app.include_router(users_router, prefix="/api", tags=["users"])

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
