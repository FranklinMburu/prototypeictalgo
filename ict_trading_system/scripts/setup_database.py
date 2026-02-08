import asyncio
import logging
from src.models.database import init_db

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    asyncio.run(init_db())
    logger.info("Database initialized.")
