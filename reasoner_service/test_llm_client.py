import pytest
import asyncio
from reasoner_service.llm_client import LLMClient

@pytest.mark.asyncio
async def test_llmclient_context_manager():
    async with LLMClient(provider="openai", api_key="test", base_url="http://localhost:9999") as client:
        assert client.session is not None
        assert not client.session.closed
    # After exit, session should be closed
    assert client.session is None or client.session.closed

@pytest.mark.asyncio
async def test_llmclient_double_enter_exit():
    client = LLMClient(provider="openai", api_key="test", base_url="http://localhost:9999")
    async with client:
        assert client.session is not None
        assert not client.session.closed
    # Try entering again
    async with client:
        assert client.session is not None
        assert not client.session.closed
    assert client.session is None or client.session.closed
