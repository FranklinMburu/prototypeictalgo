import os
from dotenv import load_dotenv
load_dotenv()
import logging
from ict_trading_system.config import settings
logging.basicConfig(level=logging.INFO)
logging.info(f"[DEBUG] Loaded WEBHOOK_SECRET at startup: {settings.WEBHOOK_SECRET}")
from dotenv import load_dotenv
load_dotenv()



import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from ict_trading_system.config import settings
from ict_trading_system.src.utils.logger import setup_logging, close_logging
import logging
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# ...existing code...

app = FastAPI(title="ICT Smart Money Trading Alert System", version="1.0.0")

# ...existing code...

# Prometheus metrics endpoint (must be after app is defined)
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from ict_trading_system.config import settings
from ict_trading_system.src.utils.logger import setup_logging, close_logging
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
# Import and include routers

# Prometheus metrics endpoint (must be after app is defined)
@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Set up global rate limiter (e.g., 100 requests/minute per IP)
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Lifespan event handler for startup/shutdown ---
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    required = [settings.OPENAI_API_KEY, settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID, settings.WEBHOOK_SECRET, settings.DATABASE_URL]
    if any([not v or v == "" for v in required]):
        logger.critical("Missing required environment variables. Check your .env file.")
        raise RuntimeError("Missing required environment variables. Application will not start.")
    logger.info("Startup validation complete. All required environment variables are set.")
    # Start background signal worker
    from ict_trading_system.src.services.signal_processor import signal_worker
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(signal_worker())
    yield
    # Shutdown logic
    logger.info("Application shutdown: cleaning up resources.")
    close_logging()

app.router.lifespan_context = lifespan

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


from ict_trading_system.src.api.webhooks import router as webhook_router
from ict_trading_system.src.api.telegram_bot import router as telegram_router
from ict_trading_system.src.api.users import router as users_router
from ict_trading_system.src.api.memory import router as memory_router
try:
    from src.api.smc import router as smc_router
except ImportError:
    smc_router = None

app.include_router(webhook_router, prefix="/api/webhook", tags=["webhook"])
app.include_router(telegram_router, prefix="/api/telegram", tags=["telegram"])
app.include_router(users_router, prefix="/api", tags=["users"])
app.include_router(memory_router, prefix="/api", tags=["memory"])

# Mount SMC API if enabled in settings
if hasattr(settings, "SMC_ENABLED") and getattr(settings, "SMC_ENABLED", False):
    if smc_router:
        app.include_router(smc_router, prefix="/api/smc", tags=["smc"])

if __name__ == "__main__":
    try:
        uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)
    finally:
        close_logging()
