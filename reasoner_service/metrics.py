"""Prometheus metrics helper with a safe fallback when prometheus_client is absent.

This module exports a small set of metrics used by the orchestrator and notifiers.
If the real prometheus_client is available it is used, otherwise a no-op shim is provided
so tests and local development don't require installing prometheus.
"""

from __future__ import annotations
import logging
from typing import Any
from .config import get_settings

logger = logging.getLogger(__name__)


class _NoOpMetric:
    def __init__(self, *a, **k):
        pass

    def inc(self, amount: float = 1.0):
        return None

    def labels(self, *a, **k):
        return self

    def observe(self, value: float):
        return None


def _make_noop_histogram(*a, **k):
    return _NoOpMetric()


try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server  # type: ignore
except Exception:  # pragma: no cover - local dev/test fallback
    Counter = _NoOpMetric  # type: ignore
    Histogram = _NoOpMetric  # type: ignore
    Gauge = _NoOpMetric  # type: ignore

    def start_http_server(port: int) -> None:  # type: ignore
        logger.debug("prometheus_client not available; start_http_server noop")


# Metrics used across the orchestrator
decisions_processed_total = Counter("decisions_processed_total", "Decisions processed", ["result"])  # type: ignore
deduplicated_decisions_total = Counter("deduplicated_decisions_total", "Deduplicated decisions total")  # type: ignore

# DLQ metrics
dlq_retries_total = Counter("dlq_retries_total", "DLQ retry attempts")  # type: ignore
dlq_size = Gauge("dlq_size", "Current DLQ size")  # type: ignore
# Redis reconnect attempts metric
redis_reconnect_attempts = Counter("redis_reconnect_attempts", "Redis reconnect attempts")  # type: ignore
redis_op_errors_total = Counter("redis_op_errors_total", "Redis operation errors")  # type: ignore
redis_op_retries_total = Counter("redis_op_retries_total", "Redis operation retries")  # type: ignore
redis_circuit_opened_total = Counter("redis_circuit_opened_total", "Redis circuit opened events")  # type: ignore
redis_op_calls_total = Counter("redis_op_calls_total", "Redis operation calls")  # type: ignore


def start_metrics_server_if_enabled():
    cfg = get_settings()
    try:
        if getattr(cfg, "METRICS_PORT", None):
            start_http_server(cfg.METRICS_PORT)  # type: ignore
    except Exception:
        logger.exception("failed to start metrics server")
