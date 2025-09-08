from fastapi import APIRouter, HTTPException
from apps.smc.api import router as smc_router

# This file acts as a bridge to mount the SMC API router in the main FastAPI app.

router = smc_router
