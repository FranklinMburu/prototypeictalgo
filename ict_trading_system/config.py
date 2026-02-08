import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List

load_dotenv()

class Settings(BaseSettings):

    REASONER_PROVIDER: str = Field('gemini')
    GEMINI_API_KEY: str = Field('')
    SMC_ENABLED: bool = Field(False)
    SMC_PROVIDER: str = Field("gpt-3.5-turbo")
    SMC_TIMEOUT_MS: int = Field(6000)
    SMC_MAX_TOKENS: int = Field(512)
    SMC_TEMPERATURE: float = Field(0.2)
    OPENAI_API_KEY: str = Field(...)
    TELEGRAM_BOT_TOKEN: str = Field(...)
    TELEGRAM_CHAT_ID: str = Field(...)
    WEBHOOK_SECRET: str = Field(...)
    PORT: int = Field(8000)
    MIN_CONFIDENCE_SCORE: int = Field(75)
    MAX_DAILY_SIGNALS: int = Field(10)
    ACTIVE_SESSIONS: List[str] = Field(['london', 'newyork'])
    DATABASE_URL: str = Field('sqlite:///./trading_system.db')

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "allow"
    }
import logging

settings = Settings()
logger = logging.getLogger(__name__)
logger.debug("[CONFIG] Settings loaded from environment")

