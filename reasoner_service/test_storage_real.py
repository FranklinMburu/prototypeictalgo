
import pytest
import pytest_asyncio
import asyncio
from reasoner_service import storage as st
import uuid

pytestmark = pytest.mark.asyncio

ASYNC_SQLITE_DSN = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_sessionmaker():
    engine, sessionmaker = await st.create_engine_and_sessionmaker(ASYNC_SQLITE_DSN)
    await st.init_models(engine)
    try:
        yield sessionmaker
    finally:
        await engine.dispose()

async def test_insert_and_get_by_id_and_recent(db_sessionmaker):
    sample_raw = {"a": 1, "b": "x"}
    id1 = await st.insert_decision(
        db_sessionmaker,
        symbol="TST",
        decision_text='{"ok": true}',
        raw=sample_raw,
        bias="neutral",
        confidence=0.12,
        recommendation="do_nothing",
        repair_used=False,
        fallback_used=True,
        duration_ms=123
    )
    assert isinstance(id1, str) and len(id1) > 0
    got = await st.get_decision_by_id(db_sessionmaker, id1)
    assert got is not None
    assert got["symbol"] == "TST"
    # insert another
    id2 = await st.insert_decision(
        db_sessionmaker,
        symbol="TST2",
        decision_text='{"ok": true}',
        raw=None,
        bias="bullish",
        confidence=0.9,
        recommendation="enter",
        repair_used=False,
        fallback_used=False,
        duration_ms=10
    )
    recent = await st.get_recent_decisions(db_sessionmaker, limit=10)
    assert isinstance(recent, list)
    assert len(recent) >= 2
    ids = [r["id"] for r in recent[:2]]
    assert id1 in ids and id2 in ids

async def test_log_notification_entries(db_sessionmaker):
    id1 = await st.insert_decision(
        db_sessionmaker,
        symbol="SYM",
        decision_text='{"d":1}',
        raw=None,
        bias="neutral",
        confidence=0.1,
        recommendation="do_nothing",
        repair_used=False,
        fallback_used=False,
        duration_ms=1
    )
    log_id = await st.log_notification(db_sessionmaker, decision_id=id1, channel="slack", status="success", http_status=200, error=None)
    assert isinstance(log_id, str) and len(log_id) > 0
    log_id2 = await st.log_notification(db_sessionmaker, decision_id=None, channel="telegram", status="failure", http_status=500, error="timeout")
    assert isinstance(log_id2, str)
