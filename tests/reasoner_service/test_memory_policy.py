"""Tests for memory policy checks."""

import pytest

from reasoner_service.policy.memory_policy import check_similarity


@pytest.mark.asyncio
async def test_check_similarity_veto() -> None:
    async def lookup_fn(key, top_n):
        return [{"r_multiple": -0.2}, {"r_multiple": -0.1}]

    result = await check_similarity(("ES", "MODEL", "London"), lookup_fn, negative_threshold=-0.05)
    assert result["result"] == "veto"
    assert result["reason"] == "memory_underperformance"


@pytest.mark.asyncio
async def test_check_similarity_promote() -> None:
    def lookup_fn(key, top_n):
        return [{"r_multiple": 0.2}, {"r_multiple": 0.1}]

    result = await check_similarity(("ES", "MODEL", "London"), lookup_fn, positive_threshold=0.1)
    assert result["result"] == "promote"


@pytest.mark.asyncio
async def test_check_similarity_pass_on_empty() -> None:
    def lookup_fn(key, top_n):
        return []

    result = await check_similarity(("ES", "MODEL", "London"), lookup_fn)
    assert result["result"] == "pass"
