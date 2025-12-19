"""Pluggable policy backends for PolicyStore."""

from typing import Dict, Any, Optional
from abc import ABC, abstractmethod


class PolicyBackend(ABC):
    """Abstract base class for policy data sources."""

    @abstractmethod
    async def get_policy(self, policy_name: str, context: dict) -> dict:
        """Retrieve policy by name and optional context.

        Args:
            policy_name: Name of the policy (e.g., 'killzone', 'exposure')
            context: Optional context dict for deriving policies

        Returns:
            Policy dict with relevant fields, or empty dict if not found
        """
        pass


class DefaultPolicyBackend(PolicyBackend):
    """Default in-memory backend using marker fallback."""

    async def get_policy(self, policy_name: str, context: dict) -> dict:
        """Fallback to reading markers from context (backward-compatible)."""
        if policy_name == "killzone":
            return {"active": bool(context.get("killzone", False))}
        if policy_name == "regime":
            return {"regime": context.get("regime")}
        if policy_name == "cooldown":
            return {"cooldown_until": int(context.get("cooldown_until", 0) or 0)}
        if policy_name == "exposure":
            return {
                "exposure": float(context.get("exposure", 0) or 0),
                "max_exposure": float(context.get("max_exposure", 0) or 0),
            }
        if policy_name == "confidence_threshold":
            return {"min_confidence": 0.5}
        return {}


class OrchestratorConfigBackend(PolicyBackend):
    """Backend that reads from orchestrator._policy_config."""

    def __init__(self, orch: "DecisionOrchestrator"):  # noqa: F821
        self.orch = orch

    async def get_policy(self, policy_name: str, context: dict) -> dict:
        """Read from orchestrator config or return empty."""
        try:
            cfg_obj = getattr(self.orch, "_policy_config", None)
            if cfg_obj and policy_name in cfg_obj:
                return cfg_obj.get(policy_name) or {}
        except Exception:
            pass
        return {}


class HttpPolicyBackend(PolicyBackend):
    """HTTP-based policy backend for remote policy services.

    Example:
        backend = HttpPolicyBackend("http://policy-service:8080")
        policy = await backend.get_policy("killzone", {"symbol": "AAPL"})
    """

    def __init__(self, base_url: str, timeout: float = 5.0):
        """Initialize HTTP backend.

        Args:
            base_url: Base URL of policy service (e.g., http://localhost:8080)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def get_policy(self, policy_name: str, context: dict) -> dict:
        """Fetch policy from HTTP service."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/policies/{policy_name}"
                async with session.post(
                    url, json=context, timeout=self.timeout
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {}
        except Exception:
            return {}


class RedisPolicyBackend(PolicyBackend):
    """Redis-based policy backend for caching policy decisions.

    Example:
        backend = RedisPolicyBackend("redis://localhost:6379", ttl=300)
        policy = await backend.get_policy("killzone", {"symbol": "AAPL"})
    """

    def __init__(self, redis_url: str, key_prefix: str = "policy:", ttl: int = 300):
        """Initialize Redis backend.

        Args:
            redis_url: Redis connection URL
            key_prefix: Prefix for Redis keys
            ttl: TTL for cached policies in seconds
        """
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.ttl = ttl
        self._redis = None

    async def _ensure_connection(self):
        """Lazy-initialize Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self.redis_url)
                # Test connection
                await self._redis.ping()
            except Exception:
                self._redis = None

    async def get_policy(self, policy_name: str, context: dict) -> dict:
        """Get policy from Redis cache, fall back to empty."""
        try:
            await self._ensure_connection()
            if self._redis is None:
                return {}

            # Build cache key from policy name and context hash
            import hashlib
            import json

            context_hash = hashlib.md5(
                json.dumps(context, sort_keys=True, default=str).encode()
            ).hexdigest()
            key = f"{self.key_prefix}{policy_name}:{context_hash}"

            # Try to get from cache
            cached = await self._redis.get(key)
            if cached:
                return json.loads(cached)

            return {}
        except Exception:
            return {}

    async def set_policy(self, policy_name: str, context: dict, policy_data: dict):
        """Cache a policy decision in Redis."""
        try:
            await self._ensure_connection()
            if self._redis is None:
                return False

            import hashlib
            import json

            context_hash = hashlib.md5(
                json.dumps(context, sort_keys=True, default=str).encode()
            ).hexdigest()
            key = f"{self.key_prefix}{policy_name}:{context_hash}"

            await self._redis.setex(
                key, self.ttl, json.dumps(policy_data)
            )
            return True
        except Exception:
            return False

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
            self._redis = None


class ChainedPolicyBackend(PolicyBackend):
    """Chain multiple backends with fallback (try first, fall back to second, etc)."""

    def __init__(self, *backends: PolicyBackend):
        """Initialize with ordered backends to try.

        Args:
            backends: Variable number of PolicyBackend instances in priority order
        """
        self.backends = backends

    async def get_policy(self, policy_name: str, context: dict) -> dict:
        """Try each backend in order until one returns a non-empty result."""
        for backend in self.backends:
            try:
                result = await backend.get_policy(policy_name, context)
                if result:  # Non-empty dict
                    return result
            except Exception:
                continue
        return {}
