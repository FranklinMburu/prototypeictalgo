import sys
import os
import types
import importlib

# Ensure repository root is on sys.path for package imports
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Do not add ict_trading_system to sys.path to avoid package name conflicts
# between top-level `reasoner_service` and `ict_trading_system/reasoner_service`.

# Provide lightweight fakes for missing external dependencies to allow collection
# These fakes are minimal and intended only for unit test collection; tests that
# need richer behavior should monkeypatch or provide more specific fakes.

def _ensure_module(name: str):
    if importlib.util.find_spec(name) is None:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod
    return importlib.import_module(name)

# Fake `redis.asyncio` module with a minimal client factory.
try:
    import redis  # noqa: F401
except Exception:
    redis_mod = _ensure_module('redis')
    asyncio_mod = types.ModuleType('redis.asyncio')

    class _FakeRedisClient:
        def __init__(self, *args, **kwargs):
            pass

        async def ping(self):
            return True

        async def close(self):
            return True

        async def rpush(self, key, value):
            return 1

        async def lpop(self, key):
            return None

        async def lrange(self, key, s, e):
            return []

        async def llen(self, key):
            return 0

        async def delete(self, key):
            return 0

        async def set(self, *args, **kwargs):
            return True

        async def incr(self, key):
            return 1

    def from_url(url):
        return _FakeRedisClient()

    asyncio_mod.from_url = from_url
    sys.modules['redis'] = redis_mod
    sys.modules['redis.asyncio'] = asyncio_mod

# Fake `openai` module
try:
    import openai  # noqa: F401
except Exception:
    _ensure_module('openai')

# Optionally fake other heavy deps that cause import-time errors
for pkg in ('uvicorn', 'starlette', 'anyio'):
    try:
        importlib.import_module(pkg)
    except Exception:
        _ensure_module(pkg)

# Provide a minimal `reasoner_service` package shim for imports during tests
if 'reasoner_service' not in sys.modules:
    # attempt to map to local package directories if they exist
    # prefer top-level reasoner_service, then ict_trading_system/reasoner_service
    local_paths = [os.path.join(ROOT, 'reasoner_service'), os.path.join(ROOT, 'ict_trading_system', 'reasoner_service')]
    found = False
    for p in local_paths:
        if os.path.isdir(p):
            # add parent dir to sys.path so imports like 'reasoner_service.orchestrator' resolve
            parent = os.path.dirname(p)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            found = True
            break
    if not found:
        # fallback minimal shim
        rs = types.ModuleType('reasoner_service')
        # minimal config.get_settings
        cfg_mod = types.ModuleType('reasoner_service.config')
        def _get_settings():
            class S:
                REDIS_DLQ_ENABLED = False
                REDIS_DLQ_KEY = 'dlq'
                DLQ_POLL_INTERVAL_SECONDS = 1
                REDIS_DEDUP_ENABLED = False
                REDIS_DEDUP_PREFIX = 'dedup:'
                REDIS_DEDUP_TTL_SECONDS = 60
                DEDUP_ENABLED = False
                REDIS_RECONNECT_JITTER_MS = 100
            return S()
        cfg_mod.get_settings = _get_settings
        metrics_mod = types.ModuleType('reasoner_service.metrics')
        class _M:
            def inc(self, *a, **k):
                return
            def labels(self, *a, **k):
                return self
        metrics_mod.redis_op_errors_total = _M()
        metrics_mod.redis_op_retries_total = _M()
        metrics_mod.redis_circuit_opened_total = _M()
        metrics_mod.redis_reconnect_attempts = _M()
        metrics_mod.dlq_size = _M()
        metrics_mod.decisions_processed_total = _M()
        metrics_mod.deduplicated_decisions_total = _M()
        metrics_mod.dlq_retries_total = _M()

        sys.modules['reasoner_service'] = rs
        sys.modules['reasoner_service.config'] = cfg_mod
        sys.modules['reasoner_service.metrics'] = metrics_mod

# Expose a pytest fixture to help tests access the repo root
import pytest

@pytest.fixture(autouse=True)
def repo_root():
    return ROOT
