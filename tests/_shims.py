# Minimal shims for test environment: prometheus_client and aiohttp
import types

# prometheus_client shim
prometheus_client = types.SimpleNamespace()

def _generate_latest():
    return b""

prometheus_client.generate_latest = _generate_latest
prometheus_client.CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

# aiohttp shim
class _FakeResponse:
    def __init__(self, status=200, content=b""):
        self.status = status
        self._content = content
        self.content = [content]

    async def json(self):
        return {}

    async def text(self):
        return ""

class ClientSession:
    def __init__(self, *args, **kwargs):
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return

    async def post(self, *args, **kwargs):
        return _FakeResponse()

    async def close(self):
        self.closed = True

# expose in module-like objects for import
import sys
sys.modules['prometheus_client'] = prometheus_client

import types as _types
_aio = _types.SimpleNamespace(ClientSession=ClientSession)
sys.modules['aiohttp'] = _aio

# slowapi shim (use real ModuleType so submodules import works)
import types as _types_mod
slowapi_mod = _types_mod.ModuleType('slowapi')

class Limiter:
    def __init__(self, *args, **kwargs):
        pass
    def limit(self, spec):
        # return a decorator that leaves the function unchanged
        def _dec(fn):
            return fn
        return _dec

def _rate_limit_exceeded_handler(request, exc):
    return None

slowapi_mod.Limiter = Limiter
slowapi_mod._rate_limit_exceeded_handler = _rate_limit_exceeded_handler

# slowapi.util submodule
util_mod = _types_mod.ModuleType('slowapi.util')
def _get_remote_address(request):
    try:
        return request.client.host
    except Exception:
        return '127.0.0.1'
util_mod.get_remote_address = _get_remote_address

# slowapi.errors submodule
errors_mod = _types_mod.ModuleType('slowapi.errors')
class RateLimitExceeded(Exception):
    pass
errors_mod.RateLimitExceeded = RateLimitExceeded

sys.modules['slowapi'] = slowapi_mod
sys.modules['slowapi.util'] = util_mod
sys.modules['slowapi.errors'] = errors_mod

# sentry_sdk shim
def _sentry_init(*args, **kwargs):
    return None
def _sentry_capture_exception(exc):
    return None
sys.modules['sentry_sdk'] = _types_mod.SimpleNamespace(init=_sentry_init, capture_exception=_sentry_capture_exception)

# sentry_sdk.integrations.fastapi shim
fastapi_integ = _types_mod.ModuleType('sentry_sdk.integrations.fastapi')
class FastApiIntegration:
    def __init__(self, *args, **kwargs):
        pass
fastapi_integ.FastApiIntegration = FastApiIntegration
sys.modules['sentry_sdk.integrations.fastapi'] = fastapi_integ

# aiosqlite shim: provide an async connect function used by SQLAlchemy aiosqlite dialect at import
import importlib
if importlib.util.find_spec('aiosqlite') is None:
    import types as _types_local
    _aiosqlite_mod = _types_local.ModuleType('aiosqlite')
    async def _aiosqlite_connect(*args, **kwargs):
        class DummyConn:
            async def execute(self, *a, **k):
                return None
            async def close(self):
                return None
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc, tb):
                return None
        return DummyConn()

    class DatabaseError(Exception):
        pass
    class OperationalError(DatabaseError):
        pass
    class IntegrityError(DatabaseError):
        pass

    _aiosqlite_mod.connect = _aiosqlite_connect
    _aiosqlite_mod.DatabaseError = DatabaseError
    _aiosqlite_mod.OperationalError = OperationalError
    _aiosqlite_mod.IntegrityError = IntegrityError
    _aiosqlite_mod.paramstyle = 'qmark'

    # Provide aliases expected by SQLAlchemy/aiosqlite dialect
    _aiosqlite_mod.Error = DatabaseError
    _aiosqlite_mod.InterfaceError = DatabaseError
    _aiosqlite_mod.Warning = Exception
    _aiosqlite_mod.NotSupportedError = DatabaseError
    _aiosqlite_mod.ProgrammingError = DatabaseError
    _aiosqlite_mod.sqlite_version = '3.39.0'
    _aiosqlite_mod.sqlite_version_info = (3, 39, 0)

    sys.modules['aiosqlite'] = _aiosqlite_mod
