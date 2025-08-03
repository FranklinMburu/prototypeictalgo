import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List

load_dotenv()

class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(...)
    TELEGRAM_BOT_TOKEN: str = Field(...)
    TELEGRAM_CHAT_ID: str = Field(...)
    WEBHOOK_SECRET: str = Field(...)
    PORT: int = Field(8000)
    MIN_CONFIDENCE_SCORE: int = Field(75)
    MAX_DAILY_SIGNALS: int = Field(10)
    ACTIVE_SESSIONS: List[str] = Field(['london', 'newyork'])
    DATABASE_URL: str = Field('sqlite:///./trading_system.db')

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
