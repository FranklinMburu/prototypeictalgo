import asyncio
import json
from fastapi.testclient import TestClient
import pytest
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from reasoner_service.app import create_app
from reasoner_service.config import get_settings


class FakeOrchestrator:
    def __init__(self):
        self._persist_dlq = []
        self._dlq_lock = asyncio.Lock()
        self._redis = None


@pytest.fixture
def client():
    orch = FakeOrchestrator()
    app = create_app(orchestrator=orch)
    with TestClient(app) as c:
        yield c


def test_admin_inspect_and_flush(client):
    # inspect empty DLQ
    r = client.get('/admin/dlq')
    assert r.status_code == 200
    data = r.json()
    assert data['count'] == 0

    # flush should succeed
    r = client.post('/admin/dlq/flush')
    assert r.status_code == 200
    assert r.json().get('deleted') is True


def test_admin_requeue_and_flush_with_token(monkeypatch):
    from reasoner_service.config import get_settings
    s = get_settings()
    s.ADMIN_TOKEN = "secret"

    orch = FakeOrchestrator()
    # fake redis with simple list semantics
    class FakeRedis:
        def __init__(self):
            self._list = ["{}"]

        async def lrange(self, key, start, end):
            return self._list

        async def delete(self, key):
            self._list = []

    orch._redis = FakeRedis()

    app = create_app(orchestrator=orch)
    with TestClient(app) as c:
        # list should show 1
        r = c.get('/admin/dlq')
        assert r.status_code == 200
        assert r.json().get('count') == 1
        # unauthorized without token
        r = c.post('/admin/dlq/flush')
        assert r.status_code == 401
        # with token
        r = c.post('/admin/dlq/flush', headers={'X-Admin-Token': 'secret'})
        assert r.status_code == 200
        assert r.json().get('deleted') is True
