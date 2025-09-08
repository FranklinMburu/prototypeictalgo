"""
LLMClient: Production-grade, extensible client for LLM providers (OpenAI, Azure, etc.)
- Async, robust error handling, retry/backoff, streaming support
- Pluggable for multiple providers
- Observability hooks (metrics, logging)
- Testable and easy to extend
"""


import asyncio
import logging
import json
from typing import Any, Dict, Optional, AsyncGenerator

import aiohttp

logger = logging.getLogger("reasoner_service.llm_client")

class LLMClient:
    async def repair(self, *args, **kwargs):
        """Dummy repair method for test patching. Should be replaced/mocked in tests."""
        raise NotImplementedError("LLMClient.repair is not implemented. Patch this in tests.")
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        self.provider = provider.lower()
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
        self.extra = kwargs

    async def __aenter__(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def complete(self, prompt: str, **kwargs) -> str:
        """Get a completion from the LLM provider."""
        if self.provider == "openai":
            return await self._openai_complete(prompt, **kwargs)
        elif self.provider == "azure":
            return await self._azure_complete(prompt, **kwargs)
        else:
            raise NotImplementedError(f"Provider {self.provider} not supported.")

    async def stream_complete(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream completion from the LLM provider."""
        if self.provider == "openai":
            async for chunk in self._openai_stream_complete(prompt, **kwargs):
                yield chunk
        elif self.provider == "azure":
            async for chunk in self._azure_stream_complete(prompt, **kwargs):
                yield chunk
        else:
            raise NotImplementedError(f"Provider {self.provider} not supported.")

    async def _openai_complete(self, prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 512, temperature: float = 0.7, **kwargs) -> str:
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        payload.update(kwargs)
        for attempt in range(3):
            try:
                async with self.session.post(url, headers=headers, json=payload, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        err = await resp.text()
                        logger.error(f"OpenAI error: {resp.status} {err}")
                        await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"OpenAI request failed: {e}")
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("OpenAI completion failed after retries.")

    async def _openai_stream_complete(self, prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 512, temperature: float = 0.7, **kwargs) -> AsyncGenerator[str, None]:
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        payload.update(kwargs)
        for attempt in range(3):
            try:
                async with self.session.post(url, headers=headers, json=payload, timeout=60) as resp:
                    if resp.status == 200:
                        async for line in resp.content:
                            if line:
                                chunk = line.decode("utf-8").strip()
                                if chunk.startswith("data: "):
                                    chunk = chunk[6:]
                                if chunk and chunk != "[DONE]":
                                    try:
                                        data = json.loads(chunk)
                                        delta = data["choices"][0]["delta"].get("content", "")
                                        if delta:
                                            yield delta
                                    except Exception:
                                        continue
                        return
                    else:
                        err = await resp.text()
                        logger.error(f"OpenAI stream error: {resp.status} {err}")
                        await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"OpenAI stream request failed: {e}")
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("OpenAI streaming completion failed after retries.")

    async def _azure_complete(self, prompt: str, deployment_id: str = None, max_tokens: int = 512, temperature: float = 0.7, **kwargs) -> str:
        if not deployment_id:
            raise ValueError("Azure OpenAI requires deployment_id.")
        url = self.base_url or f"https://YOUR_AZURE_RESOURCE_NAME.openai.azure.com/openai/deployments/{deployment_id}/chat/completions?api-version=2023-03-15-preview"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        payload.update(kwargs)
        for attempt in range(3):
            try:
                async with self.session.post(url, headers=headers, json=payload, timeout=30) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
                    else:
                        err = await resp.text()
                        logger.error(f"Azure error: {resp.status} {err}")
                        await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Azure request failed: {e}")
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("Azure completion failed after retries.")

    async def _azure_stream_complete(self, prompt: str, deployment_id: str = None, max_tokens: int = 512, temperature: float = 0.7, **kwargs) -> AsyncGenerator[str, None]:
        if not deployment_id:
            raise ValueError("Azure OpenAI requires deployment_id.")
        url = self.base_url or f"https://YOUR_AZURE_RESOURCE_NAME.openai.azure.com/openai/deployments/{deployment_id}/chat/completions?api-version=2023-03-15-preview"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        payload.update(kwargs)
        for attempt in range(3):
            try:
                async with self.session.post(url, headers=headers, json=payload, timeout=60) as resp:
                    if resp.status == 200:
                        async for line in resp.content:
                            if line:
                                chunk = line.decode("utf-8").strip()
                                if chunk.startswith("data: "):
                                    chunk = chunk[6:]
                                if chunk and chunk != "[DONE]":
                                    try:
                                        data = json.loads(chunk)
                                        delta = data["choices"][0]["delta"].get("content", "")
                                        if delta:
                                            yield delta
                                    except Exception:
                                        continue
                        return
                    else:
                        err = await resp.text()
                        logger.error(f"Azure stream error: {resp.status} {err}")
                        await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Azure stream request failed: {e}")
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError("Azure streaming completion failed after retries.")

    # Add more providers here as needed

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None
