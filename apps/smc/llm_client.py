from typing import Any, Dict, Optional
import asyncio
import httpx
from ict_trading_system.src.utils.logger import setup_logging
import logging
from ict_trading_system.config import settings
from tenacity import AsyncRetrying, stop_after_attempt, wait_fixed, retry_if_exception_type

setup_logging()

class LLMProvider:
    async def complete(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError

class FakeLLM(LLMProvider):
    def __init__(self, response: Optional[str] = None):
        self.response = response

    async def complete(self, prompt: str, **kwargs) -> str:
        # Return a deterministic, valid JSON string for tests
        if self.response:
            return self.response
        return (
            '{'
            '"metadata":{"symbol":"XAUUSD","timeframe_context":["4H","1H","5M"],"timestamp":"2025-08-11T12:00:00Z"},'
            '"checklist":['
            '{"key":"htf_bias","status":"met","rationale":"Uptrend confirmed"},'
            '{"key":"session_killzone","status":"met","rationale":"NY open"},'
            '{"key":"liquidity_context","status":"partial","rationale":"Sweep below swing low"},'
            '{"key":"poi","status":"met","rationale":"15M OB tapped"},'
            '{"key":"ltf_confirmation","status":"partial","rationale":"CHoCH, rising momentum"},'
            '{"key":"risk_execution","status":"met","rationale":"SL/TP set, RR 1:3"},'
            '{"key":"discipline","status":"met","rationale":"Within daily limit"}'
            '],'
            '"confidence_score":78,'
            '"opportunity_tier":"strong",'
            '"action":"long",'
            '"risk":{"stop_loss":0.2,"take_profit":0.6,"rr_min":3.0,"risk_per_trade":1.0}'
            '}'
        )

class OpenAILLM(LLMProvider):
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1/chat/completions"
        self.timeout = settings.SMC_TIMEOUT_MS / 1000

    async def complete(self, prompt: str, **kwargs) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.SMC_PROVIDER,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": settings.SMC_MAX_TOKENS,
            "temperature": settings.SMC_TEMPERATURE,
        }
        payload.update(kwargs)
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(self.base_url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
