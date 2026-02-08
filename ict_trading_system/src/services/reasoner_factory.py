from ict_trading_system.src.services.openai_service import cached_gpt_analysis
from ict_trading_system.src.services.gemini_adapter import GeminiAdapter
from ict_trading_system.config import settings
import logging

logger = logging.getLogger(__name__)

class ReasonerFactory:
    @staticmethod
    def create():
        provider = getattr(settings, 'REASONER_PROVIDER', None) or 'gemini'
        logger.debug(f"[REASONER FACTORY] Selected provider: {provider}")
        logger.info(f"[REASONER FACTORY] Creating reasoner with provider: {provider}")
        if provider.lower() == 'openai':
            logger.info("[REASONER FACTORY] Selected OpenAIAdapter")
            return OpenAIAdapter()
        logger.info(f"[REASONER FACTORY] Selected GeminiAdapter (provider={provider})")
        return GeminiAdapter()

class OpenAIAdapter:
    def chat(self, prompt: str):
        # Use the existing OpenAI logic
        result = cached_gpt_analysis(prompt)
        return ReasonerResponse(
            text=result["content"],
            raw=result
        )

class ReasonerResponse:
    def __init__(self, text, raw=None):
        self.text = text
        self.raw = raw or {}
